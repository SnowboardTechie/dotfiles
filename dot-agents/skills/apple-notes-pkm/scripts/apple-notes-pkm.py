#!/usr/bin/env python3
"""apple-notes-pkm — bounded, scoped helper for the iCloud "Second Brain" folder.

Every command prints one JSON object. Reads and writes are hard-scoped to one
root folder (default "Second Brain" in the iCloud account); a note outside it is
reported as not found. Search never returns the whole library: results are
capped small and carry only {id, title, folder, modified, snippet}. Full content
is fetched only by exact id and returned as clean Markdown, never inline media.

Writes require the note's current revision token (its modification timestamp as
read) and are verified by an immediate readback. There is no delete command.

Exit codes: 0 ok · 1 error · 2 usage · 3 stale revision · 4 refused (unsafe)
· 5 Automation permission denied · 6 post-write verification failed.

Environment: APPLE_NOTES_PKM_ROOT / APPLE_NOTES_PKM_ACCOUNT override the scope
(used by the disposable pilot folder and tests); APPLE_NOTES_PKM_OSASCRIPT points
the tests at a stub interpreter.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from notes_markdown import (  # noqa: E402
    markdown_to_notes_html,
    notes_html_to_markdown,
    scrub_data_uris,
    split_frontmatter,
)

SCRIPT_DIR = Path(__file__).resolve().parent
JXA = SCRIPT_DIR / "notes.jxa"
OSASCRIPT = os.environ.get("APPLE_NOTES_PKM_OSASCRIPT", "/usr/bin/osascript")  # tests stub this
DEFAULT_ROOT = os.environ.get("APPLE_NOTES_PKM_ROOT", "Second Brain")
DEFAULT_ACCOUNT = os.environ.get("APPLE_NOTES_PKM_ACCOUNT", "iCloud")
PERMISSION_MARKERS = ("Not authorized to send Apple events", "-1743", "-10004")

EXIT_OK, EXIT_ERROR, EXIT_USAGE, EXIT_STALE, EXIT_REFUSED, EXIT_PERMISSION, EXIT_UNVERIFIED = 0, 1, 2, 3, 4, 5, 6


class HelperError(Exception):
    def __init__(self, message: str, code: int = EXIT_ERROR, **extra):
        super().__init__(message)
        self.code = code
        self.extra = extra


def jxa(request: dict, *, timeout: int = 180) -> dict:
    request = {"root": DEFAULT_ROOT, "account": DEFAULT_ACCOUNT, **request}
    try:
        proc = subprocess.run(
            [OSASCRIPT, "-l", "JavaScript", str(JXA), json.dumps(request)],
            capture_output=True, text=True, timeout=timeout, check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise HelperError(f"Notes automation timed out after {timeout}s") from exc
    stdout = proc.stdout.strip()
    stderr = proc.stderr.strip()
    if any(marker in stderr for marker in PERMISSION_MARKERS):
        raise HelperError(
            "macOS Automation permission for Notes is missing or denied for this process; "
            "grant it in System Settings > Privacy & Security > Automation (a human action)",
            EXIT_PERMISSION, stderr=stderr,
        )
    if proc.returncode != 0 and not stdout:
        raise HelperError(f"osascript failed: {stderr or proc.returncode}")
    try:
        result = json.loads(stdout)
    except json.JSONDecodeError as exc:
        raise HelperError(f"unparseable helper output: {stdout[:300]!r} {stderr[:300]!r}") from exc
    if not result.get("ok"):
        number = result.get("errorNumber")
        message = result.get("error", "unknown error")
        if any(marker in message for marker in PERMISSION_MARKERS):
            raise HelperError(message, EXIT_PERMISSION)
        if number == "stale":
            raise HelperError(message, EXIT_STALE)
        if number == "unsafe":
            raise HelperError(message, EXIT_REFUSED)
        raise HelperError(message)
    result.pop("ok", None)
    return result


def normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def present_note(note: dict, *, raw: bool = False) -> dict:
    """Shape a full note for callers: Markdown content, no inline media."""
    out = {
        "id": note["id"],
        "title": note["title"],
        "folder": note["folder"],
        "created": note.get("created"),
        "modified": note.get("modified"),
        "revision": note.get("revision") or note.get("modified"),
        "attachments": note.get("attachments", []),
        "shared": note.get("shared"),
        "passwordProtected": note.get("passwordProtected"),
        "markdown": notes_html_to_markdown(note.get("body", "")),
    }
    if raw:
        out["body_html"] = scrub_data_uris(note.get("body", ""))
        out["plaintext"] = note.get("plaintext", "")
    return out


def read_body_arg(args) -> str:
    if getattr(args, "body_file", None):
        return Path(args.body_file).read_text(encoding="utf-8")
    if getattr(args, "body", None) is not None:
        return args.body
    if not sys.stdin.isatty():
        return sys.stdin.read()
    raise HelperError("provide --body, --body-file, or Markdown on stdin", EXIT_USAGE)


def verify_files(files: list[str]) -> list[str]:
    resolved = []
    for item in files or []:
        path = Path(item).expanduser().resolve()
        if not path.is_file():
            raise HelperError(f"attachment file not found: {item}", EXIT_USAGE)
        resolved.append(str(path))
    return resolved


# ---------------------------------------------------------------- commands

def cmd_health(args):
    if args.probe:
        return jxa({"op": "probe", "activate": args.activate}, timeout=600)
    result = jxa({"op": "health"})
    result["helper"] = str(SCRIPT_DIR)
    result["scope"] = {"account": DEFAULT_ACCOUNT, "root": DEFAULT_ROOT}
    return result


def cmd_folders(args):
    return jxa({"op": "folders"})


def cmd_ensure_root(args):
    return jxa({"op": "ensure-root"})


def cmd_ensure_folder(args):
    return jxa({"op": "ensure-folder", "path": args.path})


def cmd_search(args):
    return jxa({"op": "search", "query": args.query, "limit": args.limit, "folder": args.folder, "mode": args.mode}, timeout=300)


def cmd_list(args):
    return jxa({"op": "list", "folder": args.folder or "", "limit": args.limit}, timeout=300)


def cmd_inventory(args):
    return jxa({"op": "inventory"}, timeout=900)


def cmd_read(args):
    result = jxa({"op": "read", "id": args.id})
    return {"note": present_note(result["note"], raw=args.raw)}


def _readback(note_id: str) -> dict:
    return jxa({"op": "read", "id": note_id})["note"]


def cmd_create(args):
    markdown = read_body_arg(args)
    meta, body = split_frontmatter(markdown) if args.strip_frontmatter else ({}, markdown)
    html_body = markdown_to_notes_html(body, title=args.title, meta=meta if args.keep_meta else None)
    files = verify_files(args.attach)
    result = jxa({"op": "create", "folder": args.folder, "body": html_body, "attachments": files}, timeout=600)
    created = result["note"]
    check = _readback(created["id"])
    problems = []
    if check["title"] != args.title:
        problems.append(f"title mismatch: expected {args.title!r}, got {check['title']!r}")
    if len(check.get("attachments", [])) < len(files):
        problems.append(f"attachments: expected {len(files)}, found {len(check.get('attachments', []))}")
    if not normalize_text(check.get("plaintext", "")):
        problems.append("note body is empty after create")
    out = {"note": present_note(check), "verified": not problems, "problems": problems}
    if problems:
        raise HelperError("post-write verification failed: " + "; ".join(problems), EXIT_UNVERIFIED, result=out)
    return out


def cmd_append(args):
    markdown = read_body_arg(args)
    if not markdown.strip():
        raise HelperError("append body is empty", EXIT_USAGE)
    html_body = "<div><br></div>" + markdown_to_notes_html(markdown)
    result = jxa({"op": "append", "id": args.id, "revision": args.revision, "body": html_body})
    check = _readback(result["note"]["id"])
    expected = normalize_text(re.sub(r"<[^>]+>", " ", html_body))
    actual = normalize_text(check.get("plaintext", ""))
    problems = []
    if expected and expected[-min(len(expected), 80):] not in actual:
        problems.append("appended text not found in readback")
    out = {"note": present_note(check), "verified": not problems, "problems": problems}
    if problems:
        raise HelperError("post-write verification failed: " + "; ".join(problems), EXIT_UNVERIFIED, result=out)
    return out


def cmd_replace(args):
    markdown = read_body_arg(args)
    current = _readback(args.id)
    title = args.title or current["title"]
    html_body = markdown_to_notes_html(markdown, title=title)
    result = jxa({"op": "replace", "id": args.id, "revision": args.revision, "body": html_body})
    check = _readback(result["note"]["id"])
    problems = []
    if check["title"] != title:
        problems.append(f"title mismatch: expected {title!r}, got {check['title']!r}")
    if not normalize_text(check.get("plaintext", "")):
        problems.append("note body is empty after replace")
    out = {"note": present_note(check), "verified": not problems, "problems": problems}
    if problems:
        raise HelperError("post-write verification failed: " + "; ".join(problems), EXIT_UNVERIFIED, result=out)
    return out


def cmd_attach(args):
    files = verify_files(args.files)
    result = jxa({"op": "attach", "id": args.id, "revision": args.revision, "files": files}, timeout=600)
    check = _readback(result["note"]["id"])
    before = len(result["note"].get("attachments", [])) - len(files)
    problems = []
    if len(check.get("attachments", [])) < before + len(files):
        problems.append("attachment count did not increase as expected")
    out = {"note": present_note(check), "verified": not problems, "problems": problems}
    if problems:
        raise HelperError("post-write verification failed: " + "; ".join(problems), EXIT_UNVERIFIED, result=out)
    return out


def cmd_links(args):
    return jxa({"op": "links", "id": args.id}, timeout=300)


def cmd_backlinks(args):
    if not args.id and not args.title:
        raise HelperError("provide --id or --title", EXIT_USAGE)
    return jxa({"op": "backlinks", "id": args.id, "title": args.title, "limit": args.limit}, timeout=600)


def cmd_convert(args):
    """Offline: render Markdown to the HTML the helper would send (no Notes access)."""
    markdown = read_body_arg(args)
    meta, body = split_frontmatter(markdown) if args.strip_frontmatter else ({}, markdown)
    return {"html": markdown_to_notes_html(body, title=args.title, meta=meta if args.keep_meta else None)}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="apple-notes-pkm", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("health", help="account/root/folder preflight")
    p.add_argument("--probe", action="store_true", help="time each Notes scripting surface separately")
    p.add_argument("--activate", action="store_true", help="bring Notes to the foreground first (probe only)")
    p.set_defaults(func=cmd_health)
    sub.add_parser("folders", help="folders beneath the root with note counts").set_defaults(func=cmd_folders)
    sub.add_parser("ensure-root", help="create the root folder if missing (setup/import only)").set_defaults(func=cmd_ensure_root)
    p = sub.add_parser("ensure-folder", help="create a folder path beneath the root (import/setup only)")
    p.add_argument("path")
    p.set_defaults(func=cmd_ensure_folder)

    p = sub.add_parser("search", help="bounded search; at most 25 summaries")
    p.add_argument("query")
    p.add_argument("--limit", type=int, default=10)
    p.add_argument("--folder", help="restrict to a folder path beneath the root")
    p.add_argument("--mode", choices=("any", "title", "body"), default="any")
    p.set_defaults(func=cmd_search)

    p = sub.add_parser("list", help="summaries of one folder's own notes (bounded)")
    p.add_argument("--folder", default="")
    p.add_argument("--limit", type=int, default=50)
    p.set_defaults(func=cmd_list)

    sub.add_parser("inventory", help="migration/verification only: every note summary beneath the root").set_defaults(func=cmd_inventory)

    p = sub.add_parser("read", help="exact-id read as Markdown")
    p.add_argument("id")
    p.add_argument("--raw", action="store_true", help="also include body HTML and plaintext")
    p.set_defaults(func=cmd_read)

    p = sub.add_parser("create", help="create a note in an existing folder beneath the root")
    p.add_argument("--folder", required=True, help="folder path beneath the root ('' for the root itself)")
    p.add_argument("--title", required=True)
    p.add_argument("--body")
    p.add_argument("--body-file")
    p.add_argument("--attach", nargs="*", default=[])
    p.add_argument("--strip-frontmatter", action="store_true")
    p.add_argument("--keep-meta", action="store_true", help="append retained frontmatter values as visible text")
    p.set_defaults(func=cmd_create)

    p = sub.add_parser("append", help="append Markdown to a note (requires --revision)")
    p.add_argument("id")
    p.add_argument("--revision", required=True)
    p.add_argument("--body")
    p.add_argument("--body-file")
    p.set_defaults(func=cmd_append)

    p = sub.add_parser("replace", help="guarded full-body replacement (refuses notes with attachments)")
    p.add_argument("id")
    p.add_argument("--revision", required=True)
    p.add_argument("--title")
    p.add_argument("--body")
    p.add_argument("--body-file")
    p.set_defaults(func=cmd_replace)

    p = sub.add_parser("attach", help="attach files to an existing note (requires --revision)")
    p.add_argument("id")
    p.add_argument("--revision", required=True)
    p.add_argument("files", nargs="+")
    p.set_defaults(func=cmd_attach)

    p = sub.add_parser("links", help="outgoing links from a note, resolved against titles")
    p.add_argument("id")
    p.set_defaults(func=cmd_links)

    p = sub.add_parser("backlinks", help="notes linking to (or mentioning) a title")
    p.add_argument("--id")
    p.add_argument("--title")
    p.add_argument("--limit", type=int, default=10)
    p.set_defaults(func=cmd_backlinks)

    p = sub.add_parser("convert", help="offline Markdown -> Notes HTML preview")
    p.add_argument("--title")
    p.add_argument("--body")
    p.add_argument("--body-file")
    p.add_argument("--strip-frontmatter", action="store_true")
    p.add_argument("--keep-meta", action="store_true")
    p.set_defaults(func=cmd_convert)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        result = args.func(args)
    except HelperError as exc:
        payload = {"ok": False, "error": str(exc), "code": exc.code, **exc.extra}
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        return exc.code
    payload = {"ok": True, **result}
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    return EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main())
