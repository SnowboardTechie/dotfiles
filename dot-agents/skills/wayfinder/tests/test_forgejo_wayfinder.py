#!/usr/bin/env python3
"""Offline tests for the Forgejo Wayfinder adapter.

Every test runs against `FakeForgejo`, an in-memory tracker that mimics the
endpoints the adapter actually calls, including the two behaviors that made
earlier versions wrong: `CreateIssueOption.labels` takes numeric ids, and a
`labels=` query naming an unknown label returns every issue rather than none.

Nothing here touches the network, and no test can be made to pass by reaching
a real tracker.

Run: python3 -m unittest dot-agents/skills/wayfinder/tests/test_forgejo_wayfinder.py
"""

from __future__ import annotations

import contextlib
import hashlib
import importlib.util
import io
import json
import sys
import unittest
from pathlib import Path
from typing import Any

MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "forgejo_wayfinder.py"
SPEC = importlib.util.spec_from_file_location("forgejo_wayfinder", MODULE_PATH)
assert SPEC and SPEC.loader
WF = importlib.util.module_from_spec(SPEC)
# Register before exec: @dataclass resolves annotations through
# sys.modules[cls.__module__], which is None for an unregistered module.
sys.modules["forgejo_wayfinder"] = WF
SPEC.loader.exec_module(WF)

REPO = WF.RepoRef(host="git.example.test", owner="bryan", repo="workspace")
T0 = "2026-08-19T09:00:00Z"
T1 = "2026-08-19T10:00:00Z"
T2 = "2026-08-19T11:00:00Z"


def claim_id(operation: str, session: str) -> tuple[str, ...]:
    """The claim identity a test means: `(operation, session)`."""
    return WF.claim_identity(op_for(operation), session)


def op_for(name: str) -> str:
    """A stable, injected operation id, derived from a readable name.

    Operation ids are the ownership token, and the adapter mints them from
    `secrets`. Tests must be deterministic, so every test injects one — and
    deriving it from a name keeps "the same operation" and "a different
    operation" legible in the assertions rather than being 32 hex characters
    the reader has to diff by eye.
    """
    return hashlib.sha256(name.encode("utf-8")).hexdigest()[:32]


def ticket_body(question: str, map_number: int, ticket_type: str = "grilling") -> str:
    return (
        f"## Question\n\n{question}\n\n"
        + WF.render_ticket_metadata(map_number, ticket_type)
        + "\n"
    )


class FakeForgejo(WF.Transport):
    """In-memory stand-in for the endpoints the adapter uses."""

    def __init__(self, *, private: bool = True, labels: dict[str, int] | None = None) -> None:
        self.private = private
        self.issues: dict[int, dict[str, Any]] = {}
        self.dependencies: dict[int, list[int]] = {}
        self.comments: dict[int, list[dict]] = {}
        self.labels: dict[str, int] = dict(labels if labels is not None else {})
        self.label_meta: dict[str, dict[str, str]] = {}
        # Store a wrong colour/description/id on creation, to prove an exact
        # readback catches a create the server mangled.
        self.mangle_label: dict[str, dict] = {}
        # The same for issue creation: a real server can store a title, body,
        # or label set that is not what was sent, and an exact readback is the
        # only thing that notices.
        self.mangle_issue: dict = {}
        # Keep pre-existing assignees instead of replacing them, the way a
        # partially applied PATCH would.
        self.keep_assignees = False
        # Append something to a patched body, so "the decision line is there"
        # is not mistaken for "the body is what we wrote".
        self.mangle_patch_body = ""
        # The same for a stored comment: the API echoes what was sent while the
        # server stored something else, and only an exact readback notices.
        self.mangle_comment_body = ""
        self.calls: list[tuple[str, str]] = []
        self._clock = 0
        self._next_number = 1
        self._next_comment_id = 1000
        self._next_label_id = 1
        # (issue, nth GET) -> callback, fired once just before that GET
        # returns, to simulate another session writing between our reads.
        self.on_get: dict[tuple[int, int], Any] = {}
        self._gets: dict[int, int] = {}
        # Raise on the Nth matching write, to prove a retry converges.
        self.fail_on: dict[str, int] = {}
        self._write_counts: dict[str, int] = {}
        # Tags whose writes are *acknowledged but not persisted*. A 2xx is not
        # proof of storage: a proxy, a retry layer, or a half-applied API call
        # can all answer cheerfully while nothing changed. Every guarded write
        # must catch this at readback rather than reporting success.
        self.swallow: set[str] = set()

    # -- helpers used by tests ------------------------------------------

    def _stamp(self) -> str:
        self._clock += 1
        return f"2026-08-19T00:00:{self._clock:02d}Z"

    def add_label(self, name: str, definition: dict | None = None) -> int:
        if name not in self.labels:
            self.labels[name] = self._next_label_id
            self._next_label_id += 1
        # Colour and description are part of what an exact readback checks, so
        # the fake stores what a create supplied — and, for a label seeded by a
        # test, whatever the adapter's own definition says.
        declared = definition or WF.LABEL_DEFINITIONS.get(name) or {}
        self.label_meta.setdefault(
            name,
            {
                "color": str(declared.get("color", "#000000")),
                "description": str(declared.get("description", "")),
            },
        )
        return self.labels[name]

    def add_issue(
        self,
        *,
        title: str,
        body: str,
        labels: list[str],
        state: str = "open",
        number: int | None = None,
    ) -> int:
        num = number if number is not None else self._next_number
        self._next_number = max(self._next_number, num + 1)
        self.issues[num] = {
            "number": num,
            "title": title,
            "body": body,
            "state": state,
            "labels": [{"name": name, "id": self.add_label(name)} for name in labels],
            "assignees": [],
            "updated_at": self._stamp(),
            "html_url": f"https://{REPO.host}/{REPO.slug}/issues/{num}",
        }
        return num

    def add_comment(self, number: int, body: str) -> int:
        cid = self._next_comment_id
        self._next_comment_id += 1
        self.comments.setdefault(number, []).append(
            {"id": cid, "body": body, "created_at": self._stamp()}
        )
        return cid

    def _maybe_fail(self, tag: str) -> None:
        limit = self.fail_on.get(tag)
        if limit is None:
            return
        self._write_counts[tag] = self._write_counts.get(tag, 0) + 1
        if self._write_counts[tag] >= limit:
            raise WF.WayfinderError(f"injected failure at {tag}")

    # -- transport -------------------------------------------------------

    def request(self, method: str, path: str, payload: dict | None = None):
        method = method.upper()
        self.calls.append((method, path))
        base = REPO.api_base

        if method == "GET" and path == base:
            return 200, {"full_name": REPO.slug, "private": self.private}

        if path.startswith(f"{base}/labels"):
            if method == "GET":
                query = _query(path)
                page, limit = int(query.get("page", "1")), int(query.get("limit", "50"))
                rows = [
                    {
                        "id": i,
                        "name": n,
                        "color": self.label_meta.get(n, {}).get("color", "#000000"),
                        "description": self.label_meta.get(n, {}).get("description", ""),
                    }
                    for n, i in sorted(self.labels.items())
                ]
                start = (page - 1) * limit
                return 200, rows[start : start + limit]
            if method == "POST":
                self._maybe_fail("label")
                name = payload["name"]
                if "label" in self.swallow:
                    return 201, {"id": 999, "name": name}
                stored = dict(payload)
                stored.update(self.mangle_label.get(name, {}))
                label_id = self.add_label(name, stored)
                self.label_meta[name] = {
                    "color": str(stored.get("color", "")),
                    "description": str(stored.get("description", "")),
                }
                reported = self.mangle_label.get(name, {}).get("reported_id", label_id)
                return 201, {"id": reported, "name": name}

        if method == "GET" and path.startswith(f"{base}/issues?"):
            # Forgejo returns *every* issue when the `labels=` filter names a
            # label the repository does not have, so the fake does too — the
            # adapter must not rely on the filter narrowing anything.
            query = _query(path)
            limit, page = int(query.get("limit", "50")), int(query.get("page", "1"))
            ordered = sorted(self.issues.values(), key=lambda i: i["number"])
            start = (page - 1) * limit
            return 200, [dict(issue) for issue in ordered[start : start + limit]]

        if "/comments" in path:
            number = int(path.split("/issues/")[1].split("/")[0])
            if method == "GET":
                query = _query(path)
                limit, page = int(query.get("limit", "50")), int(query.get("page", "1"))
                rows = sorted(self.comments.get(number, []), key=lambda c: c["id"])
                start = (page - 1) * limit
                return 200, [dict(c) for c in rows[start : start + limit]]
            if method == "POST":
                self._maybe_fail("comment")
                for kind in ("claim", "release", "resolution", "index"):
                    if f"wayfinder:{kind}" in payload["body"] and kind in self.swallow:
                        return 201, {"id": -1, "body": payload["body"]}
                if "comment" in self.swallow:
                    return 201, {"id": -1, "body": payload["body"]}
                stored_body = payload["body"] + self.mangle_comment_body
                cid = self.add_comment(number, stored_body)
                return 201, {"id": cid, "body": payload["body"]}

        if path.endswith("/dependencies"):
            number = int(path.split("/issues/")[1].split("/")[0])
            if method == "GET":
                return 200, [{"number": d} for d in sorted(self.dependencies.get(number, []))]
            if method == "POST":
                if "dependency" in self.swallow:
                    return 201, {"number": number}
                self.dependencies.setdefault(number, []).append(int(payload["index"]))
                return 201, {"number": number}

        if method == "POST" and path == f"{base}/issues":
            # Numeric ids only — a name here is the bug this fake exists to catch.
            for value in payload.get("labels", []):
                if not isinstance(value, int):
                    raise AssertionError(
                        f"CreateIssueOption.labels must be numeric ids, got {value!r}"
                    )
            by_id = {i: n for n, i in self.labels.items()}
            names = [by_id[i] for i in payload.get("labels", [])]
            title = self.mangle_issue.get("title", payload["title"])
            body = payload["body"] + self.mangle_issue.get("body_suffix", "")
            for dropped in self.mangle_issue.get("drop_labels", []):
                names = [n for n in names if n != dropped]
            names = names + list(self.mangle_issue.get("extra_labels", []))
            number = self.add_issue(title=title, body=body, labels=names)
            return 201, dict(self.issues[number])

        if method in ("GET", "PATCH") and "/issues/" in path:
            number = int(path.rsplit("/issues/", 1)[1])
            if number not in self.issues:
                return 404, None
            if method == "GET":
                self._gets[number] = self._gets.get(number, 0) + 1
                hook = self.on_get.pop((number, self._gets[number]), None)
                if hook is not None:
                    hook(self, number)
                return 200, dict(self.issues[number])
            tag = (
                "patch-close"
                if payload.get("state")
                else "patch-assignees"
                if "assignees" in payload
                else "patch-body"
            )
            self._maybe_fail(tag)
            if tag in self.swallow:
                # Acknowledged, stored nowhere.
                return 200, dict(self.issues[number])
            stored = dict(payload)
            if "assignees" in stored:
                # Forgejo takes logins and returns user objects.
                fresh = [{"login": name} for name in stored["assignees"]]
                if self.keep_assignees:
                    # A partially applied PATCH: ours added, theirs retained.
                    existing = list(self.issues[number].get("assignees") or [])
                    logins = {p["login"] for p in existing}
                    fresh = existing + [p for p in fresh if p["login"] not in logins]
                stored["assignees"] = fresh
            if "body" in stored and self.mangle_patch_body:
                stored["body"] = stored["body"] + self.mangle_patch_body
            self.issues[number].update(stored)
            self.issues[number]["updated_at"] = self._stamp()
            return 200, dict(self.issues[number])

        raise AssertionError(f"unexpected request: {method} {path}")


def _query(path: str) -> dict[str, str]:
    if "?" not in path:
        return {}
    return dict(
        pair.split("=", 1) for pair in path.split("?", 1)[1].split("&") if "=" in pair
    )


def run_cli(api: "FakeForgejo", *args: str) -> Any:
    """Run the real CLI against the in-memory tracker and parse its JSON.

    `build_transport` is the only seam that would reach the network, so it is
    the only thing replaced. Everything else — argument parsing, dispatch,
    output shape — is the code a human would run.
    """
    argv = [
        "--origin", f"ssh://git@{REPO.host}/{REPO.owner}/{REPO.repo}.git",
        "--tracker", REPO.slug,
        *args,
    ]
    out = io.StringIO()
    real = WF.build_transport
    WF.build_transport = lambda repo, **kwargs: api  # type: ignore[assignment]
    try:
        with contextlib.redirect_stdout(out):
            code = WF.main(argv)
    finally:
        WF.build_transport = real  # type: ignore[assignment]
    if code != 0:
        raise AssertionError(f"CLI exited {code}: {out.getvalue()}")
    return json.loads(out.getvalue())


def seeded_tracker(**kwargs) -> tuple[WF.WayfinderTracker, FakeForgejo]:
    """A private tracker holding one map and three tickets.

    #2 is takeable, #3 is blocked by the open #2, #4 is claimed by session-a.
    """
    api = FakeForgejo(**kwargs)
    for name in WF.LABEL_DEFINITIONS:
        api.add_label(name)
    api.add_issue(
        title="Chart the thing",
        body=(
            "Human prose above the managed region.\n\n"
            f"{WF.MAP_BEGIN}\n## Destination\n\nA reviewed spec.\n\n"
            "## Decisions so far\n\n## Not yet specified\n\n- storage shape\n"
            f"{WF.MAP_END}\n"
        ),
        labels=[WF.MAP_LABEL],
        number=1,
    )
    api.add_issue(
        title="Pick the storage shape",
        body=ticket_body("Which storage shape?", 1),
        labels=[WF.TICKET_LABEL, "wayfinder:grilling"],
        number=2,
    )
    api.add_issue(
        title="Pick the migration path",
        body=ticket_body("Which migration path?", 1),
        labels=[WF.TICKET_LABEL, "wayfinder:grilling"],
        number=3,
    )
    api.add_issue(
        title="Research the vendor API",
        body=ticket_body("What does the vendor return?", 1, "research"),
        labels=[WF.TICKET_LABEL, "wayfinder:research"],
        number=4,
    )
    api.add_comment(4, WF.render_record("claim", {"session": "hermes/session-a", "operation": op_for("hermes/session-a"), "at": T0}))
    api.dependencies[3] = [2]
    return WF.WayfinderTracker(api, REPO), api


# ==========================================================================
# Origin, identity, and input validation
# ==========================================================================


class OriginParsingTest(unittest.TestCase):
    def test_parses_ssh_scp_and_https_origins(self) -> None:
        cases = {
            "ssh://forgejo@git.example.test/bryan/dotfiles.git": "git.example.test",
            "ssh://forgejo@git.example.test:5518/bryan/dotfiles.git": "git.example.test",
            "forgejo@git.example.test:bryan/dotfiles.git": "git.example.test",
            "https://git.example.test/bryan/dotfiles": "git.example.test",
        }
        for origin, host in cases.items():
            with self.subTest(origin=origin):
                ref = WF.parse_origin(origin)
                self.assertEqual((ref.host, ref.owner, ref.repo), (host, "bryan", "dotfiles"))

    def test_rejects_an_unparseable_origin(self) -> None:
        with self.assertRaises(WF.WayfinderError):
            WF.parse_origin("not-a-remote")

    def test_rejects_malformed_owner_repo_and_host(self) -> None:
        for tracker in ("", "workspace", "a/b/c", "../etc/passwd", "bryan/../x", "bryan/a b"):
            with self.subTest(tracker=tracker), self.assertRaises(WF.WayfinderError):
                WF.resolve_repo("ssh://f@git.example.test/bryan/dotfiles.git", tracker)
        for origin in (
            "https://exa mple.test/bryan/repo",
            "https://-bad.test/bryan/repo",
        ):
            with self.subTest(origin=origin), self.assertRaises(WF.WayfinderError):
                WF.parse_origin(origin)

    def test_tracker_choice_is_required_and_explicit(self) -> None:
        ref = WF.resolve_repo(
            "ssh://forgejo@git.example.test/bryan/dotfiles.git", "bryan/sgg-workspace"
        )
        self.assertEqual(ref.slug, "bryan/sgg-workspace")
        self.assertEqual(ref.host, "git.example.test")

    def test_session_and_timestamp_must_be_line_safe(self) -> None:
        for bad in ("", "  ", "a b", "a\nb", "x-->y", "a" * 200, "-leading"):
            with self.subTest(session=bad), self.assertRaises(WF.WayfinderError):
                WF.validate_session(bad)
        self.assertEqual(WF.validate_session("hermes/0f3c-9a21.2"), "hermes/0f3c-9a21.2")
        for bad in ("", "2026-08-19", "2026-08-19T10:00:00", "yesterday", "2026-08-19T10:00:00+01:00"):
            with self.subTest(at=bad), self.assertRaises(WF.WayfinderError):
                WF.validate_timestamp(bad)
        self.assertEqual(WF.validate_timestamp(T1), T1)


# ==========================================================================
# Item 1 — numeric label ids
# ==========================================================================


class LabelTest(unittest.TestCase):
    def test_existing_labels_resolve_to_numeric_ids(self) -> None:
        tracker, api = seeded_tracker()
        ids, missing = tracker.resolve_label_ids([WF.TICKET_LABEL, "wayfinder:task"])
        self.assertEqual(missing, [])
        self.assertEqual(ids[WF.TICKET_LABEL], api.labels[WF.TICKET_LABEL])
        for value in ids.values():
            self.assertIsInstance(value, int)

    def test_missing_labels_are_reported_in_preview_and_not_created(self) -> None:
        api = FakeForgejo()
        tracker = WF.WayfinderTracker(api, REPO)
        ids, missing = tracker.resolve_label_ids([WF.MAP_LABEL], apply=False)
        self.assertEqual(missing, [WF.MAP_LABEL])
        self.assertEqual(ids, {})
        self.assertEqual(api.labels, {})

    def test_apply_creates_only_missing_labels_and_reads_them_back(self) -> None:
        api = FakeForgejo(labels={WF.TICKET_LABEL: 7})
        tracker = WF.WayfinderTracker(api, REPO)
        ids, created = tracker.resolve_label_ids(
            [WF.TICKET_LABEL, "wayfinder:task"], apply=True
        )
        self.assertEqual(created, ["wayfinder:task"])
        self.assertEqual(ids[WF.TICKET_LABEL], 7)
        self.assertIn("wayfinder:task", api.labels)
        self.assertEqual(ids["wayfinder:task"], api.labels["wayfinder:task"])

    def test_an_undeclared_label_is_refused(self) -> None:
        tracker, _ = seeded_tracker()
        with self.assertRaises(WF.WayfinderError):
            tracker.resolve_label_ids(["something-else"])

    def test_a_label_that_does_not_read_back_raises(self) -> None:
        api = FakeForgejo()

        def swallow(method, path, payload=None):
            if method.upper() == "POST" and path.endswith("/labels"):
                return 201, {}
            return FakeForgejo.request(api, method, path, payload)

        api.request = swallow  # type: ignore[method-assign]
        tracker = WF.WayfinderTracker(api, REPO)
        with self.assertRaises(WF.WayfinderError) as caught:
            tracker.resolve_label_ids([WF.MAP_LABEL], apply=True)
        self.assertIn("did not read back", str(caught.exception))

    def test_create_map_preview_shows_missing_label_creation(self) -> None:
        api = FakeForgejo()
        tracker = WF.WayfinderTracker(api, REPO)
        preview = tracker.create_map(title="M", managed="## Destination")
        self.assertIn("create missing label(s): wayfinder:map", preview.render())
        self.assertEqual(api.labels, {})

    def test_created_issues_carry_the_expected_label_names(self) -> None:
        tracker, api = seeded_tracker()
        ticket = tracker.create_ticket(
            map_number=1, title="T", question="Q", ticket_type="task",
            creation=op_for("labels"), apply=True,
        )
        self.assertIn(WF.TICKET_LABEL, ticket.labels)
        self.assertIn("wayfinder:task", ticket.labels)

    def test_every_declared_label_has_a_colour(self) -> None:
        for name, definition in WF.LABEL_DEFINITIONS.items():
            with self.subTest(label=name):
                self.assertRegex(definition["color"], r"\A#[0-9a-f]{6}\Z")
                self.assertTrue(definition["description"])


# ==========================================================================
# Item 2 — mutation preflight
# ==========================================================================


class PreflightTest(unittest.TestCase):
    def mutations(self, tracker):
        """One callable per mutation family, all with apply=True."""
        return {
            "create-map": lambda: tracker.create_map(
                title="M", managed="## Destination", apply=True
            ),
            "create-ticket": lambda: tracker.create_ticket(
                map_number=1, title="T", question="Q", ticket_type="task", apply=True
            ),
            "wire-blocking": lambda: tracker.wire_blocking(
                map_number=1, blocked=3, blocked_by=2, apply=True
            ),
            "claim": lambda: tracker.claim(
                map_number=1, number=2, session="hermes/s1", claimed_at=T1, apply=True,
                operation=op_for("hermes/s1"),
            ),
            "release": lambda: tracker.release(
                map_number=1, number=4, session="hermes/session-a", released_at=T1, apply=True,
                operation=op_for("hermes/session-a"),
            ),
            "resolve": lambda: tracker.resolve_ticket(
                map_number=1,
                number=4,
                session="hermes/session-a",
                claim_operation=op_for("hermes/session-a"),
                answer="Because.",
                map_index_line="Chose X",
                apply=True,
            ),
        }

    def test_every_mutation_family_refuses_a_public_repository(self) -> None:
        tracker, api = seeded_tracker(private=False)
        for name, run in self.mutations(tracker).items():
            with self.subTest(mutation=name):
                with self.assertRaises(WF.WayfinderError) as caught:
                    run()
                self.assertIn("public", str(caught.exception))

    def test_a_public_repository_is_refused_before_any_write(self) -> None:
        tracker, api = seeded_tracker(private=False)
        for name, run in self.mutations(tracker).items():
            with self.subTest(mutation=name):
                before = [c for c in api.calls if c[0] in ("POST", "PATCH")]
                with contextlib.suppress(WF.WayfinderError):
                    run()
                self.assertEqual([c for c in api.calls if c[0] in ("POST", "PATCH")], before)

    def test_preflight_refuses_a_body_marker_on_an_unlabelled_issue(self) -> None:
        """A body marker alone is not identity — anyone can paste one."""
        tracker, api = seeded_tracker()
        api.add_issue(
            title="Pasted marker",
            body=ticket_body("Not really a ticket", 1),
            labels=[],
            number=60,
        )
        with self.assertRaises(WF.WayfinderError) as caught:
            tracker.preflight_ticket(60, 1)
        self.assertIn(WF.TICKET_LABEL, str(caught.exception))

    def test_preflight_refuses_a_wrong_metadata_version(self) -> None:
        tracker, api = seeded_tracker()
        api.add_issue(
            title="Future ticket",
            body="## Question\n\nQ\n\n<!-- wayfinder:ticket v9\nmap: 1\ntype: grilling\n-->\n",
            labels=[WF.TICKET_LABEL],
            number=61,
        )
        with self.assertRaises(WF.WayfinderError) as caught:
            tracker.preflight_ticket(61, 1)
        self.assertIn("wayfinder:ticket metadata block", str(caught.exception))

    def test_preflight_refuses_an_unknown_ticket_type(self) -> None:
        tracker, api = seeded_tracker()
        api.add_issue(
            title="Odd ticket",
            body="## Question\n\nQ\n\n<!-- wayfinder:ticket v1\nmap: 1\ntype: vibes\n-->\n",
            labels=[WF.TICKET_LABEL],
            number=62,
        )
        with self.assertRaises(WF.WayfinderError):
            tracker.preflight_ticket(62, 1)

    def test_preflight_refuses_a_ticket_from_another_map(self) -> None:
        tracker, api = seeded_tracker()
        api.add_issue(
            title="Other map",
            body=ticket_body("Not ours", 99),
            labels=[WF.TICKET_LABEL],
            number=63,
        )
        with self.assertRaises(WF.WayfinderError) as caught:
            tracker.preflight_ticket(63, 1)
        self.assertIn("wayfinder:grilling", str(caught.exception))

    def test_preflight_refuses_an_issue_that_is_not_a_map(self) -> None:
        tracker, api = seeded_tracker()
        api.add_issue(title="Ordinary", body="hello", labels=[], number=64)
        with self.assertRaises(WF.WayfinderError):
            tracker.preflight_map(64)

    def test_wiring_refuses_a_ticket_outside_the_map(self) -> None:
        tracker, api = seeded_tracker()
        api.add_issue(
            title="Foreign", body=ticket_body("x", 99), labels=[WF.TICKET_LABEL], number=65
        )
        with self.assertRaises(WF.WayfinderError):
            tracker.wire_blocking(map_number=1, blocked=2, blocked_by=65, apply=True)


