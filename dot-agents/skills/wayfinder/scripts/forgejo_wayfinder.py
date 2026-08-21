#!/usr/bin/env python3
"""Deterministic Forgejo adapter for Wayfinder maps and decision tickets.

Wayfinder charts a body of work as one **map** issue plus **decision ticket**
child issues on a private Forgejo tracker. This module owns the mechanics so
the skill body does not have to carry API prose that drifts.

Design constraints, each of which is a test in
`../tests/test_forgejo_wayfinder.py`:

* **Preview first.** Every mutation returns a `Preview` unless `apply=True`.
* **Every mutation preflights.** Repository privacy, issue identity, label,
  metadata version, and map association are revalidated immediately before the
  write — not once at session start, and never inferred from a body marker
  alone.
* **Private trackers only.** Several of Bryan's repositories on this host are
  public; exploratory deliberation must never land on one.
* **Tokens never surface, and never travel to an unexpected host.** `auto`
  always prefers Tea. Token transport is opt-in, requires an allowlisted host,
  and refuses cross-origin redirects so an `Authorization` header cannot be
  forwarded off-origin.
* **No body this adapter manages is ever rewritten.** Forgejo has no
  compare-and-swap on issue update, so *any* body PATCH can overwrite a human
  edit that landed after the last read — no client-side lock or readback can
  close that window. Every piece of adapter-owned state is therefore
  append-only: issues and comments are created, never edited. The map's
  decision index is a deterministic replay of exact-schema `index` comments on
  the map issue, not a section of its body.
* **Claims are server-ordered.** Claim and release are append-only comments,
  arbitrated by Forgejo's monotonic comment id. Two contenders cannot both win.
* **Resolution is idempotent.** A deterministic marker lets a retry inspect
  what already landed and complete only the missing steps, and the index
  replay collapses duplicates onto the earliest record per resolution key.
* **A decision publishes before its ticket closes.** The resolution comment
  and the exact index record land and read back first; the close is the last
  write, so a failed index append leaves the ticket open and its dependents
  blocked rather than exposing downstream work with no decision of record.
* **One current decision per ticket.** The index replay dedupes retries onto
  each key's earliest record, then lets a genuinely new key for the same
  ticket — a correction, recorded after an explicit reopen — supersede the
  old one. History stays append-only and inspectable.
* **Creates converge on retry.** Every create carries a caller-retained
  creation identity in exact managed metadata; a retry after a lost response
  finds the issue the first attempt made instead of duplicating it, and an
  ambiguous or inexact match fails closed.
* **Preview and apply are byte-identical.** `claim` and the create commands
  refuse to apply without the identity the preview printed, so the record that
  lands is the record that was reviewed.
* **Exact scoping.** No operation touches an issue outside the map and ticket
  set supplied.

Grounded against Forgejo 16.0.1+gitea-1.22.0 on 2026-08-19, from the live
Swagger and live API:

* `CreateIssueOption.labels` is `array<int64>` — **label ids, not names**. Names
  work in the `labels=` *query* filter but not in a create body.
* A `labels=` query naming a label the repository does not have returns **every**
  issue rather than none, so the filter cannot be relied on to narrow anything.
* `Comment` carries a server-assigned monotonic `id`; there is no `If-Match` or
  version field on issue update, so `id` order is the only total order available.
* There is no sub-issue endpoint, so map parentage is a managed metadata block.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import secrets
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Iterable, Sequence

METADATA_VERSION = "v1"

MAP_LABEL = "wayfinder:map"
TICKET_LABEL = "wayfinder:ticket"
TICKET_TYPES = ("grilling", "research", "prototype", "task")

# Deterministic label definitions. Creation needs a colour, and a fixed one
# keeps the tracker's appearance reproducible rather than luck-of-the-draw.
LABEL_DEFINITIONS: dict[str, dict[str, str]] = {
    MAP_LABEL: {"color": "#5319e7", "description": "Wayfinder map (canonical artifact)"},
    TICKET_LABEL: {"color": "#1d76db", "description": "Wayfinder decision ticket"},
    **{
        f"wayfinder:{kind}": {
            "color": color,
            "description": f"Wayfinder {kind} ticket",
        }
        for kind, color in (
            ("grilling", "#0e8a16"),
            ("research", "#fbca04"),
            ("prototype", "#d93f0b"),
            ("task", "#b60205"),
        )
    },
}

# Managed regions. Everything outside them is human prose and is never touched.
MAP_BEGIN = f"<!-- wayfinder:map:begin {METADATA_VERSION} -->"
MAP_END = "<!-- wayfinder:map:end -->"
TICKET_META_RE = re.compile(
    r"<!--\s*wayfinder:ticket\s+(?P<version>v\d+)\s*\n(?P<body>.*?)\n-->",
    re.DOTALL,
)

# Managed records are *comments*. Forgejo assigns each a monotonic id, which is
# the only server-side total order this API offers — so every arbitration and
# ordering decision here is made by replaying comments in id order.
#
# `claim`/`release` arbitrate one ticket. `resolution` is an idempotency marker
# on the ticket. `index` records one decided ticket on its map: the map's
# decision index is the replay of these records, never a section of its body,
# because a body PATCH cannot be made safe against a concurrent human edit.
RECORD_KINDS = ("claim", "release", "resolution", "index")
RECORD_RE = re.compile(
    r"<!--\s*wayfinder:(?P<kind>claim|release|resolution|index)\s+"
    r"(?P<version>v\d+)\s*\n(?P<body>.*?)\n-->",
    re.DOTALL,
)

# One managed line per field, so a value can never introduce structure.
FIELD_RE = re.compile(r"\A[a-z][a-z0-9_]{0,31}\Z")

# A decision gist becomes the index comment's visible line and its `gist`
# record field, so it must stay one safe line that cannot forge structure.
MAX_INDEX_LINE = 300

# A session identity must be safe to embed in a single metadata line, and a
# timestamp must be unambiguous, because both take part in arbitration.
SESSION_RE = re.compile(r"\A[A-Za-z0-9][A-Za-z0-9._/-]{0,127}\Z")

# A timestamp must be a *real* instant, not merely a well-shaped string. The
# regex only fixes the layout — `2026-99-99T99:99:99Z` matches it — so every
# timestamp is additionally parsed with `datetime.strptime`, which rejects an
# impossible month, day, hour, minute, or second. Only UTC `Z` is accepted:
# an offset form would make two records' order depend on reading their zones.
ISO_SHAPE_RE = re.compile(r"\A\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z\Z")


def is_utc_timestamp(value: str) -> bool:
    """Whether this is a real UTC instant, not just an ISO-shaped string."""
    if not ISO_SHAPE_RE.match(value or ""):
        return False
    text = value[:-1]  # drop the Z
    fmt = "%Y-%m-%dT%H:%M:%S.%f" if "." in text else "%Y-%m-%dT%H:%M:%S"
    try:
        parsed = datetime.strptime(text, fmt)
    except ValueError:
        return False
    # Round-trip guard: strptime accepts a leap second textually on some
    # builds, and a value we cannot reproduce is a value we cannot order.
    return parsed.strftime("%Y-%m-%dT%H:%M:%S") == text.split(".")[0]


class _Predicate:
    """A named value validator with the `.match()` shape a schema expects.

    Schemas are a dict of `field -> validator`, and most validators are plain
    regexes. Some checks — a real calendar date, a positive integer — cannot be
    expressed as one, so they wear the same interface rather than forcing every
    call site to branch on validator type.
    """

    __slots__ = ("name", "_test")

    def __init__(self, name: str, test: Callable[[str], bool]) -> None:
        self.name = name
        self._test = test

    def match(self, value: str) -> bool:
        return self._test(value or "")

    def __repr__(self) -> str:  # pragma: no cover - diagnostics only
        return f"<{self.name}>"


ISO_RE = _Predicate("utc-timestamp", is_utc_timestamp)

# An **operation id** is the ownership token. A session is not one: the same
# session legitimately runs nested or concurrent operations, and if a release
# matched on session alone it would clear a sibling operation's claim — a
# self-inflicted lost lock that no amount of cross-session care prevents.
#
# 128 bits of `secrets.token_hex`, so two operations cannot collide and one
# cannot be guessed from another.
OPERATION_RE = re.compile(r"\A[a-f0-9]{32}\Z")

# Issue numbers. Forgejo numbers issues from 1, so zero is not a ticket or a
# map — it is a missing value that a permissive parser would let stand in for
# one. The 18-digit bound keeps `int()` away from unbounded input.
POSITIVE_RE = re.compile(r"\A[1-9][0-9]{0,17}\Z")
KEY_RE = re.compile(r"\A[a-f0-9]{16}\Z")

# Exact v1 schemas. A record that does not match its kind *exactly* — missing
# key, unknown key, duplicate key, empty value, wrong version, malformed value —
# never arbitrates and never satisfies readback or idempotency. Permissive
# parsing is how a half-written record silently takes a lock.
RECORD_SCHEMAS: dict[str, dict[str, Any]] = {
    "claim": {"session": SESSION_RE, "operation": OPERATION_RE, "at": ISO_RE},
    "release": {"session": SESSION_RE, "operation": OPERATION_RE, "at": ISO_RE},
    # `key` already binds map, ticket, and answer, so `map` is the only extra
    # field idempotency demonstrably needs — it scopes the marker to one map
    # without re-deriving the digest.
    "resolution": {"session": SESSION_RE, "key": KEY_RE, "map": POSITIVE_RE},
    # One decided ticket on its map. The `key` is the same resolution key, so a
    # retried resolution — even one that rewords its gist — converges on the
    # earliest record per key at replay. The `gist` field, not the comment's
    # visible prose, is what replay renders: prose is presentation, and stable
    # state never rides on prose matching.
    "index": {
        "session": SESSION_RE,
        "key": KEY_RE,
        "map": POSITIVE_RE,
        "ticket": POSITIVE_RE,
        "gist": _Predicate("index-gist", lambda value: is_index_line(value)),
        "at": ISO_RE,
    },
}
OWNER_RE = re.compile(r"\A[A-Za-z0-9][A-Za-z0-9._-]{0,63}\Z")
HOST_RE = re.compile(r"\A[A-Za-z0-9][A-Za-z0-9.-]{0,252}(?::\d{1,5})?\Z")

TOKEN_ENV_NAMES = ("FORGEJO_TOKEN", "GITEA_TOKEN")
# Token transport is opt-in *and* host-pinned: an ambient token must never be
# sent to whatever host an origin URL happens to name.
HOST_ALLOWLIST_ENV = "WAYFINDER_FORGEJO_HOSTS"

# Issue listing is paginated. The cap is a runaway guard, not a budget:
# hitting it raises rather than returning a truncated frontier.
PAGE_SIZE = 50
MAX_ISSUE_PAGES = 40
MAX_COMMENT_PAGES = 40

_ORIGIN_RE = re.compile(
    r"""^(?:
          ssh://[^@]+@(?P<ssh_host>[^:/]+)(?::\d+)?/
        | https?://(?P<http_host>[^/]+)/
        | [^@/]+@(?P<scp_host>[^:/]+):
        )
        (?P<owner>[^/]+)/(?P<repo>[^/]+?)(?:\.git)?/?$""",
    re.VERBOSE,
)


class WayfinderError(RuntimeError):
    """Refusal or failure that must stop the caller, never be worked around."""


# --------------------------------------------------------------------------
# Transport
# --------------------------------------------------------------------------


class Transport:
    """Minimal API surface the adapter needs. Injectable so tests run offline."""

    def request(
        self, method: str, path: str, payload: dict | None = None
    ) -> tuple[int, Any]:
        raise NotImplementedError


class TeaTransport(Transport):
    """Default transport: shell out to `tea api`, which supplies the credential.

    Preferred over holding a token here. Tea reads its own configuration, so no
    secret ever enters this process's memory, arguments, or output.
    """

    def __init__(self, host: str, *, runner: Callable[..., Any] | None = None) -> None:
        self.host = host
        self._run = runner or subprocess.run

    def request(
        self, method: str, path: str, payload: dict | None = None
    ) -> tuple[int, Any]:
        command = ["tea", "api", "--login", self.host, "--method", method.upper()]
        stdin = None
        if payload is not None:
            command += ["--data", "@-"]
            stdin = json.dumps(payload)
        command.append(path)
        result = self._run(
            command, capture_output=True, text=True, input=stdin, check=False
        )
        if result.returncode != 0:
            # stderr may echo the request line; never include the payload.
            raise WayfinderError(
                f"tea api {method.upper()} {path} failed: "
                f"{(result.stderr or '').strip()[:500]}"
            )
        text = (result.stdout or "").strip()
        if not text:
            return 204, None
        try:
            return 200, json.loads(text)
        except json.JSONDecodeError as exc:
            raise WayfinderError(
                f"tea api {path} returned non-JSON: {text[:200]}"
            ) from exc


class _SameOriginRedirectHandler(urllib.request.HTTPRedirectHandler):
    """Refuse every redirect.

    An `Authorization: token …` header set on the original request would be
    replayed on the redirect target by `urllib`'s default handler. Rather than
    try to decide which redirects are safe, refuse all of them: the Forgejo API
    does not need them, and a redirect to another origin is exactly how an
    ambient credential leaves the host it was meant for.
    """

    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: D102
        raise WayfinderError(
            f"refusing an API redirect ({code}) to {urllib.parse.urlsplit(newurl).netloc!r}; "
            "the Forgejo API should not redirect, and forwarding credentials is unsafe"
        )


class TokenTransport(Transport):
    """Fallback transport for hosts without Tea configured.

    Opt-in only, and host-pinned. The token is read once and used only as a
    header on the exact allowlisted host; it never appears in an error message,
    a repr, or a redirect.
    """

    def __init__(
        self,
        host: str,
        *,
        token: str,
        opener: Callable[..., Any] | None = None,
        scheme: str = "https",
    ) -> None:
        if not token:
            raise WayfinderError("TokenTransport requires a non-empty token")
        if not HOST_RE.match(host or ""):
            raise WayfinderError(f"refusing a malformed Forgejo host: {host!r}")
        self.host = host
        self.base_url = f"{scheme}://{host}"
        self._token = token
        self._open = opener or urllib.request.build_opener(
            _SameOriginRedirectHandler()
        ).open

    def __repr__(self) -> str:  # pragma: no cover - defensive
        return f"TokenTransport(host={self.host!r})"

    @staticmethod
    def _validated_path(path: str) -> str:
        """Reject a request path that could steer the request off the pin.

        A leading `//`, an embedded scheme, or a bare CR/LF are the three ways
        a caller-supplied path turns into a different destination or a second
        request. None of them can appear in a legitimate API path.
        """
        if not isinstance(path, str) or not path.startswith("/"):
            raise WayfinderError(f"refusing a non-absolute API path: {path!r}")
        if path.startswith("//"):
            raise WayfinderError(f"refusing an API path with an authority: {path!r}")
        if "://" in path:
            raise WayfinderError(f"refusing an API path containing a scheme: {path!r}")
        if any(ch in path for ch in "\r\n\x00 "):
            raise WayfinderError(f"refusing an API path with unsafe characters: {path!r}")
        if ".." in path.split("/"):
            raise WayfinderError(f"refusing an API path with traversal: {path!r}")
        return path

    def request(
        self, method: str, path: str, payload: dict | None = None
    ) -> tuple[int, Any]:
        path = self._validated_path(path)
        url = f"{self.base_url}/api/v1{path}"
        # Belt and braces: the host is validated at construction and the path
        # cannot carry an authority, but re-derive the netloc from the URL
        # actually being sent so the credential can only ever go to the pin.
        netloc = urllib.parse.urlsplit(url).netloc
        if netloc != self.host:
            raise WayfinderError(
                f"refusing a request to {netloc!r}; this transport is pinned to {self.host!r}"
            )
        data = json.dumps(payload).encode("utf-8") if payload is not None else None
        request = urllib.request.Request(url, data=data, method=method.upper())
        request.add_header("Authorization", f"token {self._token}")
        request.add_header("Accept", "application/json")
        if data is not None:
            request.add_header("Content-Type", "application/json")
        try:
            with self._open(request, timeout=30) as response:
                raw = response.read().decode("utf-8", errors="replace")
                status = response.status
        except urllib.error.HTTPError as exc:
            raise WayfinderError(
                f"{method.upper()} {path} failed: HTTP {exc.code}"
            ) from None
        except WayfinderError:
            raise
        except (OSError, urllib.error.URLError) as exc:
            raise WayfinderError(
                f"{method.upper()} {path} failed: {type(exc).__name__}"
            ) from None
        if not raw.strip():
            return status, None
        try:
            return status, json.loads(raw)
        except json.JSONDecodeError as exc:
            raise WayfinderError(f"{path} returned non-JSON") from exc


def token_from_environment(environ: dict[str, str] | None = None) -> str | None:
    env = environ if environ is not None else dict(os.environ)
    for name in TOKEN_ENV_NAMES:
        value = (env.get(name) or "").strip()
        if value:
            return value
    return None


def allowlisted_hosts(environ: dict[str, str] | None = None) -> tuple[str, ...]:
    env = environ if environ is not None else dict(os.environ)
    raw = (env.get(HOST_ALLOWLIST_ENV) or "").strip()
    return tuple(part.strip() for part in raw.split(",") if part.strip())


# --------------------------------------------------------------------------
# Values
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class RepoRef:
    host: str
    owner: str
    repo: str

    @property
    def slug(self) -> str:
        return f"{self.owner}/{self.repo}"

    @property
    def api_base(self) -> str:
        return f"/repos/{self.owner}/{self.repo}"


@dataclass(frozen=True)
class ManagedRecord:
    """One append-only managed comment, identified by its comment id.

    `comment_id` is the arbitration key. It is server-assigned and monotonic,
    unlike `updated_at`, which this API *sets* on write and therefore cannot use
    to decide who was first.
    """

    comment_id: int
    kind: str
    fields: dict[str, str]

    @property
    def session(self) -> str:
        return self.fields.get("session", "")

    @property
    def operation(self) -> str:
        """The ownership token this record acquires or releases.

        Records only reach this class through the exact schema, so a claim or
        release always has one; an index record has none and reads back empty.
        """
        return self.fields.get("operation", "")

    @property
    def ticket(self) -> str:
        return self.fields.get("ticket", "")

    @property
    def at(self) -> str:
        return self.fields.get("at", "")


# Held for the old name so existing call sites and tests keep reading naturally.
ClaimRecord = ManagedRecord


@dataclass(frozen=True)
class Ticket:
    number: int
    title: str
    state: str
    map_number: int
    ticket_type: str
    labels: tuple[str, ...] = ()
    blocked_by: tuple[int, ...] = ()
    claim: dict[str, str] | None = None
    updated_at: str = ""
    html_url: str = ""

    @property
    def is_open(self) -> bool:
        return self.state == "open"

    @property
    def is_claimed(self) -> bool:
        return self.claim is not None


@dataclass(frozen=True)
class Preview:
    """A mutation that has not happened. Bryan reads this before anything runs.

    `action` is the human name of the command ("claim", "resolve"). It is
    deliberately not called `operation`: in this adapter an *operation* is the
    ownership token that a claim or map lock is bound to.
    """

    action: str
    repo: str
    steps: tuple[str, ...]
    content: tuple[dict[str, Any], ...] = ()

    def render(self) -> str:
        lines = [f"DRY RUN — {self.action} on {self.repo}", ""]
        lines += [f"  {i}. {step}" for i, step in enumerate(self.steps, start=1)]
        for item in self.content:
            lines += [
                "",
                f"--- {item.get('label', 'content')} ---",
                str(item.get("text", "")),
            ]
        lines += ["", "Nothing was written. Re-run with --apply to perform these steps."]
        return "\n".join(lines)


@dataclass(frozen=True)
class WriteGuard:
    """Exactly what must still be true at the instant of one external write.

    Naming a guard is mandatory, not decorative: `enforce` is the single place
    the privacy, identity, label, metadata, and ownership checks live, and a
    write that cannot state its guard cannot go through it.

    Ownership is a full identity tuple, never a bare operation id: an id can be
    read out of the tracker by anyone who can read the issue, so it is a
    *handle*, not a credential. `claim_owner` is `(operation, session)`.
    """

    what: str
    map_number: int | None = None
    ticket: int | None = None
    # Additional tickets whose exact identity must also hold at the write
    # instant — e.g. the other endpoint of a dependency edge (`blocked_by`).
    extra_tickets: tuple[int, ...] = ()
    claim_owner: tuple[str, ...] | None = None
    # Recovery targets an acquisition that may be queued behind the current
    # winner rather than holding. It still requires that the acquisition exist
    # under this exact identity — it just does not require it to be winning.
    claim_queued_owner: tuple[str, ...] | None = None
    # Reads the write closure needs but must not perform itself, because any
    # network read after the privacy check reopens the drift window.
    snapshot_blockers: bool = False


@dataclass(frozen=True)
class GuardState:
    """Everything the guard read, so the write performs no read of its own.

    The write closure receives this and must use it. A closure that issues its
    own GET — even a harmless-looking one — puts a network round trip between
    the privacy check and the mutation, which is exactly the window
    `enforce` exists to close.
    """

    repository: dict
    map: dict | None = None
    map_issue: dict | None = None
    ticket: "Ticket | None" = None
    ticket_issue: dict | None = None
    claim: ManagedRecord | None = None
    claim_queued: ManagedRecord | None = None
    blockers: tuple[int, ...] = ()


@dataclass(frozen=True)
class ClaimOutcome:
    won: bool
    ticket: int
    reason: str
    holder: dict[str, str] | None = None
    # The ownership token this attempt used. Callers must keep it: it is what
    # a later release, resolve, or explicit recovery has to name.
    operation: str = ""


@dataclass
class ResolutionOutcome:
    """What a resolve did, so a retry can be reported honestly."""

    ticket: int
    commented: bool = False
    closed: bool = False
    indexed: bool = False
    already: list[str] = field(default_factory=list)
    map: dict | None = None
    # A resolution is only successful when its exact-key index record replays
    # on the map; anything less returns explicit retry guidance.
    resolved: bool = False
    recovery: str = ""


# --------------------------------------------------------------------------
# Parsing
# --------------------------------------------------------------------------


def parse_origin(origin: str) -> RepoRef:
    """Parse a Git origin URL into a repository reference.

    Handles `ssh://user@host[:port]/owner/repo.git`, the SCP-style
    `user@host:owner/repo.git`, and `https://host/owner/repo`.
    """
    match = _ORIGIN_RE.match(origin.strip())
    if not match:
        raise WayfinderError(f"could not parse a repository out of origin: {origin!r}")
    host = (
        match.group("ssh_host") or match.group("http_host") or match.group("scp_host")
    )
    return _validated_ref(host, match.group("owner"), match.group("repo"))


def _validated_ref(host: str, owner: str, repo: str) -> RepoRef:
    if not HOST_RE.match(host or ""):
        raise WayfinderError(f"refusing a malformed host: {host!r}")
    for label, value in (("owner", owner), ("repository", repo)):
        if not OWNER_RE.match(value or ""):
            raise WayfinderError(f"refusing a malformed {label}: {value!r}")
    return RepoRef(host=host, owner=owner, repo=repo)


def parse_exact_block(
    schema: dict[str, Any], text: str
) -> dict[str, str] | None:
    """Parse a `key: value` block against an exact schema, or reject it whole.

    Shared by arbitration records and ticket metadata, so the two cannot drift
    into different notions of "valid".
    """
    fields: dict[str, str] = {}
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            # A blank line is not a field. Skipping it would let a writer split
            # a block so that a reader tolerates padding it never emits, and
            # tolerated padding is where a forged half-record hides.
            return None
        if ":" not in stripped:
            return None
        key, _, value = stripped.partition(":")
        key, value = key.strip(), value.strip()
        if key in fields:
            return None  # duplicate key: which one wins is not a question we answer
        if key not in schema:
            return None  # unknown key: the block is not the shape we wrote
        if not value:
            return None
        fields[key] = value
    if set(fields) != set(schema):
        return None  # missing key
    for key, validator in schema.items():
        if not validator.match(fields[key]):
            return None
    return fields


def parse_schema_block(kind: str, text: str) -> dict[str, str] | None:
    """Parse one managed block against its exact schema, or reject it.

    Returns `None` — never a partial dict — when anything is off: a line that
    is not `key: value`, a duplicate key, an unknown key, a missing key, an
    empty value, or a value that fails its pattern. A record this function
    rejects can neither arbitrate nor satisfy idempotency, which is the whole
    point: a half-written or forged record must not be able to take a lock.
    """
    schema = RECORD_SCHEMAS.get(kind)
    if schema is None:
        return None
    return parse_exact_block(schema, text)


def new_operation_id() -> str:
    """A fresh ownership token.

    Unguessable and collision-resistant so one operation cannot release
    another's claim, and so a retry can prove it is the *same* operation rather
    than merely the same session.
    """
    return secrets.token_hex(16)


def validate_operation(operation: str) -> str:
    operation = (operation or "").strip()
    if not OPERATION_RE.match(operation):
        raise WayfinderError(
            f"refusing a malformed operation id: {operation!r} "
            "(expected 32 lowercase hex characters, e.g. from --new-operation)"
        )
    return operation


# A **creation identity** makes create retry-safe after an ambiguous success:
# Forgejo can commit a POST while the client loses the response, and a blind
# retry would mint a duplicate canonical map or ticket. The preview mints and
# prints one; apply requires it, embeds it in an exact managed metadata block
# on the created issue, and a retry searches this tracker for it — zero
# matches creates, one exact match converges, anything else fails closed.
CREATED_RE = re.compile(
    r"<!--\s*wayfinder:created\s+(?P<version>v\d+)\s*\n(?P<body>.*?)\n-->",
    re.DOTALL,
)
CREATED_SCHEMA: dict[str, Any] = {"creation": OPERATION_RE}


def new_creation_id() -> str:
    """A fresh caller-retained creation identity (same shape as an operation)."""
    return secrets.token_hex(16)


def validate_creation(creation: str) -> str:
    creation = (creation or "").strip()
    if not OPERATION_RE.match(creation):
        raise WayfinderError(
            f"refusing a malformed creation id: {creation!r} "
            "(expected the 32 lowercase hex characters the preview printed)"
        )
    return creation


def render_created_marker(creation: str) -> str:
    """The managed block binding a created issue to its creation identity."""
    return (
        f"<!-- wayfinder:created {METADATA_VERSION}\n"
        f"creation: {validate_creation(creation)}\n"
        "-->"
    )


def parse_creation(body: str) -> str:
    """The creation identity an issue body carries, exactly, or ``""``.

    Exactly one block, at the current version, matching the exact schema — the
    same discipline as ticket metadata, because converging on a wrong or
    ambiguous identity is how a retry adopts an issue it did not create.
    """
    matches = list(CREATED_RE.finditer(body or ""))
    current = [m for m in matches if m.group("version") == METADATA_VERSION]
    if len(matches) != 1 or len(current) != 1:
        return ""
    fields = parse_exact_block(CREATED_SCHEMA, current[0].group("body"))
    return fields["creation"] if fields else ""


# Ticket metadata is identity, not description, so it gets the same exact
# treatment as an arbitration record: exactly `map` and `type`, both valid.
TICKET_META_SCHEMA: dict[str, Any] = {
    "map": POSITIVE_RE,
    "type": _Predicate("ticket-type", lambda value: value in TICKET_TYPES),
}


def parse_ticket_metadata(body: str) -> dict[str, str]:
    """Read the managed `wayfinder:ticket` block, exactly, or return `{}`.

    Every rejection here is a case where permissive parsing would have let the
    adapter operate on an issue it could not actually identify:

    * more than one metadata block — which `map` is authoritative?
    * a block at another metadata version — written by code we are not;
    * a malformed, blank, duplicate, unknown, or empty field;
    * `map: 0` or a negative/non-numeric map — Forgejo numbers issues from 1,
      so zero is a missing value dressed as one;
    * a `type` outside the declared enum.

    An empty dict means "this is not a ticket", and every caller treats it that
    way rather than filling in a default.
    """
    matches = list(TICKET_META_RE.finditer(body or ""))
    current = [m for m in matches if m.group("version") == METADATA_VERSION]
    if len(matches) != 1 or len(current) != 1:
        return {}
    match = current[0]
    fields = parse_exact_block(TICKET_META_SCHEMA, match.group("body"))
    if fields is None:
        return {}
    return {**fields, "version": match.group("version")}


def require_ticket_metadata(body: str, subject: str) -> dict[str, str]:
    meta = parse_ticket_metadata(body)
    if not meta:
        raise WayfinderError(
            f"{subject} does not carry exactly one valid {METADATA_VERSION} "
            "wayfinder:ticket metadata block (map plus type, nothing else); "
            "refusing to treat it as a ticket"
        )
    return meta


_MANAGED_MARKER_RE = re.compile(r"<!--\s*wayfinder", re.IGNORECASE)


def require_no_managed_markers(text: str, subject: str) -> str:
    """Free-form content posted to the tracker must not smuggle managed state.

    Claim arbitration and the decision index parse **every** comment on an
    issue, and ticket identity parses issue bodies — so a Wayfinder marker
    pasted inside an answer or question becomes live state the moment it
    lands: a quoted release block really releases the claim it names, and a
    quoted claim block queues a zombie acquisition. Screening here is what
    keeps the adapter's own writes from forging or destroying the records its
    next step is guarded by. Link to tracker state; never paste it.
    """
    if _MANAGED_MARKER_RE.search(text or ""):
        raise WayfinderError(
            f"{subject} contains a Wayfinder managed marker (`<!-- wayfinder…`); "
            "markers in free-form content become live records when posted — link "
            "to the tracker state instead of pasting it"
        )
    return text


def require_one_managed_region(body: str, subject: str) -> None:
    """A map has exactly one balanced managed region at the current version.

    Zero regions is not a map. Two is worse than none: the adapter would merge
    a decision into one of them and a reader would see the other.
    """
    begins = (body or "").count(MAP_BEGIN)
    ends = (body or "").count(MAP_END)
    if begins == 1 and ends == 1 and body.index(MAP_BEGIN) < body.index(MAP_END):
        return
    stale = re.findall(r"<!--\s*wayfinder:map:begin\s+(v\d+)\s*-->", body or "")
    wrong_version = [v for v in stale if v != METADATA_VERSION]
    detail = (
        f"managed region declares version {wrong_version[0]}, not {METADATA_VERSION}"
        if begins == 0 and wrong_version
        else f"found {begins} begin and {ends} end marker(s)"
    )
    raise WayfinderError(
        f"{subject} does not hold exactly one balanced {METADATA_VERSION} managed "
        f"region ({detail}); refusing to treat it as a map"
    )


def describe_identity(identity: Sequence[str]) -> str:
    """Render an acquisition identity for a message a human has to act on."""
    parts = tuple(identity)
    return f"operation {parts[0]} (session {parts[1]!r})"


def render_ticket_metadata(map_number: int, ticket_type: str) -> str:
    """Render ticket metadata, validated by the same schema that reads it."""
    if ticket_type not in TICKET_TYPES:
        raise WayfinderError(
            f"unknown ticket type {ticket_type!r}; "
            f"expected one of {', '.join(TICKET_TYPES)}"
        )
    if not POSITIVE_RE.match(str(map_number)):
        raise WayfinderError(
            f"refusing to render ticket metadata for map {map_number!r}; "
            "Forgejo numbers issues from 1, so zero and below are not maps"
        )
    return (
        f"<!-- wayfinder:ticket {METADATA_VERSION}\n"
        f"map: {map_number}\n"
        f"type: {ticket_type}\n"
        "-->"
    )


def validate_session(session: str) -> str:
    """A session identity takes part in arbitration, so it must be exact."""
    session = (session or "").strip()
    if not SESSION_RE.match(session):
        raise WayfinderError(
            f"refusing a session identity that is not a single safe line: {session!r}"
        )
    return session


def validate_timestamp(value: str) -> str:
    value = (value or "").strip()
    if not ISO_RE.match(value):
        raise WayfinderError(
            f"refusing a timestamp that is not a real ISO 8601 UTC instant (…Z): "
            f"{value!r}"
        )
    return value


def render_record(kind: str, fields: dict[str, str]) -> str:
    """Render a managed comment body, validated against its exact schema.

    Rendering and parsing share `RECORD_SCHEMAS`, so this adapter cannot emit a
    record its own reader would reject — a class of bug that would present as
    an operation mysteriously failing its own readback.
    """
    schema = RECORD_SCHEMAS.get(kind)
    if schema is None:
        raise WayfinderError(f"unknown managed record kind: {kind!r}")
    supplied = {key: str(value) for key, value in fields.items()}
    missing = sorted(set(schema) - set(supplied))
    unknown = sorted(set(supplied) - set(schema))
    if missing or unknown:
        raise WayfinderError(
            f"{kind} record has the wrong fields — "
            f"missing {missing or 'none'}, unknown {unknown or 'none'}; "
            f"expected exactly {sorted(schema)}"
        )
    for key, value in supplied.items():
        if not FIELD_RE.match(key):
            raise WayfinderError(f"refusing a malformed record field name: {key!r}")
        if not value.strip() or not is_single_line(value) or "-->" in value:
            raise WayfinderError(
                f"refusing a record field that is not a single safe line: {key}={value!r}"
            )
        if not schema[key].match(value):
            raise WayfinderError(
                f"{kind}.{key} does not match its schema: {value!r}"
            )
    lines = "\n".join(f"{key}: {value}" for key, value in sorted(supplied.items()))
    return f"<!-- wayfinder:{kind} {METADATA_VERSION}\n{lines}\n-->"


def iter_record_blocks(body: str) -> list[tuple[str, str, dict[str, str] | None]]:
    """Every managed block in one comment body, as `(kind, version, fields)`.

    `finditer`, not `search`: a comment can legitimately carry more than one
    block, and reading only the first is how a marker hides behind another.

    `fields` is `None` when the block does not match its kind's exact schema.
    Callers must skip those blocks — never treat them as partially usable.
    """
    blocks: list[tuple[str, str, dict[str, str] | None]] = []
    for match in RECORD_RE.finditer(body or ""):
        kind = match.group("kind")
        version = match.group("version")
        fields = (
            parse_schema_block(kind, match.group("body"))
            if version == METADATA_VERSION
            else None
        )
        blocks.append((kind, version, fields))
    return blocks


def parse_records(comments: Iterable[dict], kinds: Sequence[str] | None = None) -> list[ManagedRecord]:
    """Every schema-valid managed record, ordered by Forgejo's comment id.

    A record with the wrong metadata version, a missing/duplicate/unknown key,
    an empty value, or a malformed session, operation, ticket, or timestamp is
    **ignored** rather than allowed to win or block: arbitration must not turn
    on something this adapter cannot fully validate.

    A comment without a positive integer id is ignored the same way. The id is
    the total order every replay decision rests on — Forgejo assigns ids from 1,
    so a zero, negative, malformed, or missing id is not a position in that
    order, and a record carried by one must never arbitrate or index.
    """
    wanted = tuple(kinds) if kinds is not None else ("claim", "release")
    records: list[ManagedRecord] = []
    for comment in comments:
        comment_id = _positive_comment_id(comment)
        if comment_id is None:
            continue
        for kind, _version, fields in iter_record_blocks(comment.get("body") or ""):
            if kind not in wanted or fields is None:
                continue
            records.append(
                ManagedRecord(comment_id=comment_id, kind=kind, fields=dict(fields))
            )
    return sorted(records, key=lambda r: r.comment_id)


def _positive_comment_id(comment: dict) -> int | None:
    """The comment's server id, or `None` when it is not a positive integer.

    Exact shapes only. `int()` would also accept `"1_0"`, `"  12  "`, `"007"`,
    and `True` — each a malformed id that would then take a position in the
    replay order. A real Forgejo returns plain integers; anything else is a
    server this adapter must not arbitrate on.
    """
    raw = comment.get("id")
    if isinstance(raw, bool):
        return None
    if isinstance(raw, int):
        return raw if raw >= 1 else None
    if isinstance(raw, str) and POSITIVE_RE.match(raw):
        return int(raw)
    return None


def acquisition_identity(record: ManagedRecord) -> tuple[str, ...]:
    """The full identity of one acquisition or drop.

    An operation id alone is not identity. It is unguessable, but it is *also*
    written into a public-to-the-tracker comment, so anything that can read the
    issue can quote it back. Ownership therefore binds the operation to the
    session that acquired it.

    A claim's scope is the issue its comment lives on, so the ticket is implicit
    and is not repeated in the key.
    """
    return (record.operation, record.session)


def claim_identity(operation: str, session: str) -> tuple[str, ...]:
    return (operation, session)


def active_holder(
    records: Iterable[ManagedRecord], *, hold: str, drop: str
) -> ManagedRecord | None:
    """The earliest `hold` record whose full identity has not posted a `drop`.

    Replaying in comment-id order is what makes this a *total* order: every
    contender reading the same comment list computes the same winner, whatever
    order their writes arrived in.

    Arbitration is keyed on `acquisition_identity`, not on the session and not
    on the operation alone. Three things follow, and all are required:

    * a drop clears exactly the acquisition it names, so one operation can
      never release a sibling operation of the same session;
    * a second acquisition by the same session is a *contender*, not a no-op,
      so a session cannot hold two overlapping critical sections;
    * a drop quoting a real operation id under the wrong session clears nothing.
    """
    held: list[ManagedRecord] = []
    for record in records:
        identity = acquisition_identity(record)
        if record.kind == hold:
            if not any(acquisition_identity(e) == identity for e in held):
                held.append(record)
        elif record.kind == drop:
            held = [e for e in held if acquisition_identity(e) != identity]
    return held[0] if held else None


def active_claim(records: Iterable[ManagedRecord]) -> ManagedRecord | None:
    """The acquisition that currently holds a ticket."""
    return active_holder(records, hold="claim", drop="release")


def acquisition_is_active(
    records: Iterable[ManagedRecord],
    *,
    hold: str,
    drop: str,
    identity: Sequence[str],
) -> bool:
    """Whether this exact acquisition still stands, even if it is not the winner.

    A loser must verify *its own* withdrawal, and a recovery must verify the
    acquisition it targeted. Checking only `active_holder` would let a losing
    acquisition report "withdrawn" while its unmatched hold record sits in the
    log waiting to become the winner the moment the current holder releases —
    a zombie lock.
    """
    wanted = tuple(identity)
    live: set[tuple[str, ...]] = set()
    for record in records:
        record_id = acquisition_identity(record)
        if record.kind == hold:
            live.add(record_id)
        elif record.kind == drop:
            live.discard(record_id)
    return wanted in live


def find_acquisition(
    records: Iterable[ManagedRecord], *, hold: str, identity: Sequence[str]
) -> ManagedRecord | None:
    """The earliest schema-valid `hold` record matching this exact identity.

    Recovery needs this and not `active_holder`: the acquisition to clean up is
    frequently *queued behind* the current winner, which is precisely the
    zombie a failed withdrawal leaves. Returning it lets recovery act on the
    exact record rather than on whoever happens to hold the lock now.
    """
    wanted = tuple(identity)
    for record in records:
        if record.kind == hold and acquisition_identity(record) == wanted:
            return record
    return None


def resolution_key(map_number: int, ticket: int, answer: str) -> str:
    """Deterministic idempotency key for one resolution.

    Derived from the map, the ticket, and the answer text, so a retry of the
    *same* resolution recognizes its own earlier comment while a genuinely
    different answer does not masquerade as one.
    """
    digest = hashlib.sha256(
        f"{map_number}\n{ticket}\n{answer.strip()}".encode("utf-8")
    ).hexdigest()
    return digest[:16]


def find_resolution(
    comments: Iterable[dict], *, key: str, map_number: int, session: str
) -> bool:
    """Whether a *structurally valid* resolution marker for exactly this key exists.

    Every check here replaces a substring test that could be satisfied by the
    answer prose itself:

    * iterate **all** blocks in a comment, not just the first;
    * require `kind == "resolution"`, the exact current metadata version,
      and the exact resolution schema;
    * require the parsed `key`, `map`, and `session` fields to match exactly.

    A marker for a different map, a different session, or an older version is
    not this resolution, and must never satisfy readback or idempotency.
    """
    for comment in comments:
        for kind, _version, fields in iter_record_blocks(comment.get("body") or ""):
            if kind != "resolution" or fields is None:
                continue
            if (
                fields.get("key") == key
                and fields.get("map") == str(map_number)
                and fields.get("session") == session
            ):
                return True
    return False


def is_single_line(value: str) -> bool:
    """One line by the same rule the parser splits on.

    `parse_exact_block` reads records with `str.splitlines()`, which splits on
    more than CR/LF — U+2028/U+2029, NEL, VT, FF. A value that renders as one
    line but parses as two is a record the writer emits and its own reader
    rejects, so "single line" must mean the *parser's* notion, not a CR/LF
    check.
    """
    return len(value.splitlines()) == 1 and "\r" not in value and "\n" not in value


def is_index_line(value: str) -> bool:
    """Whether a gist is a valid single-line index entry (schema predicate)."""
    try:
        validate_index_line(value)
    except WayfinderError:
        return False
    return True


def validate_index_line(line: str) -> str:
    """Validate a decision gist before it can reach a preview or a write.

    The gist becomes the visible line of an index comment and a field of its
    managed record. Anything that could add a line, open a heading, or forge a
    managed marker would let one decision impersonate structure or another
    record — so those are refused here, before the value is shown to Bryan or
    sent anywhere.
    """
    text = (line or "").strip()
    if not text:
        raise WayfinderError("a map index entry cannot be empty")
    if not is_single_line(text):
        raise WayfinderError(f"a map index entry must be a single line: {line!r}")
    if len(text) > MAX_INDEX_LINE:
        raise WayfinderError(
            f"a map index entry must be at most {MAX_INDEX_LINE} characters, got {len(text)}"
        )
    if text.lstrip("-* \t").strip() == "":
        raise WayfinderError(f"a map index entry needs content, not just a bullet: {line!r}")
    if text.lstrip("-* \t").startswith("#"):
        raise WayfinderError(f"a map index entry cannot open a heading: {line!r}")
    if "<!--" in text or "-->" in text:
        raise WayfinderError(f"a map index entry cannot contain an HTML comment: {line!r}")
    if "wayfinder:" in text.lower():
        raise WayfinderError(
            f"a map index entry cannot contain a Wayfinder managed marker: {line!r}"
        )
    return text


def replace_managed_region(body: str, managed: str) -> str:
    """Build a map body from prose plus the managed region.

    Only `create_map` calls this, on a body that has not been posted yet — the
    adapter never rewrites an existing issue body.
    """
    block = f"{MAP_BEGIN}\n{managed.strip()}\n{MAP_END}"
    if MAP_BEGIN in body and MAP_END in body:
        head, _, rest = body.partition(MAP_BEGIN)
        _, _, tail = rest.partition(MAP_END)
        return f"{head}{block}{tail}"
    if MAP_BEGIN in body or MAP_END in body:
        raise WayfinderError(
            "map body has an unbalanced managed region; refusing to write"
        )
    return (body.rstrip() + "\n\n" + block + "\n") if body.strip() else block + "\n"


def extract_managed_region(body: str) -> str:
    if MAP_BEGIN not in body or MAP_END not in body:
        return ""
    _, _, rest = body.partition(MAP_BEGIN)
    managed, _, _ = rest.partition(MAP_END)
    return managed.strip()


def render_index_comment(fields: dict[str, str]) -> str:
    """The full body of one index comment: a visible gist line plus its record.

    The visible line is what a human reads on the map issue's timeline; the
    record is what replay reads. Both are rendered here, deterministically, so
    an exact readback can compare the whole comment byte for byte.
    """
    marker = render_record("index", fields)
    return f"Decision #{fields['ticket']}: {fields['gist']}\n\n{marker}"


def index_replay(records: Iterable[ManagedRecord]) -> list[ManagedRecord]:
    """The map's decision index: at most one current decision per ticket.

    Two deterministic passes over the records in comment-id order:

    * **first per key wins** — deduplicating by `key`, not by gist text, is
      what makes resolution converge: a retry that rewords its gist still
      carries the same key, so it can never add a second entry;
    * **latest key per ticket wins** — a genuinely new key for the same ticket
      is a *correction* (a changed answer, recorded after the ticket was
      reopened and re-resolved), and it supersedes the earlier decision rather
      than coexisting with it. Supersession is keyed on each key's *first*
      record, so a late duplicate of an old key — a stale retry — can never
      overturn a correction.

    History stays append-only and inspectable: every record remains on the map
    (`map_index_records`); replay only decides which one is current.
    """
    seen: set[str] = set()
    first_per_key: list[ManagedRecord] = []
    for record in sorted(records, key=lambda r: r.comment_id):
        key = record.fields.get("key", "")
        if key in seen:
            continue
        seen.add(key)
        first_per_key.append(record)
    current: dict[str, ManagedRecord] = {}
    for record in first_per_key:
        current[record.fields.get("ticket", "")] = record
    return sorted(current.values(), key=lambda r: r.comment_id)


def decision_view(record: ManagedRecord) -> dict[str, str]:
    """How one index entry is reported to a reader."""
    return {
        "ticket": record.fields.get("ticket", ""),
        "gist": record.fields.get("gist", ""),
        "key": record.fields.get("key", ""),
        "session": record.session,
        "at": record.at,
        "comment_id": str(record.comment_id),
    }


# --------------------------------------------------------------------------
# Frontier
# --------------------------------------------------------------------------


def compute_frontier(tickets: Iterable[Ticket]) -> list[Ticket]:
    """Open, unblocked, unclaimed tickets in stable map order.

    Blocked means *any* named blocker is still open. A blocker outside the
    supplied set counts as unresolved rather than being ignored: silently
    dropping an unknown dependency would hand out a ticket that is not
    actually takeable.
    """
    ordered = sorted(tickets, key=lambda t: t.number)
    closed = {t.number for t in ordered if not t.is_open}
    known = {t.number for t in ordered}
    frontier = []
    for ticket in ordered:
        if not ticket.is_open or ticket.is_claimed:
            continue
        if any(b not in known or b not in closed for b in ticket.blocked_by):
            continue
        frontier.append(ticket)
    return frontier


# --------------------------------------------------------------------------
# Client
# --------------------------------------------------------------------------


class WayfinderTracker:
    """Read, preview, and apply Wayfinder state on exactly one repository."""

    def __init__(self, transport: Transport, repo: RepoRef) -> None:
        self.transport = transport
        self.repo = repo

    # -- reads -------------------------------------------------------------

    def repository(self) -> dict:
        _, data = self.transport.request("GET", self.repo.api_base)
        if not isinstance(data, dict):
            raise WayfinderError(f"{self.repo.slug} did not resolve to a repository")
        return data

    def require_private(self) -> dict:
        """Refuse a public tracker. Maps hold premature deliberation."""
        data = self.repository()
        if data.get("private") is not True:
            raise WayfinderError(
                f"{self.repo.slug} is public — Wayfinder maps go only on private "
                "trackers. Use the private workspace tracker for this effort."
            )
        return data

    def get_issue(self, number: int) -> dict:
        _, data = self.transport.request(
            "GET", f"{self.repo.api_base}/issues/{number}"
        )
        if not isinstance(data, dict):
            raise WayfinderError(f"issue #{number} not found in {self.repo.slug}")
        return data

    def blockers(self, number: int) -> tuple[int, ...]:
        _, data = self.transport.request(
            "GET", f"{self.repo.api_base}/issues/{number}/dependencies"
        )
        return tuple(sorted(int(item["number"]) for item in (data or [])))

    def comments(self, number: int) -> list[dict]:
        """Every comment on one issue, paginated, in server order."""
        collected: list[dict] = []
        for page in range(1, MAX_COMMENT_PAGES + 1):
            _, batch = self.transport.request(
                "GET",
                f"{self.repo.api_base}/issues/{number}/comments"
                f"?limit={PAGE_SIZE}&page={page}",
            )
            batch = batch or []
            collected.extend(batch)
            if len(batch) < PAGE_SIZE:
                return collected
        raise WayfinderError(
            f"#{number} has more than {MAX_COMMENT_PAGES * PAGE_SIZE} comments to scan; "
            "refusing to arbitrate a claim from a truncated record"
        )

    def claim_records(self, number: int) -> list[ClaimRecord]:
        return parse_records(self.comments(number))

    def current_claim(self, number: int) -> ClaimRecord | None:
        return active_claim(self.claim_records(number))

    def labels(self) -> dict[str, int]:
        """Existing repository labels, name -> numeric id."""
        return {name: int(row["id"]) for name, row in self.label_rows().items()}

    def label_rows(self) -> dict[str, dict]:
        """Existing repository labels in full, so readback can be exact."""
        found: dict[str, dict] = {}
        for page in range(1, MAX_ISSUE_PAGES + 1):
            _, batch = self.transport.request(
                "GET", f"{self.repo.api_base}/labels?limit={PAGE_SIZE}&page={page}"
            )
            batch = batch or []
            for label in batch:
                found[str(label["name"])] = dict(label)
            if len(batch) < PAGE_SIZE:
                return found
        raise WayfinderError(f"{self.repo.slug} has more labels than this adapter will scan")

    def resolve_label_ids(
        self, names: Sequence[str], *, apply: bool = False
    ) -> tuple[dict[str, int], list[str]]:
        """Map label names to the numeric ids `CreateIssueOption` requires.

        Returns `(ids, created_or_missing)`. In preview mode the second element
        names the labels that *would* be created; under `apply` it names the
        ones that *were*, each read back from the API rather than assumed.
        """
        for name in names:
            if name not in LABEL_DEFINITIONS:
                raise WayfinderError(
                    f"refusing to manage an undeclared label: {name!r}"
                )
        existing = self.labels()
        ids = {name: existing[name] for name in names if name in existing}
        missing = [name for name in names if name not in existing]
        if not apply:
            return ids, missing

        for name in missing:
            definition = LABEL_DEFINITIONS[name]
            created: dict = {}

            def write(_state: GuardState, name=name, definition=definition,
                      created=created) -> None:
                _, data = self.transport.request(
                    "POST",
                    f"{self.repo.api_base}/labels",
                    {
                        "name": name,
                        "color": definition["color"],
                        "description": definition["description"],
                    },
                )
                if isinstance(data, dict):
                    created.update(data)

            def verify(_state: GuardState, name=name, definition=definition,
                       created=created) -> bool:
                # Exact: the label must exist *and* carry the colour and
                # description we asked for, *and* be the id the create
                # reported. "A label by that name appeared" would accept
                # someone else's label, or ours with the wrong appearance.
                row = self.label_rows().get(name)
                if row is None:
                    return False
                if str(row.get("color", "")).lstrip("#").lower() != definition[
                    "color"
                ].lstrip("#").lower():
                    return False
                if str(row.get("description", "")) != definition["description"]:
                    return False
                if "id" in created and int(row["id"]) != int(created["id"]):
                    return False
                return True

            self.guarded_write(
                WriteGuard(what=f"creating label {name!r}"),
                write,
                verify,
                unverified=(
                    f"label {name!r} did not read back with the exact name, colour, "
                    "description, and id it was created with; tracker state is unclear"
                ),
            )
        if missing:
            refreshed = self.labels()
            for name in missing:
                if name not in refreshed:  # pragma: no cover - guarded above
                    raise WayfinderError(
                        f"label {name!r} did not read back after creation; "
                        "tracker state is unchanged"
                    )
                ids[name] = refreshed[name]
        return ids, missing

    def read_map(self, map_number: int) -> dict:
        """Load the map at low resolution: title, state, managed region, and
        the decision index derived by replaying the map's index records.

        Identity lives in `read_map_issue`, so the identity a read enforces
        and the identity a write enforces cannot diverge.
        """
        view = self.read_map_issue(map_number)[1]
        view["decisions"] = self.map_decisions(map_number)
        return view

    def _issue_pages(self, state: str) -> list[dict]:
        """Every candidate issue, paginated.

        The `labels=` filter cannot be trusted to narrow anything — Forgejo
        returns every issue when the named label does not exist yet, which is
        the situation before the first map. And a frontier computed from a
        truncated page hands out work while blocked and claimed state is
        invisible. So: page until exhausted, and raise rather than stop short.
        """
        label = urllib.parse.quote(TICKET_LABEL)
        issues: list[dict] = []
        for page in range(1, MAX_ISSUE_PAGES + 1):
            _, batch = self.transport.request(
                "GET",
                f"{self.repo.api_base}/issues"
                f"?state={state}&type=issues&limit={PAGE_SIZE}&page={page}&labels={label}",
            )
            batch = batch or []
            issues.extend(batch)
            if len(batch) < PAGE_SIZE:
                return issues
        raise WayfinderError(
            f"{self.repo.slug} has more than {MAX_ISSUE_PAGES * PAGE_SIZE} issues to scan; "
            "refusing to compute a frontier from a truncated listing"
        )

    def _ticket_from_issue(self, issue: dict, map_number: int) -> Ticket:
        meta = parse_ticket_metadata(issue.get("body") or "")
        number = int(issue["number"])
        holder = active_claim(self.claim_records(number))
        return Ticket(
            number=number,
            title=issue["title"],
            state=issue["state"],
            map_number=map_number,
            # No default. An issue with unreadable metadata is not a ticket,
            # and `""` says so instead of quietly claiming it is a grilling.
            ticket_type=meta.get("type", ""),
            labels=tuple(label["name"] for label in issue.get("labels", [])),
            blocked_by=self.blockers(number),
            claim=self.holder_view(holder) if holder else None,
            updated_at=issue.get("updated_at", ""),
            html_url=issue.get("html_url", ""),
        )

    def list_tickets(self, map_number: int, *, state: str = "all") -> list[Ticket]:
        """Every ticket whose managed metadata names this map."""
        tickets = [
            self._ticket_from_issue(issue, map_number)
            for issue in self._issue_pages(state)
            if self._belongs_to(issue, map_number)
        ]
        return sorted(tickets, key=lambda t: t.number)

    def frontier(self, map_number: int) -> list[Ticket]:
        return compute_frontier(self.list_tickets(map_number, state="all"))

    @staticmethod
    def _belongs_to(issue: dict, map_number: int) -> bool:
        meta = parse_ticket_metadata(issue.get("body") or "")
        return (
            meta.get("version") == METADATA_VERSION
            and meta.get("map") == str(map_number)
            and meta.get("type") in TICKET_TYPES
        )

    # -- identity reads (no privacy check; see `enforce`) -------------------

    def read_map_issue(self, map_number: int) -> tuple[dict, dict]:
        """Read a map issue and require its exact identity.

        A map is an issue that is *this* number, carries `wayfinder:map`, and
        holds exactly one balanced managed region at the current metadata
        version. A body marker alone is not identity — anyone can paste one
        into an unrelated issue — and a duplicated or half-written region means
        the adapter cannot tell which text it is supposed to merge into.
        """
        issue = self.get_issue(map_number)
        if int(issue.get("number", -1)) != int(map_number):
            raise WayfinderError(
                f"asked for map #{map_number} but the API returned #{issue.get('number')}; "
                "refusing to operate on an issue that is not the one requested"
            )
        labels = tuple(label["name"] for label in issue.get("labels", []))
        if MAP_LABEL not in labels:
            raise WayfinderError(
                f"#{map_number} in {self.repo.slug} is not labelled {MAP_LABEL}; "
                "refusing to treat it as a map"
            )
        body = issue.get("body") or ""
        require_one_managed_region(body, f"#{map_number}")
        return issue, {
            "number": issue["number"],
            "title": issue["title"],
            "state": issue["state"],
            "html_url": issue.get("html_url", ""),
            "updated_at": issue.get("updated_at", ""),
            "managed": extract_managed_region(body),
        }

    def read_ticket_issue(self, number: int, map_number: int) -> tuple[dict, Ticket]:
        """Read a ticket issue and require its exact identity.

        Checks the issue number the API actually returned, both required labels
        — `wayfinder:ticket` *and* the `wayfinder:{type}` label matching the
        declared type — and the exact ticket metadata schema. A type label that
        disagrees with the body means two sources of truth, and this adapter
        refuses to pick one.
        """
        issue = self.get_issue(number)
        if int(issue["number"]) != int(number):
            raise WayfinderError(
                f"asked for #{number} but the API returned #{issue['number']}"
            )
        labels = tuple(label["name"] for label in issue.get("labels", []))
        if TICKET_LABEL not in labels:
            raise WayfinderError(
                f"#{number} is not labelled {TICKET_LABEL}; refusing to treat it as a ticket"
            )
        meta = require_ticket_metadata(issue.get("body") or "", f"#{number}")
        ticket_type = meta["type"]
        type_label = f"wayfinder:{ticket_type}"
        if type_label not in labels:
            raise WayfinderError(
                f"#{number} declares type {ticket_type!r} in its metadata but is not "
                f"labelled {type_label}; refusing to operate on a ticket whose labels "
                "and body disagree"
            )
        if meta["map"] != str(map_number):
            raise WayfinderError(
                f"#{number} belongs to map {meta['map']!r}, not {map_number}; "
                "refusing to operate on it"
            )
        return issue, self._ticket_from_issue(issue, map_number)

    # -- preflight (read-only paths) ---------------------------------------

    def preflight_ticket(self, number: int, map_number: int) -> Ticket:
        """Revalidate a ticket for a read-only or preview path.

        Guarded writes do not call this: they go through `enforce`, which
        orders the same checks so that privacy is the *last* read before the
        mutation. Here the order does not matter, because nothing is written.
        """
        self.require_private()
        return self.read_ticket_issue(number, map_number)[1]

    def preflight_map(self, map_number: int) -> dict:
        """Revalidate privacy and exact map identity before reading a map."""
        self.require_private()
        return self.read_map_issue(map_number)[1]

    # -- the single guarded-write path -------------------------------------

    def enforce(self, guard: WriteGuard) -> GuardState:
        """Re-establish every authority a write depends on, at this instant.

        This is the *only* place those checks live. Spelling them out around
        each call site is how one call site quietly ends up missing one; a
        write that cannot name its guard does not happen.

        **Privacy is checked last, on purpose.** Every other read — map
        identity, ticket identity and metadata, ownership, dependency snapshot —
        happens first, and `require_private()` is the final network round trip
        before the single write. Checking privacy first and *then* issuing three
        more reads leaves a window in which the repository can be made public
        while the adapter is still deciding; the mutation would then land on a
        public tracker that the adapter had already approved. The returned
        `GuardState` carries everything the write needs so the write closure
        performs no read of its own and cannot reopen that window.

        Between any two steps of a longer operation the repository can be made
        public, a label can be removed, a ticket can be re-pointed at another
        map, or a claim can change hands. Re-reading here — not at the top of
        the operation — is what makes the authority contemporaneous with the
        write it protects.
        """
        map_issue = current_map = None
        if guard.map_number is not None:
            map_issue, current_map = self.read_map_issue(guard.map_number)

        ticket_issue = ticket = None
        if guard.ticket is not None:
            if guard.map_number is None:  # pragma: no cover - construction error
                raise WayfinderError(
                    f"{guard.what}: a ticket guard must name the map it belongs to"
                )
            ticket_issue, ticket = self.read_ticket_issue(guard.ticket, guard.map_number)

        if guard.extra_tickets:
            if guard.map_number is None:  # pragma: no cover - construction error
                raise WayfinderError(
                    f"{guard.what}: an extra ticket guard must name its map"
                )
            for extra in guard.extra_tickets:
                self.read_ticket_issue(extra, guard.map_number)

        claim = claim_queued = None
        if guard.claim_owner is not None or guard.claim_queued_owner is not None:
            records = self.claim_records(guard.ticket)
            if guard.claim_owner is not None:
                claim = self._require_holder(
                    guard, records, wanted=guard.claim_owner, hold="claim", drop="release"
                )
            if guard.claim_queued_owner is not None:
                claim_queued = self._require_acquisition(
                    guard,
                    records,
                    wanted=guard.claim_queued_owner,
                    hold="claim",
                    drop="release",
                    what_scope=f"#{guard.ticket}",
                )

        blockers: tuple[int, ...] = ()
        if guard.snapshot_blockers:
            blockers = self.blockers(guard.ticket)

        # LAST. Nothing may read the network after this and before the write.
        repository = self.require_private()
        return GuardState(
            repository=repository,
            map=current_map,
            map_issue=map_issue,
            ticket=ticket,
            ticket_issue=ticket_issue,
            claim=claim,
            claim_queued=claim_queued,
            blockers=blockers,
        )

    @staticmethod
    def _require_holder(
        guard: WriteGuard,
        records: Sequence[ManagedRecord],
        *,
        wanted: Sequence[str],
        hold: str,
        drop: str,
    ) -> ManagedRecord:
        """Require that this exact identity is the *current holder*."""
        wanted = tuple(wanted)
        holder = active_holder(records, hold=hold, drop=drop)
        if holder is None:
            raise WayfinderError(
                f"{guard.what}: nothing holds the claim on #{guard.ticket}; "
                f"acquisition {describe_identity(wanted)} does not hold it"
            )
        if acquisition_identity(holder) != wanted:
            raise WayfinderError(
                f"{guard.what}: the claim on #{guard.ticket} "
                f"is held by {describe_identity(acquisition_identity(holder))}, not "
                f"{describe_identity(wanted)}; only the current holder may write"
            )
        return holder

    @staticmethod
    def _require_acquisition(
        guard: WriteGuard,
        records: Sequence[ManagedRecord],
        *,
        wanted: Sequence[str],
        hold: str,
        drop: str,
        what_scope: str,
    ) -> ManagedRecord:
        """Require that this exact acquisition exists and is still live.

        Deliberately does *not* require it to be winning: the acquisition a
        recovery has to clear is usually queued behind the current holder,
        which is what a failed withdrawal leaves behind.
        """
        wanted = tuple(wanted)
        found = find_acquisition(records, hold=hold, identity=wanted)
        if found is None:
            raise WayfinderError(
                f"{guard.what}: no {hold} on {what_scope} matches "
                f"{describe_identity(wanted)}; refusing to post a drop record for an "
                "acquisition that was never made"
            )
        if not acquisition_is_active(records, hold=hold, drop=drop, identity=wanted):
            raise WayfinderError(
                f"{guard.what}: {describe_identity(wanted)} on {what_scope} is already "
                "released; nothing to recover"
            )
        return found

    def guarded_write(
        self,
        guard: WriteGuard,
        write: Callable[[GuardState], Any],
        verify: Callable[[GuardState], bool],
        *,
        unverified: str = "",
    ) -> GuardState:
        """Guard, write exactly once, then prove the write actually landed.

        A transport that returns 200 has not necessarily persisted anything —
        a proxy, a retry layer, or a partially applied API call can all
        acknowledge without storing. So every mutation ends by reading the
        state back and checking for the *exact* thing it wrote: this issue
        number, this assignee, this body, this identity tuple. Failing that
        check is a failure of the operation, not a warning.

        `write` must not read the network. Everything it needs is in the
        `GuardState` the guard just captured, and a read there would put a
        round trip between the privacy check and the mutation.
        """
        state = self.enforce(guard)
        write(state)
        if not verify(state):
            raise WayfinderError(
                unverified
                or f"{guard.what} did not read back; treat the tracker state as unchanged "
                "and retry after inspecting it"
            )
        return state

    def _patch_issue_direct(self, number: int, payload: dict) -> dict:
        """One PATCH, no preceding read.

        The staleness guard that used to live here is gone, and not because it
        stopped mattering: `enforce` reads the issue itself, immediately before
        this call, so its read *is* the fresh one. Re-reading here would only
        add a round trip after the privacy check — the window this design
        exists to close.
        """
        _, data = self.transport.request(
            "PATCH", f"{self.repo.api_base}/issues/{number}", payload
        )
        if not isinstance(data, dict):
            raise WayfinderError(f"patching #{number} returned no issue to verify")
        return data

    def _post_record(self, number: int, kind: str, fields: dict[str, str]) -> dict:
        _, data = self.transport.request(
            "POST",
            f"{self.repo.api_base}/issues/{number}/comments",
            {"body": render_record(kind, fields)},
        )
        return data if isinstance(data, dict) else {}

    def _all_issue_pages(self) -> list[dict]:
        issues: list[dict] = []
        for page in range(1, MAX_ISSUE_PAGES + 1):
            _, batch = self.transport.request(
                "GET",
                f"{self.repo.api_base}/issues"
                f"?state=all&type=issues&limit={PAGE_SIZE}&page={page}",
            )
            batch = batch or []
            issues.extend(batch)
            if len(batch) < PAGE_SIZE:
                return issues
        raise WayfinderError(
            f"{self.repo.slug} has more than {MAX_ISSUE_PAGES * PAGE_SIZE} issues to scan"
        )

    def _find_created(self, creation: str) -> tuple[set[int], list[dict]]:
        """Pre-write issue-number snapshot plus issues carrying this creation id.

        One listing pass serves both needs: the snapshot that creation readback
        checks against, and the exact-scope search a retry converges through.
        """
        issues = self._all_issue_pages()
        numbers = {int(issue["number"]) for issue in issues}
        matches = [
            issue
            for issue in issues
            if parse_creation(issue.get("body") or "") == creation
        ]
        return numbers, matches

    def _converge_created(
        self,
        matches: Sequence[dict],
        *,
        creation: str,
        title: str,
        body: str,
        labels: Sequence[str],
        subject: str,
    ) -> int:
        """Converge a retried create on the one issue its first attempt made.

        A retry after an ambiguous success — the POST committed while the
        response was lost — finds its own earlier issue by creation identity
        instead of creating a duplicate. One exact match converges; anything
        ambiguous or inexact fails closed for manual reconciliation, because
        adopting an issue that is not byte-for-byte what was previewed would
        hand back an object nobody reviewed.
        """
        if len(matches) != 1:
            raise WayfinderError(
                f"{len(matches)} issues carry creation identity {creation}; "
                f"refusing to converge {subject} on an ambiguous match — "
                "reconcile the tracker manually"
            )
        number = int(matches[0]["number"])
        issue = self.get_issue(number)
        actual_labels = {label["name"] for label in issue.get("labels", [])}
        if (
            issue.get("title") != title
            or (issue.get("body") or "") != body
            or actual_labels != set(labels)
        ):
            raise WayfinderError(
                f"#{number} carries creation identity {creation} but is not "
                f"byte-for-byte the previewed {subject}; refusing to converge — "
                "reconcile the tracker manually"
            )
        return number

    def _verify_created_issue(
        self,
        created: dict,
        *,
        before: set[int],
        title: str,
        body: str,
        labels: Sequence[str],
        subject: str,
    ) -> int:
        """Prove the create actually created *this* issue, exactly.

        Four separate ways a create can look successful without being:

        * nothing was created and an existing issue came back — caught by the
          pre-write snapshot of issue numbers;
        * a different issue came back — caught by re-reading the number;
        * the title or body was not stored as sent — caught byte for byte;
        * the label set differs — caught as an exact set, so a missing
          `wayfinder:map` *and* a stray extra label both fail.
        """
        if "number" not in created:
            raise WayfinderError(f"creating {subject} returned no issue number")
        number = int(created["number"])
        if number < 1:
            raise WayfinderError(
                f"creating {subject} returned issue number {number}; Forgejo "
                "numbers issues from 1, so this is not a created issue and the "
                "tracker state is unclear"
            )
        if number in before:
            raise WayfinderError(
                f"creating {subject} returned the pre-existing #{number}; "
                "nothing was created and the tracker is unchanged"
            )
        issue = self.get_issue(number)
        if int(issue.get("number", -1)) != number:
            raise WayfinderError(
                f"creating {subject}: asked for #{number} but the API returned "
                f"#{issue.get('number')}"
            )
        if issue.get("title") != title:
            raise WayfinderError(
                f"creating {subject}: #{number} stored title "
                f"{issue.get('title')!r}, not {title!r}"
            )
        if (issue.get("body") or "") != body:
            raise WayfinderError(
                f"creating {subject}: #{number} did not store the exact body that "
                "was previewed"
            )
        actual = {label["name"] for label in issue.get("labels", [])}
        if actual != set(labels):
            raise WayfinderError(
                f"creating {subject}: #{number} carries labels {sorted(actual)}, "
                f"not exactly {sorted(set(labels))}"
            )
        return number

    def create_map(
        self,
        *,
        title: str,
        managed: str,
        prose: str = "",
        creation: str | None = None,
        apply: bool = False,
    ) -> Preview | dict:
        self.require_private()
        require_no_managed_markers(managed, "the managed map region")
        require_no_managed_markers(prose, "the map prose")
        if creation:
            creation = validate_creation(creation)
        elif apply:
            raise WayfinderError(
                "applying create-map requires the exact --creation the preview "
                "printed; a retry with the same identity converges on the issue "
                "the earlier attempt may have created instead of duplicating it"
            )
        else:
            creation = new_creation_id()
        body = replace_managed_region(prose, managed)
        body = body.rstrip() + "\n\n" + render_created_marker(creation) + "\n"
        require_one_managed_region(body, "the map body about to be written")
        if not apply:
            _ids, missing = self.resolve_label_ids([MAP_LABEL], apply=False)
            steps = [f"create issue {title!r} labelled {MAP_LABEL}"]
            if missing:
                steps.insert(0, f"create missing label(s): {', '.join(missing)}")
            steps.insert(
                0,
                f"creation identity: {creation} — retain it; apply with "
                f"--creation {creation} --apply, and a retry with the same "
                "identity converges instead of creating a duplicate",
            )
            steps.append("verify by re-reading the created issue")
            return Preview(
                action="create map",
                repo=self.repo.slug,
                steps=tuple(steps),
                content=({"label": f"map body: {title}", "text": body},),
            )
        before, matches = self._find_created(creation)
        if matches:
            number = self._converge_created(
                matches,
                creation=creation,
                title=title,
                body=body,
                labels=[MAP_LABEL],
                subject=f"map {title!r}",
            )
            # Full map identity too, not just exact content.
            self.read_map_issue(number)
            return self.read_map(number)
        ids, _missing = self.resolve_label_ids([MAP_LABEL], apply=True)
        created: dict = {}

        def write(_state: GuardState) -> None:
            _, data = self.transport.request(
                "POST",
                f"{self.repo.api_base}/issues",
                {"title": title, "body": body, "labels": [ids[MAP_LABEL]]},
            )
            if not isinstance(data, dict):
                raise WayfinderError("creating the map returned no issue")
            created.update(data)

        def verify(_state: GuardState) -> bool:
            number = self._verify_created_issue(
                created,
                before=before,
                title=title,
                body=body,
                labels=[MAP_LABEL],
                subject=f"map {title!r}",
            )
            # And it must satisfy full map identity, including exactly one
            # balanced managed region.
            self.read_map_issue(number)
            return True

        self.guarded_write(WriteGuard(what=f"creating map {title!r}"), write, verify)
        return self.read_map(int(created["number"]))

    def create_ticket(
        self,
        *,
        map_number: int,
        title: str,
        question: str,
        ticket_type: str,
        creation: str | None = None,
        apply: bool = False,
    ) -> Preview | Ticket:
        self.preflight_map(map_number)
        question = require_no_managed_markers(question, f"the question for {title!r}")
        if creation:
            creation = validate_creation(creation)
        elif apply:
            raise WayfinderError(
                "applying create-ticket requires the exact --creation the preview "
                "printed; a retry with the same identity converges on the issue "
                "the earlier attempt may have created instead of duplicating it"
            )
        else:
            creation = new_creation_id()
        metadata = render_ticket_metadata(map_number, ticket_type)
        body = (
            f"## Question\n\n{question.strip()}\n\n{metadata}\n\n"
            f"{render_created_marker(creation)}\n"
        )
        names = [TICKET_LABEL, f"wayfinder:{ticket_type}"]
        if not apply:
            _ids, missing = self.resolve_label_ids(names, apply=False)
            steps = [f"create issue {title!r} labelled {', '.join(names)}"]
            if missing:
                steps.insert(0, f"create missing label(s): {', '.join(missing)}")
            steps.insert(
                0,
                f"creation identity: {creation} — retain it; apply with "
                f"--creation {creation} --apply, and a retry with the same "
                "identity converges instead of creating a duplicate",
            )
            steps += [
                f"record map {map_number} and type {ticket_type} in its managed metadata",
                "verify by re-reading the created issue",
            ]
            return Preview(
                action="create ticket",
                repo=self.repo.slug,
                steps=tuple(steps),
                content=({"label": f"ticket body: {title}", "text": body},),
            )
        before, matches = self._find_created(creation)
        if matches:
            number = self._converge_created(
                matches,
                creation=creation,
                title=title,
                body=body,
                labels=names,
                subject=f"ticket {title!r}",
            )
            # Full ticket identity too: metadata version, exact map, exact
            # type, and the matching type label.
            _, ticket = self.read_ticket_issue(number, map_number)
            if ticket.ticket_type != ticket_type:
                raise WayfinderError(
                    f"converging on ticket {title!r}: #{number} reads back as type "
                    f"{ticket.ticket_type!r}, not {ticket_type!r}"
                )
            return self.preflight_ticket(number, map_number)
        ids, _missing = self.resolve_label_ids(names, apply=True)
        created: dict = {}

        def write(_state: GuardState) -> None:
            _, data = self.transport.request(
                "POST",
                f"{self.repo.api_base}/issues",
                {
                    "title": title,
                    "body": body,
                    "labels": [ids[name] for name in names],
                },
            )
            if not isinstance(data, dict):
                raise WayfinderError("creating the ticket returned no issue")
            created.update(data)

        def verify(_state: GuardState) -> bool:
            number = self._verify_created_issue(
                created,
                before=before,
                title=title,
                body=body,
                labels=names,
                subject=f"ticket {title!r}",
            )
            # Exact ticket identity too: metadata version, exact map, exact
            # type, and the matching type label.
            _, ticket = self.read_ticket_issue(number, map_number)
            if ticket.ticket_type != ticket_type:
                raise WayfinderError(
                    f"creating ticket {title!r}: #{number} reads back as type "
                    f"{ticket.ticket_type!r}, not {ticket_type!r}"
                )
            return True

        self.guarded_write(
            WriteGuard(what=f"creating ticket {title!r}", map_number=map_number),
            write,
            verify,
        )
        return self.preflight_ticket(int(created["number"]), map_number)

    def wire_blocking(
        self, *, map_number: int, blocked: int, blocked_by: int, apply: bool = False
    ) -> Preview | tuple[int, ...]:
        """Add a native dependency edge, scoped to this map's tickets."""
        if int(blocked) == int(blocked_by):
            raise WayfinderError(
                f"refusing to make #{blocked} depend on itself"
            )
        for number in (blocked, blocked_by):
            self.preflight_ticket(number, map_number)
        steps = (
            f"make #{blocked} depend on #{blocked_by} (native issue dependency)",
            f"verify by re-reading #{blocked}'s dependencies",
        )
        if not apply:
            return Preview(action="wire blocking", repo=self.repo.slug, steps=steps)

        # The final guard revalidates exact map/ticket identity for BOTH
        # endpoints — `blocked` and `blocked_by` — immediately before the
        # privacy check and the POST, so identity, label, or map drift on
        # either endpoint prevents the dependency write.
        expected: set[int] = set()

        def write(state: GuardState) -> None:
            expected.update(set(state.blockers) | {int(blocked_by)})
            self.transport.request(
                "POST",
                f"{self.repo.api_base}/issues/{blocked}/dependencies",
                {"owner": self.repo.owner, "repo": self.repo.repo, "index": blocked_by},
            )

        def verify(_state: GuardState) -> bool:
            # Exact set, derived from the pre-write snapshot plus the one edge
            # requested. A missing edge, a removed unrelated edge, and an
            # unexpected extra edge all fail — the last one conservatively,
            # because a dependency we did not ask for is state we cannot
            # explain.
            actual = set(self.blockers(blocked))
            if actual == expected:
                return True
            raise WayfinderError(
                f"dependency readback for #{blocked} is {sorted(actual)}, not exactly "
                f"{sorted(expected)}; missing {sorted(expected - actual)}, unexpected "
                f"{sorted(actual - expected)} — treat the tracker as unchanged"
            )

        self.guarded_write(
            WriteGuard(
                what=f"wiring #{blocked} → #{blocked_by}",
                map_number=map_number,
                ticket=blocked,
                extra_tickets=(int(blocked_by),),
                snapshot_blockers=True,
            ),
            write,
            verify,
        )
        return self.blockers(blocked)

    def _record_landed(
        self,
        number: int,
        *,
        kind: str,
        fields: dict[str, str],
        posted: dict,
        known_comment_ids: set[int],
    ) -> bool:
        """Whether *this* write produced a record, not whether one exists.

        A pre-existing record with the same identity is not proof: retrying a
        write whose earlier attempt landed and whose new attempt was swallowed
        would read back the old record and report success. So the readback
        requires the API to have returned a **positive** comment id, and a
        comment under exactly that id — absent from the pre-write snapshot —
        whose body is byte-exact. A create that echoes no id, a zero, or a
        negative one is a server this adapter cannot verify against, and an
        unverifiable write is a failed write.
        """
        expected_body = render_record(kind, fields)
        return self._new_comment_landed(
            number,
            expected_body=expected_body,
            posted=posted,
            known_comment_ids=known_comment_ids,
        )

    def _new_comment_landed(
        self,
        number: int,
        *,
        expected_body: str,
        posted: dict,
        known_comment_ids: set[int],
    ) -> bool:
        posted_id = _positive_comment_id(posted)
        if posted_id is None or posted_id in known_comment_ids:
            return False
        for comment in self.comments(number):
            if _positive_comment_id(comment) != posted_id:
                continue
            return (comment.get("body") or "") == expected_body
        return False

    @staticmethod
    def _comment_id_snapshot(comments: Iterable[dict]) -> set[int]:
        """Every positive comment id present before a write."""
        ids = (_positive_comment_id(comment) for comment in comments)
        return {comment_id for comment_id in ids if comment_id is not None}

    def claim(
        self,
        *,
        map_number: int,
        number: int,
        session: str,
        claimed_at: str,
        assignee: str | None = None,
        operation: str | None = None,
        apply: bool = False,
    ) -> Preview | ClaimOutcome:
        """Claim a ticket through an append-only, server-ordered record.

        Post one claim comment carrying a fresh **operation id**, then re-read
        every managed record and let Forgejo's monotonic comment id decide. The
        earliest unreleased acquisition wins; every other contender stands
        down. Two contenders cannot both return `won=True`, because both
        compute the winner from the same ordered comment list rather than from
        whose write landed last.

        Ownership is `(operation, session)`. Passing `operation` retries an
        interrupted attempt idempotently — but only when *this* session owns
        that exact operation on *this* ticket. An operation id is written into
        a tracker comment, so anyone who can read the issue can quote it; a
        foreign session presenting a real id is an impostor, not a retry, and
        is refused.
        """
        session = validate_session(session)
        claimed_at = validate_timestamp(claimed_at)
        if operation:
            operation = validate_operation(operation)
        elif apply:
            # Preview and apply must be byte-identical: minting here would post
            # a different record than the one Bryan reviewed.
            raise WayfinderError(
                "applying a claim requires the exact --operation the preview "
                "printed; re-run the same command with --operation <id> --apply"
            )
        else:
            operation = new_operation_id()
        identity = claim_identity(operation, session)
        self.preflight_ticket(number, map_number)
        records = self.claim_records(number)
        holder = active_claim(records)
        if holder is not None and acquisition_identity(holder) == identity:
            # Our own acquisition, already holding: an idempotent retry of an
            # attempt that landed. Do not post a second record.
            return ClaimOutcome(
                won=True,
                ticket=number,
                reason="already claimed by this operation (idempotent retry)",
                holder=self.holder_view(holder),
                operation=operation,
            )
        if holder is not None:
            same_operation = holder.operation == operation
            return ClaimOutcome(
                won=False,
                ticket=number,
                reason=(
                    f"operation {operation} on #{number} belongs to session "
                    f"{holder.session!r}, not {session!r}; quoting another session's "
                    "operation id does not transfer its claim"
                    if same_operation
                    else "already claimed by another session"
                    if holder.session != session
                    else "already claimed by another operation of this same session; "
                    "a session must not hold two overlapping claims on one ticket"
                ),
                holder=self.holder_view(holder),
                operation=operation,
            )
        if acquisition_is_active(
            records, hold="claim", drop="release", identity=identity
        ):
            # Ours, queued behind nobody visible as holder — should not happen,
            # but reporting it beats posting a second acquisition.
            return ClaimOutcome(
                won=False,
                ticket=number,
                reason=(
                    f"{describe_identity(identity)} already has a queued claim on "
                    f"#{number}; recover or release it rather than claiming again"
                ),
                operation=operation,
            )

        fields = {"session": session, "operation": operation, "at": claimed_at}
        record = render_record("claim", fields)
        steps = [
            f"post one claim record for operation {operation} (session {session}) on #{number}",
            f"assign #{number} to {assignee}" if assignee else "leave assignment unchanged",
            f"re-read every managed record on #{number} and stand down unless "
            f"{describe_identity(identity)} is the earliest unreleased claim",
        ]
        if not apply:
            steps.append(
                f"to apply exactly this record, re-run with --operation "
                f"{operation} --apply (apply refuses to mint a fresh operation)"
            )
            return Preview(
                action="claim ticket",
                repo=self.repo.slug,
                steps=tuple(steps),
                content=({"label": "claim record", "text": record},),
            )

        known = self._comment_id_snapshot(self.comments(number))
        posted: dict = {}
        self.guarded_write(
            WriteGuard(what=f"claiming #{number}", map_number=map_number, ticket=number),
            lambda _state: posted.update(self._post_record(number, "claim", fields)),
            lambda _state: self._record_landed(
                number,
                kind="claim",
                fields=fields,
                posted=posted,
                known_comment_ids=known,
            ),
            unverified=(
                f"claim record for {describe_identity(identity)} on #{number} did not "
                f"read back as a new comment; tracker state is unclear — inspect "
                f"#{number} before retrying"
            ),
        )

        winner = self.current_claim(number)
        if winner is None:  # pragma: no cover - readback proved a live record
            raise WayfinderError(
                f"claim record on #{number} did not read back; tracker state is unclear"
            )
        if acquisition_identity(winner) != identity:
            # We lost, and we left a claim record behind. Leaving it queued is
            # not harmless: when the winner releases, the *loser's* stale claim
            # becomes the active one and the ticket silently transfers to a
            # session that already walked away. Withdraw exactly our own
            # acquisition before returning.
            withdrawn, detail = self._withdraw_claim(
                map_number=map_number,
                number=number,
                session=session,
                operation=operation,
                at=claimed_at,
            )
            return ClaimOutcome(
                won=False,
                ticket=number,
                reason=(
                    "an earlier unreleased claim holds this ticket; this operation's "
                    + (
                        f"losing claim was withdrawn ({operation})"
                        if withdrawn
                        else "losing claim is STILL QUEUED — recover it explicitly with "
                        + self.claim_recovery_command(map_number, number, session, operation)
                        + f" ({detail})"
                    )
                ),
                holder=self.holder_view(winner),
                operation=operation,
            )

        if assignee:
            # Assignment is a separate write with its own guard: it may only
            # happen while *this* acquisition still holds the claim, and the
            # exact assignee set must read back.
            self.guarded_write(
                WriteGuard(
                    what=f"assigning #{number} to {assignee}",
                    map_number=map_number,
                    ticket=number,
                    claim_owner=identity,
                ),
                lambda _state: self._patch_issue_direct(number, {"assignees": [assignee]}),
                lambda _state: self._assignees(number) == {assignee},
                unverified=(
                    f"#{number} does not read back with exactly {{{assignee!r}}} "
                    f"assigned; the claim is held by {describe_identity(identity)} but "
                    "the assignment did not persist as requested"
                ),
            )

        return ClaimOutcome(
            won=True, ticket=number, reason="claimed", operation=operation
        )

    def _assignees(self, number: int) -> set[str]:
        """The exact assignee set on an issue.

        Exact, not "contains": an assignment that leaves someone else's login
        in place has not done what the preview said it would, and a ticket with
        two assignees is a ticket two people think they own.
        """
        issue = self.get_issue(number)
        return {
            str(person.get("login", ""))
            for person in (issue.get("assignees") or [])
        }

    @staticmethod
    def claim_recovery_command(
        map_number: int, number: int, session: str, operation: str
    ) -> str:
        return (
            f"`release --map {map_number} --ticket {number} --session {session} "
            f"--operation {operation}`"
        )

    def holder_view(self, record: ManagedRecord) -> dict[str, str]:
        """How a holder is reported: always including what recovery needs."""
        view = {
            "session": record.session,
            "operation": record.operation,
            "at": record.at,
            "comment_id": str(record.comment_id),
        }
        if record.ticket:
            view["ticket"] = record.ticket
        return view

    def _withdraw_claim(
        self, *, map_number: int, number: int, session: str, operation: str, at: str
    ) -> tuple[bool, str]:
        """Post and verify a release for this acquisition's own losing claim.

        Best-effort by design: if the withdrawal itself fails we still return a
        stand-down, but we say so — and name the full identity — rather than
        reporting a clean loss over a claim that is still queued.

        The verification is `acquisition_is_active`, not "am I the winner". A
        losing claim that is merely *not winning* is exactly the zombie this
        withdrawal exists to prevent: it becomes the active claim the moment
        the current holder releases.
        """
        try:
            self._drop_claim(
                map_number=map_number,
                number=number,
                session=session,
                operation=operation,
                at=at,
                what=f"withdrawing losing claim {operation} on #{number}",
                require_holder=False,
            )
        except WayfinderError as error:
            return False, str(error)
        return True, ""

    def _drop_claim(
        self,
        *,
        map_number: int,
        number: int,
        session: str,
        operation: str,
        at: str,
        what: str,
        require_holder: bool,
    ) -> None:
        """The one place a release record is written.

        `require_holder` separates the two legitimate releases: giving up a
        claim we hold, and clearing an acquisition of ours that is queued
        behind someone else. Both write exactly one record; both verify that
        this exact identity is afterwards inactive.
        """
        identity = claim_identity(operation, session)
        fields = {"session": session, "operation": operation, "at": at}
        known = self._comment_id_snapshot(self.comments(number))
        posted: dict = {}
        self.guarded_write(
            WriteGuard(
                what=what,
                map_number=map_number,
                ticket=number,
                claim_owner=identity if require_holder else None,
                claim_queued_owner=None if require_holder else identity,
            ),
            lambda _state: posted.update(self._post_record(number, "release", fields)),
            lambda _state: self._record_landed(
                number,
                kind="release",
                fields=fields,
                posted=posted,
                known_comment_ids=known,
            )
            and not acquisition_is_active(
                self.claim_records(number),
                hold="claim",
                drop="release",
                identity=identity,
            ),
            unverified=(
                f"{what} did not read back as a new release record leaving "
                f"{describe_identity(identity)} inactive; the claim is still held"
            ),
        )

    def release(
        self,
        *,
        map_number: int,
        number: int,
        session: str,
        released_at: str,
        operation: str,
        apply: bool = False,
    ) -> Preview | ClaimOutcome:
        """Release one named acquisition. Never clears any other.

        `operation` is required and exact, and it is checked *together with*
        the session that acquired it. Releasing on session alone would clear
        whichever claim that session held, including a sibling operation's;
        releasing on operation alone would let anyone who can read the tracker
        quote an id back and drop someone else's claim.

        This is also the recovery path for a **queued** acquisition — a losing
        claim whose withdrawal failed, sitting behind the current winner. That
        record is the zombie that takes the ticket the moment the winner
        releases, so recovery must be able to reach it without disturbing the
        winner. Read the identity from the `claim` output, from `claim-status`,
        or from the holder reported by a refusal.

        A claim left behind by an interrupted session is surfaced for explicit
        reclaim rather than expired: an assignment that looks abandoned may be
        a session that is merely slow, and stealing it loses work.
        """
        session = validate_session(session)
        released_at = validate_timestamp(released_at)
        operation = validate_operation(operation)
        identity = claim_identity(operation, session)
        self.preflight_ticket(number, map_number)
        records = self.claim_records(number)
        holder = active_claim(records)
        mine = find_acquisition(records, hold="claim", identity=identity)
        if mine is None:
            same_operation = next(
                (r for r in records if r.kind == "claim" and r.operation == operation),
                None,
            )
            return ClaimOutcome(
                won=False,
                ticket=number,
                reason=(
                    f"operation {operation} on #{number} was acquired by session "
                    f"{same_operation.session!r}, not {session!r}; refusing to release "
                    "another session's acquisition"
                    if same_operation is not None
                    else f"{describe_identity(identity)} never claimed #{number}"
                ),
                holder=self.holder_view(same_operation or holder)
                if (same_operation or holder)
                else None,
                operation=operation,
            )
        if not acquisition_is_active(
            records, hold="claim", drop="release", identity=identity
        ):
            return ClaimOutcome(
                won=True,
                ticket=number,
                reason="already released by this operation (idempotent retry)",
                operation=operation,
            )
        queued = holder is not None and acquisition_identity(holder) != identity
        fields = {"session": session, "operation": operation, "at": released_at}
        record = render_record("release", fields)
        if not apply:
            return Preview(
                action="release claim",
                repo=self.repo.slug,
                steps=(
                    (
                        f"clear the QUEUED claim {describe_identity(identity)} on "
                        f"#{number}, which sits behind "
                        f"{describe_identity(acquisition_identity(holder))}"
                        if queued
                        else f"release {describe_identity(identity)} on #{number}"
                    ),
                    f"post one release record naming operation {operation}",
                    f"verify {describe_identity(identity)} is no longer active on "
                    f"#{number}"
                    + (", and that the current holder is untouched" if queued else ""),
                ),
                content=({"label": "release record", "text": record},),
            )
        self._drop_claim(
            map_number=map_number,
            number=number,
            session=session,
            operation=operation,
            at=released_at,
            what=(
                f"clearing the queued claim {operation} on #{number}"
                if queued
                else f"releasing #{number}"
            ),
            require_holder=not queued,
        )
        if queued:
            still = self.current_claim(number)
            if still is None or acquisition_identity(still) != acquisition_identity(holder):
                raise WayfinderError(
                    f"clearing the queued claim {operation} on #{number} disturbed the "
                    "current holder; treat the tracker as unclear and inspect it"
                )
            return ClaimOutcome(
                won=True,
                ticket=number,
                reason=(
                    f"queued claim {operation} cleared; "
                    f"{describe_identity(acquisition_identity(holder))} still holds "
                    f"#{number}"
                ),
                holder=self.holder_view(holder),
                operation=operation,
            )
        return ClaimOutcome(
            won=True, ticket=number, reason="released", operation=operation
        )

    # -- the decision index (append-only) -----------------------------------

    def map_index_records(self, map_number: int) -> list[ManagedRecord]:
        """Every schema-valid index record on the map, in comment-id order."""
        return parse_records(self.comments(map_number), kinds=("index",))

    def map_decisions(self, map_number: int) -> list[dict[str, str]]:
        """The map's decision index, derived by replay.

        Nothing stores this list: it is a deterministic function of the map's
        comment history, so there is no shared mutable text for two writers —
        or a writer and a human — to overwrite. See `index_replay` for the
        per-key convergence rules.
        """
        return [
            decision_view(record)
            for record in index_replay(self.map_index_records(map_number))
        ]

    def resolve_ticket(
        self,
        *,
        map_number: int,
        number: int,
        session: str,
        answer: str,
        map_index_line: str,
        claim_operation: str,
        at: str = "",
        apply: bool = False,
    ) -> Preview | ResolutionOutcome:
        """Post the resolution, index it on the map, then close the ticket.

        The close is deliberately **last**: the resolution comment and the
        exact map index record must publish and read back before the ticket
        leaves the frontier, so a failed index append leaves the ticket open
        and its blocked dependents stay out of the frontier.

        Only the exact claiming **acquisition** may resolve — the operation
        *and* the session that acquired it, not either alone. An operation id
        lives in a tracker comment, so an impostor session can read one; and a
        session may be running another operation on another ticket. Every
        external write goes through `guarded_write`, so each one re-establishes
        privacy, identity, labels, metadata, and ownership at the instant it
        happens and then proves itself by exact readback.

        The index step is **append-only**: it posts one exact-schema `index`
        record comment on the map, and the map's decision index is the replay
        of those records. Two concurrent resolutions post two comments —
        neither can overwrite the other's, and neither touches the map body,
        so a human editing the map at any instant can never lose prose to this
        operation. There is nothing to lock and nothing to recover.

        The whole operation is resumable: deterministic markers let a retry
        perform only the steps that did not land, and the replay collapses a
        duplicated index record onto the earliest per key — so retries
        converge whatever their wording or interleaving.
        """
        session = validate_session(session)
        claim_operation = validate_operation(claim_operation)
        map_index_line = validate_index_line(map_index_line)
        answer = require_no_managed_markers(answer, f"the resolution answer for #{number}")
        now = validate_timestamp(at) if at else None
        claim_owner = claim_identity(claim_operation, session)

        entry = self.enforce(
            WriteGuard(
                what=f"resolving #{number}",
                map_number=map_number,
                ticket=number,
                claim_owner=claim_owner,
            )
        )
        ticket = entry.ticket

        key = resolution_key(map_number, number, answer)
        marker = render_record(
            "resolution",
            {"key": key, "map": str(map_number), "session": session},
        )
        record = f"{answer.rstrip()}\n\n{marker}"

        already = self._resolution_progress(
            number, key=key, map_number=map_number, session=session, ticket=ticket
        )
        if "indexed" not in already and ticket is not None and not ticket.is_open:
            # The approved correction rule: corrections reopen affected
            # decisions. A changed answer must never silently supersede — or
            # coexist with — a closed ticket's decision of record.
            raise WayfinderError(
                f"#{number} is closed and key {key} is not its decision of record; "
                f"a changed answer is a correction. Reopen #{number}, re-claim it, "
                "and resolve again — the new index record then supersedes the old "
                "one at replay, and history stays append-only"
            )
        steps: list[str] = []
        if "comment" not in already:
            steps.append(f"comment the resolution on #{number}")
        if "indexed" not in already:
            steps.append(
                f"post one index record for #{number} on map #{map_number}; the "
                "map's decision index is the replay of these records, and the map "
                "body is never edited"
            )
        if "closed" not in already:
            steps.append(
                f"close #{number} — last, so the decision of record is published "
                "before the ticket leaves the frontier"
            )
        steps.append(
            f"guard every write on {describe_identity(claim_owner)}; verify each one "
            "by exact readback"
        )
        if already:
            steps.insert(0, f"already done, skipping: {', '.join(sorted(already))}")

        if not apply:
            return Preview(
                action="resolve ticket",
                repo=self.repo.slug,
                steps=tuple(steps),
                content=(
                    {"label": f"resolution comment on #{number}", "text": record},
                    {
                        "label": f"index comment on #{map_number} (visible line)",
                        "text": f"Decision #{number}: {map_index_line}",
                    },
                ),
            )

        if now is None:
            raise WayfinderError(
                "--at is required to apply a resolution: the index record carries "
                "a timestamp"
            )

        outcome = ResolutionOutcome(ticket=number, already=sorted(already))

        if "comment" not in already:
            known = self._comment_id_snapshot(self.comments(number))
            posted: dict = {}

            def comment_write(_state: GuardState) -> None:
                _, data = self.transport.request(
                    "POST",
                    f"{self.repo.api_base}/issues/{number}/comments",
                    {"body": record},
                )
                if isinstance(data, dict):
                    posted.update(data)

            def comment_verify(_state: GuardState) -> bool:
                # A *new* comment, under the positive id the API returned, whose
                # body is byte-exact. An older comment carrying the same marker
                # would let a swallowed retry pass.
                return self._new_comment_landed(
                    number,
                    expected_body=record,
                    posted=posted,
                    known_comment_ids=known,
                )

            self.guarded_write(
                WriteGuard(
                    what=f"commenting the resolution on #{number}",
                    map_number=map_number,
                    ticket=number,
                    claim_owner=claim_owner,
                ),
                comment_write,
                comment_verify,
                unverified=(
                    f"resolution comment on #{number} did not read back as a new "
                    "comment with the exact body that was previewed"
                ),
            )
            outcome.commented = True

        if "indexed" not in already:
            index_body = render_index_comment(
                {
                    "session": session,
                    "key": key,
                    "map": str(map_number),
                    "ticket": str(number),
                    "gist": map_index_line,
                    "at": now,
                }
            )
            index_known = self._comment_id_snapshot(self.comments(map_number))
            index_posted: dict = {}

            def index_write(_state: GuardState) -> None:
                _, data = self.transport.request(
                    "POST",
                    f"{self.repo.api_base}/issues/{map_number}/comments",
                    {"body": index_body},
                )
                if isinstance(data, dict):
                    index_posted.update(data)

            def index_verify(_state: GuardState) -> bool:
                return self._new_comment_landed(
                    map_number,
                    expected_body=index_body,
                    posted=index_posted,
                    known_comment_ids=index_known,
                )

            self.guarded_write(
                WriteGuard(
                    what=f"indexing #{number} on map #{map_number}",
                    map_number=map_number,
                    ticket=number,
                    claim_owner=claim_owner,
                ),
                index_write,
                index_verify,
                unverified=(
                    f"index record for #{number} on map #{map_number} did not read "
                    "back as a new comment with the exact body that was previewed"
                ),
            )
            outcome.indexed = True

        # The close is LAST, after the resolution comment and the exact index
        # record have published and read back: a failed index append leaves
        # the ticket open, so dependency computation keeps its dependents out
        # of the frontier until a decision of record exists.
        if "closed" not in already:
            self.guarded_write(
                WriteGuard(
                    what=f"closing #{number}",
                    map_number=map_number,
                    ticket=number,
                    claim_owner=claim_owner,
                ),
                lambda _state: self._patch_issue_direct(number, {"state": "closed"}),
                lambda _state: self._closed_with_identity_intact(number, map_number),
                unverified=(
                    f"#{number} did not read back as closed with its ticket identity "
                    "intact"
                ),
            )
            outcome.closed = True

        # `resolved` is the full conjunction, re-read from the tracker: the
        # exact-key resolution comment, an index record whose key is this
        # ticket's *current* decision at replay, and the closed ticket.
        outcome.map = self.read_map(map_number)
        current = next(
            (
                entry
                for entry in outcome.map.get("decisions", [])
                if entry.get("ticket") == str(number)
            ),
            None,
        )
        indexed_current = current is not None and current.get("key") == key
        commented = find_resolution(
            self.comments(number), key=key, map_number=map_number, session=session
        )
        closed = self.get_issue(number).get("state") == "closed"
        outcome.resolved = commented and indexed_current and closed
        if not outcome.resolved:
            if (
                current is not None
                and not indexed_current
                and any(
                    record.fields.get("key") == key
                    and record.fields.get("ticket") == str(number)
                    for record in self.map_index_records(map_number)
                )
            ):
                outcome.recovery = (
                    f"#{number} indexed key {key}, but its current decision of "
                    f"record is key {current['key']}; this answer was superseded. "
                    f"To make it current, reopen #{number} and resolve it again."
                )
            else:
                outcome.recovery = (
                    f"#{number} is not fully resolved: it needs the exact-key "
                    f"resolution comment, index record {key} replaying as its "
                    f"current decision on map #{map_number}, and a closed ticket. "
                    "Re-run the same resolve; completed steps are skipped."
                )
        return outcome


    def _closed_with_identity_intact(self, number: int, map_number: int) -> bool:
        """Exactly closed, and still the ticket we closed.

        Reading only `state == "closed"` would accept a close that also lost
        the ticket's labels or metadata — which is how a "closed" ticket stops
        being findable from its map. The identity failure is re-raised against
        the close, so the operator is told which step broke rather than being
        handed the next step's confusing complaint.
        """
        try:
            issue, _ticket = self.read_ticket_issue(number, map_number)
        except WayfinderError as error:
            raise WayfinderError(
                f"#{number} was closed but no longer reads back as a ticket of map "
                f"#{map_number} ({error}); the close did not leave its identity "
                "intact, so the resolution is not complete"
            ) from error
        return issue.get("state") == "closed"

    def _resolution_progress(
        self,
        number: int,
        *,
        key: str,
        map_number: int,
        session: str,
        ticket: Ticket | None,
    ) -> set[str]:
        """Which of the three external steps already landed for this key.

        "indexed" is an exact-key match against the map's index records — never
        a text comparison. The key binds map, ticket, and answer, so an
        identical gist recorded for a *different* ticket can never satisfy this
        resolution, and a retry that rewords its gist still recognizes its own
        earlier record.
        """
        done: set[str] = set()
        if find_resolution(
            self.comments(number), key=key, map_number=map_number, session=session
        ):
            done.add("comment")
        if ticket is not None and not ticket.is_open:
            done.add("closed")
        if any(
            record.fields.get("key") == key
            and record.fields.get("ticket") == str(number)
            for record in self.map_index_records(map_number)
        ):
            done.add("indexed")
        return done


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------


