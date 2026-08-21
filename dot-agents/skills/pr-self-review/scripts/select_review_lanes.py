#!/usr/bin/env python3
"""Deterministic review-lane selection for `pr-self-review` and `code-review`.

Standards and Spec **always** run. Risk runs when the change plausibly touches
something that can hurt: authentication, secrets, private data, untrusted
input, network behavior, filesystem paths and permissions, persistence and
migrations, queues and retries, concurrency, deployment, package publication,
agent permissions, memory retention, or unattended mutation.

Two rules make this worth being code rather than a judgment call:

* **Standards and Spec cannot be suppressed.** No input turns them off.
* **Ambiguity includes Risk, never excludes it.** An unrecognized signal that
  looks security-adjacent selects the lane. A false Risk lane costs one child
  agent; a missed one ships the defect.

CairnOS always selects Risk regardless of what the diff touches: it is Bryan's
own operating-system work, where a change that looks cosmetic can still alter
boot, permissions, or update behavior.

Usage:
    select_review_lanes.py --repo owner/repo --changed-files-from -
    select_review_lanes.py --repo owner/repo --changed-file src/auth.py [...]
    select_review_lanes.py --repo owner/repo --changed-files-from - --json
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import PurePosixPath
from typing import Iterable, Sequence

ALWAYS_LANES = ("standards", "spec")
RISK = "risk"

# Repositories where Risk is unconditional, matched on the repository name so
# `bryan/cairn-os`, `cairn-os`, and a fork all resolve the same way.
ALWAYS_RISK_REPOS = ("cairn-os", "cairnos")

# Path signals. Each entry is (compiled pattern, human reason). Patterns match
# anywhere in the POSIX-normalized path, case-insensitively.
_PATH_SIGNALS: tuple[tuple[str, str], ...] = (
    (r"(^|/)\.github/workflows/", "CI workflow definition"),
    (r"(^|/)\.forgejo/", "forge automation definition"),
    (r"(^|/)(dockerfile|containerfile)", "container image definition"),
    (r"(^|/)docker-compose[^/]*\.ya?ml$", "container orchestration"),
    (r"(^|/)(deploy|deployment|release|promote|rollback)[^/]*", "deployment or release path"),
    (r"(^|/)(migrations?|alembic|schema)(/|$)", "persistence migration"),
    (r"\.sql$", "SQL"),
    (r"(^|/)(auth|authn|authz|oauth|session|login|permission|rbac|acl)[^/]*", "authentication or authorization"),
    (r"(^|/)(secret|credential|token|keychain|vault)[^/]*", "secret or credential handling"),
    (r"\.(pem|key|crt|p12|jks)$", "key material"),
    (r"(^|/)(crypto|cipher|hash|signing|signature)[^/]*", "cryptography"),
    (r"(^|/)(queue|worker|job|task|cron|schedul)[^/]*", "queue, worker, or scheduler"),
    (r"(^|/)(webhook|callback|redirect)[^/]*", "network callback or redirect"),
    (r"(^|/)(hooks?)/", "hook that runs on someone else's action"),
    (r"(^|/)(install|setup|bootstrap|provision)[^/]*", "install or provisioning path"),
    (r"(^|/)(package|pyproject|cargo|go)\.(json|toml|mod)$", "package manifest"),
    (r"(^|/)\.npmrc$|(^|/)\.pypirc$", "package publication configuration"),
    (r"(^|/)(agents?|skills?)/.*\.(md|py|sh)$", "agent permission or unattended behavior"),
    # Anything under hermes/ is scheduler-adjacent: cron definitions, prompts,
    # and scripts that run unattended with real credentials and delivery.
    (r"(^|/)hermes/", "unattended scheduler asset"),
    (r"(^|/)(memory|memories|recall|hindsight)[^/]*", "memory retention"),
    (r"(^|/)(upload|download|tmp|temp)[^/]*", "filesystem path handling"),
    (r"(^|/)(cors|csp|headers?|middleware)[^/]*", "request-handling policy"),
    (r"(^|/)(lock|mutex|semaphore|concurren|atomic|race)[^/]*", "concurrency control"),
    (r"\.(env|envrc)$|(^|/)\.env\.", "environment configuration"),
    (r"(^|/)(sudo|systemd|launchd|pam|udev)[^/]*", "privileged system configuration"),
    (r"(^|/)(nix|nixos)/.*\.nix$|\.nix$", "declarative system configuration"),
)

# Compiled once; the reason travels with the pattern so output explains itself.
PATH_SIGNALS = tuple((re.compile(p, re.IGNORECASE), reason) for p, reason in _PATH_SIGNALS)

# A path that looks security-adjacent but matched nothing above still selects
# Risk. These are the "unknown or ambiguous" cases the policy resolves toward
# inclusion.
AMBIGUOUS_HINTS = re.compile(
    r"(secur|privile|sanitiz|escap|inject|trust|verif|validat|expos|leak|"
    r"privac|personal|pii|audit|policy|guard)",
    re.IGNORECASE,
)

# Content signals, matched against the diff's ADDED lines only.
#
# Paths alone are not enough: `src/parser.py` is a neutral filename that handles
# untrusted input, `utils.go` can grow a subprocess call, and a rename can move
# risky code out of a risky-looking directory. So the classifier reads what the
# diff actually adds.
#
# Chosen to indicate a risk *area* rather than to match all code. Deliberately
# excluded: bare `open(`, `Path(`, and `await`, which appear in nearly every
# diff and would make Risk unconditional — an always-on lane carries no signal.
_CONTENT_SIGNALS: tuple[tuple[str, str], ...] = (
    # Stems (leading boundary only) and whole words (both boundaries) are kept
    # apart deliberately: `\bauthenticat\b` can never match "authentication",
    # because the char after the stem is a word char.
    (r"(\bauthenticat|\bauthoriz|\bcredential|\bpermission"
     r"|\b(login|logout|password|passwd|bearer|jwt|oauth)\b"
     r"|api[_-]?key|access[_-]?token|refresh[_-]?token|set[_-]?cookie|session[_-]?id)",
     "authentication or credential handling"),
    (r"\b(json\.loads?|yaml\.(safe_)?load|pickle\.loads?|marshal\.loads?|unmarshal|"
     r"ElementTree|xml\.|csv\.reader|urlencode|parse_qs|deserializ|\bdecode\()",
     "parsing or deserializing external data"),
    (r"(request\.(body|query|params|args|form|json|headers|cookies)|req\.(body|query|params)|"
     r"\bsys\.argv|\binput\(|os\.environ|getenv|\bstdin\b)",
     "untrusted input"),
    (r"(subprocess|os\.system|os\.popen|shell\s*=\s*True|exec\(|eval\(|Popen|"
     r"child_process|execSync|`\$\()",
     "process execution"),
    (r"(innerHTML|dangerouslySetInnerHTML|document\.write|\bmark_safe\b|\|\s*safe\b)",
     "unescaped markup"),
    (r"(urlopen|urllib\.request|requests\.(get|post|put|patch|delete)|httpx\.|axios|"
     r"\bfetch\(|http\.Client|net/http)",
     "outbound network call"),
    (r"\b(redirect|Location:|allow_redirects|follow_redirects|CORS|Access-Control-Allow)\b",
     "redirect or cross-origin policy"),
    (r"\b(chmod|chown|umask|0o[0-7]{3}|shutil\.rmtree|os\.unlink|os\.remove|rmdir|"
     r"mkdtemp|NamedTemporaryFile|/tmp/|realpath|expanduser)\b",
     "filesystem path or permission handling"),
    (r"(CREATE TABLE|ALTER TABLE|DROP TABLE|DELETE FROM|INSERT INTO|UPDATE\s+\w+\s+SET|"
     r"\balembic\b|add_column|drop_column|\bmigrat)",
     "persistence or migration"),
    (r"\b(retry|retries|backoff|enqueue|dequeue|celery|sidekiq|\backs?\b|visibility_timeout|"
     r"dead[_-]?letter)\b",
     "queue or retry behavior"),
    (r"(\b(threading|multiprocessing|semaphore|mutex|atomic|goroutine|race)\b"
     r"|asyncio\.(gather|create_task)|\bR?Lock\(|sync\.(Mutex|WaitGroup))",
     "concurrency control"),
    (r"\b(kubectl|helm|terraform|systemctl|launchctl|docker\s+(build|push)|deploy|rollback|"
     r"promote)\b",
     "deployment, promotion, or rollback"),
    (r"(npm publish|yarn publish|twine upload|cargo publish|gh release create|"
     r"\bpypi\b|registry\.npmjs)",
     "package publication"),
    (r"(enabledToolsets|allowedTools|bypassPermissions|--yolo|--dangerously|\bsudo\b|"
     r"permission_mode|disable-model-invocation)",
     "agent permissions or unattended capability"),
    (r"\b(hindsight|memory_store|remember\(|recall\(|embedding|vector_store)\b",
     "memory retention"),
    (r"(crontab|cron\.|schedule\(|--apply\b|force[_-]?push|git\s+push|autocommit|"
     r"monitor_script)",
     "unattended mutation"),
    (r"\b(hashlib|hmac|bcrypt|scrypt|argon2|pbkdf2|AES|RSA|cipher|nacl|"
     r"secrets\.(token|choice)|os\.urandom|random\.)\b",
     "cryptography or randomness"),
)
CONTENT_SIGNALS = tuple(
    (re.compile(p, re.IGNORECASE), reason) for p, reason in _CONTENT_SIGNALS
)

# Content that reads as security-adjacent but matched no specific signal above.
# Fail closed: select Risk and label the reason as unknown.
AMBIGUOUS_CONTENT = re.compile(
    r"(secur|privileg|sanitiz|escap|inject|untrusted|tamper|spoof|forge|exploit|"
    r"vulnerab|attack|malicious|leak|exfiltrat|pii|gdpr|encrypt|decrypt|signature|"
    r"nonce|salt|allowlist|denylist|blocklist)",
    re.IGNORECASE,
)

# Only added lines matter. A removed line cannot introduce behavior, and the
# `+++ b/path` header is not code.
ADDED_LINE = re.compile(r"\A\+(?!\+\+)")


@dataclass
class Selection:
    """Which lanes to run, and why each was selected."""

    lanes: list[str] = field(default_factory=list)
    reasons: dict[str, list[str]] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)

    @property
    def risk_selected(self) -> bool:
        return RISK in self.lanes

    def to_dict(self) -> dict:
        return {"lanes": self.lanes, "reasons": self.reasons, "notes": self.notes}

    def render(self) -> str:
        lines = [f"lanes: {', '.join(self.lanes)}"]
        for lane in self.lanes:
            for reason in self.reasons.get(lane, []):
                lines.append(f"  {lane}: {reason}")
        for note in self.notes:
            lines.append(f"  note: {note}")
        return "\n".join(lines)


def repository_always_risk(repo: str) -> bool:
    """True when the repository itself makes Risk unconditional."""
    name = (repo or "").strip().rstrip("/").split("/")[-1].lower()
    normalized = name.replace("_", "-")
    return normalized in ALWAYS_RISK_REPOS or normalized.replace("-", "") in ALWAYS_RISK_REPOS


def risk_reasons(changed_files: Iterable[str]) -> list[str]:
    """Every distinct reason the diff selects Risk, in a stable order.

    Deduplicated by reason rather than by file: three auth files are one
    reason to run the lane, not three.
    """
    found: dict[str, str] = {}
    for raw in changed_files:
        path = str(PurePosixPath((raw or "").strip().replace("\\", "/")))
        if not path or path == ".":
            continue
        matched = False
        for pattern, reason in PATH_SIGNALS:
            if pattern.search(path):
                found.setdefault(reason, path)
                matched = True
        if not matched and AMBIGUOUS_HINTS.search(path):
            found.setdefault("ambiguous security-adjacent path", path)
    return [f"{reason} ({example})" for reason, example in sorted(found.items())]


NEW_HEADER = re.compile(r"\A\+\+\+ (?:b/)?(?P<path>.+?)\s*\Z")
OLD_HEADER = re.compile(r"\A--- (?:a/)?(?P<path>.+?)\s*\Z")
DEV_NULL = "/dev/null"

# THE authority command for touched paths. One literal, quoted verbatim in
# `code-review`, `pr-self-review`, this module's `--help`, and the tests, so
# every caller produces the same inventory:
#
#   -z   NUL-separated, so an unusual filename arrives verbatim rather than as
#        a quoted approximation the parser would have to unescape.
#   -M   detect renames. Without it a content-identical rename is an add plus a
#        delete, and the deleted path's risk is attributed to the wrong file.
#   -C --find-copies-harder
#        detect copies, *including* from a file the commit did not otherwise
#        touch. Plain -C only looks at modified files, so copying a risky
#        untouched source emits A and the risky source is never classified.
#   {base}...HEAD  merge-base range: the candidate's own work, not main's.
#   --   end of options, so a branch or path named like a flag cannot inject one.
NAME_STATUS_COMMAND = (
    "git diff --name-status -z -M -C --find-copies-harder {base}...HEAD --"
)
UNIFIED_DIFF_COMMAND = "git diff -M -C --find-copies-harder {base}...HEAD --"

# `git diff --name-status -z` statuses. R and C carry a similarity score and
# two paths; the rest carry one.
_TWO_PATH_STATUSES = ("R", "C")
_ONE_PATH_STATUSES = ("A", "D", "M", "T", "U", "X", "B")

# Strict status grammar. A one-path status is exactly one letter — `MM` is
# porcelain-status syntax, not name-status syntax, and accepting it would mean
# guessing. A rename or copy is exactly the letter plus a three-digit
# similarity score in 000–100; `R1000` and `R101` are not scores Git emits, and
# a parser that shrugs at them is a parser that will shrug at truncation too.
_ONE_PATH_RE = re.compile(r"\A[" + "".join(_ONE_PATH_STATUSES) + r"]\Z")
_SCORED_RE = re.compile(r"\A(?P<kind>[RC])(?P<score>[0-9]{3})\Z")

# A path is data, not a command, but a control character in one means the
# inventory is not what it appears to be. Refuse rather than classify it.
# Every C0 control plus DEL, including tab: `-z` delivers paths verbatim, so a
# tab *can* legally appear in a filename — but a control character in a path is
# far more likely a mangled or adversarial stream than a real file, and a path
# this classifier cannot render unambiguously is a path it must not classify.
_CONTROL_CHARS = re.compile(r"[\x00-\x1f\x7f]")


@dataclass(frozen=True)
class Change:
    """One entry from Git's name-status inventory."""

    status: str
    paths: tuple[str, ...]

    @property
    def kind(self) -> str:
        return self.status[0]