# ==========================================================================
# Item 3 — transport selection and credential containment
# ==========================================================================


class TransportSelectionTest(unittest.TestCase):
    def test_auto_never_selects_token_transport_from_an_ambient_token(self) -> None:
        """An exported token must not bind itself to an origin-named host."""
        env = {"FORGEJO_TOKEN": "ambient-secret"}
        transport = WF.build_transport(REPO, prefer="auto", environ=env)
        self.assertIsInstance(transport, WF.TeaTransport)

    def test_tea_is_the_default_with_no_environment_at_all(self) -> None:
        self.assertIsInstance(WF.build_transport(REPO, prefer="auto", environ={}), WF.TeaTransport)

    def test_token_mode_requires_an_allowlist(self) -> None:
        with self.assertRaises(WF.WayfinderError) as caught:
            WF.build_transport(REPO, prefer="token", environ={"FORGEJO_TOKEN": "t"})
        self.assertIn(WF.HOST_ALLOWLIST_ENV, str(caught.exception))

    def test_token_mode_refuses_a_host_outside_the_allowlist(self) -> None:
        env = {"FORGEJO_TOKEN": "t", WF.HOST_ALLOWLIST_ENV: "other.test"}
        with self.assertRaises(WF.WayfinderError) as caught:
            WF.build_transport(REPO, prefer="token", environ=env)
        self.assertIn("not in", str(caught.exception))

    def test_token_mode_accepts_an_allowlisted_host(self) -> None:
        env = {"FORGEJO_TOKEN": "t", WF.HOST_ALLOWLIST_ENV: f"a.test,{REPO.host},b.test"}
        self.assertIsInstance(
            WF.build_transport(REPO, prefer="token", environ=env), WF.TokenTransport
        )

    def test_token_mode_without_a_token_refuses(self) -> None:
        env = {WF.HOST_ALLOWLIST_ENV: REPO.host}
        with self.assertRaises(WF.WayfinderError):
            WF.build_transport(REPO, prefer="token", environ=env)

    def test_unknown_transport_is_refused(self) -> None:
        with self.assertRaises(WF.WayfinderError):
            WF.build_transport(REPO, prefer="something", environ={})


class CredentialTest(unittest.TestCase):
    def test_token_is_read_from_either_supported_variable(self) -> None:
        self.assertEqual(WF.token_from_environment({"FORGEJO_TOKEN": "a"}), "a")
        self.assertEqual(WF.token_from_environment({"GITEA_TOKEN": "b"}), "b")
        self.assertIsNone(WF.token_from_environment({"OTHER": "c"}))

    def test_token_never_appears_in_an_error_or_repr(self) -> None:
        captured: list[Any] = []

        def opener(request, timeout=None):  # noqa: ARG001
            captured.append(request)
            raise OSError("connection refused")

        transport = WF.TokenTransport(
            REPO.host, token="super-secret-token", opener=opener
        )
        with self.assertRaises(WF.WayfinderError) as caught:
            transport.request("GET", "/repos/bryan/workspace")
        self.assertNotIn("super-secret-token", str(caught.exception))
        self.assertNotIn("super-secret-token", repr(transport))
        self.assertEqual(
            captured[0].get_header("Authorization"), "token super-secret-token"
        )

    def test_a_redirect_is_refused_rather_than_followed(self) -> None:
        """urllib would replay the Authorization header on the redirect target."""
        handler = WF._SameOriginRedirectHandler()
        with self.assertRaises(WF.WayfinderError) as caught:
            handler.redirect_request(
                None, None, 302, "Found", {}, "https://evil.test/api/v1/repos/x/y"
            )
        self.assertIn("evil.test", str(caught.exception))

    def test_transport_refuses_a_path_that_could_steer_off_the_pin(self) -> None:
        """A leading `//`, a scheme, CRLF, or traversal never appears in a real path."""
        transport = WF.TokenTransport(REPO.host, token="t", opener=lambda *a, **k: None)
        for path in (
            "//evil.test/x",
            "/x?u=1 https://evil.test",
            "https://evil.test/x",
            "/repos/o/r\r\nX-Injected: 1",
            "/repos/../../secret",
            "repos/o/r",
        ):
            with self.subTest(path=path), self.assertRaises(WF.WayfinderError):
                transport.request("GET", path)

    def test_transport_refuses_a_malformed_host(self) -> None:
        for host in ("", "exa mple.test", "-bad.test", "a" * 300):
            with self.subTest(host=host), self.assertRaises(WF.WayfinderError):
                WF.TokenTransport(host, token="t")

    def test_tea_transport_never_puts_the_payload_in_an_error(self) -> None:
        class Result:
            returncode = 1
            stdout = ""
            stderr = "tea: bad request"

        transport = WF.TeaTransport(REPO.host, runner=lambda *a, **k: Result())
        with self.assertRaises(WF.WayfinderError) as caught:
            transport.request("POST", "/repos/bryan/workspace/issues", {"body": "secretish"})
        self.assertNotIn("secretish", str(caught.exception))

    def test_tea_transport_sends_the_payload_on_stdin(self) -> None:
        seen: dict[str, Any] = {}

        class Result:
            returncode = 0
            stdout = '{"number": 1}'
            stderr = ""

        def runner(command, **kwargs):
            seen["command"] = command
            seen["input"] = kwargs.get("input")
            return Result()

        transport = WF.TeaTransport(REPO.host, runner=runner)
        status, data = transport.request("POST", "/x", {"title": "T"})
        self.assertEqual((status, data), (200, {"number": 1}))
        self.assertEqual(json.loads(seen["input"]), {"title": "T"})
        self.assertIn("--login", seen["command"])


# ==========================================================================
# Item 4 — server-ordered claim arbitration
# ==========================================================================


class RecordOrderingTest(unittest.TestCase):
    def records(self, *rows) -> list[dict]:
        """Rows are `(comment_id, kind, session, at)` or `(…, operation_name)`.

        Omitting the operation name derives it from the session, which is the
        common case: one session running one operation. Supplying it is how a
        test says "the same session, a *different* critical section".
        """
        built = []
        for row in rows:
            cid, kind, session, at = row[:4]
            operation = op_for(row[4] if len(row) > 4 else session)
            built.append(
                {
                    "id": cid,
                    "body": WF.render_record(
                        kind, {"session": session, "operation": operation, "at": at}
                    ),
                }
            )
        return built

    def test_earliest_unreleased_claim_wins_by_comment_id(self) -> None:
        comments = self.records(
            (11, "claim", "b", T2),
            (10, "claim", "a", T1),
        )
        holder = WF.active_claim(WF.parse_records(comments))
        self.assertEqual(holder.session, "a")
        self.assertEqual(holder.comment_id, 10)

    def test_wall_clock_never_overrides_comment_order(self) -> None:
        """`at` is client-supplied; only the comment id is server-assigned."""
        comments = self.records(
            (10, "claim", "a", T2),  # claims a later time
            (11, "claim", "b", T0),  # claims an earlier time
        )
        self.assertEqual(WF.active_claim(WF.parse_records(comments)).session, "a")

    def test_an_uncleaned_losing_claim_surfaces_rather_than_vanishing(self) -> None:
        """A crashed loser leaves a claim behind, and it must stay visible.

        A well-behaved loser withdraws its own claim (see
        `ClaimCleanupTest`), so this state only arises when a session died
        between posting and standing down. Surfacing it is right — the next
        session sees the ticket as claimed and can release it explicitly —
        whereas silently discarding it would hide a half-finished session.
        """
        comments = self.records(
            (10, "claim", "a", T0),
            (11, "claim", "b", T1),   # b crashed before withdrawing
            (12, "release", "a", T2),
        )
        holder = WF.active_claim(WF.parse_records(comments))
        self.assertIsNotNone(holder)
        self.assertEqual(holder.session, "b")
        self.assertEqual(holder.comment_id, 11)

    def test_releasing_the_last_claim_leaves_the_ticket_unclaimed(self) -> None:
        comments = self.records((10, "claim", "a", T0), (11, "release", "a", T1))
        self.assertIsNone(WF.active_claim(WF.parse_records(comments)))

    def test_a_duplicate_claim_from_the_same_session_is_not_double_counted(self) -> None:
        comments = self.records(
            (10, "claim", "a", T0),
            (11, "claim", "a", T1),
            (12, "release", "a", T2),
        )
        self.assertIsNone(WF.active_claim(WF.parse_records(comments)))

    def test_a_reclaim_after_release_works(self) -> None:
        comments = self.records(
            (10, "claim", "a", T0),
            (11, "release", "a", T1),
            (12, "claim", "a", T2),
        )
        self.assertEqual(WF.active_claim(WF.parse_records(comments)).session, "a")

    def test_malformed_and_wrong_version_records_cannot_arbitrate(self) -> None:
        comments = [
            {"id": 10, "body": "<!-- wayfinder:claim v1\nsession: has space\nat: bad\n-->"},
            {"id": 11, "body": "<!-- wayfinder:claim v9\nsession: future\nat: " + T0 + "\n-->"},
            {"id": 12, "body": "just a human comment"},
        ]
        self.assertEqual(WF.parse_records(comments), [])
        self.assertIsNone(WF.active_claim(WF.parse_records(comments)))

    def test_a_malformed_comment_id_shape_never_arbitrates(self) -> None:
        """`int()` alone would accept every one of these.

        Underscore grouping ("1_0"), whitespace ("  12  "), leading zeros
        ("007"), and booleans (True == 1) are all int()-convertible without
        being ids a real Forgejo would return — and each would take a position
        in the replay order if tolerated.
        """
        legit = self.records((1000, "claim", "hermes/owner", T1))
        for bad_id in ("1_0", "  12  ", "007", True, 1.0):
            with self.subTest(bad_id=bad_id):
                forged = {
                    "id": bad_id,
                    "body": WF.render_record(
                        "claim",
                        {"session": "hermes/evil", "operation": op_for("evil"), "at": T0},
                    ),
                }
                holder = WF.active_claim(WF.parse_records([forged] + legit))
                self.assertIsNotNone(holder)
                self.assertEqual(holder.session, "hermes/owner")

    def test_a_nonpositive_comment_id_never_arbitrates(self) -> None:
        """Blocker regression: a forged or degenerate id must not win.

        Records replay in comment-id order and Forgejo assigns ids from 1, so a
        record carried by id 0, a negative id, or a malformed one has no
        position in that order — sorting it would put it *first*, handing the
        claim to whoever forged it.
        """
        legit = self.records((1000, "claim", "hermes/owner", T1))
        for bad_id in (-5, 0, "junk", None):
            with self.subTest(bad_id=bad_id):
                forged = {
                    "id": bad_id,
                    "body": WF.render_record(
                        "claim",
                        {"session": "hermes/evil", "operation": op_for("evil"), "at": T0},
                    ),
                }
                holder = WF.active_claim(WF.parse_records([forged] + legit))
                self.assertIsNotNone(holder)
                self.assertEqual(holder.session, "hermes/owner")

    def test_resolution_records_are_not_claim_records(self) -> None:
        comments = [
            {
                "id": 10,
                "body": WF.render_record(
                    "resolution",
                    {"key": WF.resolution_key(1, 2, "answer"), "map": "1", "session": "a"},
                ),
            }
        ]
        self.assertEqual(WF.parse_records(comments), [])


class ClaimTest(unittest.TestCase):
    def test_claiming_an_unclaimed_ticket_wins_and_reads_back(self) -> None:
        tracker, api = seeded_tracker()
        outcome = tracker.claim(
            map_number=1, number=2, session="hermes/s1", claimed_at=T1, apply=True,
            operation=op_for("hermes/s1"),
        )
        self.assertTrue(outcome.won)
        self.assertEqual(tracker.current_claim(2).session, "hermes/s1")

    def test_claiming_an_already_claimed_ticket_stands_down_without_writing(self) -> None:
        tracker, api = seeded_tracker()
        before = len(api.comments.get(4, []))
        outcome = tracker.claim(
            map_number=1, number=4, session="claude/s2", claimed_at=T1, apply=True,
            operation=op_for("claude/s2"),
        )
        self.assertFalse(outcome.won)
        self.assertEqual(outcome.holder["session"], "hermes/session-a")
        self.assertEqual(len(api.comments.get(4, [])), before)

    def test_two_contenders_interleaved_cannot_both_win(self) -> None:
        """The decisive test for item 4.

        Both sessions pass the pre-write check (neither sees a claim), both
        post, and both then read the same ordered comment list. Exactly one
        finds itself earliest.
        """
        tracker_a, api = seeded_tracker()
        tracker_b = WF.WayfinderTracker(api, REPO)
        posted: list[str] = []

        real_request = api.request

        def interleave(method, path, payload=None):
            # When A posts its claim, B posts one first — the exact race the
            # old body-overwrite scheme resolved in favour of whoever wrote last.
            if (
                method.upper() == "POST"
                and path.endswith("/issues/2/comments")
                and not posted
            ):
                posted.append("b")
                api.add_comment(
                    2, WF.render_record("claim", {"session": "claude/b", "operation": op_for("claude/b"), "at": T2})
                )
            return real_request(method, path, payload)

        api.request = interleave  # type: ignore[method-assign]
        outcome_a = tracker_a.claim(
            map_number=1, number=2, session="hermes/a", claimed_at=T1, apply=True,
            operation=op_for("hermes/a"),
        )
        api.request = real_request  # type: ignore[method-assign]
        outcome_b = tracker_b.claim(
            map_number=1, number=2, session="claude/b", claimed_at=T2, apply=True,
            operation=op_for("claude/b"),
        )
        self.assertEqual(
            [outcome_a.won, outcome_b.won].count(True),
            1,
            "exactly one contender may win",
        )
        winner = tracker_a.current_claim(2).session
        self.assertEqual(winner, "claude/b", "the earliest comment id holds the claim")
        self.assertFalse(outcome_a.won)
        self.assertTrue(outcome_b.won)

    def test_sequential_contenders_cannot_both_win(self) -> None:
        tracker_a, api = seeded_tracker()
        tracker_b = WF.WayfinderTracker(api, REPO)
        first = tracker_a.claim(
            map_number=1, number=2, session="hermes/a", claimed_at=T1, apply=True,
            operation=op_for("hermes/a"),
        )
        second = tracker_b.claim(
            map_number=1, number=2, session="claude/b", claimed_at=T2, apply=True,
            operation=op_for("claude/b"),
        )
        self.assertEqual([first.won, second.won], [True, False])

    def test_claim_validates_its_inputs_before_any_request(self) -> None:
        tracker, api = seeded_tracker()
        before = len(api.calls)
        with self.assertRaises(WF.WayfinderError):
            tracker.claim(map_number=1, number=2, session="bad session", operation=op_for("bad session"), claimed_at=T1, apply=True)
        with self.assertRaises(WF.WayfinderError):
            tracker.claim(map_number=1, number=2, session="ok", operation=op_for("ok"), claimed_at="whenever", apply=True)
        self.assertEqual(len(api.calls), before)

    def test_frontier_uses_the_authoritative_comment_state(self) -> None:
        tracker, api = seeded_tracker()
        self.assertEqual([t.number for t in tracker.frontier(1)], [2])
        api.add_comment(2, WF.render_record("claim", {"session": "someone/else", "operation": op_for("someone/else"), "at": T1}))
        self.assertEqual([t.number for t in tracker.frontier(1)], [])
        api.add_comment(2, WF.render_record("release", {"session": "someone/else", "operation": op_for("someone/else"), "at": T2}))
        self.assertEqual([t.number for t in tracker.frontier(1)], [2])

    def test_releasing_another_sessions_claim_is_refused(self) -> None:
        tracker, api = seeded_tracker()
        outcome = tracker.release(
            map_number=1, number=4, session="claude/other", released_at=T1, apply=True,
            operation=op_for("claude/other"),
        )
        self.assertFalse(outcome.won)
        self.assertEqual(tracker.current_claim(4).session, "hermes/session-a")

    def test_releasing_an_unclaimed_ticket_reports_rather_than_writing(self) -> None:
        tracker, api = seeded_tracker()
        before = len(api.comments.get(2, []))
        outcome = tracker.release(
            map_number=1, number=2, session="hermes/s1", released_at=T1, apply=True,
            operation=op_for("hermes/s1"),
        )
        self.assertFalse(outcome.won)
        self.assertEqual(len(api.comments.get(2, [])), before)

    def test_release_then_reclaim_round_trips(self) -> None:
        tracker, api = seeded_tracker()
        self.assertTrue(
            tracker.release(
                map_number=1, number=4, session="hermes/session-a", released_at=T1, apply=True,
                operation=op_for("hermes/session-a"),
            ).won
        )
        self.assertIsNone(tracker.current_claim(4))
        self.assertTrue(
            tracker.claim(
                map_number=1, number=4, session="claude/next", claimed_at=T2, apply=True,
                operation=op_for("claude/next"),
            ).won
        )

    def test_comment_pagination_is_exhausted_before_arbitrating(self) -> None:
        tracker, api = seeded_tracker()
        for index in range(WF.PAGE_SIZE + 5):
            api.add_comment(2, f"human chatter {index}")
        api.add_comment(2, WF.render_record("claim", {"session": "late/session", "operation": op_for("late/session"), "at": T2}))
        self.assertEqual(tracker.current_claim(2).session, "late/session")

    def test_an_unbounded_comment_list_raises_rather_than_arbitrating(self) -> None:
        tracker, api = seeded_tracker()

        def endless(method, path, payload=None):
            if method.upper() == "GET" and "/comments" in path:
                return 200, [{"id": i, "body": "x"} for i in range(WF.PAGE_SIZE)]
            return FakeForgejo.request(api, method, path, payload)

        api.request = endless  # type: ignore[method-assign]
        with self.assertRaises(WF.WayfinderError) as caught:
            tracker.current_claim(2)
        self.assertIn("truncated", str(caught.exception))


# ==========================================================================
# Items 5 and 6 — resolve authorization and idempotence
# ==========================================================================


class ResolveAuthorizationTest(unittest.TestCase):
    def test_an_unclaimed_ticket_cannot_be_resolved(self) -> None:
        tracker, _ = seeded_tracker()
        with self.assertRaises(WF.WayfinderError) as caught:
            tracker.resolve_ticket(
                map_number=1, number=2, session="hermes/s1",
                claim_operation=op_for("hermes/s1"),
                answer="a", map_index_line="b", at=T1, apply=True,
            )
        self.assertIn("nothing holds the claim", str(caught.exception))

    def test_only_the_current_claimant_may_resolve(self) -> None:
        tracker, _ = seeded_tracker()
        with self.assertRaises(WF.WayfinderError) as caught:
            tracker.resolve_ticket(
                map_number=1, number=4, session="claude/interloper",
                claim_operation=op_for("claude/interloper"),
                answer="a", map_index_line="b", at=T1, apply=True,
            )
        self.assertIn("only the current holder may write", str(caught.exception))

    def test_the_claimant_may_resolve(self) -> None:
        tracker, api = seeded_tracker()
        outcome = tracker.resolve_ticket(
            map_number=1, number=4, session="hermes/session-a",
            claim_operation=op_for("hermes/session-a"),
            answer="Chose the flat shape.", map_index_line="Storage shape: flat",
            at=T1, apply=True,
        )
        self.assertTrue(outcome.commented and outcome.closed and outcome.indexed)
        self.assertEqual(api.issues[4]["state"], "closed")
        self.assertEqual(
            [d["gist"] for d in outcome.map["decisions"]], ["Storage shape: flat"]
        )
        self.assertIn("Human prose above the managed region.", api.issues[1]["body"])

    def test_resolve_requires_a_session_at_the_cli_boundary(self) -> None:
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            WF.build_parser().parse_args(
                [
                    "--origin", "ssh://f@h.test/o/r.git", "--tracker", "o/r",
                    "resolve", "--map", "1", "--ticket", "2",
                    "--answer-file", "a.md", "--index-line", "x",
                ]
            )


