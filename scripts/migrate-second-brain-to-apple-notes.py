#!/usr/bin/env python3
"""One-time migration of the personal vault into the iCloud "Second Brain" folder.

Governing record: ~/second-brain/Decisions/2026-09-16-decision-apple-notes-personal-second-brain.md

Three phases, each resumable and idempotent:

  stage   Read the source vault (never modified), build a disposable staging
          tree of Apple-friendly Markdown, and write manifest.json mapping each
          source file (path + sha256) to its staged path, title, folder,
          duplicate disposition, and expected attachments. No Notes access.
  import  Create one note per `import` manifest entry through the
          apple-notes-pkm helper (folders are created beneath the root as
          needed). Entries that already carry a note id are skipped, so a
          partial run can be resumed.
  verify  Read the live inventory back and check counts, folder set, one note
          per manifest entry, attachment counts, exclusions, bounded search,
          and representative exact-id reads against the staged text.

Only source files that are human-readable notes are imported: every *.md except
AGENTS.md/CLAUDE.md, excluding .obsidian/.hermes/.git/.trash/.claude/.claudian.
Byte-identical same-title files collapse to one note; divergent same-title
files are all kept (their folders keep them distinguishable).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
HELPER_DIR = REPO_ROOT / "dot-agents" / "skills" / "apple-notes-pkm" / "scripts"
HELPER = HELPER_DIR / "apple-notes-pkm.py"
sys.path.insert(0, str(HELPER_DIR))
from notes_markdown import stage_markdown  # noqa: E402

EXCLUDED_DIRS = {".git", ".obsidian", ".hermes", ".trash", ".claude", ".claudian"}
EXCLUDED_FILES = {"AGENTS.md", "CLAUDE.md"}
ATTACHMENT_DIRS = ("Attachments", "Manuals")
MANUALS_FOLDER = "Manuals"
INBOX_FOLDER = "Inbox"
ATTACHABLE_SUFFIXES = {".pdf", ".png", ".jpg", ".jpeg", ".gif", ".heic", ".html", ".txt", ".csv", ".mp4", ".mov", ".m4a"}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def helper(*args: str, root: str | None = None, timeout: int = 900) -> dict:
    env = os.environ.copy()
    if root:
        env["APPLE_NOTES_PKM_ROOT"] = root
    proc = subprocess.run([sys.executable, str(HELPER), *args], capture_output=True, text=True, env=env, timeout=timeout, check=False)
    try:
        payload = json.loads(proc.stdout)
    except json.JSONDecodeError:
        payload = {"ok": False, "error": f"helper produced no JSON (rc={proc.returncode}): {proc.stderr[-400:]}"}
    payload.setdefault("exit", proc.returncode)
    return payload


# ---------------------------------------------------------------- stage

def source_notes(source: Path) -> list[Path]:
    notes = []
    for directory, dirnames, filenames in os.walk(source):
        dirnames[:] = sorted(d for d in dirnames if d not in EXCLUDED_DIRS)
        for name in sorted(filenames):
            if name.endswith(".md") and name not in EXCLUDED_FILES:
                notes.append(Path(directory) / name)
    return notes


def source_files(source: Path) -> list[Path]:
    files = []
    for directory, dirnames, filenames in os.walk(source):
        dirnames[:] = sorted(d for d in dirnames if d not in EXCLUDED_DIRS)
        for name in sorted(filenames):
            path = Path(directory) / name
            if not name.endswith(".md") and name != ".gitignore" and not name.startswith("."):
                files.append(path)
    return files


def preferred(paths: list[Path], source: Path) -> Path:
    """Among byte-identical copies keep the shallowest non-Archive path."""
    def rank(path: Path):
        rel = path.relative_to(source)
        return ("Archive" in rel.parts, len(rel.parts), str(rel))
    return sorted(paths, key=rank)[0]


def build_manifest(source: Path, staging: Path) -> dict:
    notes = source_notes(source)
    by_key: dict[tuple[str, str], list[Path]] = defaultdict(list)
    hashes: dict[Path, str] = {}
    for path in notes:
        digest = sha256(path)
        hashes[path] = digest
        by_key[(path.stem, digest)].append(path)

    files = source_files(source)
    files_by_name: dict[str, list[Path]] = defaultdict(list)
    for path in files:
        files_by_name[path.name].append(path)

    entries = []
    kept_for: dict[tuple[str, str], Path] = {key: preferred(paths, source) for key, paths in by_key.items()}
    referenced_files: dict[Path, list[str]] = defaultdict(list)
    staged_root = staging / "notes"

    for path in notes:
        rel = path.relative_to(source)
        key = (path.stem, hashes[path])
        keep = kept_for[key]
        entry = {
            "kind": "note",
            "source_path": str(rel),
            "source_sha256": hashes[path],
            "title": path.stem,
            "folder": str(rel.parent) if str(rel.parent) != "." else "",
            "disposition": "import" if keep == path else "duplicate-omitted",
            "duplicate_of": None if keep == path else str(keep.relative_to(source)),
            "same_title_divergent": any(k[0] == path.stem and k[1] != hashes[path] for k in by_key),
            "staged_path": None,
            "attachments": [],
            "note_id": None,
        }
        if keep == path:
            text = path.read_text(encoding="utf-8")
            staged, _meta, embeds = stage_markdown(text, title=path.stem)
            staged_path = staged_root / rel
            staged_path.parent.mkdir(parents=True, exist_ok=True)
            staged_path.write_text(staged, encoding="utf-8")
            entry["staged_path"] = str(staged_path.relative_to(staging))
            for name in embeds:
                candidates = files_by_name.get(Path(name).name, [])
                if candidates and Path(name).suffix.lower() in ATTACHABLE_SUFFIXES:
                    chosen = candidates[0]
                    entry["attachments"].append({"name": Path(name).name, "source_path": str(chosen.relative_to(source)), "resolved": True})
                    referenced_files[chosen].append(str(rel))
                else:
                    entry["attachments"].append({"name": name, "source_path": None, "resolved": False})
        entries.append(entry)

    # Manuals: one carrier note per PDF so the manual is searchable/openable in Notes.
    # A manual is "referenced" when any kept note names the file (embed or plain wikilink).
    kept_texts = {str(p.relative_to(source)): p.read_text(encoding="utf-8", errors="replace") for p in kept_for.values()}
    file_entries = []
    for path in files:
        rel = path.relative_to(source)
        if rel.parts[0] == MANUALS_FOLDER and path.suffix.lower() == ".pdf":
            mentions = sorted(name for name, text in kept_texts.items() if path.name in text)
            file_entries.append({
                "kind": "attachment-note",
                "source_path": str(rel),
                "source_sha256": sha256(path),
                "title": path.stem,
                "folder": MANUALS_FOLDER,
                "disposition": "import",
                "size_bytes": path.stat().st_size,
                "referenced_by": mentions,
                "attachments": [{"name": path.name, "source_path": str(rel), "resolved": True}],
                "note_id": None,
            })
        else:
            refs = referenced_files.get(path, [])
            file_entries.append({
                "kind": "file",
                "source_path": str(rel),
                "source_sha256": sha256(path),
                "size_bytes": path.stat().st_size,
                "disposition": "attached-to-referencing-note" if refs else "archive-only-unreferenced",
                "referenced_by": refs,
            })

    folders = sorted({e["folder"] for e in entries if e["disposition"] == "import"} | {MANUALS_FOLDER, INBOX_FOLDER})
    manifest = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_root": str(source),
        "source_commit": git_head(source),
        "root_folder": "Second Brain",
        "expected_folders": [f for f in folders if f],
        "counts": {
            "source_markdown_files": len(notes),
            "unique_title_content_pairs": len(by_key),
            "duplicate_instances_omitted": sum(1 for e in entries if e["disposition"] == "duplicate-omitted"),
            "notes_to_import": sum(1 for e in entries if e["disposition"] == "import"),
            "manual_carrier_notes": sum(1 for e in file_entries if e["kind"] == "attachment-note"),
            "attachment_files": sum(1 for e in file_entries if e["kind"] == "file"),
            "attachment_files_referenced": sum(1 for e in file_entries if e["kind"] == "file" and e["referenced_by"]),
        },
        "entries": entries,
        "files": file_entries,
    }
    return manifest


def git_head(repo: Path) -> str | None:
    proc = subprocess.run(["git", "-C", str(repo), "rev-parse", "HEAD"], capture_output=True, text=True, check=False)
    return proc.stdout.strip() or None


def cmd_stage(args) -> int:
    source = Path(args.source).expanduser().resolve()
    staging = Path(args.staging).expanduser().resolve()
    staging.mkdir(parents=True, exist_ok=True)
    manifest = build_manifest(source, staging)
    (staging / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"staging": str(staging), **manifest["counts"], "expected_folders": manifest["expected_folders"]}, indent=2))
    return 0


# ---------------------------------------------------------------- import

def load_manifest(staging: Path) -> dict:
    return json.loads((staging / "manifest.json").read_text(encoding="utf-8"))


def save_manifest(staging: Path, manifest: dict) -> None:
    tmp = staging / "manifest.json.tmp"
    tmp.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    tmp.replace(staging / "manifest.json")


def cmd_import(args) -> int:
    staging = Path(args.staging).expanduser().resolve()
    source = Path(args.source).expanduser().resolve()
    manifest = load_manifest(staging)
    root = manifest["root_folder"]

    health = helper("health", root=root)
    if not health.get("ok"):
        print(json.dumps(health, indent=2))
        return 1
    if "iCloud" not in health.get("accounts", []) or health.get("account") != "iCloud":
        print("refusing: iCloud account not found or not selected", file=sys.stderr)
        return 1
    if not health.get("rootFound"):
        ensured = helper("ensure-root", root=root)
        print("root:", json.dumps(ensured))
    for folder in manifest["expected_folders"]:
        ensured = helper("ensure-folder", folder, root=root)
        if not ensured.get("ok"):
            print(json.dumps(ensured, indent=2))
            return 1
        if ensured.get("created"):
            print("created folder:", "/".join(ensured["created"]))

    pending = [e for e in manifest["entries"] if e["disposition"] == "import" and not e.get("note_id")]
    pending += [e for e in manifest["files"] if e["kind"] == "attachment-note" and not e.get("note_id")]
    if args.limit:
        pending = pending[: args.limit]
    print(f"importing {len(pending)} notes into {root}")
    failures = 0
    for index, entry in enumerate(pending, 1):
        attach = [str(source / a["source_path"]) for a in entry.get("attachments", []) if a.get("resolved")]
        if entry["kind"] == "note":
            body_file = staging / entry["staged_path"]
        else:
            body_file = staging / "carriers" / (entry["title"] + ".md")
            body_file.parent.mkdir(parents=True, exist_ok=True)
            refs = ", ".join(entry.get("referenced_by") or []) or "no vault note referenced it"
            body_file.write_text(
                f"Attached: {entry['attachments'][0]['name']}\n\nImported from the vault folder `{MANUALS_FOLDER}/` on cutover; referenced by: {refs}.\n",
                encoding="utf-8",
            )
        cmd = ["create", "--folder", entry["folder"], "--title", entry["title"], "--body-file", str(body_file)]
        if attach:
            cmd += ["--attach", *attach]
        result = helper(*cmd, root=root, timeout=1800)
        if result.get("ok"):
            entry["note_id"] = result["note"]["id"]
            entry["imported_at"] = datetime.now(timezone.utc).isoformat()
            entry["imported_attachments"] = len(result["note"].get("attachments", []))
            status = "ok"
        else:
            failures += 1
            entry["import_error"] = result.get("error")
            note = (result.get("result") or {}).get("note")
            if note:
                entry["note_id"] = note["id"]  # created but unverified; verify will flag it
            status = f"FAILED: {result.get('error')}"
        print(f"[{index}/{len(pending)}] {entry['folder'] or '.'}/{entry['title']} -> {status}")
        save_manifest(staging, manifest)
        if failures and args.stop_on_error:
            break
    print(json.dumps({"imported": len(pending) - failures, "failed": failures}))
    return 1 if failures else 0


# ---------------------------------------------------------------- verify

def normalize(text: str) -> str:
    """Comparable prose: drop URLs, list numbering, and Markdown punctuation.
    Notes' plaintext omits link targets and renumbers lists, so neither may
    decide whether the words made it across."""
    text = re.sub(r"\((?:https?://|mailto:)[^)]*\)", " ", text or "")
    text = re.sub(r"(?:https?://|mailto:)\S+", " ", text)
    text = re.sub(r"^\s*\d+[.)]\s+", " ", text, flags=re.M)
    text = re.sub(r"[`*_>#|\\\[\]()☐☑￼-]", " ", text)
    return re.sub(r"\s+", " ", text).strip().casefold()


def _representative_reads(args, staging: Path, root: str, expected_notes: list, check) -> None:
    """Exact-id reads: the staged prose must be recoverable from the live note."""
    sample = expected_notes[:: max(1, len(expected_notes) // args.samples)][: args.samples]
    read_detail, read_ok = [], True
    for entry in sample:
        if not entry.get("note_id"):
            continue
        note = helper("read", entry["note_id"], "--raw", root=root)
        if not note.get("ok"):
            read_ok = False
            read_detail.append({"title": entry["title"], "error": note.get("error")})
            continue
        staged = (staging / entry["staged_path"]).read_text(encoding="utf-8")
        wanted = normalize(re.sub(r"\[attachment: [^\]]*\]", " ", staged))[:240]
        live = normalize(note["note"]["markdown"]) + " " + normalize(note["note"]["plaintext"])
        ok = wanted[:120] in live and note["note"]["title"] == entry["title"] and note["note"]["folder"] == entry["folder"]
        read_ok &= ok
        read_detail.append({"title": entry["title"], "folder": entry["folder"], "ok": ok})
    check("representative_reads", read_ok, read_detail)


def cmd_verify(args) -> int:
    staging = Path(args.staging).expanduser().resolve()
    manifest = load_manifest(staging)
    root = manifest["root_folder"]
    report_path = staging / "verify-report.json"
    report: dict = {"root": root, "checks": {}, "problems": []}
    if args.only_reads and report_path.exists():
        report = json.loads(report_path.read_text(encoding="utf-8"))
        report["problems"] = [p for p in report.get("problems", []) if p != "representative_reads"]

    def check(name: str, ok: bool, detail=None):
        report["checks"][name] = {"ok": ok, "detail": detail}
        if not ok:
            report["problems"].append(name)

    if args.only_reads:
        expected_notes = [e for e in manifest["entries"] if e["disposition"] == "import"]
        _representative_reads(args, staging, root, expected_notes, check)
        report["summary"] = {"problems": report["problems"]}
        report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        for name, item in report["checks"].items():
            print(("ok   " if item["ok"] else "FAIL ") + name)
        return 0 if not report["problems"] else 1

    health = helper("health", root=root)
    check("icloud_account_root", bool(health.get("ok") and health.get("rootFound") and health.get("account") == "iCloud" and health.get("accounts") == ["iCloud"]), health.get("folders"))

    inventory = helper("inventory", root=root, timeout=1800)
    if not inventory.get("ok"):
        check("inventory", False, inventory.get("error"))
        print(json.dumps(report, indent=2))
        return 1
    rows = inventory["results"]
    by_id = {r["id"]: r for r in rows}
    by_key = defaultdict(list)
    for r in rows:
        by_key[(r["folder"], r["title"])].append(r)

    expected_notes = [e for e in manifest["entries"] if e["disposition"] == "import"]
    expected_carriers = [e for e in manifest["files"] if e["kind"] == "attachment-note"]
    expected_total = len(expected_notes) + len(expected_carriers)
    check("note_count", inventory["count"] == expected_total, {"live": inventory["count"], "expected_notes": len(expected_notes), "expected_manual_carriers": len(expected_carriers)})

    live_folders = {f["path"] for f in health.get("folders", []) if f["path"]}
    missing_folders = sorted(set(manifest["expected_folders"]) - live_folders)
    extra_folders = sorted(live_folders - set(manifest["expected_folders"]))
    check("folders_present", not missing_folders, {"missing": missing_folders, "unexpected": extra_folders})

    unresolved, multi, missing_id, attachment_short = [], [], [], []
    for entry in expected_notes + expected_carriers:
        matches = by_key.get((entry["folder"], entry["title"]), [])
        if len(matches) != 1 and not entry.get("same_title_divergent"):
            (unresolved if not matches else multi).append(f"{entry['folder']}/{entry['title']} ({len(matches)})")
        if not entry.get("note_id") or entry["note_id"] not in by_id:
            missing_id.append(f"{entry['folder']}/{entry['title']}")
        expected_attachments = sum(1 for a in entry.get("attachments", []) if a.get("resolved"))
        if expected_attachments and entry.get("note_id") in by_id and by_id[entry["note_id"]]["attachmentCount"] < expected_attachments:
            attachment_short.append(f"{entry['folder']}/{entry['title']}")
    check("one_note_per_entry", not unresolved and not multi, {"missing": unresolved, "ambiguous": multi})
    check("manifest_ids_present", not missing_id, missing_id)
    check("attachments_present", not attachment_short, attachment_short)

    excluded_hits = [r for r in rows if r["title"] in ("AGENTS", "CLAUDE", "findings") or r["folder"].startswith(".")]
    check("no_excluded_artifacts", not excluded_hits, [f"{r['folder']}/{r['title']}" for r in excluded_hits])

    manifest_keys = {(e["folder"], e["title"]) for e in expected_notes + expected_carriers}
    strays = [f"{r['folder']}/{r['title']}" for r in rows if (r["folder"], r["title"]) not in manifest_keys]
    check("no_unexpected_notes", not strays, strays)

    # Bounded searches must return known notes without listing the library.
    sample = expected_notes[:: max(1, len(expected_notes) // args.samples)][: args.samples]
    search_ok, search_detail = True, []
    for entry in sample[:5]:
        result = helper("search", entry["title"], "--mode", "title", "--limit", "5", root=root, timeout=900)
        hit = result.get("ok") and any(r["title"] == entry["title"] for r in result["results"]) and len(result["results"]) <= 5
        search_ok &= bool(hit)
        search_detail.append({"query": entry["title"], "hit": bool(hit), "returned": len(result.get("results", []))})
    check("bounded_title_search", search_ok, search_detail)

    body_query = args.body_query
    result = helper("search", body_query, "--mode", "body", "--limit", "10", root=root, timeout=900)
    check("bounded_body_search", bool(result.get("ok")) and 0 < len(result.get("results", [])) <= 10, {"query": body_query, "returned": len(result.get("results", []))})

    _representative_reads(args, staging, root, expected_notes, check)

    files = manifest["files"]
    dispositions = {f["source_path"]: f["disposition"] for f in files}
    check("all_files_have_dispositions", all(dispositions.values()) and len(files) == manifest["counts"]["attachment_files"] + manifest["counts"]["manual_carrier_notes"], dispositions)

    report["summary"] = {
        "live_notes": inventory["count"],
        "expected": expected_total,
        "problems": report["problems"],
    }
    (staging / "verify-report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(report["summary"], indent=2))
    for name, item in report["checks"].items():
        print(("ok   " if item["ok"] else "FAIL ") + name)
    return 0 if not report["problems"] else 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("stage")
    p.add_argument("--source", default=str(Path.home() / "second-brain"))
    p.add_argument("--staging", required=True)
    p.set_defaults(func=cmd_stage)
    p = sub.add_parser("import")
    p.add_argument("--source", default=str(Path.home() / "second-brain"))
    p.add_argument("--staging", required=True)
    p.add_argument("--limit", type=int, default=0)
    p.add_argument("--stop-on-error", action="store_true")
    p.set_defaults(func=cmd_import)
    p = sub.add_parser("verify")
    p.add_argument("--staging", required=True)
    p.add_argument("--samples", type=int, default=12)
    p.add_argument("--body-query", default="Tool Inventory")
    p.add_argument("--only-reads", action="store_true", help="re-run only the representative reads, merging into the last report")
    p.set_defaults(func=cmd_verify)
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