def build_transport(
    repo: RepoRef,
    *,
    prefer: str = "auto",
    environ: dict[str, str] | None = None,
) -> Transport:
    """Select a transport.

    `auto` **always** picks Tea. It deliberately does not upgrade to token
    transport merely because an ambient `FORGEJO_TOKEN` happens to be exported:
    that would bind whatever credential is in the environment to whatever host
    an origin URL named. Token transport is opt-in and host-allowlisted.
    """
    if prefer in ("auto", "tea"):
        return TeaTransport(repo.host)
    if prefer != "token":
        raise WayfinderError(f"unknown transport {prefer!r}")
    allowed = allowlisted_hosts(environ)
    if not allowed:
        raise WayfinderError(
            f"token transport requires an explicit host allowlist in "
            f"{HOST_ALLOWLIST_ENV}; refusing to send a credential to {repo.host!r}"
        )
    if repo.host not in allowed:
        raise WayfinderError(
            f"{repo.host!r} is not in {HOST_ALLOWLIST_ENV}; refusing to send a credential to it"
        )
    token = token_from_environment(environ)
    if not token:
        raise WayfinderError(
            f"no Forgejo token found in {' or '.join(TOKEN_ENV_NAMES)}"
        )
    return TokenTransport(repo.host, token=token)


def resolve_repo(origin: str, chosen: str) -> RepoRef:
    """Resolve the tracker from the origin plus an explicit choice.

    The choice is mandatory. Inferring the tracker from the origin alone is how
    exploratory content ends up on the wrong repository.
    """
    parsed = parse_origin(origin)
    owner, _, repo = chosen.partition("/")
    if not owner or not repo or "/" in repo:
        raise WayfinderError(f"--tracker must be owner/repo, got {chosen!r}")
    return _validated_ref(parsed.host, owner, repo)