class ResolveIdempotenceTest(unittest.TestCase):
    ANSWER = "Chose the flat shape because migrations stay cheap."
    LINE = "Storage shape: flat, migrations stay cheap"

    def resolve(self, tracker, **kwargs):
        return tracker.resolve_ticket(
            map_number=1,
            number=4,
            session="hermes/session-a",
            claim_operation=op_for("hermes/session-a"),
            answer=self.ANSWER,
            map_index_line=self.LINE,
            at=T1,
            apply=True,
            **kwargs,
        )

    def counts(self, api) -> tuple[int, int, int]:
        key = WF.resolution_key(1, 4, self.ANSWER)
        comments = sum(
            1
            for c in api.comments.get(4, [])
            if f"key: {key}" in (c.get("body") or "")
        )
        index = sum(
            1
            for record in WF.parse_records(api.comments.get(1, []), kinds=("index",))
            if record.fields.get("key") == key
        )
        closed = 1 if api.issues[4]["state"] == "closed" else 0
        return comments, closed, index

    def test_the_key_is_deterministic_and_answer_specific(self) -> None:
        self.assertEqual(WF.resolution_key(1, 4, "x"), WF.resolution_key(1, 4, "x"))
        self.assertNotEqual(WF.resolution_key(1, 4, "x"), WF.resolution_key(1, 4, "y"))
        self.assertNotEqual(WF.resolution_key(1, 4, "x"), WF.resolution_key(1, 5, "x"))

    def test_a_second_identical_resolve_changes_nothing(self) -> None:
        tracker, api = seeded_tracker()
        self.resolve(tracker)
        first = self.counts(api)
        again = self.resolve(tracker)
        self.assertEqual(self.counts(api), first)
        self.assertEqual(self.counts(api), (1, 1, 1))
        self.assertEqual(sorted(again.already), ["closed", "comment", "indexed"])
        self.assertFalse(again.commented or again.closed or again.indexed)

    def test_retry_after_the_comment_step_converges(self) -> None:
        tracker, api = seeded_tracker()
        api.fail_on["patch-close"] = 1
        with self.assertRaises(WF.WayfinderError):
            self.resolve(tracker)
        api.fail_on.clear()
        self.resolve(tracker)
        self.assertEqual(self.counts(api), (1, 1, 1))

    def test_retry_after_a_failed_index_converges_and_the_ticket_stayed_open(self) -> None:
        tracker, api = seeded_tracker()
        # The resolution comment is the first comment POST; the index record
        # is the second. The close is last, so a failed index append must
        # leave the ticket open — no decision of record, no closed ticket.
        api.fail_on["comment"] = 2
        with self.assertRaises(WF.WayfinderError):
            self.resolve(tracker)
        self.assertEqual(api.issues[4]["state"], "open")
        api.fail_on.clear()
        self.resolve(tracker)
        self.assertEqual(self.counts(api), (1, 1, 1))

    def test_retry_after_the_comment_post_fails_converges(self) -> None:
        tracker, api = seeded_tracker()
        api.fail_on["comment"] = 1
        with self.assertRaises(WF.WayfinderError):
            self.resolve(tracker)
        api.fail_on.clear()
        self.resolve(tracker)
        self.assertEqual(self.counts(api), (1, 1, 1))

    def test_a_duplicated_index_record_still_counts_once(self) -> None:
        tracker, api = seeded_tracker()
        self.resolve(tracker)
        key = WF.resolution_key(1, 4, self.ANSWER)
        # A second identical record (a swallowed-readback retry that actually
        # landed twice) replays to one entry.
        api.add_comment(1, WF.render_index_comment({
            "session": "hermes/session-a", "key": key, "map": "1",
            "ticket": "4", "gist": self.LINE, "at": T2,
        }))
        decisions = tracker.map_decisions(1)
        self.assertEqual(len([d for d in decisions if d["key"] == key]), 1)

    def test_preview_reports_what_already_landed(self) -> None:
        tracker, api = seeded_tracker()
        self.resolve(tracker)
        preview = tracker.resolve_ticket(
            map_number=1, number=4, session="hermes/session-a",
            claim_operation=op_for("hermes/session-a"),
            answer=self.ANSWER, map_index_line=self.LINE,
        )
        rendered = preview.render()
        self.assertIn("already done, skipping", rendered)
        for step in ("comment", "closed", "indexed"):
            self.assertIn(step, rendered)


# ==========================================================================
# Blocker 1 — the decision index is append-only; the map body is never edited
# ==========================================================================


class DecisionIndexTest(unittest.TestCase):
    """The map's decision index is a replay of append-only index records.

    Forgejo has no compare-and-swap on issue update, so *no* body PATCH can be
    made safe against a human edit landing between the adapter's last read and
    its write. The adapter therefore never edits the map body at all: each
    resolution posts one exact-schema `index` comment, and the index is the
    replay of those comments. These tests hold that shape in place.
    """

    def resolve(self, tracker, number, session, answer, gist, at=T1):
        return tracker.resolve_ticket(
            map_number=1, number=number, session=session,
            claim_operation=op_for(session), answer=answer,
            map_index_line=gist, at=at, apply=True,
        )

    def test_resolution_posts_one_index_record_and_never_edits_the_body(self) -> None:
        tracker, api = seeded_tracker()
        before = api.issues[1]["body"]
        out = self.resolve(
            tracker, 4, "hermes/session-a", "Chose flat.", "Storage shape: flat"
        )
        self.assertTrue(out.resolved)
        self.assertEqual(
            api.issues[1]["body"], before, "the map body must never be edited"
        )
        records = tracker.map_index_records(1)
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0].fields["ticket"], "4")
        self.assertEqual(records[0].fields["gist"], "Storage shape: flat")
        self.assertEqual(
            [d["gist"] for d in out.map["decisions"]], ["Storage shape: flat"]
        )
        # The visible line a human reads on the map's timeline.
        bodies = [c["body"] for c in api.comments[1]]
        self.assertTrue(
            any(b.startswith("Decision #4: Storage shape: flat") for b in bodies)
        )

    def test_a_human_edit_at_any_read_interleaving_is_never_lost(self) -> None:
        """The exact final-review probe, inverted into an invariant.

        Bryan edits the map body while a resolution is mid-flight. Whichever
        read of the map issue his edit lands after — every interleaving is
        tried — the edit must survive byte-for-byte and the resolution must
        still succeed, because nothing in a resolution writes the map body.
        """
        note = "\n\nBRYAN: do not forget the migration deadline.\n"
        nth = 1
        exercised = 0
        while True:
            tracker, api = seeded_tracker()
            fired: list[int] = []

            def inject(fake, number, fired=fired):
                fake.issues[1]["body"] += note
                fired.append(1)

            api.on_get[(1, nth)] = inject
            out = self.resolve(
                tracker, 4, "hermes/session-a", "Chose flat.", "Storage shape: flat"
            )
            if not fired:
                break  # past the last map read this operation performs
            exercised += 1
            self.assertTrue(out.resolved, f"resolution failed at map GET #{nth}")
            self.assertIn(
                note.strip(),
                api.issues[1]["body"],
                f"human edit lost at map GET #{nth}",
            )
            nth += 1
        self.assertGreater(exercised, 0, "the interleaving hook never fired")

    def test_concurrent_resolutions_of_two_tickets_both_index(self) -> None:
        """Session B's whole resolution runs inside session A's index write.

        Under the old body-PATCH model this interleaving lost a decision.
        Append-only records cannot overwrite each other: both must be present
        and both resolutions must succeed.
        """
        tracker_a, api = seeded_tracker()
        tracker_b = WF.WayfinderTracker(api, REPO)
        api.add_comment(2, WF.render_record("claim", {"session": "claude/b", "operation": op_for("claude/b"), "at": T0}))
        interleaved: list[str] = []
        real_request = api.request

        def interleave(method, path, payload=None):
            body = (payload or {}).get("body", "")
            if (
                method.upper() == "POST"
                and path.endswith("/issues/1/comments")
                and "wayfinder:index" in body
                and "hermes/session-a" in body
                and not interleaved
            ):
                interleaved.append("b")
                api.request = real_request
                try:
                    outcome_b = tracker_b.resolve_ticket(
                        map_number=1, number=2, session="claude/b",
                        claim_operation=op_for("claude/b"),
                        answer="B answer.", map_index_line="B decision",
                        at=T2, apply=True,
                    )
                    self.assertTrue(outcome_b.resolved)
                finally:
                    api.request = interleave
            return real_request(method, path, payload)

        api.request = interleave
        outcome_a = tracker_a.resolve_ticket(
            map_number=1, number=4, session="hermes/session-a",
            claim_operation=op_for("hermes/session-a"),
            answer="A answer.", map_index_line="A decision",
            at=T1, apply=True,
        )
        api.request = real_request

        self.assertTrue(interleaved, "the interleaved resolution never ran")
        self.assertTrue(outcome_a.resolved)
        gists = [d["gist"] for d in tracker_a.map_decisions(1)]
        self.assertIn("A decision", gists)
        self.assertIn("B decision", gists)

    def test_an_identical_gist_for_another_ticket_indexes_separately(self) -> None:
        """Blocker 2a regression: idempotency is keyed, never text-matched."""
        tracker, api = seeded_tracker()
        gist = "Decided: keep it simple"
        out_a = self.resolve(tracker, 4, "hermes/session-a", "A.", gist)
        self.assertTrue(out_a.resolved)
        # #2 is claimed and resolved with the *same* gist text.
        api.add_comment(2, WF.render_record("claim", {"session": "claude/b", "operation": op_for("claude/b"), "at": T0}))
        preview = tracker.resolve_ticket(
            map_number=1, number=2, session="claude/b",
            claim_operation=op_for("claude/b"), answer="B.",
            map_index_line=gist,
        )
        skipping = "".join(step for step in preview.steps if "already done" in step)
        self.assertNotIn(
            "indexed", skipping,
            "another ticket's identical gist must not satisfy this resolution",
        )
        out_b = tracker.resolve_ticket(
            map_number=1, number=2, session="claude/b",
            claim_operation=op_for("claude/b"), answer="B.",
            map_index_line=gist, at=T2, apply=True,
        )
        self.assertTrue(out_b.resolved)
        decisions = tracker.map_decisions(1)
        self.assertEqual(
            sorted(d["ticket"] for d in decisions if d["gist"] == gist), ["2", "4"]
        )

    def test_a_reworded_retry_converges_on_one_entry(self) -> None:
        """Blocker 2b regression: a retry cannot add a second entry by rewording."""
        tracker, api = seeded_tracker()
        self.resolve(tracker, 4, "hermes/session-a", "Use SQLite.", "Storage: SQLite")
        again = self.resolve(
            tracker, 4, "hermes/session-a", "Use SQLite.", "Storage will be SQLite"
        )
        self.assertTrue(again.resolved)
        self.assertIn("indexed", again.already)
        decisions = tracker.map_decisions(1)
        self.assertEqual(len(decisions), 1)
        self.assertEqual(decisions[0]["gist"], "Storage: SQLite")

    def test_duplicate_index_records_replay_to_the_earliest(self) -> None:
        first = WF.ManagedRecord(
            comment_id=10, kind="index",
            fields={"key": "a" * 16, "map": "1", "ticket": "4",
                    "gist": "first wording", "session": "s/a", "at": T1},
        )
        rewrite = WF.ManagedRecord(
            comment_id=11, kind="index",
            fields={"key": "a" * 16, "map": "1", "ticket": "4",
                    "gist": "second wording", "session": "s/a", "at": T2},
        )
        other = WF.ManagedRecord(
            comment_id=12, kind="index",
            fields={"key": "b" * 16, "map": "1", "ticket": "2",
                    "gist": "other", "session": "s/b", "at": T2},
        )
        replayed = WF.index_replay([rewrite, first, other])
        self.assertEqual(
            [(r.comment_id, r.fields["gist"]) for r in replayed],
            [(10, "first wording"), (12, "other")],
        )

    def test_malformed_or_nonpositive_records_never_index(self) -> None:
        tracker, api = seeded_tracker()
        good = {"key": "a" * 16, "map": "1", "ticket": "4",
                "gist": "legit", "session": "s/a", "at": T1}
        # Wrong version.
        api.add_comment(1, WF.render_record("index", good).replace(
            "wayfinder:index v1", "wayfinder:index v0"))
        # Zero ticket.
        api.add_comment(1, WF.render_record("index", good).replace(
            "ticket: 4", "ticket: 0"))
        # Missing field.
        api.add_comment(1, WF.render_record("index", good).replace(
            "gist: legit\n", ""))
        # Carried by a nonpositive comment id.
        api.comments[1].append(
            {"id": -5, "body": WF.render_record("index", good), "created_at": T0}
        )
        api.comments[1].append(
            {"id": 0, "body": WF.render_record("index", good), "created_at": T0}
        )
        self.assertEqual(tracker.map_decisions(1), [])

    def test_a_swallowed_index_post_fails_closed_and_a_retry_converges(self) -> None:
        tracker, api = seeded_tracker()
        api.swallow.add("index")
        with self.assertRaises(WF.WayfinderError) as caught:
            self.resolve(
                tracker, 4, "hermes/session-a", "Chose flat.", "Storage shape: flat"
            )
        self.assertIn("did not read back", str(caught.exception))
        self.assertEqual(tracker.map_decisions(1), [])
        api.swallow.clear()
        out = self.resolve(
            tracker, 4, "hermes/session-a", "Chose flat.", "Storage shape: flat"
        )
        self.assertTrue(out.resolved)
        self.assertEqual(len(tracker.map_index_records(1)), 1)

    def test_a_mangled_stored_index_comment_fails_closed(self) -> None:
        """The API echoes what was sent while storing something else."""
        tracker, api = seeded_tracker()
        api.mangle_comment_body = "\n\nsurprise"
        with self.assertRaises(WF.WayfinderError):
            self.resolve(
                tracker, 4, "hermes/session-a", "Chose flat.", "Storage shape: flat"
            )

    def test_apply_requires_a_timestamp(self) -> None:
        tracker, _ = seeded_tracker()
        with self.assertRaises(WF.WayfinderError) as caught:
            tracker.resolve_ticket(
                map_number=1, number=4, session="hermes/session-a",
                claim_operation=op_for("hermes/session-a"),
                answer="a", map_index_line="Chose X", apply=True,
            )
        self.assertIn("--at is required", str(caught.exception))


# ==========================================================================
# Blocker 2 — a loser cleans up its own claim
# ==========================================================================


class ClaimCleanupTest(unittest.TestCase):
    """A contender that *posts* and then loses must withdraw its own claim.

    Two distinct paths matter, and only one of them can leave a zombie:

    * a foreign claim already visible at entry — we never post, so there is
      nothing to clean up;
    * a foreign claim that lands between our read and our post — we posted, we
      lost, and the record we left behind would become the active claim the
      moment the winner released.
    """

    def race(self, tracker, api, *, ticket=2, mine="hermes/late", theirs="claude/first",
             fail_release=False):
        """Run a claim that loses to an interleaved competitor."""
        posted: list[str] = []
        real_request = api.request

        def interleave(method, path, payload=None):
            body = (payload or {}).get("body", "")
            if (
                method.upper() == "POST"
                and path.endswith(f"/issues/{ticket}/comments")
                and "wayfinder:claim" in body
                and mine in body
                and not posted
            ):
                posted.append("x")
                api.add_comment(
                    ticket, WF.render_record("claim", {"session": theirs, "operation": op_for(theirs), "at": T0})
                )
            if (
                fail_release
                and method.upper() == "POST"
                and "wayfinder:release" in body
            ):
                raise WF.WayfinderError("injected release failure")
            return real_request(method, path, payload)

        api.request = interleave
        try:
            outcome = tracker.claim(
                map_number=1, number=ticket, session=mine, claimed_at=T1, apply=True,
                operation=op_for(mine),
            )
        finally:
            api.request = real_request
        self.assertTrue(posted, "the interleaved competitor never ran")
        return outcome

    def test_an_entry_detected_claim_posts_nothing_to_withdraw(self) -> None:
        tracker, api = seeded_tracker()
        before = len(api.comments.get(4, []))
        outcome = tracker.claim(
            map_number=1, number=4, session="claude/loser", claimed_at=T1, apply=True,
            operation=op_for("claude/loser"),
        )
        self.assertFalse(outcome.won)
        self.assertEqual(outcome.reason, "already claimed by another session")
        self.assertEqual(len(api.comments.get(4, [])), before, "nothing should be posted")

    def test_a_losing_contender_withdraws_its_own_claim(self) -> None:
        tracker, api = seeded_tracker()
        outcome = self.race(tracker, api)
        self.assertFalse(outcome.won)
        self.assertIn("withdrawn", outcome.reason)
        self.assertFalse(
            WF.acquisition_is_active(
                tracker.claim_records(2),
                hold="claim",
                drop="release",
                identity=claim_id("hermes/late", "hermes/late"),
            ),
            "the losing claim is still queued",
        )
        self.assertEqual(tracker.current_claim(2).session, "claude/first")

    def test_after_the_winner_releases_the_ticket_is_unclaimed(self) -> None:
        """The zombie-transfer regression, stated directly."""
        tracker, api = seeded_tracker()
        self.race(tracker, api)
        released = tracker.release(
            map_number=1, number=2, session="claude/first", released_at=T2, apply=True,
            operation=op_for("claude/first"),
        )
        self.assertTrue(released.won)
        self.assertIsNone(
            tracker.current_claim(2),
            "the ticket transferred to a session that already walked away",
        )

    def test_the_withdrawn_loser_can_claim_again_afterwards(self) -> None:
        """Withdrawing is not a ban — the loser may retry once the ticket frees."""
        tracker, api = seeded_tracker()
        self.race(tracker, api)
        tracker.release(
            map_number=1, number=2, session="claude/first", released_at=T2, apply=True,
            operation=op_for("claude/first"),
        )
        again = tracker.claim(
            map_number=1, number=2, session="hermes/late",
            operation=op_for("hermes/late"),
            claimed_at="2026-08-19T12:00:00Z", apply=True,
        )
        self.assertTrue(again.won)

    def test_a_failed_withdrawal_is_reported_rather_than_hidden(self) -> None:
        tracker, api = seeded_tracker()
        outcome = self.race(tracker, api, fail_release=True)
        self.assertFalse(outcome.won)
        self.assertIn("STILL QUEUED", outcome.reason)
        self.assertIn(
            op_for("hermes/late"),
            outcome.reason,
            "the exact operation to recover must be named, not just the session",
        )


# ==========================================================================
# Blocker 3 — preflight immediately before every resolution write
# ==========================================================================


class ResolutionPreflightTest(unittest.TestCase):
    ARGS = dict(
        map_number=1, number=4, session="hermes/session-a",
        claim_operation=op_for("hermes/session-a"),
        answer="Chose flat.", map_index_line="Storage shape: flat", at=T1, apply=True,
    )

    def resolve(self, tracker):
        return tracker.resolve_ticket(**self.ARGS)

    def test_going_public_between_steps_stops_before_the_next_write(self) -> None:
        for trigger, label in (
            ("/issues/4/comments", "after the comment"),
            ("/issues/1/comments", "after the index"),
        ):
            with self.subTest(step=label):
                tracker, api = seeded_tracker()
                real_request = api.request
                flipped: list[str] = []

                def flip(method, path, payload=None, _t=trigger):
                    result = real_request(method, path, payload)
                    if method.upper() in ("POST", "PATCH") and path.endswith(_t) and not flipped:
                        flipped.append("x")
                        api.private = False
                    return result

                api.request = flip
                with self.assertRaises(WF.WayfinderError) as caught:
                    self.resolve(tracker)
                api.request = real_request
                self.assertIn("public", str(caught.exception))
                self.assertTrue(flipped)
                # The map must not have been touched after the flip.
                self.assertNotIn(
                    "Storage shape: flat", WF.extract_managed_region(api.issues[1]["body"])
                )

    def test_removing_the_ticket_label_between_steps_stops(self) -> None:
        tracker, api = seeded_tracker()
        real_request = api.request
        stripped: list[str] = []

        def strip(method, path, payload=None):
            result = real_request(method, path, payload)
            if method.upper() == "POST" and path.endswith("/issues/4/comments") and not stripped:
                stripped.append("x")
                api.issues[4]["labels"] = []
            return result

        api.request = strip
        with self.assertRaises(WF.WayfinderError) as caught:
            self.resolve(tracker)
        api.request = real_request
        self.assertIn(WF.TICKET_LABEL, str(caught.exception))

    def test_losing_the_claim_between_steps_stops(self) -> None:
        tracker, api = seeded_tracker()
        real_request = api.request
        released: list[str] = []

        def steal(method, path, payload=None):
            result = real_request(method, path, payload)
            if method.upper() == "POST" and path.endswith("/issues/4/comments") and not released:
                released.append("x")
                api.add_comment(
                    4, WF.render_record("release", {"session": "hermes/session-a", "operation": op_for("hermes/session-a"), "at": T2})
                )
            return result

        api.request = steal
        with self.assertRaises(WF.WayfinderError) as caught:
            self.resolve(tracker)
        api.request = real_request
        self.assertIn("nothing holds the claim", str(caught.exception))

    def test_partial_state_stays_retryable(self) -> None:
        tracker, api = seeded_tracker()
        api.fail_on["patch-close"] = 1
        with self.assertRaises(WF.WayfinderError):
            self.resolve(tracker)
        api.fail_on.clear()
        outcome = self.resolve(tracker)
        self.assertIn("comment", outcome.already)
        self.assertIn("indexed", outcome.already)
        self.assertTrue(outcome.closed)
        self.assertTrue(outcome.resolved)
        gists = [d["gist"] for d in tracker.map_decisions(1)]
        self.assertEqual(gists.count("Storage shape: flat"), 1)


# ==========================================================================
# Blocker 4 — structural resolution parsing
# ==========================================================================


class ResolutionParsingTest(unittest.TestCase):
    KEY = "0123456789abcdef"

    def marker(self, **overrides) -> str:
        fields = {"key": self.KEY, "map": "1", "session": "hermes/s"}
        fields.update(overrides)
        return WF.render_record("resolution", fields)

    def found(self, comments) -> bool:
        return WF.find_resolution(comments, key=self.KEY, map_number=1, session="hermes/s")

    def test_an_exact_marker_is_found(self) -> None:
        body = "Answer.\n\n" + self.marker()
        self.assertTrue(self.found([{"id": 1, "body": body}]))

    def test_answer_prose_that_looks_like_a_marker_does_not_count(self) -> None:
        """Reported reproduction: a substring check was satisfied by the answer."""
        prose = f"We chose X. The key: {self.KEY} was mentioned in the ticket.\n"
        self.assertFalse(self.found([{"id": 1, "body": prose}]))

    def test_a_wrong_version_marker_does_not_count(self) -> None:
        """Reported reproduction: only the first block was read, any version."""
        stale = (
            f"<!-- wayfinder:resolution v9\nkey: {self.KEY}\nmap: 1\nsession: hermes/s\n-->"
        )
        self.assertFalse(self.found([{"id": 1, "body": stale}]))

    def test_a_wrong_map_marker_does_not_count(self) -> None:
        self.assertFalse(self.found([{"id": 1, "body": self.marker(map="99")}]))

    def test_a_wrong_session_marker_does_not_count(self) -> None:
        self.assertFalse(self.found([{"id": 1, "body": self.marker(session="other/one")}]))

    def test_a_wrong_key_marker_does_not_count(self) -> None:
        self.assertFalse(self.found([{"id": 1, "body": self.marker(key="f" * 16)}]))

    def test_a_marker_behind_another_block_is_still_found(self) -> None:
        """`search` read only the first block; `finditer` reads them all."""
        body = (
            WF.render_record("claim", {"session": "hermes/s", "operation": op_for("hermes/s"), "at": T0})
            + "\n\n"
            + self.marker()
        )
        self.assertTrue(self.found([{"id": 1, "body": body}]))

    def test_a_claim_record_is_not_a_resolution(self) -> None:
        body = WF.render_record("claim", {"session": "hermes/s", "operation": op_for("hermes/s"), "at": T0})
        self.assertFalse(self.found([{"id": 1, "body": body}]))

    def test_idempotency_does_not_trip_on_forged_prose(self) -> None:
        """End to end: a ticket whose answer mentions the key still resolves."""
        tracker, api = seeded_tracker()
        answer = "Chose flat."
        key = WF.resolution_key(1, 4, answer)
        api.add_comment(4, f"Earlier human note mentioning key: {key} in passing.")
        outcome = tracker.resolve_ticket(
            map_number=1, number=4, session="hermes/session-a",
            claim_operation=op_for("hermes/session-a"),
            answer=answer, map_index_line="Storage shape: flat", at=T1, apply=True,
        )
        self.assertTrue(outcome.commented, "prose must not satisfy the idempotency check")