def parse_name_status(data: str) -> list[Change]:
    """Parse `git diff --name-status -z` — the authority on which paths moved.

    Unified `---`/`+++` headers cannot answer this question:

    * a **content-identical rename** shows as `--- /dev/null` plus `+++ b/new`,
      so the *old* path is entirely absent. Renaming `src/auth/session.py` to
      `src/util/session.py` therefore hides the auth path that should select
      Risk;
    * a **binary delete** produces no `---`/`+++` headers at all, only a
      `Binary files … differ` line, so the deleted path is invisible.

    `-z` also removes the quoting Git otherwise applies to unusual filenames,
    so a path containing a space, quote, or semicolon arrives verbatim instead
    of as an escaped approximation. (Control characters — tab included — still
    arrive verbatim and are then refused below.)

    Parsing is strict, and deliberately so: this inventory decides whether the
    Risk lane runs, and a tolerated malformation is a silently narrowed review.
    Every rejection below is a case where the alternative is a guess —
    a suffixed status, an impossible similarity score, a leading empty field,
    a truncated tail, an empty path, a control character, or bytes that are not
    valid UTF-8.
    """
    fields = data.split("\0")
    if fields and fields[-1] == "":
        fields.pop()
    changes: list[Change] = []
    index = 0
    while index < len(fields):
        status = fields[index]
        index += 1
        if not status:
            # Not "skip the blank": an empty field where a status belongs means
            # the stream is misaligned, and the paths after it are unreliable.
            raise ValueError(
                f"empty status field at position {index - 1} in the name-status "
                "inventory; refusing to classify a misaligned stream"
            )
        # The exact bytes, no normalization first. Git emits `M` or `R087`;
        # anything else — including a whitespace-padded mutation like ` M` or
        # `M\n` — is not this protocol, and stripping it before the exact match
        # would launder a mutated field into a valid-looking status.
        scored = _SCORED_RE.match(status)
        if scored:
            if int(scored.group("score")) > 100:
                raise ValueError(
                    f"impossible similarity score in name-status entry {status!r}"
                )
            wanted = 2
        elif _ONE_PATH_RE.match(status):
            wanted = 1
        else:
            raise ValueError(f"unrecognized name-status entry: {status!r}")
        if index + wanted > len(fields):
            raise ValueError(
                f"truncated name-status inventory: {status!r} needs {wanted} path(s)"
            )
        paths = tuple(fields[index : index + wanted])
        index += wanted
        for path in paths:
            if not path:
                raise ValueError(f"empty path in name-status entry {status!r}")
            if _CONTROL_CHARS.search(path):
                raise ValueError(
                    f"refusing a path containing a control character: {path!r}"
                )
        changes.append(Change(status=status, paths=paths))
    return changes