def _as_json(value: Any) -> Any:
    if hasattr(value, "__dataclass_fields__"):
        return {k: getattr(value, k) for k in value.__dataclass_fields__}
    return str(value)


def _emit(value: Any) -> None:
    if isinstance(value, Preview):
        print(value.render())
    elif isinstance(value, (dict, list)):
        print(json.dumps(value, indent=2, sort_keys=True, default=_as_json))
    else:
        print(json.dumps(_as_json(value), indent=2, sort_keys=True, default=_as_json))


def _read_file(path: str) -> str:
    with open(path, encoding="utf-8") as handle:
        return handle.read()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Deterministic Forgejo adapter for Wayfinder maps and decision tickets."
    )
    parser.add_argument(
        "--origin", required=True, help="git remote URL of the working repository"
    )
    parser.add_argument(
        "--tracker",
        required=True,
        help="owner/repo of the private tracker (explicit, never inferred)",
    )
    parser.add_argument("--transport", choices=("auto", "tea", "token"), default="auto")
    parser.add_argument(
        "--apply",
        action="store_true",
        help="perform the mutation instead of previewing it",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("check-private", help="verify the tracker is private")

    for name in ("read-map", "list-tickets", "frontier"):
        p = sub.add_parser(name)
        p.add_argument("--map", type=int, required=True)

    creation_help = (
        "the creation identity the preview printed; required with --apply, and "
        "a retry with the same identity converges on the issue the first "
        "attempt made instead of creating a duplicate"
    )
    p = sub.add_parser("create-map")
    p.add_argument("--title", required=True)
    p.add_argument("--managed-file", required=True, help="file holding the managed map region")
    p.add_argument("--creation", help=creation_help)

    p = sub.add_parser("create-ticket")
    p.add_argument("--map", type=int, required=True)
    p.add_argument("--title", required=True)
    p.add_argument("--question-file", required=True)
    p.add_argument("--type", choices=TICKET_TYPES, required=True)
    p.add_argument("--creation", help=creation_help)

    p = sub.add_parser("wire-blocking")
    p.add_argument("--map", type=int, required=True)
    p.add_argument("--blocked", type=int, required=True)
    p.add_argument("--blocked-by", type=int, required=True)

    p = sub.add_parser("claim")
    p.add_argument("--map", type=int, required=True)
    p.add_argument("--ticket", type=int, required=True)
    p.add_argument("--session", required=True)
    p.add_argument("--at", required=True, help="ISO 8601 UTC claim timestamp")
    p.add_argument("--assignee")
    p.add_argument(
        "--operation",
        help="reuse an operation id to retry an interrupted claim idempotently; "
        "omit to mint a fresh one. The id, not the session, is the ownership "
        "token — record the one this prints, because release and resolve need it",
    )

    p = sub.add_parser("release")
    p.add_argument("--map", type=int, required=True)
    p.add_argument("--ticket", type=int, required=True)
    p.add_argument("--session", required=True)
    p.add_argument("--at", required=True, help="ISO 8601 UTC release timestamp")
    p.add_argument(
        "--operation",
        required=True,
        help="the exact claim operation id to release; see `claim-status`. Releasing "
        "on session alone would clear a sibling operation's claim",
    )

    p = sub.add_parser(
        "claim-status", help="report the current claim on a ticket, with its operation id"
    )
    p.add_argument("--map", type=int, required=True)
    p.add_argument("--ticket", type=int, required=True)

    p = sub.add_parser("resolve")
    p.add_argument("--map", type=int, required=True)
    p.add_argument("--ticket", type=int, required=True)
    p.add_argument(
        "--session",
        required=True,
        help="the claiming session; only the current claimant may resolve",
    )
    p.add_argument("--answer-file", required=True)
    p.add_argument("--index-line", required=True)
    p.add_argument(
        "--operation",
        required=True,
        help="the exact claim operation id held on this ticket; see `claim-status`",
    )
    p.add_argument(
        "--at",
        default="",
        help="ISO 8601 UTC timestamp; required with --apply (the index record "
        "carries it)",
    )

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        repo = resolve_repo(args.origin, args.tracker)
        tracker = WayfinderTracker(build_transport(repo, prefer=args.transport), repo)

        if args.command == "check-private":
            tracker.require_private()
            _emit({"repo": repo.slug, "private": True})
        elif args.command == "read-map":
            _emit(tracker.read_map(args.map))
        elif args.command == "list-tickets":
            _emit([_as_json(t) for t in tracker.list_tickets(args.map)])
        elif args.command == "frontier":
            _emit([_as_json(t) for t in tracker.frontier(args.map)])
        elif args.command == "create-map":
            _emit(
                tracker.create_map(
                    title=args.title,
                    managed=_read_file(args.managed_file),
                    creation=args.creation,
                    apply=args.apply,
                )
            )
        elif args.command == "create-ticket":
            _emit(
                tracker.create_ticket(
                    map_number=args.map,
                    title=args.title,
                    question=_read_file(args.question_file),
                    ticket_type=args.type,
                    creation=args.creation,
                    apply=args.apply,
                )
            )
        elif args.command == "wire-blocking":
            _emit(
                tracker.wire_blocking(
                    map_number=args.map,
                    blocked=args.blocked,
                    blocked_by=args.blocked_by,
                    apply=args.apply,
                )
            )
        elif args.command == "claim":
            _emit(
                tracker.claim(
                    map_number=args.map,
                    number=args.ticket,
                    session=args.session,
                    claimed_at=args.at,
                    assignee=args.assignee,
                    operation=args.operation,
                    apply=args.apply,
                )
            )
        elif args.command == "release":
            _emit(
                tracker.release(
                    map_number=args.map,
                    number=args.ticket,
                    session=args.session,
                    released_at=args.at,
                    operation=args.operation,
                    apply=args.apply,
                )
            )
        elif args.command == "resolve":
            _emit(
                tracker.resolve_ticket(
                    map_number=args.map,
                    number=args.ticket,
                    session=args.session,
                    answer=_read_file(args.answer_file),
                    map_index_line=args.index_line,
                    claim_operation=args.operation,
                    at=args.at,
                    apply=args.apply,
                )
            )
        elif args.command == "claim-status":
            tracker.preflight_ticket(args.ticket, args.map)
            records = tracker.claim_records(args.ticket)
            holder = active_claim(records)
            queued = [
                record
                for record in records
                if record.kind == "claim"
                and acquisition_is_active(
                    records,
                    hold="claim",
                    drop="release",
                    identity=acquisition_identity(record),
                )
                and (holder is None or record.comment_id != holder.comment_id)
            ]
            _emit(
                {
                    "map": args.map,
                    "ticket": args.ticket,
                    "claimed": holder is not None,
                    "holder": tracker.holder_view(holder) if holder else None,
                    "recovery": (
                        tracker.claim_recovery_command(
                            args.map, args.ticket, holder.session, holder.operation
                        ).strip("`")
                        if holder
                        else ""
                    ),
                    # A queued claim takes the ticket as soon as the holder
                    # releases, so recovery has to be able to see it.
                    "queued": [
                        {
                            **tracker.holder_view(record),
                            "recovery": tracker.claim_recovery_command(
                                args.map,
                                args.ticket,
                                record.session,
                                record.operation,
                            ).strip("`"),
                        }
                        for record in queued
                    ],
                }
            )
    except WayfinderError as error:
        print(f"REFUSED: {error}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