# ==========================================================================
# Blocker 5 — map index entry validation
# ==========================================================================


class IndexLineTest(unittest.TestCase):
    def test_a_normal_entry_is_accepted(self) -> None:
        self.assertEqual(
            WF.validate_index_line("  Storage shape: flat  "), "Storage shape: flat"
        )
        self.assertEqual(WF.validate_index_line("- Already bulleted"), "- Already bulleted")

    def test_refused_shapes(self) -> None:
        cases = {
            "empty": "",
            "whitespace": "   ",
            "newline": "first line\nsecond line",
            "carriage return": "first\rsecond",
            "heading": "# Not a decision",
            "bulleted heading": "- ## Sneaky",
            "dash only": "-",
            "bullet only": "-   ",
            "stars only": "***",
            "html comment open": "text <!-- hidden",
            "html comment close": "text --> tail",
            "managed marker": "wayfinder:map:begin v1",
            "too long": "x" * (WF.MAX_INDEX_LINE + 1),
        }
        for label, value in cases.items():
            with self.subTest(case=label), self.assertRaises(WF.WayfinderError):
                WF.validate_index_line(value)

    def test_a_bad_entry_produces_zero_writes_even_in_preview(self) -> None:
        tracker, api = seeded_tracker()
        before = [c for c in api.calls if c[0] in ("POST", "PATCH")]
        for value in ("", "a\nb", "# heading", "-", "x <!-- y"):
            with self.subTest(value=value):
                with self.assertRaises(WF.WayfinderError):
                    tracker.resolve_ticket(
                        map_number=1, number=4, session="hermes/session-a",
                        claim_operation=op_for("hermes/session-a"),
                        answer="a", map_index_line=value,
                    )
                with self.assertRaises(WF.WayfinderError):
                    tracker.resolve_ticket(
                        map_number=1, number=4, session="hermes/session-a",
                        claim_operation=op_for("hermes/session-a"),
                        answer="a", map_index_line=value, at=T1, apply=True,
                    )
        self.assertEqual([c for c in api.calls if c[0] in ("POST", "PATCH")], before)

    def test_a_record_field_cannot_forge_or_close_its_block(self) -> None:
        for value in ("has\nnewline", "closes --> here", "  "):
            with self.subTest(value=value), self.assertRaises(WF.WayfinderError):
                WF.render_record("claim", {"session": value, "operation": op_for(value), "at": T0})

    def test_an_unknown_record_kind_is_refused(self) -> None:
        with self.assertRaises(WF.WayfinderError):
            WF.render_record("mischief", {"session": "a", "at": T0})


# ==========================================================================
# Blocker 6 — map identity
# ==========================================================================


class SingleLineTest(unittest.TestCase):
    """"One line" means the parser's notion of a line, not just CR/LF.

    `parse_exact_block` splits with `str.splitlines()`, which also breaks on
    U+2028/U+2029, NEL, VT, and FF. A gist that renders as one line but parses
    as two is a record the writer emits and its own reader rejects — the
    resolution would report indexed=True while the replay never shows it, and
    every retry would post another permanently-invalid record.
    """

    SEPARATORS = ("\u2028", "\u2029", "\x85", "\x0b", "\x0c")

    def test_a_gist_with_any_line_separator_is_refused(self) -> None:
        for sep in self.SEPARATORS:
            with self.subTest(sep=repr(sep)):
                with self.assertRaises(WF.WayfinderError):
                    WF.validate_index_line(f"decided foo{sep}session: forged")

    def test_a_record_field_with_any_line_separator_is_refused(self) -> None:
        for sep in self.SEPARATORS:
            with self.subTest(sep=repr(sep)):
                with self.assertRaises(WF.WayfinderError):
                    WF.render_record(
                        "index",
                        {
                            "session": "s/a", "key": "a" * 16, "map": "1",
                            "ticket": "4", "gist": f"x{sep}y", "at": T0,
                        },
                    )

    def test_every_rendered_record_reparses_whole(self) -> None:
        """The writer/reader round trip that finding relied on breaking."""
        fields = {
            "session": "s/a", "key": "b" * 16, "map": "1",
            "ticket": "4", "gist": "Storage: flat, because: cheap", "at": T0,
        }
        body = WF.render_index_comment(fields)
        records = WF.parse_records([{"id": 7, "body": body}], kinds=("index",))
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0].fields, fields)


class ManagedMarkerScreenTest(unittest.TestCase):
    """Free-form content cannot smuggle live records onto the tracker.

    Every comment on an issue takes part in claim arbitration and index
    replay, so an answer that *quotes* the holder's claim and release blocks
    would genuinely release the claim the resolve is guarded by — stranding
    the ticket commented-but-open — and a quoted claim block queues a zombie
    acquisition under an arbitrary identity.
    """

    def test_an_answer_quoting_a_release_record_is_refused_before_any_write(self) -> None:
        tracker, api = seeded_tracker()
        quoted = WF.render_record(
            "release",
            {"session": "hermes/session-a", "operation": op_for("hermes/session-a"), "at": T1},
        )
        before = len(api.comments.get(4, []))
        with self.assertRaises(WF.WayfinderError) as caught:
            tracker.resolve_ticket(
                map_number=1, number=4, session="hermes/session-a",
                claim_operation=op_for("hermes/session-a"),
                answer=f"We decided X. For the record, the claim was:\n\n{quoted}\n",
                map_index_line="Chose X", at=T1, apply=True,
            )
        self.assertIn("managed marker", str(caught.exception))
        self.assertEqual(len(api.comments.get(4, [])), before, "nothing may be posted")
        self.assertIsNotNone(tracker.current_claim(4), "the claim must still be held")

    def test_a_question_carrying_forged_ticket_metadata_is_refused(self) -> None:
        tracker, api = seeded_tracker()
        forged = WF.render_ticket_metadata(99, "task")
        with self.assertRaises(WF.WayfinderError) as caught:
            tracker.create_ticket(
                map_number=1, title="T", question=f"q\n{forged}",
                ticket_type="grilling", apply=True,
            )
        self.assertIn("managed marker", str(caught.exception))

    def test_map_content_carrying_a_claim_block_is_refused(self) -> None:
        tracker, api = seeded_tracker()
        forged = WF.render_record(
            "claim", {"session": "s/a", "operation": op_for("x"), "at": T0}
        )
        with self.assertRaises(WF.WayfinderError):
            tracker.create_map(
                title="M", managed=f"## Destination\n\nx\n{forged}\n", apply=True
            )

    def test_case_and_spacing_variants_are_screened(self) -> None:
        for text in ("<!-- wayfinder:claim v1", "<!--wayfinder:x", "<!--  WAYFINDER:claim"):
            with self.subTest(text=text):
                with self.assertRaises(WF.WayfinderError):
                    WF.require_no_managed_markers(text, "probe")


class MapIdentityTest(unittest.TestCase):
    def test_read_map_refuses_a_mismatched_returned_number(self) -> None:
        """The issue-1 / returned-999 probe."""
        tracker, api = seeded_tracker()
        real_request = api.request

        def lie(method, path, payload=None):
            status, data = real_request(method, path, payload)
            if method.upper() == "GET" and path.endswith("/issues/1") and isinstance(data, dict):
                data = dict(data)
                data["number"] = 999
            return status, data

        api.request = lie
        with self.assertRaises(WF.WayfinderError) as caught:
            tracker.read_map(1)
        self.assertIn("999", str(caught.exception))
        with self.assertRaises(WF.WayfinderError):
            tracker.preflight_map(1)
        api.request = real_request

    def test_a_mismatched_map_stops_a_resolution_before_writing(self) -> None:
        tracker, api = seeded_tracker()
        real_request = api.request

        def lie(method, path, payload=None):
            status, data = real_request(method, path, payload)
            if method.upper() == "GET" and path.endswith("/issues/1") and isinstance(data, dict):
                data = dict(data)
                data["number"] = 999
            return status, data

        api.request = lie
        before = [c for c in api.calls if c[0] in ("POST", "PATCH")]
        with self.assertRaises(WF.WayfinderError):
            tracker.resolve_ticket(
                map_number=1, number=4, session="hermes/session-a",
                claim_operation=op_for("hermes/session-a"),
                answer="a", map_index_line="Chose X", at=T1, apply=True,
            )
        api.request = real_request
        self.assertEqual([c for c in api.calls if c[0] in ("POST", "PATCH")], before)


# ==========================================================================
# Managed regions, scoping, pagination, and previews
# ==========================================================================


class ManagedRegionTest(unittest.TestCase):
    def test_replacing_the_region_preserves_surrounding_prose(self) -> None:
        body = f"BEFORE\n\n{WF.MAP_BEGIN}\nold\n{WF.MAP_END}\n\nAFTER\n"
        updated = WF.replace_managed_region(body, "new")
        self.assertTrue(updated.startswith("BEFORE"))
        self.assertTrue(updated.rstrip().endswith("AFTER"))
        self.assertIn("new", updated)
        self.assertNotIn("old", updated)

    def test_a_body_with_no_region_gains_one_without_losing_prose(self) -> None:
        updated = WF.replace_managed_region("Someone wrote this by hand.\n", "managed")
        self.assertIn("Someone wrote this by hand.", updated)
        self.assertEqual(WF.extract_managed_region(updated), "managed")

    def test_an_unbalanced_region_is_refused(self) -> None:
        with self.assertRaises(WF.WayfinderError):
            WF.replace_managed_region(f"text {WF.MAP_BEGIN} no end", "managed")

    def test_no_body_index_helpers_survive(self) -> None:
        """The decision index moved out of the map body, permanently.

        A helper that merges text into the managed region is exactly the write
        that cannot be made safe against a concurrent human edit, so its
        reappearance is a design regression, not a refactor.
        """
        for name in ("append_decision", "has_decision"):
            self.assertFalse(hasattr(WF, name), f"{name} must not come back")

    def test_a_direct_patch_performs_no_preceding_read(self) -> None:
        """The staleness guard moved into `enforce`, and had to.

        The old helper did GET-then-PATCH, which put a network round trip
        between the guard's privacy check and the mutation — the exact window
        `enforce` exists to close. The guard now reads the issue itself,
        immediately before the write, so its read *is* the fresh one and the
        write closure issues a bare PATCH.
        """
        tracker, api = seeded_tracker()
        before = list(api.calls)
        tracker._patch_issue_direct(2, {"body": "x"})
        added = api.calls[len(before):]
        self.assertEqual(
            added,
            [("PATCH", f"{REPO.api_base}/issues/2")],
            "a direct patch must be exactly one request",
        )
        self.assertFalse(
            hasattr(tracker, "_patch_issue"),
            "the read-then-patch helper must not come back",
        )


class FrontierTest(unittest.TestCase):
    def ticket(self, number, **kwargs) -> WF.Ticket:
        defaults = dict(title=f"T{number}", state="open", map_number=1, ticket_type="grilling")
        defaults.update(kwargs)
        return WF.Ticket(number=number, **defaults)

    def test_open_unblocked_unclaimed_in_stable_order(self) -> None:
        tickets = [
            self.ticket(5),
            self.ticket(2),
            self.ticket(9, state="closed"),
            self.ticket(7, blocked_by=(2,)),
            self.ticket(8, claim={"session": "other", "at": T0}),
        ]
        self.assertEqual([t.number for t in WF.compute_frontier(tickets)], [2, 5])

    def test_a_ticket_unblocks_when_its_blocker_closes(self) -> None:
        blocked = self.ticket(7, blocked_by=(2,))
        self.assertEqual(
            [t.number for t in WF.compute_frontier([self.ticket(2), blocked])], [2]
        )
        self.assertEqual(
            [t.number for t in WF.compute_frontier([self.ticket(2, state="closed"), blocked])],
            [7],
        )

    def test_an_unknown_blocker_keeps_a_ticket_off_the_frontier(self) -> None:
        self.assertEqual(WF.compute_frontier([self.ticket(7, blocked_by=(99,))]), [])

    def test_reads_the_frontier_from_the_tracker(self) -> None:
        tracker, _ = seeded_tracker()
        self.assertEqual([t.number for t in tracker.frontier(1)], [2])


class ScopingTest(unittest.TestCase):
    def test_tickets_from_another_map_are_ignored(self) -> None:
        tracker, api = seeded_tracker()
        api.add_issue(
            title="Someone else's ticket",
            body=ticket_body("Not ours", 99),
            labels=[WF.TICKET_LABEL, "wayfinder:grilling"],
            number=50,
        )
        self.assertNotIn(50, [t.number for t in tracker.list_tickets(1)])

    def test_a_wrong_version_ticket_is_not_listed(self) -> None:
        tracker, api = seeded_tracker()
        api.add_issue(
            title="Future",
            body="<!-- wayfinder:ticket v9\nmap: 1\ntype: grilling\n-->\n",
            labels=[WF.TICKET_LABEL],
            number=51,
        )
        self.assertNotIn(51, [t.number for t in tracker.list_tickets(1)])

    def test_an_unlabelled_issue_is_not_treated_as_a_map(self) -> None:
        tracker, api = seeded_tracker()
        api.add_issue(title="Ordinary issue", body="hello", labels=[], number=60)
        with self.assertRaises(WF.WayfinderError):
            tracker.read_map(60)


class PaginationTest(unittest.TestCase):
    """A frontier computed from a truncated listing hands out unsafe work."""

    def test_tickets_beyond_the_first_page_are_still_found(self) -> None:
        tracker, api = seeded_tracker()
        for number in range(100, 100 + WF.PAGE_SIZE * 2):
            api.add_issue(title=f"noise {number}", body="unrelated", labels=[], number=number)
        far = api.add_issue(
            title="Late ticket",
            body=ticket_body("Asked last", 1),
            labels=[WF.TICKET_LABEL],
            number=500,
        )
        self.assertIn(far, [t.number for t in tracker.list_tickets(1)])

    def test_pagination_stops_on_a_short_page(self) -> None:
        tracker, api = seeded_tracker()
        before = len(api.calls)
        tracker.list_tickets(1)
        listings = [c for c in api.calls[before:] if "/issues?" in c[1]]
        self.assertEqual(len(listings), 1, "a short first page needs no second request")

    def test_an_unbounded_listing_raises_rather_than_truncating(self) -> None:
        tracker, api = seeded_tracker()

        def endless(method, path, payload=None):
            if method.upper() == "GET" and "/issues?" in path:
                return 200, [
                    {"number": i, "title": "x", "body": "", "state": "open", "labels": []}
                    for i in range(WF.PAGE_SIZE)
                ]
            return FakeForgejo.request(api, method, path, payload)

        api.request = endless  # type: ignore[method-assign]
        with self.assertRaises(WF.WayfinderError) as caught:
            tracker.list_tickets(1)
        self.assertIn("truncated", str(caught.exception))


class PreviewTest(unittest.TestCase):
    def test_every_mutation_previews_by_default(self) -> None:
        tracker, api = seeded_tracker()
        writes_before = [c for c in api.calls if c[0] in ("POST", "PATCH")]
        previews = [
            tracker.create_map(title="M", managed="## Destination"),
            tracker.create_ticket(map_number=1, title="T", question="Q", ticket_type="task"),
            tracker.wire_blocking(map_number=1, blocked=3, blocked_by=2),
            tracker.claim(map_number=1, number=2, session="s/1", operation=op_for("s/1"), claimed_at=T1),
            tracker.release(map_number=1, number=4, session="hermes/session-a", operation=op_for("hermes/session-a"), released_at=T1),
            tracker.resolve_ticket(
                map_number=1, number=4, session="hermes/session-a",
                claim_operation=op_for("hermes/session-a"),
                answer="Because.", map_index_line="Chose X",
            ),
        ]
        for preview in previews:
            with self.subTest(operation=getattr(preview, "operation", preview)):
                self.assertIsInstance(preview, WF.Preview)
        self.assertEqual([c for c in api.calls if c[0] in ("POST", "PATCH")], writes_before)

    def test_preview_shows_the_exact_content_that_would_be_written(self) -> None:
        tracker, _ = seeded_tracker()
        preview = tracker.create_ticket(
            map_number=1, title="Pick a shape", question="Which shape?", ticket_type="grilling"
        )
        rendered = preview.render()
        self.assertIn("DRY RUN", rendered)
        self.assertIn("Which shape?", rendered)
        self.assertIn("map: 1", rendered)
        self.assertIn("--apply", rendered)


class ApplyTest(unittest.TestCase):
    def test_creating_a_ticket_reads_back_its_metadata(self) -> None:
        tracker, _ = seeded_tracker()
        ticket = tracker.create_ticket(
            map_number=1, title="New", question="Why?", ticket_type="task",
            creation=op_for("new"), apply=True,
        )
        self.assertEqual((ticket.map_number, ticket.ticket_type), (1, "task"))

    def test_wiring_blocking_verifies_the_dependency_read_back(self) -> None:
        tracker, api = seeded_tracker()
        blockers = tracker.wire_blocking(map_number=1, blocked=2, blocked_by=3, apply=True)
        self.assertIn(3, blockers)

    def test_a_dependency_that_does_not_persist_raises(self) -> None:
        tracker, api = seeded_tracker()

        def swallow(method, path, payload=None):
            if path.endswith("/dependencies") and method.upper() == "POST":
                return 201, {}
            return FakeForgejo.request(api, method, path, payload)

        api.request = swallow  # type: ignore[method-assign]
        with self.assertRaises(WF.WayfinderError) as caught:
            tracker.wire_blocking(map_number=1, blocked=2, blocked_by=3, apply=True)
        self.assertIn("not exactly [3]", str(caught.exception))


class CliTest(unittest.TestCase):
    def _reject(self, argv: list[str]) -> None:
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            WF.build_parser().parse_args(argv)

    def test_apply_is_opt_in(self) -> None:
        args = WF.build_parser().parse_args(
            ["--origin", "ssh://f@h.test/o/r.git", "--tracker", "o/r", "frontier", "--map", "1"]
        )
        self.assertFalse(args.apply)

    def test_tracker_and_origin_are_both_required(self) -> None:
        self._reject(["frontier", "--map", "1"])

    def test_unknown_ticket_type_is_rejected_at_the_boundary(self) -> None:
        self._reject(
            [
                "--origin", "ssh://f@h.test/o/r.git", "--tracker", "o/r",
                "create-ticket", "--map", "1", "--title", "T",
                "--question-file", "q.md", "--type", "vibes",
            ]
        )

    def test_release_requires_a_timestamp(self) -> None:
        self._reject(
            [
                "--origin", "ssh://f@h.test/o/r.git", "--tracker", "o/r",
                "release", "--map", "1", "--ticket", "2", "--session", "s",
                "--operation", op_for("o"),
            ]
        )

    def test_release_requires_an_operation(self) -> None:
        """There is no session-only release: it would clear a sibling's claim."""
        self._reject(
            [
                "--origin", "ssh://f@h.test/o/r.git", "--tracker", "o/r",
                "release", "--map", "1", "--ticket", "2", "--session", "s",
                "--at", T1,
            ]
        )

    def test_resolve_requires_an_operation(self) -> None:
        self._reject(
            [
                "--origin", "ssh://f@h.test/o/r.git", "--tracker", "o/r",
                "resolve", "--map", "1", "--ticket", "2", "--session", "s",
                "--answer-file", "a.md", "--index-line", "Chose X", "--at", T1,
            ]
        )

    def test_the_lock_subcommands_are_gone(self) -> None:
        """No map body write exists, so no lock or lock recovery may either."""
        for command in ("release-map-lock", "map-lock"):
            with self.subTest(command=command):
                self._reject(
                    [
                        "--origin", "ssh://f@h.test/o/r.git", "--tracker", "o/r",
                        command, "--map", "1",
                    ]
                )

    def test_claim_may_mint_its_own_operation(self) -> None:
        """`claim` is the one place an operation id may be omitted."""
        parser = WF.build_parser()
        args = parser.parse_args(
            [
                "--origin", "ssh://f@h.test/o/r.git", "--tracker", "o/r",
                "claim", "--map", "1", "--ticket", "2", "--session", "s",
                "--at", T1,
            ]
        )
        self.assertIsNone(args.operation)

    def test_claim_status_is_available_for_inspection(self) -> None:
        parser = WF.build_parser()
        args = parser.parse_args(
            [
                "--origin", "ssh://f@h.test/o/r.git", "--tracker", "o/r",
                "claim-status", "--map", "1", "--ticket", "2",
            ]
        )
        self.assertEqual(args.command, "claim-status")


# ==========================================================================
# Cycle-1 item 2 — operation identity is ownership identity
# ==========================================================================