def changed_files_from_name_status(changes: Iterable[Change]) -> list[str]:
    """Every path the inventory touches, both sides of a rename or copy.

    Both sides matter: the source may carry a path signal the destination does
    not, which is exactly the rename that would otherwise launder risky code
    out of a risky-looking directory.

    First-seen order, duplicates collapsed — so a path appearing as both a
    rename source and a later modification counts once and cannot double-count.
    """
    paths: list[str] = []
    for change in changes:
        for path in change.paths:
            if path != DEV_NULL and path not in paths:
                paths.append(path)
    return paths


def changed_files_from_diff(diff: Iterable[str]) -> list[str]:
    """Paths named by a unified diff's headers.

    **Weaker than `parse_name_status` and kept only as a fallback.** It cannot
    see a content-identical rename's source or a binary deletion at all; see
    `parse_name_status` for why. Prefer the name-status inventory whenever the
    caller can produce one.
    """
    paths: list[str] = []
    for line in diff:
        for pattern in (OLD_HEADER, NEW_HEADER):
            match = pattern.match(line)
            if not match:
                continue
            path = match.group("path")
            if path != DEV_NULL and path not in paths:
                paths.append(path)
    return paths


# Documentation extensions. A line here can still select Risk — a skill body
# that grants a toolset is a real permission change — but the reason says it
# came from prose, so a reviewer can see that Risk was selected on writing
# *about* security rather than on code that *does* it.
PROSE_SUFFIXES = (".md", ".markdown", ".rst", ".txt", ".adoc")


def added_lines(diff: Iterable[str]) -> list[str]:
    """The diff's added lines, without the `+` and without file headers."""
    return [line for _, line in added_lines_with_paths(diff)]


def added_lines_with_paths(diff: Iterable[str]) -> list[tuple[str, str]]:
    """`(path, added line)` pairs, so a reason can name where it came from."""
    pairs: list[tuple[str, str]] = []
    current = ""
    for line in diff:
        header = NEW_HEADER.match(line)
        if header:
            # Added lines belong to the *new* path; a deletion has none.
            path = header.group("path")
            current = "" if path == DEV_NULL else path
            continue
        if ADDED_LINE.match(line):
            pairs.append((current, line[1:]))
    return pairs


def _is_prose(path: str) -> bool:
    return path.lower().endswith(PROSE_SUFFIXES)


def content_risk_reasons(diff: Iterable[str]) -> list[str]:
    """Every distinct reason the diff's *content* selects Risk.

    Deduplicated by reason and capped at one example each, so the output stays a
    short explanation rather than a transcript of the diff. A reason found only
    in documentation is marked, because "this diff discusses authentication" and
    "this diff changes authentication" deserve different attention even though
    both select the lane.
    """
    found: dict[str, tuple[str, str]] = {}

    def record(reason: str, path: str, line: str) -> None:
        existing = found.get(reason)
        # A code example outranks a prose one for the same reason.
        if existing is None or (_is_prose(existing[0]) and not _is_prose(path)):
            found[reason] = (path, line[:80])

    for path, line in added_lines_with_paths(diff):
        stripped = line.strip()
        if not stripped or stripped.startswith(("#", "//", "*")):
            # Comments and blank lines describe code; they do not add behavior.
            continue
        matched = False
        for pattern, reason in CONTENT_SIGNALS:
            if pattern.search(stripped):
                record(reason, path, stripped)
                matched = True
        if not matched and AMBIGUOUS_CONTENT.search(stripped):
            record("unrecognized security-adjacent content", path, stripped)

    reasons = []
    for reason, (path, example) in sorted(found.items()):
        where = " in prose" if _is_prose(path) else ""
        reasons.append(f"{reason}{where} ({path or 'unknown file'}: {example!r})")
    return reasons