class OperationIdentityTest(unittest.TestCase):
    """A session is not a lock token; an operation is.

    Every test here fails under session-keyed arbitration, which is the point:
    a session legitimately runs nested and concurrent operations, and each one
    needs its own critical section.
    """

    def records(self, *rows) -> list[WF.ManagedRecord]:
        built = [
            {
                "id": cid,
                "body": WF.render_record(
                    kind, {"session": s, "operation": op_for(op), "at": at}
                ),
            }
            for cid, kind, s, op, at in rows
        ]
        return WF.parse_records(built)

    # -- arbitration ----------------------------------------------------

    def test_one_release_does_not_clear_a_sibling_operation(self) -> None:
        """The self-inflicted lost lock: same session, two operations."""
        records = self.records(
            (10, "claim", "hermes/s", "outer", T0),
            (11, "release", "hermes/s", "outer", T2),
        )
        self.assertIsNone(WF.active_claim(records))

        nested = self.records(
            (10, "claim", "hermes/s", "outer", T0),
            (11, "claim", "hermes/s", "inner", T1),
            (12, "release", "hermes/s", "inner", T2),
        )
        holder = WF.active_claim(nested)
        self.assertIsNotNone(holder, "releasing the inner operation cleared the outer one")
        self.assertEqual(holder.operation, op_for("outer"))

    def test_nested_same_session_claims_do_not_coalesce(self) -> None:
        records = self.records(
            (10, "claim", "hermes/s", "outer", T0),
            (11, "claim", "hermes/s", "inner", T1),
        )
        self.assertTrue(
            WF.acquisition_is_active(
                records,
                hold="claim",
                drop="release",
                identity=claim_id("inner", "hermes/s"),
            ),
            "the second operation was swallowed into the first",
        )
        self.assertEqual(WF.active_claim(records).operation, op_for("outer"))

    def test_a_repeated_identical_operation_is_one_hold(self) -> None:
        """An idempotent retry recognizes itself instead of queueing again."""
        records = self.records(
            (10, "claim", "hermes/s", "same", T0),
            (11, "claim", "hermes/s", "same", T1),
            (12, "release", "hermes/s", "same", T2),
        )
        self.assertIsNone(WF.active_claim(records))

    def test_a_release_naming_an_unknown_operation_clears_nothing(self) -> None:
        records = self.records(
            (10, "claim", "hermes/s", "mine", T0),
            (11, "release", "hermes/s", "someone-elses", T1),
        )
        self.assertEqual(WF.active_claim(records).operation, op_for("mine"))

    # -- claims ---------------------------------------------------------

    def test_a_second_same_session_claim_with_a_new_operation_is_refused(self) -> None:
        tracker, api = seeded_tracker()
        first = tracker.claim(
            map_number=1, number=2, session="hermes/s", claimed_at=T1,
            operation=op_for("outer"), apply=True,
        )
        self.assertTrue(first.won)
        before = len(api.comments.get(2, []))
        second = tracker.claim(
            map_number=1, number=2, session="hermes/s", claimed_at=T2,
            operation=op_for("inner"), apply=True,
        )
        self.assertFalse(second.won, "one session held two overlapping claims")
        self.assertIn("another operation of this same session", second.reason)
        self.assertEqual(
            len(api.comments.get(2, [])), before, "the refusal must write nothing"
        )

    def test_an_idempotent_retry_with_the_same_operation_posts_nothing(self) -> None:
        tracker, api = seeded_tracker()
        first = tracker.claim(
            map_number=1, number=2, session="hermes/s", claimed_at=T1,
            operation=op_for("retry"), apply=True,
        )
        before = len(api.comments.get(2, []))
        again = tracker.claim(
            map_number=1, number=2, session="hermes/s", claimed_at=T2,
            operation=op_for("retry"), apply=True,
        )
        self.assertTrue(again.won)
        self.assertIn("idempotent retry", again.reason)
        self.assertEqual(again.operation, first.operation)
        self.assertEqual(len(api.comments.get(2, [])), before)

    def test_a_preview_mints_an_unguessable_operation(self) -> None:
        """Minting lives in the preview; apply posts only the reviewed record."""
        tracker, _ = seeded_tracker()
        operations = []
        for _ in range(2):
            preview = tracker.claim(
                map_number=1, number=2, session="hermes/s", claimed_at=T1
            )
            record = preview.content[0]["text"]
            blocks = WF.iter_record_blocks(record)
            self.assertEqual(len(blocks), 1)
            operations.append(blocks[0][2]["operation"])
        self.assertRegex(operations[0], r"\A[a-f0-9]{32}\Z")
        self.assertNotEqual(
            operations[0], operations[1], "operation ids must not be derivable"
        )

    def test_releasing_a_foreign_operation_is_refused(self) -> None:
        tracker, api = seeded_tracker()
        before = len(api.comments.get(4, []))
        outcome = tracker.release(
            map_number=1, number=4, session="hermes/session-a", released_at=T1,
            operation=op_for("never-claimed"), apply=True,
        )
        self.assertFalse(outcome.won)
        self.assertIn("never claimed", outcome.reason)
        self.assertEqual(len(api.comments.get(4, [])), before)
        self.assertEqual(
            tracker.current_claim(4).operation, op_for("hermes/session-a")
        )

    def test_releasing_another_sessions_operation_is_refused(self) -> None:
        """Knowing the operation id is not authority to release it."""
        tracker, api = seeded_tracker()
        before = len(api.comments.get(4, []))
        outcome = tracker.release(
            map_number=1, number=4, session="claude/impostor", released_at=T1,
            operation=op_for("hermes/session-a"), apply=True,
        )
        self.assertFalse(outcome.won)
        self.assertIn("refusing to release another session", outcome.reason)
        self.assertEqual(len(api.comments.get(4, [])), before)

    def test_releasing_one_operation_leaves_the_sessions_other_claim(self) -> None:
        tracker, api = seeded_tracker()
        tracker.claim(
            map_number=1, number=2, session="hermes/s", claimed_at=T1,
            operation=op_for("on-two"), apply=True,
        )
        tracker.claim(
            map_number=1, number=3, session="hermes/s", claimed_at=T1,
            operation=op_for("on-three"), apply=True,
        )
        tracker.release(
            map_number=1, number=2, session="hermes/s", released_at=T2,
            operation=op_for("on-two"), apply=True,
        )
        self.assertIsNone(tracker.current_claim(2))
        self.assertEqual(tracker.current_claim(3).operation, op_for("on-three"))

    def test_a_second_release_of_the_same_operation_is_idempotent(self) -> None:
        tracker, api = seeded_tracker()
        tracker.release(
            map_number=1, number=4, session="hermes/session-a", released_at=T1,
            operation=op_for("hermes/session-a"), apply=True,
        )
        before = len(api.comments.get(4, []))
        again = tracker.release(
            map_number=1, number=4, session="hermes/session-a", released_at=T2,
            operation=op_for("hermes/session-a"), apply=True,
        )
        self.assertTrue(again.won)
        self.assertIn("idempotent retry", again.reason)
        self.assertEqual(len(api.comments.get(4, [])), before)


    def test_concurrent_different_sessions_still_produce_exactly_one_winner(self) -> None:
        tracker_a, api = seeded_tracker()
        tracker_b = WF.WayfinderTracker(api, REPO)
        first = tracker_a.claim(
            map_number=1, number=2, session="hermes/a", claimed_at=T1,
            operation=op_for("a"), apply=True,
        )
        second = tracker_b.claim(
            map_number=1, number=2, session="claude/b", claimed_at=T2,
            operation=op_for("b"), apply=True,
        )
        self.assertEqual([first.won, second.won], [True, False])
        self.assertEqual(second.holder["operation"], op_for("a"))
        self.assertFalse(
            WF.acquisition_is_active(
                tracker_a.claim_records(2),
                hold="claim",
                drop="release",
                identity=claim_id("b", "claude/b"),
            ),
            "the loser left a queued claim behind",
        )


# ==========================================================================
# Cycle-1 item 3 — exact managed-record schemas
# ==========================================================================


class RecordSchemaTest(unittest.TestCase):
    """A record that is not exactly right never arbitrates.

    Permissive parsing is how a truncated write, a hand-edited comment, or a
    forged block silently takes a lock.
    """

    GOOD = {
        "claim": {"session": "hermes/s", "operation": op_for("o"), "at": T0},
        "release": {"session": "hermes/s", "operation": op_for("o"), "at": T0},
        "resolution": {
            "session": "hermes/s", "key": WF.resolution_key(1, 2, "a"), "map": "1"
        },
        "index": {
            "session": "hermes/s", "key": WF.resolution_key(1, 2, "a"), "map": "1",
            "ticket": "4", "gist": "Storage shape: flat", "at": T0
        },
    }

    def block(self, kind: str, lines: str) -> str:
        return f"<!-- wayfinder:{kind} v1\n{lines}\n-->"

    def rendered(self, kind: str, **overrides) -> str:
        fields = dict(self.GOOD[kind])
        fields.update(overrides)
        return "\n".join(f"{k}: {v}" for k, v in sorted(fields.items()))

    def test_every_good_record_round_trips(self) -> None:
        for kind, fields in self.GOOD.items():
            with self.subTest(kind=kind):
                parsed = WF.parse_schema_block(kind, self.rendered(kind))
                self.assertEqual(parsed, fields)

    def test_a_missing_key_is_rejected_for_every_kind(self) -> None:
        for kind, fields in self.GOOD.items():
            for key in fields:
                with self.subTest(kind=kind, missing=key):
                    lines = "\n".join(
                        f"{k}: {v}" for k, v in sorted(fields.items()) if k != key
                    )
                    self.assertIsNone(WF.parse_schema_block(kind, lines))

    def test_an_unknown_key_is_rejected_for_every_kind(self) -> None:
        for kind in self.GOOD:
            with self.subTest(kind=kind):
                self.assertIsNone(
                    WF.parse_schema_block(
                        kind, self.rendered(kind) + "\nsmuggled: yes"
                    )
                )

    def test_a_duplicate_key_is_rejected_rather_than_last_wins(self) -> None:
        for kind in self.GOOD:
            with self.subTest(kind=kind):
                self.assertIsNone(
                    WF.parse_schema_block(
                        kind, self.rendered(kind) + "\nsession: someone/else"
                    )
                )

    def test_an_empty_value_is_rejected(self) -> None:
        for kind, fields in self.GOOD.items():
            for key in fields:
                with self.subTest(kind=kind, empty=key):
                    self.assertIsNone(
                        WF.parse_schema_block(kind, self.rendered(kind, **{key: ""}))
                    )

    def test_a_line_that_is_not_key_value_is_rejected(self) -> None:
        for kind in self.GOOD:
            with self.subTest(kind=kind):
                self.assertIsNone(
                    WF.parse_schema_block(kind, self.rendered(kind) + "\nnonsense")
                )

    def test_wrong_kind_fields_are_rejected(self) -> None:
        """An index record's fields do not make a claim, and vice versa."""
        self.assertIsNone(WF.parse_schema_block("claim", self.rendered("index")))
        self.assertIsNone(WF.parse_schema_block("index", self.rendered("claim")))
        self.assertIsNone(WF.parse_schema_block("claim", self.rendered("resolution")))
        self.assertIsNone(WF.parse_schema_block("unknown-kind", self.rendered("claim")))

    def test_malformed_values_are_rejected_field_by_field(self) -> None:
        cases = [
            ("claim", "session", "has space"),
            ("claim", "session", "-leading-dash"),
            ("claim", "operation", "not-hex"),
            ("claim", "operation", op_for("o")[:31]),
            ("claim", "operation", op_for("o").upper()),
            ("claim", "at", "yesterday"),
            ("claim", "at", "2026-08-19 09:00:00Z"),
            ("index", "ticket", "-1"),
            ("index", "ticket", "4.0"),
            ("index", "ticket", "01"),
            ("index", "gist", "## a heading"),
            ("index", "gist", "- "),
            ("index", "gist", "x" * 301),
            ("index", "gist", "wayfinder: marker text"),
            ("resolution", "key", "abc"),
            ("resolution", "key", WF.resolution_key(1, 2, "a") + "0"),
            ("resolution", "map", "one"),
        ]
        for kind, key, value in cases:
            with self.subTest(kind=kind, key=key, value=value):
                self.assertIsNone(
                    WF.parse_schema_block(kind, self.rendered(kind, **{key: value}))
                )

    def test_a_wrong_version_block_never_parses(self) -> None:
        body = f"<!-- wayfinder:claim v9\n{self.rendered('claim')}\n-->"
        self.assertEqual(WF.iter_record_blocks(body), [("claim", "v9", None)])
        self.assertEqual(WF.parse_records([{"id": 1, "body": body}]), [])

    def test_an_invalid_record_cannot_arbitrate(self) -> None:
        bad = self.block("claim", self.rendered("claim", operation="short"))
        good = self.block("claim", self.rendered("claim"))
        comments = [{"id": 10, "body": bad}, {"id": 11, "body": good}]
        holder = WF.active_claim(WF.parse_records(comments))
        self.assertIsNotNone(holder)
        self.assertEqual(holder.comment_id, 11, "a malformed record took the lock")

    def test_an_invalid_resolution_marker_never_satisfies_idempotency(self) -> None:
        key = WF.resolution_key(1, 2, "answer")
        good = self.block("resolution", f"key: {key}\nmap: 1\nsession: hermes/s")
        smuggled = self.block(
            "resolution", f"key: {key}\nmap: 1\nsession: hermes/s\nextra: 1"
        )
        duplicated = self.block(
            "resolution", f"key: {key}\nkey: {key}\nmap: 1\nsession: hermes/s"
        )
        for body in (smuggled, duplicated):
            with self.subTest(body=body):
                self.assertFalse(
                    WF.find_resolution(
                        [{"id": 1, "body": body}],
                        key=key,
                        map_number=1,
                        session="hermes/s",
                    )
                )
        self.assertTrue(
            WF.find_resolution(
                [{"id": 1, "body": good}], key=key, map_number=1, session="hermes/s"
            )
        )

    def test_render_refuses_what_parse_would_reject(self) -> None:
        """The writer and the reader share one schema, by construction."""
        with self.assertRaises(WF.WayfinderError) as caught:
            WF.render_record("claim", {"session": "hermes/s", "at": T0})
        self.assertIn("missing ['operation']", str(caught.exception))
        with self.assertRaises(WF.WayfinderError):
            WF.render_record(
                "claim",
                {"session": "hermes/s", "operation": op_for("o"), "at": T0, "extra": "x"},
            )
        with self.assertRaises(WF.WayfinderError) as caught:
            WF.render_record(
                "claim", {"session": "hermes/s", "operation": "nope", "at": T0}
            )
        self.assertIn("does not match its schema", str(caught.exception))

    def test_every_rendered_record_parses_back_identically(self) -> None:
        for kind, fields in self.GOOD.items():
            with self.subTest(kind=kind):
                body = WF.render_record(kind, fields)
                blocks = WF.iter_record_blocks(body)
                self.assertEqual(blocks, [(kind, WF.METADATA_VERSION, fields)])

    def test_a_malformed_operation_is_refused_at_the_api_boundary(self) -> None:
        tracker, _ = seeded_tracker()
        for value in ("", "nope", op_for("o")[:8], "../../etc/passwd"):
            with self.subTest(value=value):
                with self.assertRaises(WF.WayfinderError):
                    tracker.release(
                        map_number=1, number=4, session="hermes/session-a",
                        released_at=T1, operation=value, apply=True,
                    )


# ==========================================================================
# Cycle-1 item 4 — one guarded-write path for every mutation
# ==========================================================================


def claimed_tracker(**kwargs):
    """A seeded tracker where #2 is held by a known operation."""
    tracker, api = seeded_tracker(**kwargs)
    tracker.claim(
        map_number=1, number=2, session="hermes/s", claimed_at=T1,
        operation=op_for("c2"), apply=True,
    )
    return tracker, api


class GuardedWriteTest(unittest.TestCase):
    """Every external write re-establishes authority and proves itself.

    The guard is one code path, so these tests are written against the
    families rather than against remembered call sites: a new write that
    forgets its preflight cannot exist, because there is nowhere else to
    write from.
    """

    # -- map identity is required before a ticket write -------------------

    def test_a_claim_refuses_when_the_map_lost_its_label(self) -> None:
        tracker, api = seeded_tracker()
        api.issues[1]["labels"] = [{"name": "something-else", "id": 99}]
        before = len(api.comments.get(2, []))
        with self.assertRaises(WF.WayfinderError) as caught:
            tracker.claim(
                map_number=1, number=2, session="hermes/s", claimed_at=T1,
                operation=op_for("c"), apply=True,
            )
        self.assertIn(WF.MAP_LABEL, str(caught.exception))
        self.assertEqual(len(api.comments.get(2, [])), before)

    def test_a_claim_refuses_when_the_api_returns_a_different_map(self) -> None:
        tracker, api = seeded_tracker()
        real_request = api.request

        def wrong_number(method, path, payload=None):
            status, data = real_request(method, path, payload)
            if method.upper() == "GET" and path.endswith("/issues/1"):
                data = dict(data)
                data["number"] = 77
            return status, data

        api.request = wrong_number  # type: ignore[method-assign]
        before = len(api.comments.get(2, []))
        with self.assertRaises(WF.WayfinderError) as caught:
            tracker.claim(
                map_number=1, number=2, session="hermes/s", claimed_at=T1,
                operation=op_for("c"), apply=True,
            )
        self.assertIn("77", str(caught.exception))
        self.assertEqual(len(api.comments.get(2, [])), before)

    # -- the repository flips public immediately before each write --------

    def flip_public_before(self, api, tag: str) -> None:
        """Make the tracker public the moment a matching write is attempted."""
        real_request = api.request

        def flip(method, path, payload=None):
            if method.upper() in ("POST", "PATCH") and tag in path + str(payload):
                api.private = False
            return real_request(method, path, payload)

        api.request = flip  # type: ignore[method-assign]

    def test_every_write_family_refuses_a_repository_that_just_went_public(self) -> None:
        families = {
            "label": lambda t, a: t.create_map(
                title="M", managed="## Destination\n\nx\n", apply=True
            ),
            "create-ticket": lambda t, a: t.create_ticket(
                map_number=1, title="T", question="q", ticket_type="grilling", apply=True
            ),
            "dependency": lambda t, a: t.wire_blocking(
                map_number=1, blocked=2, blocked_by=3, apply=True
            ),
            "claim": lambda t, a: t.claim(
                map_number=1, number=2, session="hermes/n", claimed_at=T1,
                operation=op_for("n"), apply=True,
            ),
            "release": lambda t, a: t.release(
                map_number=1, number=4, session="hermes/session-a", released_at=T1,
                operation=op_for("hermes/session-a"), apply=True,
            ),
            "resolve": lambda t, a: t.resolve_ticket(
                map_number=1, number=4, session="hermes/session-a",
                claim_operation=op_for("hermes/session-a"),
                answer="A.", map_index_line="Chose X", at=T1, apply=True,
            ),
        }
        for name, run in families.items():
            with self.subTest(family=name):
                tracker, api = seeded_tracker()
                api.private = False
                with self.assertRaises(WF.WayfinderError) as caught:
                    run(tracker, api)
                self.assertIn("public", str(caught.exception))

    # -- ticket drift immediately before assignment / withdrawal / close --

    def test_a_ticket_that_loses_its_label_before_assignment_stops(self) -> None:
        tracker, api = seeded_tracker()

        def strip_label(fake, number):
            fake.issues[2]["labels"] = [{"name": "wayfinder:grilling", "id": 9}]

        # The claim comment posts, then the assignment guard re-reads #2.
        api.on_get[(2, 3)] = strip_label
        with self.assertRaises(WF.WayfinderError) as caught:
            tracker.claim(
                map_number=1, number=2, session="hermes/s", claimed_at=T1,
                assignee="bryan", operation=op_for("c"), apply=True,
            )
        self.assertIn(WF.TICKET_LABEL, str(caught.exception))
        self.assertEqual(api.issues[2]["assignees"], [])

    def test_a_ticket_repointed_to_another_map_before_the_close_stops(self) -> None:
        tracker, api = claimed_tracker()

        def repoint(fake, number):
            fake.issues[2]["body"] = ticket_body("Which storage shape?", 99)

        api.on_get[(2, 4)] = repoint
        with self.assertRaises(WF.WayfinderError) as caught:
            tracker.resolve_ticket(
                map_number=1, number=2, session="hermes/s",
                claim_operation=op_for("c2"),
                answer="A.", map_index_line="Chose X", at=T1, apply=True,
            )
        self.assertIn("belongs to map", str(caught.exception))
        self.assertEqual(api.issues[2]["state"], "open", "the close must not have run")

    def test_a_withdrawal_refuses_a_tracker_that_went_public(self) -> None:
        """Cleanup is not a licence to write to an unidentified tracker."""
        tracker, api = seeded_tracker()
        real_request = api.request
        seen: list[str] = []

        def interleave(method, path, payload=None):
            body = (payload or {}).get("body", "")
            if method.upper() == "POST" and "wayfinder:claim" in body and not seen:
                seen.append("x")
                api.add_comment(
                    2,
                    WF.render_record(
                        "claim",
                        {
                            "session": "claude/first",
                            "operation": op_for("first"),
                            "at": T0,
                        },
                    ),
                )
            result = real_request(method, path, payload)
            if method.upper() == "POST" and "wayfinder:claim" in body:
                api.private = False  # the tracker flips right after we post
            return result

        api.request = interleave  # type: ignore[method-assign]
        outcome = tracker.claim(
            map_number=1, number=2, session="hermes/late", claimed_at=T1,
            operation=op_for("late"), apply=True,
        )
        self.assertFalse(outcome.won)
        self.assertIn("STILL QUEUED", outcome.reason)
        self.assertIn(op_for("late"), outcome.reason)
        self.assertNotIn(
            "wayfinder:release",
            "".join(c["body"] for c in api.comments.get(2, [])),
            "nothing may be written to a public tracker",
        )

    # -- map and claim drift before the index write ------------------------

    def test_the_map_losing_its_label_stops_the_index_write(self) -> None:
        """Identity drift after the resolution comment, before the index posts."""
        tracker, api = claimed_tracker()
        real_request = api.request

        def strip_after_the_comment(method, path, payload=None):
            result = real_request(method, path, payload)
            if (
                method.upper() == "POST"
                and path.endswith("/issues/2/comments")
                and "wayfinder:resolution" in (payload or {}).get("body", "")
            ):
                api.issues[1]["labels"] = [{"name": "plain", "id": 42}]
            return result

        api.request = strip_after_the_comment  # type: ignore[method-assign]
        with self.assertRaises(WF.WayfinderError) as caught:
            tracker.resolve_ticket(
                map_number=1, number=2, session="hermes/s",
                claim_operation=op_for("c2"),
                answer="A.", map_index_line="Chose X", at=T1, apply=True,
            )
        self.assertIn(WF.MAP_LABEL, str(caught.exception))
        self.assertNotIn(
            "wayfinder:index",
            "".join(c["body"] for c in api.comments.get(1, [])),
            "no index record may land on a map that lost its identity",
        )
        self.assertEqual(
            api.issues[2]["state"], "open",
            "the close is last and must not have run",
        )

    def test_a_released_claim_stops_the_index_write(self) -> None:
        """The claim changes hands between the comment and the index post."""
        tracker, api = claimed_tracker()
        real_request = api.request
        released: list[str] = []

        def release_after_the_comment(method, path, payload=None):
            result = real_request(method, path, payload)
            if (
                method.upper() == "POST"
                and path.endswith("/issues/2/comments")
                and "wayfinder:resolution" in (payload or {}).get("body", "")
                and not released
            ):
                released.append("x")
                api.add_comment(2, WF.render_record(
                    "release",
                    {"session": "hermes/s", "operation": op_for("c2"), "at": T2},
                ))
            return result

        api.request = release_after_the_comment  # type: ignore[method-assign]
        with self.assertRaises(WF.WayfinderError) as caught:
            tracker.resolve_ticket(
                map_number=1, number=2, session="hermes/s",
                claim_operation=op_for("c2"),
                answer="A.", map_index_line="Chose X", at=T1, apply=True,
            )
        self.assertIn("nothing holds the claim", str(caught.exception))
        self.assertNotIn(
            "wayfinder:index",
            "".join(c["body"] for c in api.comments.get(1, [])),
            "an index record may only be posted by the live claimant",
        )

    # -- acknowledged-but-not-persisted writes ----------------------------

    def test_a_swallowed_claim_fails_closed(self) -> None:
        tracker, api = seeded_tracker()
        api.swallow.add("claim")
        with self.assertRaises(WF.WayfinderError) as caught:
            tracker.claim(
                map_number=1, number=2, session="hermes/s", claimed_at=T1,
                operation=op_for("c"), apply=True,
            )
        self.assertIn("did not read back", str(caught.exception))
        self.assertIsNone(tracker.current_claim(2))

    def test_a_swallowed_release_fails_closed(self) -> None:
        tracker, api = claimed_tracker()
        api.swallow.add("release")
        with self.assertRaises(WF.WayfinderError) as caught:
            tracker.release(
                map_number=1, number=2, session="hermes/s", released_at=T2,
                operation=op_for("c2"), apply=True,
            )
        self.assertIn("still held", str(caught.exception))
        self.assertEqual(tracker.current_claim(2).operation, op_for("c2"))

    def test_a_swallowed_assignment_fails_closed(self) -> None:
        tracker, api = seeded_tracker()
        api.swallow.add("patch-assignees")
        with self.assertRaises(WF.WayfinderError) as caught:
            tracker.claim(
                map_number=1, number=2, session="hermes/s", claimed_at=T1,
                assignee="bryan", operation=op_for("c"), apply=True,
            )
        self.assertIn("does not read back with exactly", str(caught.exception))

    def test_a_swallowed_dependency_fails_closed(self) -> None:
        tracker, api = seeded_tracker()
        api.swallow.add("dependency")
        with self.assertRaises(WF.WayfinderError) as caught:
            tracker.wire_blocking(map_number=1, blocked=2, blocked_by=3, apply=True)
        self.assertIn("not exactly [3]", str(caught.exception))
        self.assertNotIn(3, api.dependencies.get(2, []))

    def test_a_swallowed_label_creation_fails_closed(self) -> None:
        api = FakeForgejo()  # a tracker with no labels at all yet
        tracker = WF.WayfinderTracker(api, REPO)
        api.swallow.add("label")
        with self.assertRaises(WF.WayfinderError) as caught:
            tracker.resolve_label_ids([WF.MAP_LABEL], apply=True)
        self.assertIn("did not read back", str(caught.exception))
        self.assertNotIn(WF.MAP_LABEL, api.labels)

    def test_a_swallowed_index_post_fails_closed(self) -> None:
        tracker, api = claimed_tracker()
        api.swallow.add("index")
        with self.assertRaises(WF.WayfinderError) as caught:
            tracker.resolve_ticket(
                map_number=1, number=2, session="hermes/s",
                claim_operation=op_for("c2"),
                answer="A.", map_index_line="Chose X", at=T1, apply=True,
            )
        self.assertIn("did not read back", str(caught.exception))
        self.assertEqual(tracker.map_decisions(1), [])

    def test_a_swallowed_close_fails_closed(self) -> None:
        tracker, api = claimed_tracker()
        api.swallow.add("patch-close")
        with self.assertRaises(WF.WayfinderError) as caught:
            tracker.resolve_ticket(
                map_number=1, number=2, session="hermes/s",
                claim_operation=op_for("c2"),
                answer="A.", map_index_line="Chose X", at=T1, apply=True,
            )
        self.assertIn("did not read back as closed", str(caught.exception))

    # -- privacy drift immediately before the index write ------------------

    def test_public_flip_after_the_index_stops_the_close(self) -> None:
        """Safety beats completion: nothing lands on a tracker that went public."""
        tracker, api = claimed_tracker()
        real_request = api.request

        def go_public_after_the_index(method, path, payload=None):
            result = real_request(method, path, payload)
            if (
                method.upper() == "POST"
                and "wayfinder:index" in (payload or {}).get("body", "")
            ):
                api.private = False
            return result

        api.request = go_public_after_the_index  # type: ignore[method-assign]
        with self.assertRaises(WF.WayfinderError) as caught:
            tracker.resolve_ticket(
                map_number=1, number=2, session="hermes/s",
                claim_operation=op_for("c2"),
                answer="A.", map_index_line="Chose X", at=T1, apply=True,
            )
        self.assertIn("public", str(caught.exception))
        self.assertEqual(
            api.issues[2]["state"], "open",
            "the close landed on a tracker that had just gone public",
        )


# ==========================================================================
# Cycle-1 item 5 — serialized resolution still holds end to end
# ==========================================================================


class ResolutionCompletionTest(unittest.TestCase):
    def test_a_clean_resolution_reports_resolved(self) -> None:
        tracker, api = claimed_tracker()
        outcome = tracker.resolve_ticket(
            map_number=1, number=2, session="hermes/s",
            claim_operation=op_for("c2"),
            answer="A.", map_index_line="Chose X", at=T1, apply=True,
        )
        self.assertTrue(outcome.resolved)
        self.assertEqual(outcome.recovery, "")
        self.assertEqual(
            [d["gist"] for d in outcome.map["decisions"]], ["Chose X"]
        )
        self.assertEqual(api.issues[2]["state"], "closed")

    def test_success_requires_the_exact_key_to_replay(self) -> None:
        """`resolved` is measured against the replay, not against "the write
        seemed to work": a record that lands but does not replay — wrong key,
        malformed, superseded — is not a resolution."""
        tracker, api = claimed_tracker()
        outcome = tracker.resolve_ticket(
            map_number=1, number=2, session="hermes/s",
            claim_operation=op_for("c2"),
            answer="A.", map_index_line="Chose X", at=T1, apply=True,
        )
        key = WF.resolution_key(1, 2, "A.")
        self.assertEqual([d["key"] for d in outcome.map["decisions"]], [key])

    def test_a_retry_after_a_swallowed_index_converges(self) -> None:
        tracker, api = claimed_tracker()
        api.swallow.add("index")
        with self.assertRaises(WF.WayfinderError):
            tracker.resolve_ticket(
                map_number=1, number=2, session="hermes/s",
                claim_operation=op_for("c2"),
                answer="A.", map_index_line="Chose X", at=T1, apply=True,
            )
        api.swallow.discard("index")
        again = tracker.resolve_ticket(
            map_number=1, number=2, session="hermes/s",
            claim_operation=op_for("c2"),
            answer="A.", map_index_line="Chose X", at=T2, apply=True,
        )
        self.assertTrue(again.resolved)
        self.assertEqual(sorted(again.already), ["comment"])
        self.assertTrue(again.indexed and again.closed)
        self.assertEqual(len(tracker.map_index_records(1)), 1)


# ==========================================================================
# Cycle-2 section C — ownership is (operation, session[, ticket])
# ==========================================================================


class OwnershipTupleTest(unittest.TestCase):
    """An operation id is a handle, not a credential.

    Every id this adapter mints is written into a tracker comment, so anything
    that can read the issue can quote it back. The tests here all present a
    *real, current* operation id from the wrong session or the wrong ticket, and
    require that it buys nothing.
    """

    def test_a_foreign_session_cannot_release_with_the_right_operation(self) -> None:
        tracker, api = seeded_tracker()
        won = tracker.claim(
            map_number=1, number=2, session="hermes/owner", claimed_at=T1,
            operation=op_for("mine"), apply=True,
        )
        self.assertTrue(won.won)
        exposed = tracker.current_claim(2).operation  # readable from the tracker
        before = len(api.comments.get(2, []))

        outcome = tracker.release(
            map_number=1, number=2, session="claude/impostor", released_at=T2,
            operation=exposed, apply=True,
        )
        self.assertFalse(outcome.won)
        self.assertIn("refusing to release another session", outcome.reason)
        self.assertEqual(len(api.comments.get(2, [])), before, "nothing may be written")
        self.assertEqual(
            tracker.current_claim(2).session, "hermes/owner", "the claim moved"
        )

    def test_a_forged_release_record_clears_nothing(self) -> None:
        """Even a well-formed release under the wrong session is inert."""
        tracker, api = seeded_tracker()
        tracker.claim(
            map_number=1, number=2, session="hermes/owner", claimed_at=T1,
            operation=op_for("mine"), apply=True,
        )
        api.add_comment(
            2,
            WF.render_record(
                "release",
                {
                    "session": "claude/impostor",
                    "operation": op_for("mine"),
                    "at": T2,
                },
            ),
        )
        holder = tracker.current_claim(2)
        self.assertIsNotNone(holder, "a foreign release cleared the claim")
        self.assertEqual(holder.session, "hermes/owner")

    def test_an_impostor_with_the_exposed_operation_cannot_resolve(self) -> None:
        """No comment, no close, no index — the whole resolution refuses."""
        tracker, api = seeded_tracker()
        tracker.claim(
            map_number=1, number=2, session="hermes/owner", claimed_at=T1,
            operation=op_for("mine"), apply=True,
        )
        exposed = tracker.current_claim(2).operation
        comments_before = len(api.comments.get(2, []))
        body_before = api.issues[1]["body"]

        with self.assertRaises(WF.WayfinderError) as caught:
            tracker.resolve_ticket(
                map_number=1, number=2, session="claude/impostor",
                claim_operation=exposed,
                answer="I decide.", map_index_line="Chose theirs",
                at=T2, apply=True,
            )
        self.assertIn("only the current holder may write", str(caught.exception))
        self.assertEqual(len(api.comments.get(2, [])), comments_before)
        self.assertEqual(api.issues[2]["state"], "open")
        self.assertEqual(api.issues[1]["body"], body_before)

    def test_a_foreign_idempotent_claim_retry_is_refused(self) -> None:
        tracker, api = seeded_tracker()
        tracker.claim(
            map_number=1, number=2, session="hermes/owner", claimed_at=T1,
            operation=op_for("mine"), apply=True,
        )
        before = len(api.comments.get(2, []))
        outcome = tracker.claim(
            map_number=1, number=2, session="claude/impostor", claimed_at=T2,
            operation=op_for("mine"), apply=True,
        )
        self.assertFalse(outcome.won, "an impostor inherited the claim as a retry")
        self.assertIn("does not transfer its claim", outcome.reason)
        self.assertEqual(len(api.comments.get(2, [])), before)

    def test_same_session_sibling_operations_stay_independently_owned(self) -> None:
        tracker, api = seeded_tracker()
        tracker.claim(
            map_number=1, number=2, session="hermes/s", claimed_at=T1,
            operation=op_for("on-2"), apply=True,
        )
        tracker.claim(
            map_number=1, number=3, session="hermes/s", claimed_at=T1,
            operation=op_for("on-3"), apply=True,
        )
        # Releasing one names its own operation and touches nothing else.
        tracker.release(
            map_number=1, number=2, session="hermes/s", released_at=T2,
            operation=op_for("on-2"), apply=True,
        )
        self.assertIsNone(tracker.current_claim(2))
        self.assertEqual(tracker.current_claim(3).operation, op_for("on-3"))
        # And the released operation cannot be used to clear the sibling.
        outcome = tracker.release(
            map_number=1, number=3, session="hermes/s", released_at=T2,
            operation=op_for("on-2"), apply=True,
        )
        self.assertFalse(outcome.won)
        self.assertEqual(tracker.current_claim(3).operation, op_for("on-3"))

    def test_resolve_requires_the_exact_session_as_well_as_the_operation(self) -> None:
        tracker, api = claimed_tracker()
        # Right operation, right ticket, but the session in the guard differs.
        with self.assertRaises(WF.WayfinderError):
            tracker.resolve_ticket(
                map_number=1, number=2, session="hermes/other",
                claim_operation=op_for("c2"),
                answer="A.", map_index_line="Chose X", at=T1, apply=True,
            )
        self.assertEqual(api.issues[2]["state"], "open")


# ==========================================================================
# Cycle-2 section D — recover a queued acquisition by exact identity
# ==========================================================================


class QueuedRecoveryTest(unittest.TestCase):
    """A failed withdrawal leaves a zombie *behind the winner*.

    That record becomes the active claim or lock the moment the winner
    releases, so recovery has to reach it — without disturbing the winner.
    Recovery that only works on the current holder is not recovery.
    """

    def losing_claim(self, tracker, api):
        """Race so that `hermes/late` posts a claim and then loses, badly."""
        real_request = api.request
        fired: list[str] = []

        def interleave(method, path, payload=None):
            body = (payload or {}).get("body", "")
            if method.upper() == "POST" and "wayfinder:claim" in body and not fired:
                fired.append("x")
                api.add_comment(
                    2,
                    WF.render_record(
                        "claim",
                        {
                            "session": "claude/first",
                            "operation": op_for("first"),
                            "at": T0,
                        },
                    ),
                )
                api.swallow.add("release")  # the withdrawal will not persist
            return real_request(method, path, payload)

        api.request = interleave  # type: ignore[method-assign]
        outcome = tracker.claim(
            map_number=1, number=2, session="hermes/late", claimed_at=T1,
            operation=op_for("late"), apply=True,
        )
        api.request = real_request  # type: ignore[method-assign]
        api.swallow.discard("release")
        return outcome

    def test_the_printed_command_recovers_the_queued_claim(self) -> None:
        tracker, api = seeded_tracker()
        outcome = self.losing_claim(tracker, api)
        self.assertFalse(outcome.won)
        self.assertIn("STILL QUEUED", outcome.reason)

        identity = claim_id("late", "hermes/late")
        self.assertTrue(
            WF.acquisition_is_active(
                tracker.claim_records(2), hold="claim", drop="release", identity=identity
            ),
            "premise broken: there is no zombie to recover",
        )
        # The reason names every argument recovery needs.
        for fragment in ("--map 1", "--ticket 2", "--session hermes/late",
                         f"--operation {op_for('late')}"):
            self.assertIn(fragment, outcome.reason)

        recovered = tracker.release(
            map_number=1, number=2, session="hermes/late", released_at=T2,
            operation=op_for("late"), apply=True,
        )
        self.assertTrue(recovered.won)
        self.assertIn("queued claim", recovered.reason)
        self.assertFalse(
            WF.acquisition_is_active(
                tracker.claim_records(2), hold="claim", drop="release", identity=identity
            ),
            "the zombie survived recovery",
        )
        # And the winner is untouched, before *and* after it releases.
        self.assertEqual(tracker.current_claim(2).session, "claude/first")
        tracker.release(
            map_number=1, number=2, session="claude/first", released_at=T2,
            operation=op_for("first"), apply=True,
        )
        self.assertIsNone(
            tracker.current_claim(2),
            "the recovered zombie took the ticket when the winner released",
        )

    def test_queued_claim_recovery_refuses_a_foreign_session(self) -> None:
        tracker, api = seeded_tracker()
        self.losing_claim(tracker, api)
        before = len(api.comments.get(2, []))
        outcome = tracker.release(
            map_number=1, number=2, session="claude/impostor", released_at=T2,
            operation=op_for("late"), apply=True,
        )
        self.assertFalse(outcome.won)
        self.assertEqual(len(api.comments.get(2, [])), before)

    def test_claim_status_reports_the_queued_claim_and_its_recovery(self) -> None:
        """Recovery cannot target what inspection does not show."""
        tracker, api = seeded_tracker()
        self.losing_claim(tracker, api)
        payload = run_cli(api, "claim-status", "--map", "1", "--ticket", "2")
        self.assertEqual(payload["holder"]["session"], "claude/first")
        self.assertEqual(len(payload["queued"]), 1, payload["queued"])
        zombie = payload["queued"][0]
        self.assertEqual(zombie["session"], "hermes/late")
        self.assertEqual(zombie["operation"], op_for("late"))
        for fragment in ("--map 1", "--ticket 2", "--session hermes/late",
                         f"--operation {op_for('late')}"):
            self.assertIn(fragment, zombie["recovery"])

    def test_a_swallowed_recovery_write_returns_failure(self) -> None:
        tracker, api = seeded_tracker()
        self.losing_claim(tracker, api)
        api.swallow.add("release")
        identity = claim_id("late", "hermes/late")
        with self.assertRaises(WF.WayfinderError) as caught:
            tracker.release(
                map_number=1, number=2, session="hermes/late", released_at=T2,
                operation=op_for("late"), apply=True,
            )
        self.assertIn("did not read back", str(caught.exception))
        self.assertTrue(
            WF.acquisition_is_active(
                tracker.claim_records(2), hold="claim", drop="release", identity=identity
            ),
            "a swallowed recovery reported success",
        )

    def test_recovery_refuses_an_acquisition_that_was_never_made(self) -> None:
        tracker, api = seeded_tracker()
        before = len(api.comments.get(2, []))
        outcome = tracker.release(
            map_number=1, number=2, session="hermes/ghost", released_at=T2,
            operation=op_for("never"), apply=True,
        )
        self.assertFalse(outcome.won)
        self.assertIn("never claimed", outcome.reason)
        self.assertEqual(len(api.comments.get(2, [])), before)

    def test_recovering_an_already_released_acquisition_is_idempotent(self) -> None:
        tracker, api = seeded_tracker()
        tracker.release(
            map_number=1, number=4, session="hermes/session-a", released_at=T1,
            operation=op_for("hermes/session-a"), apply=True,
        )
        before = len(api.comments.get(4, []))
        again = tracker.release(
            map_number=1, number=4, session="hermes/session-a", released_at=T2,
            operation=op_for("hermes/session-a"), apply=True,
        )
        self.assertTrue(again.won)
        self.assertIn("idempotent", again.reason)
        self.assertEqual(len(api.comments.get(4, [])), before)


# ==========================================================================
# Cycle-2 section B — privacy is the LAST read before the write
# ==========================================================================


class PrivacyIsLastReadTest(unittest.TestCase):
    """Flip the repository public *during* the final identity read.

    A test that merely starts public proves the first check works. What matters
    is the ordering: if privacy is checked and then three more reads happen,
    the mutation lands on a tracker the adapter approved a round trip ago.
    These tests make the flip happen inside that window, and require the write
    never to occur.
    """

    def flip_during(self, api, *, when) -> None:
        """Go public partway through the guard's reads.

        `when(method, path)` selects the read to flip on — a map read, a ticket
        read, a comment read, or a dependency read. The repository is public by
        the time `require_private()` runs, and `require_private()` runs last.
        """
        real_request = api.request

        def hooked(method, path, payload=None):
            if method.upper() == "GET" and when(method.upper(), path):
                api.private = False
            return real_request(method, path, payload)

        api.request = hooked  # type: ignore[method-assign]

    def assert_no_writes(self, api, run) -> str:
        writes_before = [c for c in api.calls if c[0] in ("POST", "PATCH")]
        with self.assertRaises(WF.WayfinderError) as caught:
            run()
        writes_after = [c for c in api.calls if c[0] in ("POST", "PATCH")]
        self.assertEqual(
            writes_after,
            writes_before,
            "a write happened after the repository went public",
        )
        message = str(caught.exception)
        self.assertIn("public", message)
        return message

    ON_MAP = staticmethod(lambda method, path: path.endswith("/issues/1"))
    ON_TICKET = staticmethod(
        lambda method, path: path.endswith("/issues/2") or path.endswith("/issues/4")
    )
    ON_COMMENTS = staticmethod(lambda method, path: "/comments" in path)
    ON_DEPENDENCIES = staticmethod(lambda method, path: path.endswith("/dependencies"))

    def test_a_claim_stops_when_the_flip_lands_on_the_ticket_read(self) -> None:
        tracker, api = seeded_tracker()
        self.flip_during(api, when=self.ON_TICKET)
        self.assert_no_writes(
            api,
            lambda: tracker.claim(
                map_number=1, number=2, session="hermes/s", claimed_at=T1,
                operation=op_for("c"), apply=True,
            ),
        )
        self.assertIsNone(tracker_ignoring_privacy(api).current_claim(2))

    def test_a_claim_stops_when_the_flip_lands_on_the_map_read(self) -> None:
        tracker, api = seeded_tracker()
        self.flip_during(api, when=self.ON_MAP)
        self.assert_no_writes(
            api,
            lambda: tracker.claim(
                map_number=1, number=2, session="hermes/s", claimed_at=T1,
                operation=op_for("c"), apply=True,
            ),
        )

    def test_a_claim_stops_when_the_flip_lands_on_the_comment_read(self) -> None:
        """The ownership read is the last thing before privacy."""
        tracker, api = seeded_tracker()
        tracker.claim(
            map_number=1, number=2, session="hermes/s", claimed_at=T1,
            operation=op_for("c"), apply=True,
        )
        self.flip_during(api, when=self.ON_COMMENTS)
        self.assert_no_writes(
            api,
            lambda: tracker.release(
                map_number=1, number=2, session="hermes/s", released_at=T2,
                operation=op_for("c"), apply=True,
            ),
        )

    def test_an_assignment_stops_when_the_flip_lands_on_the_ownership_read(self) -> None:
        tracker, api = seeded_tracker()
        # Claim first, cleanly, then flip only for the assignment's guard.
        outcome = tracker.claim(
            map_number=1, number=2, session="hermes/s", claimed_at=T1,
            operation=op_for("c"), apply=True,
        )
        self.assertTrue(outcome.won)
        self.flip_during(api, when=self.ON_COMMENTS)
        writes_before = [c for c in api.calls if c[0] in ("POST", "PATCH")]
        with self.assertRaises(WF.WayfinderError):
            tracker.guarded_write(
                WF.WriteGuard(
                    what="assigning #2",
                    map_number=1,
                    ticket=2,
                    claim_owner=claim_id("c", "hermes/s"),
                ),
                lambda _s: tracker._patch_issue_direct(2, {"assignees": ["bryan"]}),
                lambda _s: True,
            )
        self.assertEqual(
            [c for c in api.calls if c[0] in ("POST", "PATCH")], writes_before
        )
        self.assertEqual(api.issues[2]["assignees"], [])

    def test_a_dependency_stops_when_the_flip_lands_on_the_snapshot_read(self) -> None:
        tracker, api = seeded_tracker()
        self.flip_during(api, when=self.ON_DEPENDENCIES)
        self.assert_no_writes(
            api,
            lambda: tracker.wire_blocking(
                map_number=1, blocked=2, blocked_by=3, apply=True
            ),
        )
        self.assertNotIn(3, api.dependencies.get(2, []))

    def test_a_resolution_stops_at_every_step_the_flip_can_land_on(self) -> None:
        for label, when in (
            ("map read", self.ON_MAP),
            ("ticket read", self.ON_TICKET),
            ("ownership read", self.ON_COMMENTS),
        ):
            with self.subTest(read=label):
                tracker, api = claimed_tracker()
                self.flip_during(api, when=when)
                body_before = api.issues[1]["body"]
                self.assert_no_writes(
                    api,
                    lambda: tracker.resolve_ticket(
                        map_number=1, number=2, session="hermes/s",
                        claim_operation=op_for("c2"),
                        answer="A.", map_index_line="Chose X", at=T1, apply=True,
                    ),
                )
                self.assertEqual(api.issues[1]["body"], body_before)
                self.assertEqual(api.issues[2]["state"], "open")

    def test_a_creation_stops_when_the_flip_lands_on_the_label_read(self) -> None:
        tracker, api = seeded_tracker()
        before = len(api.issues)
        self.flip_during(api, when=lambda method, path: "/labels" in path)
        with self.assertRaises(WF.WayfinderError) as caught:
            tracker.create_ticket(
                map_number=1, title="T", question="q?",
                ticket_type="grilling", creation=op_for("flip"), apply=True,
            )
        self.assertIn("public", str(caught.exception))
        self.assertEqual(len(api.issues), before, "an issue was created")

    def test_the_privacy_check_is_the_last_request_before_a_write(self) -> None:
        """Stated directly against the request log, for every write family."""
        families = {
            "claim": lambda t, a: t.claim(
                map_number=1, number=2, session="hermes/s", claimed_at=T1,
                operation=op_for("c"), apply=True,
            ),
            "release": lambda t, a: t.release(
                map_number=1, number=4, session="hermes/session-a", released_at=T1,
                operation=op_for("hermes/session-a"), apply=True,
            ),
            "dependency": lambda t, a: t.wire_blocking(
                map_number=1, blocked=2, blocked_by=3, apply=True
            ),
            "create-ticket": lambda t, a: t.create_ticket(
                map_number=1, title="T", question="q?",
                ticket_type="grilling", creation=op_for("last-read"), apply=True,
            ),
        }
        for name, run in families.items():
            with self.subTest(family=name):
                tracker, api = seeded_tracker()
                run(tracker, api)
                for index, (method, path) in enumerate(api.calls):
                    if method not in ("POST", "PATCH"):
                        continue
                    previous = api.calls[index - 1]
                    self.assertEqual(
                        previous,
                        ("GET", REPO.api_base),
                        f"the request before the {name} write was {previous}, not the "
                        "privacy check",
                    )