def select_lanes(
    repo: str,
    changed_files: Sequence[str] | None = None,
    diff: Sequence[str] | None = None,
    name_status: Sequence[Change] | None = None,
) -> Selection:
    """Select review lanes. Standards and Spec are never omitted.

    Two inputs with two distinct jobs, and conflating them is what let a
    renamed or binary-deleted risky file slip through:

    * `name_status` is the **authority on which paths the change touches**. It
      sees a content-identical rename's source and a binary deletion, neither of
      which appears in a unified diff.
    * `diff` is the **content-signal input only** — its added lines say what the
      change does, never which paths exist.

    `changed_files` remains accepted for callers that have only a path list.
    Whatever authority was used is recorded in `notes`, because a weaker one
    must not read like a complete sweep.
    """
    selection = Selection(lanes=list(ALWAYS_LANES))
    selection.reasons["standards"] = ["always runs"]
    selection.reasons["spec"] = ["always runs"]

    if name_status is not None:
        paths = changed_files_from_name_status(name_status)
        if changed_files:
            extra = [p for p in changed_files if p not in paths]
            paths.extend(extra)
    elif changed_files:
        paths = list(changed_files)
        selection.notes.append(
            "paths came from a caller-supplied list, not `git diff --name-status`: "
            "a content-identical rename's source or a binary deletion may be missing"
        )
    elif diff is not None:
        paths = changed_files_from_diff(diff)
        selection.notes.append(
            "paths were derived from unified diff headers, which cannot see a "
            "content-identical rename's source, a copy from an untouched source, "
            "or a binary deletion — supply `" + NAME_STATUS_COMMAND + "` for a "
            "complete inventory"
        )
    else:
        paths = []

    reasons: list[str] = []
    if repository_always_risk(repo):
        reasons.append(f"{repo} always runs Risk regardless of changed paths")
    reasons.extend(risk_reasons(paths))
    if diff is None:
        selection.notes.append(
            "no diff supplied: content signals were not evaluated, so this "
            "selection is weaker than a full sweep"
        )
    else:
        content = content_risk_reasons(diff)
        reasons.extend(content)
        if content and all(" in prose (" in reason for reason in content):
            selection.notes.append(
                "every content signal came from documentation, not executable "
                "lines — Risk still runs, but weigh it accordingly"
            )

    if reasons:
        selection.lanes.append(RISK)
        selection.reasons[RISK] = reasons
    return selection