def tracker_ignoring_privacy(api: "FakeForgejo") -> WF.WayfinderTracker:
    """A reader for assertions, after a test has made the repo public.

    Reading claim records does not require privacy — only writing does — so
    this exists purely to inspect state without the test tripping over its own
    fault injection.
    """
    return WF.WayfinderTracker(api, REPO)


# ==========================================================================
# Cycle-2 section E — map and ticket identity are exact
# ==========================================================================


class ExactIdentityTest(unittest.TestCase):
    def test_a_map_with_no_managed_region_is_not_a_map(self) -> None:
        tracker, api = seeded_tracker()
        api.issues[1]["body"] = "Just prose, no managed region.\n"
        with self.assertRaises(WF.WayfinderError) as caught:
            tracker.read_map(1)
        self.assertIn("exactly one balanced", str(caught.exception))

    def test_a_map_with_two_managed_regions_is_not_a_map(self) -> None:
        """Which one would a decision be merged into? Refuse rather than pick."""
        tracker, api = seeded_tracker()
        one = f"{WF.MAP_BEGIN}\n## Decisions so far\n\n{WF.MAP_END}"
        api.issues[1]["body"] = f"{one}\n\nprose\n\n{one}\n"
        with self.assertRaises(WF.WayfinderError) as caught:
            tracker.read_map(1)
        self.assertIn("2 begin", str(caught.exception))

    def test_an_unbalanced_managed_region_is_not_a_map(self) -> None:
        tracker, api = seeded_tracker()
        for body in (
            f"{WF.MAP_BEGIN}\n## Decisions so far\n",
            f"## Decisions so far\n{WF.MAP_END}\n",
            f"{WF.MAP_END}\n## Decisions so far\n{WF.MAP_BEGIN}\n",
        ):
            with self.subTest(body=body[:30]):
                api.issues[1]["body"] = body
                with self.assertRaises(WF.WayfinderError):
                    tracker.read_map(1)

    def test_a_wrong_version_managed_region_is_not_a_map(self) -> None:
        tracker, api = seeded_tracker()
        api.issues[1]["body"] = (
            "<!-- wayfinder:map:begin v9 -->\n## Decisions so far\n"
            f"{WF.MAP_END}\n"
        )
        with self.assertRaises(WF.WayfinderError) as caught:
            tracker.read_map(1)
        self.assertIn("v9", str(caught.exception))

    def test_ticket_metadata_uses_an_exact_schema(self) -> None:
        good = WF.render_ticket_metadata(1, "grilling")
        self.assertEqual(
            WF.parse_ticket_metadata(good),
            {"map": "1", "type": "grilling", "version": "v1"},
        )
        cases = {
            "duplicate block": good + "\n" + good,
            "duplicate field": "<!-- wayfinder:ticket v1\nmap: 1\nmap: 2\ntype: grilling\n-->",
            "unknown field": "<!-- wayfinder:ticket v1\nmap: 1\ntype: grilling\nx: 1\n-->",
            "missing type": "<!-- wayfinder:ticket v1\nmap: 1\n-->",
            "missing map": "<!-- wayfinder:ticket v1\ntype: grilling\n-->",
            "blank line": "<!-- wayfinder:ticket v1\nmap: 1\n\ntype: grilling\n-->",
            "malformed line": "<!-- wayfinder:ticket v1\nmap: 1\ntype: grilling\nnonsense\n-->",
            "empty value": "<!-- wayfinder:ticket v1\nmap: \ntype: grilling\n-->",
            "zero map": "<!-- wayfinder:ticket v1\nmap: 0\ntype: grilling\n-->",
            "negative map": "<!-- wayfinder:ticket v1\nmap: -1\ntype: grilling\n-->",
            "leading zero map": "<!-- wayfinder:ticket v1\nmap: 01\ntype: grilling\n-->",
            "non-numeric map": "<!-- wayfinder:ticket v1\nmap: one\ntype: grilling\n-->",
            "unknown type": "<!-- wayfinder:ticket v1\nmap: 1\ntype: vibes\n-->",
            "wrong version": "<!-- wayfinder:ticket v9\nmap: 1\ntype: grilling\n-->",
        }
        for label, body in cases.items():
            with self.subTest(case=label):
                self.assertEqual(WF.parse_ticket_metadata(body), {})

    def test_rendering_ticket_metadata_rejects_a_non_positive_map(self) -> None:
        for bad in (0, -1):
            with self.subTest(map=bad), self.assertRaises(WF.WayfinderError):
                WF.render_ticket_metadata(bad, "grilling")

    def test_a_ticket_without_its_type_label_is_not_a_ticket(self) -> None:
        tracker, api = seeded_tracker()
        api.issues[2]["labels"] = [{"name": WF.TICKET_LABEL, "id": 2}]
        with self.assertRaises(WF.WayfinderError) as caught:
            tracker.preflight_ticket(2, 1)
        self.assertIn("wayfinder:grilling", str(caught.exception))

    def test_a_type_label_that_disagrees_with_the_body_is_refused(self) -> None:
        """Two sources of truth, and this adapter refuses to pick one."""
        tracker, api = seeded_tracker()
        api.issues[2]["labels"] = [
            {"name": WF.TICKET_LABEL, "id": 2},
            {"name": "wayfinder:research", "id": 3},
        ]
        with self.assertRaises(WF.WayfinderError) as caught:
            tracker.preflight_ticket(2, 1)
        self.assertIn("labels and body disagree", str(caught.exception))

    def test_a_claim_fails_when_the_referenced_map_lacks_exact_identity(self) -> None:
        for label, damage in (
            ("no label", lambda a: a.issues[1].__setitem__("labels", [])),
            (
                "no managed region",
                lambda a: a.issues[1].__setitem__("body", "prose only\n"),
            ),
            (
                "two managed regions",
                lambda a: a.issues[1].__setitem__(
                    "body",
                    f"{WF.MAP_BEGIN}\nx\n{WF.MAP_END}\n{WF.MAP_BEGIN}\ny\n{WF.MAP_END}\n",
                ),
            ),
        ):
            with self.subTest(case=label):
                tracker, api = seeded_tracker()
                damage(api)
                before = len(api.comments.get(2, []))
                with self.assertRaises(WF.WayfinderError):
                    tracker.claim(
                        map_number=1, number=2, session="hermes/s", claimed_at=T1,
                        operation=op_for("c"), apply=True,
                    )
                self.assertEqual(len(api.comments.get(2, [])), before)

# ==========================================================================
# Cycle-2 section F — value validation is real, not shape-matching
# ==========================================================================


class ValueValidationTest(unittest.TestCase):
    def test_an_iso_shaped_impossible_instant_is_rejected(self) -> None:
        for bad in (
            "2026-99-99T99:99:99Z",
            "2026-13-01T00:00:00Z",
            "2026-02-30T00:00:00Z",
            "2026-01-32T00:00:00Z",
            "2026-01-01T24:00:00Z",
            "2026-01-01T00:60:00Z",
            "2026-01-01T00:00:60Z",
            "2026-00-01T00:00:00Z",
            "2026-01-00T00:00:00Z",
        ):
            with self.subTest(value=bad):
                self.assertRegex(bad, r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z")
                self.assertFalse(
                    WF.is_utc_timestamp(bad), "the regex shape passed as a real instant"
                )
                with self.assertRaises(WF.WayfinderError):
                    WF.validate_timestamp(bad)

    def test_a_non_utc_or_offset_timestamp_is_rejected(self) -> None:
        for bad in (
            "2026-08-19T09:00:00",
            "2026-08-19T09:00:00+00:00",
            "2026-08-19T09:00:00-07:00",
            "2026-08-19 09:00:00Z",
            "2026-08-19T09:00:00z",
        ):
            with self.subTest(value=bad):
                self.assertFalse(WF.is_utc_timestamp(bad))

    def test_real_instants_are_accepted_including_leap_days(self) -> None:
        for good in (
            "2026-08-19T09:00:00Z",
            "2024-02-29T23:59:59Z",
            "2026-12-31T00:00:00Z",
            "2026-08-19T09:00:00.123456Z",
        ):
            with self.subTest(value=good):
                self.assertTrue(WF.is_utc_timestamp(good))
                self.assertEqual(WF.validate_timestamp(good), good)

    def test_a_bad_timestamp_reaches_no_arbitration(self) -> None:
        body = "<!-- wayfinder:claim v1\nat: 2026-99-99T99:99:99Z\n" + (
            f"operation: {op_for('x')}\nsession: hermes/s\n-->"
        )
        self.assertEqual(WF.parse_records([{"id": 10, "body": body}]), [])

    def test_zero_is_not_a_ticket_or_a_map(self) -> None:
        for kind, field in (
            ("index", "ticket"),
            ("index", "map"),
            ("resolution", "map"),
        ):
            with self.subTest(kind=kind, field=field):
                fields = dict(RecordSchemaTest.GOOD[kind])
                fields[field] = "0"
                lines = "\n".join(f"{k}: {v}" for k, v in sorted(fields.items()))
                self.assertIsNone(WF.parse_schema_block(kind, lines))
                with self.assertRaises(WF.WayfinderError):
                    WF.render_record(kind, fields)

    def test_negative_and_oversized_numbers_are_rejected(self) -> None:
        for bad in ("-1", "+1", "1.0", "01", " 1", "1 ", "1" * 19, "9" * 25, "1e3"):
            with self.subTest(value=bad):
                self.assertFalse(
                    WF.POSITIVE_RE.match(bad), f"{bad!r} passed as a positive integer"
                )

    def test_the_largest_accepted_number_is_bounded_and_int_safe(self) -> None:
        """A bound, not a budget: `int()` must never see unbounded input."""
        biggest = "9" * 18
        self.assertTrue(WF.POSITIVE_RE.match(biggest))
        self.assertEqual(int(biggest), 10**18 - 1)
        self.assertFalse(WF.POSITIVE_RE.match("9" * 19))

    def test_a_blank_line_inside_a_block_is_rejected(self) -> None:
        """Padding a reader tolerates is padding a forger can hide behind.

        A *trailing* newline is not in scope: `RECORD_RE` captures the body
        between `\n` and `\n-->`, so one never reaches this function. Leading
        and interior blanks do.
        """
        for kind, fields in RecordSchemaTest.GOOD.items():
            with self.subTest(kind=kind):
                lines = "\n".join(f"{k}: {v}" for k, v in sorted(fields.items()))
                self.assertIsNotNone(WF.parse_schema_block(kind, lines))
                for label, padded in (
                    ("leading", f"\n{lines}"),
                    ("interior", lines.replace("\n", "\n\n", 1)),
                    ("interior whitespace", lines.replace("\n", "\n   \n", 1)),
                ):
                    with self.subTest(padding=label):
                        self.assertIsNone(
                            WF.parse_schema_block(kind, padded),
                            f"{label} padding was tolerated for {kind}",
                        )

    def test_rendering_and_parsing_share_one_validation(self) -> None:
        """A value render accepts must parse, and vice versa."""
        for kind, fields in RecordSchemaTest.GOOD.items():
            for field in fields:
                for bad in ("0", "", " ", "nope", "2026-99-99T99:99:99Z"):
                    candidate = dict(fields)
                    candidate[field] = bad
                    lines = "\n".join(
                        f"{k}: {v}" for k, v in sorted(candidate.items())
                    )
                    parsed = WF.parse_schema_block(kind, lines)
                    rendered_ok = True
                    try:
                        WF.render_record(kind, candidate)
                    except WF.WayfinderError:
                        rendered_ok = False
                    with self.subTest(kind=kind, field=field, value=bad):
                        self.assertEqual(
                            rendered_ok,
                            parsed is not None,
                            "render and parse disagree about this value",
                        )


# ==========================================================================
# Cycle-2 section G — exact post-state verification for every write
# ==========================================================================


class ExactReadbackTest(unittest.TestCase):
    def test_a_create_that_returns_an_existing_issue_fails_closed(self) -> None:
        """A transport that creates nothing and echoes a real map."""
        tracker, api = seeded_tracker()
        real_request = api.request

        def echo_existing(method, path, payload=None):
            if method.upper() == "POST" and path == f"{REPO.api_base}/issues":
                return 201, dict(api.issues[1])  # a genuinely valid map
            return real_request(method, path, payload)

        api.request = echo_existing  # type: ignore[method-assign]
        before = len(api.issues)
        with self.assertRaises(WF.WayfinderError) as caught:
            tracker.create_map(title="M", managed="## Decisions so far\n",
                               creation=op_for("echo-map"), apply=True)
        self.assertIn("pre-existing", str(caught.exception))
        self.assertEqual(len(api.issues), before)

    def test_a_create_that_returns_an_existing_ticket_fails_closed(self) -> None:
        tracker, api = seeded_tracker()
        real_request = api.request

        def echo_existing(method, path, payload=None):
            if method.upper() == "POST" and path == f"{REPO.api_base}/issues":
                return 201, dict(api.issues[2])
            return real_request(method, path, payload)

        api.request = echo_existing  # type: ignore[method-assign]
        with self.assertRaises(WF.WayfinderError) as caught:
            tracker.create_ticket(
                map_number=1, title="T", question="q?",
                ticket_type="grilling", creation=op_for("echo-ticket"), apply=True,
            )
        self.assertIn("pre-existing", str(caught.exception))

    def test_a_create_that_stores_a_different_title_fails_closed(self) -> None:
        tracker, api = seeded_tracker()
        api.mangle_issue = {"title": "Something Else"}
        with self.assertRaises(WF.WayfinderError) as caught:
            tracker.create_map(title="M", managed="## Decisions so far\n",
                               creation=op_for("mangle-title"), apply=True)
        self.assertIn("stored title", str(caught.exception))

    def test_a_create_that_stores_a_different_body_fails_closed(self) -> None:
        tracker, api = seeded_tracker()
        api.mangle_issue = {"body_suffix": "\n\nsomething the server added\n"}
        with self.assertRaises(WF.WayfinderError) as caught:
            tracker.create_ticket(
                map_number=1, title="T", question="q?",
                ticket_type="grilling", creation=op_for("mangle-body"), apply=True,
            )
        self.assertIn("exact body", str(caught.exception))

    def test_a_create_that_stores_the_wrong_labels_fails_closed(self) -> None:
        tracker, api = seeded_tracker()
        api.mangle_issue = {"drop_labels": [WF.MAP_LABEL]}
        with self.assertRaises(WF.WayfinderError) as caught:
            tracker.create_map(title="M", managed="## Decisions so far\n",
                               creation=op_for("drop-labels"), apply=True)
        self.assertIn("carries labels", str(caught.exception))

    def test_a_create_that_adds_an_extra_label_fails_closed(self) -> None:
        tracker, api = seeded_tracker()
        api.mangle_issue = {"extra_labels": ["random:label"]}
        with self.assertRaises(WF.WayfinderError) as caught:
            tracker.create_ticket(
                map_number=1, title="T", question="q?",
                ticket_type="grilling", creation=op_for("extra-label"), apply=True,
            )
        self.assertIn("not exactly", str(caught.exception))

    def test_a_label_created_with_the_wrong_colour_fails_closed(self) -> None:
        api = FakeForgejo()
        tracker = WF.WayfinderTracker(api, REPO)
        api.mangle_label[WF.MAP_LABEL] = {"color": "#ffffff"}
        with self.assertRaises(WF.WayfinderError) as caught:
            tracker.resolve_label_ids([WF.MAP_LABEL], apply=True)
        self.assertIn("exact name, colour", str(caught.exception))

    def test_a_label_created_under_a_different_id_fails_closed(self) -> None:
        api = FakeForgejo()
        tracker = WF.WayfinderTracker(api, REPO)
        api.mangle_label[WF.MAP_LABEL] = {"reported_id": 4242}
        with self.assertRaises(WF.WayfinderError):
            tracker.resolve_label_ids([WF.MAP_LABEL], apply=True)

    def test_an_assignment_that_keeps_a_pre_existing_assignee_fails_closed(self) -> None:
        """Exact set, not "contains": two assignees is two people who think they own it."""
        tracker, api = seeded_tracker()
        api.issues[2]["assignees"] = [{"login": "someone-else"}]
        api.keep_assignees = True
        with self.assertRaises(WF.WayfinderError) as caught:
            tracker.claim(
                map_number=1, number=2, session="hermes/s", claimed_at=T1,
                assignee="bryan", operation=op_for("c"), apply=True,
            )
        self.assertIn("exactly", str(caught.exception))

    def test_a_dependency_result_with_an_unexpected_extra_fails_closed(self) -> None:
        """State we did not ask for is state we cannot explain."""
        tracker, api = seeded_tracker()
        real_request = api.request

        def over_wire(method, path, payload=None):
            if method.upper() == "POST" and path.endswith("/dependencies"):
                api.dependencies.setdefault(2, []).extend([3, 4])
                return 201, {"number": 2}
            return real_request(method, path, payload)

        api.request = over_wire  # type: ignore[method-assign]
        with self.assertRaises(WF.WayfinderError) as caught:
            tracker.wire_blocking(map_number=1, blocked=2, blocked_by=3, apply=True)
        self.assertIn("unexpected [4]", str(caught.exception))

    def test_a_dependency_result_that_dropped_an_existing_edge_fails_closed(self) -> None:
        tracker, api = seeded_tracker()
        api.dependencies[2] = [4]
        real_request = api.request

        def replace_all(method, path, payload=None):
            if method.upper() == "POST" and path.endswith("/dependencies"):
                api.dependencies[2] = [3]  # dropped #4
                return 201, {"number": 2}
            return real_request(method, path, payload)

        api.request = replace_all  # type: ignore[method-assign]
        with self.assertRaises(WF.WayfinderError) as caught:
            tracker.wire_blocking(map_number=1, blocked=2, blocked_by=3, apply=True)
        self.assertIn("missing [4]", str(caught.exception))

    def test_a_pre_existing_record_is_not_proof_of_a_new_write(self) -> None:
        """The subtlest swallow: retry a write whose first attempt landed."""
        tracker, api = seeded_tracker()
        fields = {
            "session": "hermes/s",
            "operation": op_for("c"),
            "at": T1,
        }
        # Seed the exact record a claim would post, then swallow the new write.
        api.add_comment(2, WF.render_record("claim", fields))
        api.swallow.add("claim")
        # It reads as an idempotent retry of a landed claim, so no write at all.
        outcome = tracker.claim(
            map_number=1, number=2, session="hermes/s", claimed_at=T1,
            operation=op_for("c"), apply=True,
        )
        self.assertTrue(outcome.won)
        self.assertIn("idempotent retry", outcome.reason)
        # And a *release* whose write is swallowed while an identical release
        # already exists must still fail, not read the old one as proof.
        api.swallow.discard("claim")
        api.add_comment(2, WF.render_record("release", fields))
        api.swallow.add("release")
        with self.assertRaises(WF.WayfinderError):
            tracker._drop_claim(
                map_number=1, number=2, session="hermes/s",
                operation=op_for("c"), at=T1,
                what="probe", require_holder=False,
            )

    def test_a_close_that_loses_the_ticket_label_fails_closed(self) -> None:
        tracker, api = claimed_tracker()
        real_request = api.request

        def strip_on_close(method, path, payload=None):
            result = real_request(method, path, payload)
            if method.upper() == "PATCH" and (payload or {}).get("state") == "closed":
                api.issues[2]["labels"] = []
            return result

        api.request = strip_on_close  # type: ignore[method-assign]
        with self.assertRaises(WF.WayfinderError) as caught:
            tracker.resolve_ticket(
                map_number=1, number=2, session="hermes/s",
                claim_operation=op_for("c2"),
                answer="A.", map_index_line="Chose X", at=T1, apply=True,
            )
        self.assertIn("wayfinder:ticket", str(caught.exception))


class ReadbackSnapshotTest(unittest.TestCase):
    """A record that was already there is not evidence of a new write.

    This is the subtle half of "acknowledged but not persisted": retry a write
    whose *earlier* attempt landed, and a readback that only looks for "a
    record with these fields" finds the old one and reports success. Every
    record readback therefore requires a comment that was absent from a
    pre-write snapshot.
    """

    def test_record_landed_requires_a_comment_absent_before_the_write(self) -> None:
        tracker, api = seeded_tracker()
        fields = {"session": "hermes/s", "operation": op_for("c"), "at": T1}
        existing = api.add_comment(2, WF.render_record("claim", fields))
        known = {int(c["id"]) for c in api.comments[2]}

        # Nothing new written: the pre-existing identical record must not count,
        # even when the API echoes its id back.
        self.assertFalse(
            tracker._record_landed(
                2, kind="claim", fields=fields,
                posted={"id": existing}, known_comment_ids=known,
            ),
            "a pre-existing record was accepted as proof of a new write",
        )
        # The same record, outside the snapshot and under the returned id:
        # that does count.
        self.assertTrue(
            tracker._record_landed(
                2, kind="claim", fields=fields,
                posted={"id": existing}, known_comment_ids=set(),
            )
        )

    def test_record_landed_requires_a_positive_returned_id(self) -> None:
        """A server that echoes no id, zero, or a negative one is unverifiable.

        The id is what pins "this write" to "this comment"; without it the
        readback would have to accept any byte-exact newcomer, which is how a
        concurrent identical record becomes proof of a write that never landed.
        """
        tracker, api = seeded_tracker()
        fields = {"session": "hermes/s", "operation": op_for("c"), "at": T1}
        api.add_comment(2, WF.render_record("claim", fields))
        for posted in ({}, {"id": 0}, {"id": -1}, {"id": "junk"}):
            with self.subTest(posted=posted):
                self.assertFalse(
                    tracker._record_landed(
                        2, kind="claim", fields=fields,
                        posted=posted, known_comment_ids=set(),
                    )
                )

    def test_record_landed_requires_the_exact_body(self) -> None:
        tracker, api = seeded_tracker()
        fields = {"session": "hermes/s", "operation": op_for("c"), "at": T1}
        cid = api.add_comment(2, WF.render_record("claim", fields) + "\ntrailing\n")
        self.assertFalse(
            tracker._record_landed(
                2, kind="claim", fields=fields,
                posted={"id": cid}, known_comment_ids=set(),
            ),
            "a record with extra bytes appended was accepted",
        )

    def test_record_landed_requires_the_returned_comment_id(self) -> None:
        tracker, api = seeded_tracker()
        fields = {"session": "hermes/s", "operation": op_for("c"), "at": T1}
        cid = api.add_comment(2, WF.render_record("claim", fields))
        self.assertTrue(
            tracker._record_landed(
                2, kind="claim", fields=fields,
                posted={"id": cid}, known_comment_ids=set(),
            )
        )
        self.assertFalse(
            tracker._record_landed(
                2, kind="claim", fields=fields,
                posted={"id": cid + 500}, known_comment_ids=set(),
            ),
            "a comment other than the one the API reported was accepted",
        )

    def test_a_reclaim_whose_write_is_swallowed_is_not_a_false_zombie(self) -> None:
        """The end-to-end consequence of the snapshot filter.

        `hermes/late` claims, loses, withdraws cleanly. Later it retries the
        same operation while another session holds the ticket, and that write is
        swallowed. Without the snapshot filter the readback finds the *old*
        withdrawn claim record, the attempt believes it queued a claim, and the
        operator is told to recover a zombie that does not exist — sending them
        to clean up state that is already clean while the real failure (the
        write never landed) goes unreported.
        """
        tracker, api = seeded_tracker()
        real_request = api.request
        fired: list[str] = []

        def interleave(method, path, payload=None):
            body = (payload or {}).get("body", "")
            if method.upper() == "POST" and "wayfinder:claim" in body and not fired:
                fired.append("x")
                api.add_comment(
                    2,
                    WF.render_record(
                        "claim",
                        {"session": "claude/first", "operation": op_for("first"), "at": T0},
                    ),
                )
            return real_request(method, path, payload)

        api.request = interleave  # type: ignore[method-assign]
        first = tracker.claim(
            map_number=1, number=2, session="hermes/late", claimed_at=T1,
            operation=op_for("late"), apply=True,
        )
        api.request = real_request  # type: ignore[method-assign]
        self.assertFalse(first.won)
        self.assertIn("was withdrawn", first.reason, "premise: the loser cleaned up")

        identity = claim_id("late", "hermes/late")
        self.assertFalse(
            WF.acquisition_is_active(
                tracker.claim_records(2), hold="claim", drop="release", identity=identity
            ),
            "premise broken: the withdrawal did not take",
        )

        # The winner leaves, so the retry is a legitimate fresh attempt whose
        # only obstacle is the swallowed write.
        tracker.release(
            map_number=1, number=2, session="claude/first", released_at=T2,
            operation=op_for("first"), apply=True,
        )
        self.assertIsNone(tracker.current_claim(2))

        api.swallow.add("claim")
        with self.assertRaises(WF.WayfinderError) as caught:
            tracker.claim(
                map_number=1, number=2, session="hermes/late", claimed_at=T1,
                operation=op_for("late"), apply=True,
            )
        # The *specific* failure matters. Accepting the old withdrawn record as
        # proof would get past this readback and fail later with a misleading
        # "tracker state is unclear", or report a zombie that does not exist.
        self.assertIn("did not read back as a new comment", str(caught.exception))
        self.assertFalse(
            WF.acquisition_is_active(
                tracker.claim_records(2), hold="claim", drop="release", identity=identity
            ),
            "a swallowed retry was reported as a queued claim",
        )
        self.assertIsNone(tracker.current_claim(2), "the ticket must stay unclaimed")


class CloseIdentityTest(unittest.TestCase):
    def test_a_close_that_drops_the_ticket_identity_is_attributed_to_the_close(
        self,
    ) -> None:
        """The close's own readback must catch it, not a later step.

        Stripping the label and restoring it on the next read means only the
        close's readback can see the damage — so a readback that checks
        `state == "closed"` alone passes and the operation reports success over
        a ticket that is no longer findable from its map.
        """
        tracker, api = claimed_tracker()
        real_request = api.request
        state = {"stripped": False}
        saved = list(api.issues[2]["labels"])

        def strip_then_restore(method, path, payload=None):
            if (
                method.upper() == "PATCH"
                and path.endswith("/issues/2")
                and (payload or {}).get("state") == "closed"
            ):
                result = real_request(method, path, payload)
                api.issues[2]["labels"] = []
                state["stripped"] = True
                return result
            result = real_request(method, path, payload)
            if state["stripped"] and method.upper() == "GET" and path.endswith("/issues/2"):
                # The readback has already seen the damage; put it back so no
                # later step can be the one that complains.
                api.issues[2]["labels"] = saved
                state["stripped"] = False
            return result

        api.request = strip_then_restore  # type: ignore[method-assign]
        with self.assertRaises(WF.WayfinderError) as caught:
            tracker.resolve_ticket(
                map_number=1, number=2, session="hermes/s",
                claim_operation=op_for("c2"),
                answer="A.", map_index_line="Chose X", at=T1, apply=True,
            )
        self.assertIn("was closed but no longer reads back as a ticket", str(caught.exception))


# ==========================================================================
# Shipping blocker 1 — canonical decision state publishes before the close
# ==========================================================================


class ResolutionOrderingTest(unittest.TestCase):
    """The close is the last write: no decision of record, no closed ticket."""

    def resolve(self, tracker, **kwargs):
        args = dict(
            map_number=1, number=2, session="hermes/s",
            claim_operation=op_for("c2"), answer="Chose flat.",
            map_index_line="Storage shape: flat", at=T1, apply=True,
        )
        args.update(kwargs)
        return tracker.resolve_ticket(**args)

    def test_the_index_record_posts_before_the_close(self) -> None:
        tracker, api = claimed_tracker()
        out = self.resolve(tracker)
        self.assertTrue(out.resolved)
        index_post = next(
            i for i, (method, path) in enumerate(api.calls)
            if method == "POST" and path.endswith("/issues/1/comments")
        )
        close_patch = next(
            i for i, (method, path) in enumerate(api.calls)
            if method == "PATCH" and path.endswith("/issues/2")
        )
        self.assertLess(
            index_post, close_patch,
            "the canonical decision must publish before the ticket closes",
        )

    def test_a_failed_index_keeps_the_ticket_open_and_dependents_blocked(self) -> None:
        tracker, api = seeded_tracker()  # #3 is blocked by the open #2
        tracker.claim(
            map_number=1, number=2, session="hermes/s", claimed_at=T1,
            operation=op_for("c2"), apply=True,
        )
        api.swallow.add("index")
        with self.assertRaises(WF.WayfinderError):
            self.resolve(tracker)
        self.assertEqual(
            api.issues[2]["state"], "open",
            "a failed index append must leave the ticket open",
        )
        self.assertNotIn(
            3, [t.number for t in tracker.frontier(1)],
            "dependents must stay blocked while no decision of record exists",
        )
        api.swallow.discard("index")
        again = self.resolve(tracker)
        self.assertTrue(again.resolved)
        self.assertEqual(again.already, ["comment"])
        self.assertTrue(again.indexed and again.closed)
        self.assertIn(
            3, [t.number for t in tracker.frontier(1)],
            "the dependent unblocks once the decision of record exists",
        )

    def test_resolved_requires_the_index_to_be_the_tickets_current_decision(self) -> None:
        """`resolved` is comment + exact ticket-scoped current index + close."""
        tracker, api = claimed_tracker()
        out = self.resolve(tracker)
        self.assertTrue(out.resolved)
        # An index record for the same key but a DIFFERENT ticket never
        # satisfies this ticket's resolution.
        key = WF.resolution_key(1, 2, "Chose flat.")
        records = tracker.map_index_records(1)
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0].fields["ticket"], "2")
        self.assertEqual(records[0].fields["key"], key)