def read_raw(source: str) -> str:
    """Read a source verbatim — NUL-separated data must not be line-split.

    Decoding is strict. Git stores paths as bytes, so an inventory *can* carry
    something that is not valid UTF-8; substituting replacement characters
    would silently change which file a path names, and a mangled path is
    matched against the risk patterns as if it were real. Refuse instead, and
    say which source was undecodable.
    """
    if source == "-":
        raw = getattr(sys.stdin, "buffer", None)
        if raw is None:
            # A text-only stdin (a test harness, a wrapper) has already decoded;
            # trust it rather than refusing to run.
            return sys.stdin.read()
        data = raw.read()
    else:
        with open(source, "rb") as handle:
            data = handle.read()
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError as error:
        raise ValueError(
            f"{source!r} is not valid UTF-8 ({error}); refusing to classify paths "
            "decoded with substitutions"
        ) from error


def read_lines(source: str) -> list[str]:
    return read_raw(source).splitlines()


def read_changed_files(source: str) -> list[str]:
    return [line.strip() for line in read_lines(source) if line.strip()]


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Select review lanes for a diff.",
        epilog=(
            "Produce the two inputs with exactly these commands:\n"
            f"  {NAME_STATUS_COMMAND}   > name-status.z\n"
            f"  {UNIFIED_DIFF_COMMAND}  > diff.patch\n"
            "The name-status inventory is the path authority; the unified diff is "
            "a content signal only."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--repo", required=True, help="owner/repo of the reviewed repository")
    parser.add_argument(
        "--changed-files-from",
        help="file containing one changed path per line, or - for stdin",
    )
    parser.add_argument(
        "--changed-file", action="append", default=[], help="a changed path (repeatable)"
    )
    parser.add_argument(
        "--name-status-from",
        help=(
            "file containing the output of exactly `" + NAME_STATUS_COMMAND + "`, "
            "or - for stdin. This is the authority on which paths the change "
            "touches: it sees a content-identical rename's source, a copy from an "
            "untouched source, and a binary deletion, none of which appears in a "
            "unified diff."
        ),
    )
    parser.add_argument(
        "--diff-from",
        help=(
            "file containing the unified diff, or - for stdin; its added lines are "
            "inspected for content signals and every touched path (added, modified, "
            "renamed, or deleted) is classified. Omit to classify on paths alone, "
            "which is weaker and is reported as such."
        ),
    )
    parser.add_argument("--json", action="store_true", help="emit JSON instead of text")
    args = parser.parse_args(argv)

    stdin_readers = [
        name
        for name, value in (
            ("--changed-files-from", args.changed_files_from),
            ("--diff-from", args.diff_from),
            ("--name-status-from", args.name_status_from),
        )
        if value == "-"
    ]
    if len(stdin_readers) > 1:
        parser.error(f"only one of {', '.join(stdin_readers)} may read stdin")

    changed = list(args.changed_file)
    if args.changed_files_from:
        changed += read_changed_files(args.changed_files_from)

    diff: list[str] | None = None
    if args.diff_from:
        diff = read_lines(args.diff_from)

    name_status: list[Change] | None = None
    if args.name_status_from:
        try:
            name_status = parse_name_status(read_raw(args.name_status_from))
        except (ValueError, OSError) as error:
            parser.error(f"unusable name-status inventory: {error}")

    selection = select_lanes(args.repo, changed, diff, name_status)
    print(json.dumps(selection.to_dict(), indent=2, sort_keys=True) if args.json else selection.render())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