# ==========================================================================
# Shipping blocker 2 — creates converge after an ambiguous success
# ==========================================================================


class CreationConvergenceTest(unittest.TestCase):
    """A create whose response was lost must converge on retry, not duplicate."""

    def lose_response_once(self, api) -> None:
        """The POST commits on the server; the client never sees the response."""
        real_request = api.request
        lost: list[str] = []

        def lose(method, path, payload=None):
            result = real_request(method, path, payload)
            if (
                method.upper() == "POST"
                and path == f"{REPO.api_base}/issues"
                and not lost
            ):
                lost.append("x")
                raise WF.WayfinderError("connection lost after the server committed")
            return result

        api.request = lose  # type: ignore[method-assign]

    def test_previews_expose_a_retained_creation_identity(self) -> None:
        tracker, _ = seeded_tracker()
        for preview in (
            tracker.create_map(
                title="M", managed="## Destination", creation=op_for("m")
            ),
            tracker.create_ticket(
                map_number=1, title="T", question="Q?", ticket_type="task",
                creation=op_for("t"),
            ),
        ):
            with self.subTest(action=preview.action):
                rendered = preview.render()
                self.assertIn("creation identity", rendered)
                self.assertIn("--creation", rendered)
                self.assertIn("wayfinder:created", rendered)

    def test_apply_without_the_previewed_creation_is_refused(self) -> None:
        tracker, api = seeded_tracker()
        before = len(api.issues)
        for run in (
            lambda: tracker.create_map(title="M", managed="## D", apply=True),
            lambda: tracker.create_ticket(
                map_number=1, title="T", question="Q?", ticket_type="task",
                apply=True,
            ),
        ):
            with self.assertRaises(WF.WayfinderError) as caught:
                run()
            self.assertIn("--creation", str(caught.exception))
        self.assertEqual(len(api.issues), before)

    def test_a_ticket_retry_after_a_lost_response_converges(self) -> None:
        tracker, api = seeded_tracker()
        self.lose_response_once(api)
        kwargs = dict(
            map_number=1, title="T", question="Q?", ticket_type="task",
            creation=op_for("create-t"), apply=True,
        )
        with self.assertRaises(WF.WayfinderError):
            tracker.create_ticket(**kwargs)
        ticket = tracker.create_ticket(**kwargs)
        matching = [i for i in api.issues.values() if i["title"] == "T"]
        self.assertEqual(len(matching), 1, "the retry created a duplicate ticket")
        self.assertEqual(ticket.number, matching[0]["number"])
        self.assertEqual((ticket.map_number, ticket.ticket_type), (1, "task"))

    def test_a_map_retry_after_a_lost_response_converges(self) -> None:
        tracker, api = seeded_tracker()
        self.lose_response_once(api)
        kwargs = dict(
            title="M", managed="## Destination\n", creation=op_for("create-m"),
            apply=True,
        )
        with self.assertRaises(WF.WayfinderError):
            tracker.create_map(**kwargs)
        view = tracker.create_map(**kwargs)
        matching = [i for i in api.issues.values() if i["title"] == "M"]
        self.assertEqual(len(matching), 1, "the retry created a duplicate map")
        self.assertEqual(view["number"], matching[0]["number"])

    def test_multiple_matches_fail_closed(self) -> None:
        tracker, api = seeded_tracker()
        creation = op_for("dup")
        body = f"x\n\n{WF.render_created_marker(creation)}\n"
        api.add_issue(title="A", body=body, labels=[], number=70)
        api.add_issue(title="B", body=body, labels=[], number=71)
        with self.assertRaises(WF.WayfinderError) as caught:
            tracker.create_ticket(
                map_number=1, title="T", question="Q?", ticket_type="task",
                creation=creation, apply=True,
            )
        self.assertIn("2 issues carry creation identity", str(caught.exception))
        self.assertNotIn("T", [i["title"] for i in api.issues.values()])

    def test_an_inexact_match_fails_closed(self) -> None:
        tracker, api = seeded_tracker()
        creation = op_for("odd")
        api.add_issue(
            title="Wrong",
            body=f"different\n\n{WF.render_created_marker(creation)}\n",
            labels=[], number=72,
        )
        with self.assertRaises(WF.WayfinderError) as caught:
            tracker.create_ticket(
                map_number=1, title="T", question="Q?", ticket_type="task",
                creation=creation, apply=True,
            )
        self.assertIn("byte-for-byte", str(caught.exception))
        self.assertNotIn("T", [i["title"] for i in api.issues.values()])

    def test_a_created_issue_carries_its_creation_identity(self) -> None:
        tracker, api = seeded_tracker()
        ticket = tracker.create_ticket(
            map_number=1, title="T", question="Q?", ticket_type="task",
            creation=op_for("t2"), apply=True,
        )
        self.assertEqual(
            WF.parse_creation(api.issues[ticket.number]["body"]), op_for("t2")
        )

    def test_previewed_and_applied_bodies_are_byte_identical(self) -> None:
        tracker, api = seeded_tracker()
        creation = op_for("bytes")
        kwargs = dict(
            map_number=1, title="T", question="Q?", ticket_type="task",
            creation=creation,
        )
        previewed = tracker.create_ticket(**kwargs).content[0]["text"]
        ticket = tracker.create_ticket(**kwargs, apply=True)
        self.assertEqual(api.issues[ticket.number]["body"], previewed)

    def test_a_malformed_creation_id_is_refused(self) -> None:
        tracker, api = seeded_tracker()
        for bad in ("nope", op_for("x")[:8], op_for("x").upper()):
            with self.subTest(creation=bad), self.assertRaises(WF.WayfinderError):
                tracker.create_ticket(
                    map_number=1, title="T", question="Q?", ticket_type="task",
                    creation=bad, apply=True,
                )


# ==========================================================================
# Shipping blocker 3 — one canonical current decision per ticket
# ==========================================================================


class DecisionSupersessionTest(unittest.TestCase):
    """Replay exposes at most one current canonical decision per ticket."""

    def resolve(self, tracker, answer, gist, at=T1):
        return tracker.resolve_ticket(
            map_number=1, number=2, session="hermes/s",
            claim_operation=op_for("c2"), answer=answer,
            map_index_line=gist, at=at, apply=True,
        )

    def test_the_original_decision_is_current(self) -> None:
        tracker, _ = claimed_tracker()
        out = self.resolve(tracker, "Original.", "Original decision")
        self.assertTrue(out.resolved)
        self.assertEqual(
            [d["gist"] for d in tracker.map_decisions(1)], ["Original decision"]
        )

    def test_a_changed_answer_on_a_closed_ticket_is_refused(self) -> None:
        tracker, api = claimed_tracker()
        self.resolve(tracker, "Original.", "Original decision")
        map_comments = len(api.comments.get(1, []))
        ticket_comments = len(api.comments.get(2, []))
        with self.assertRaises(WF.WayfinderError) as caught:
            self.resolve(tracker, "Corrected.", "Corrected decision", at=T2)
        self.assertIn("reopen", str(caught.exception).lower())
        self.assertEqual(
            len(api.comments.get(1, [])), map_comments,
            "no second current decision may be indexed",
        )
        self.assertEqual(
            len(api.comments.get(2, [])), ticket_comments,
            "the refusal must write nothing",
        )
        self.assertEqual(
            [d["gist"] for d in tracker.map_decisions(1)], ["Original decision"]
        )

    def test_a_correction_after_reopen_supersedes(self) -> None:
        tracker, api = claimed_tracker()
        self.resolve(tracker, "Original.", "Original decision")
        api.issues[2]["state"] = "open"  # Bryan reopens the affected decision
        out = self.resolve(tracker, "Corrected.", "Corrected decision", at=T2)
        self.assertTrue(out.resolved)
        self.assertEqual(
            [d["gist"] for d in tracker.map_decisions(1)], ["Corrected decision"],
            "exactly one current decision per ticket",
        )
        # History stays append-only and inspectable: both records remain.
        self.assertEqual(len(tracker.map_index_records(1)), 2)

    def test_repeated_correction_keeps_one_current_decision(self) -> None:
        tracker, api = claimed_tracker()
        self.resolve(tracker, "First.", "First decision")
        api.issues[2]["state"] = "open"
        self.resolve(tracker, "Second.", "Second decision", at=T2)
        api.issues[2]["state"] = "open"
        out = self.resolve(tracker, "Third.", "Third decision", at="2026-08-19T12:00:00Z")
        self.assertTrue(out.resolved)
        self.assertEqual(
            [d["gist"] for d in tracker.map_decisions(1)], ["Third decision"]
        )
        self.assertEqual(len(tracker.map_index_records(1)), 3)

    def test_a_retry_of_the_same_decision_converges(self) -> None:
        tracker, api = claimed_tracker()
        self.resolve(tracker, "Original.", "Original decision")
        again = self.resolve(tracker, "Original.", "Original decision", at=T2)
        self.assertTrue(again.resolved)
        self.assertEqual(sorted(again.already), ["closed", "comment", "indexed"])
        self.assertEqual(len(tracker.map_decisions(1)), 1)

    def test_a_late_duplicate_of_an_old_key_cannot_overturn_a_correction(self) -> None:
        """Replay ordering: supersession keys on each key's FIRST record."""
        old = WF.ManagedRecord(
            comment_id=10, kind="index",
            fields={"key": "a" * 16, "map": "1", "ticket": "7",
                    "gist": "old", "session": "s/a", "at": T0},
        )
        correction = WF.ManagedRecord(
            comment_id=20, kind="index",
            fields={"key": "b" * 16, "map": "1", "ticket": "7",
                    "gist": "corrected", "session": "s/a", "at": T1},
        )
        stale_retry = WF.ManagedRecord(
            comment_id=30, kind="index",
            fields={"key": "a" * 16, "map": "1", "ticket": "7",
                    "gist": "old reworded", "session": "s/a", "at": T2},
        )
        replayed = WF.index_replay([stale_retry, correction, old])
        self.assertEqual(
            [(r.comment_id, r.fields["gist"]) for r in replayed],
            [(20, "corrected")],
        )

    def test_a_superseded_retry_reports_not_resolved(self) -> None:
        tracker, api = claimed_tracker()
        self.resolve(tracker, "Original.", "Original decision")
        api.issues[2]["state"] = "open"
        self.resolve(tracker, "Corrected.", "Corrected decision", at=T2)
        # A stale retry of the superseded original: nothing new lands, and it
        # must be reported as not being the decision of record.
        again = self.resolve(
            tracker, "Original.", "Original decision", at="2026-08-19T12:00:00Z"
        )
        self.assertFalse(again.resolved)
        self.assertIn("superseded", again.recovery)
        self.assertEqual(
            [d["gist"] for d in tracker.map_decisions(1)], ["Corrected decision"]
        )


# ==========================================================================
# Shipping blocker 4 — preview and apply are byte-identical for claims
# ==========================================================================


class ClaimPreviewApplyTest(unittest.TestCase):
    def test_apply_without_an_operation_is_refused_before_any_request(self) -> None:
        tracker, api = seeded_tracker()
        before = len(api.calls)
        with self.assertRaises(WF.WayfinderError) as caught:
            tracker.claim(
                map_number=1, number=2, session="hermes/s", claimed_at=T1,
                apply=True,
            )
        self.assertIn("--operation", str(caught.exception))
        self.assertEqual(len(api.calls), before, "the refusal must be local")

    def test_the_preview_prints_the_operation_and_the_apply_command(self) -> None:
        tracker, _ = seeded_tracker()
        preview = tracker.claim(
            map_number=1, number=2, session="hermes/s", claimed_at=T1,
            operation=op_for("c"),
        )
        rendered = preview.render()
        self.assertIn(op_for("c"), rendered)
        self.assertIn("--operation", rendered)
        self.assertIn("--apply", rendered)

    def test_previewed_and_applied_records_are_byte_identical(self) -> None:
        tracker, api = seeded_tracker()
        preview = tracker.claim(
            map_number=1, number=2, session="hermes/s", claimed_at=T1,
            operation=op_for("c"),
        )
        previewed = preview.content[0]["text"]
        outcome = tracker.claim(
            map_number=1, number=2, session="hermes/s", claimed_at=T1,
            operation=op_for("c"), apply=True,
        )
        self.assertTrue(outcome.won)
        bodies = [c["body"] for c in api.comments[2]]
        self.assertIn(
            previewed, bodies, "the applied record differs from the reviewed one"
        )

    def test_the_cli_refuses_apply_without_an_operation(self) -> None:
        _tracker, api = seeded_tracker()
        argv = [
            "--origin", f"ssh://git@{REPO.host}/{REPO.owner}/{REPO.repo}.git",
            "--tracker", REPO.slug, "--apply",
            "claim", "--map", "1", "--ticket", "2", "--session", "s", "--at", T1,
        ]
        real = WF.build_transport
        WF.build_transport = lambda repo, **kwargs: api  # type: ignore[assignment]
        err = io.StringIO()
        try:
            with contextlib.redirect_stderr(err), contextlib.redirect_stdout(io.StringIO()):
                code = WF.main(argv)
        finally:
            WF.build_transport = real  # type: ignore[assignment]
        self.assertEqual(code, 2)
        self.assertIn("--operation", err.getvalue())


# ==========================================================================
# Shipping blocker 5 — both dependency endpoints guarded at write time
# ==========================================================================


class WireBothEndpointsTest(unittest.TestCase):
    """The final guard revalidates BOTH endpoints just before the POST.

    The entry preflight reads each endpoint once (its first GET); the guard's
    re-read is the second GET, so drift injected there lands exactly between
    the preflight and the write — the window this blocker closes.
    """

    @staticmethod
    def strip_labels(fake, number) -> None:
        fake.issues[number]["labels"] = []

    @staticmethod
    def repoint(fake, number) -> None:
        fake.issues[number]["body"] = ticket_body("moved", 99)

    def test_blocked_by_drift_at_write_time_prevents_the_write(self) -> None:
        for label, damage, fragment in (
            ("label stripped", self.strip_labels, WF.TICKET_LABEL),
            ("repointed to another map", self.repoint, "belongs to map"),
        ):
            with self.subTest(drift=label):
                tracker, api = seeded_tracker()
                api.on_get[(3, 2)] = damage  # the guard's re-read of blocked_by
                with self.assertRaises(WF.WayfinderError) as caught:
                    tracker.wire_blocking(
                        map_number=1, blocked=2, blocked_by=3, apply=True
                    )
                self.assertIn(fragment, str(caught.exception))
                self.assertNotIn(
                    3, api.dependencies.get(2, []),
                    "the dependency write must not land after endpoint drift",
                )

    def test_blocked_drift_at_write_time_prevents_the_write(self) -> None:
        tracker, api = seeded_tracker()
        api.on_get[(2, 2)] = self.strip_labels  # the guard's re-read of blocked
        with self.assertRaises(WF.WayfinderError):
            tracker.wire_blocking(map_number=1, blocked=2, blocked_by=3, apply=True)
        self.assertNotIn(3, api.dependencies.get(2, []))

    def test_a_clean_wire_still_lands_and_reads_back_exactly(self) -> None:
        tracker, api = seeded_tracker()
        blockers = tracker.wire_blocking(
            map_number=1, blocked=2, blocked_by=3, apply=True
        )
        self.assertEqual(sorted(api.dependencies[2]), sorted(blockers))
        self.assertIn(3, blockers)


if __name__ == "__main__":
    unittest.main()
