#!/usr/bin/env python3
"""Offline tests for the apple-notes-pkm helper and the vault->Notes migration.

No Notes.app access: the Markdown <-> Notes-HTML converter, the staging
transform, the helper's scoping/exit-code contract (against a stubbed
osascript), and the migration manifest builder are exercised on fixtures.
"""
from __future__ import annotations

import importlib.util
import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "dot-agents" / "skills" / "apple-notes-pkm" / "scripts"
HELPER = SCRIPTS / "apple-notes-pkm.py"
MIGRATE = ROOT / "scripts" / "migrate-second-brain-to-apple-notes.py"
sys.path.insert(0, str(SCRIPTS))
import notes_markdown as nm  # noqa: E402


def load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


FIXTURE = """---
tags:
  - area/tools
  - type/exploration
aliases:
  - Alias One
related: [[Target Note]], [[Other#Part|part]]
created: 2026-09-16
status: active
---

# Fixture Note

Intro with **bold**, `code`, a [link](https://example.com/a?b=1&c=2), and [[Target Note]].
Aliased [[Target Note|the target]] and a section [[Target Note#Section Two|second]]
spanning [[Target Note|two
lines]].

> [!tip] Chosen: **Option B**
> Rationale line.

| Pros | Cons |
|------|------|
| Fast \\| cheap | Needs `setup` |

- [ ] open task
- [x] done task
- parent
  - child with [[Target Note|alias]]
1. one
2. two

```bash
echo "hi" && ls
```

![[image.png]]
![[Missing Note]]
"""


class ConverterTests(unittest.TestCase):
    def test_frontmatter_split_and_retained_meta(self):
        meta, body = nm.split_frontmatter(FIXTURE)
        self.assertEqual(meta["tags"], ["area/tools", "type/exploration"])
        self.assertEqual(meta["aliases"], ["Alias One"])
        self.assertEqual(meta["related"], "[[Target Note]], [[Other#Part|part]]")
        self.assertTrue(body.startswith("# Fixture Note"))
        lines = nm.meta_lines(meta)
        self.assertIn("Aliases: Alias One", lines)
        self.assertIn("Related: Target Note, part (Other › Part)", lines)
        self.assertIn("Tags: area/tools, type/exploration", lines)

    def test_inline_list_detection(self):
        self.assertEqual(nm._parse_simple_yaml(["related: [[[A]], [[B]]]"])["related"], ["[[A]]", "[[B]]"])
        self.assertEqual(nm._parse_simple_yaml(["related: [[A]], [[B]]"])["related"], "[[A]], [[B]]")
        self.assertEqual(nm._parse_simple_yaml(["related: [[A]]"])["related"], "[[A]]")

    def test_wikilinks_flatten_to_titles_everywhere(self):
        meta, body = nm.split_frontmatter(FIXTURE)
        html = nm.markdown_to_notes_html(body, title="Fixture Note", meta=meta)
        self.assertNotIn("[[", html)
        self.assertNotIn("]]", html)
        self.assertIn("the target (Target Note)", html)
        self.assertIn("second (Target Note › Section Two)", html)
        self.assertIn("two<br>lines (Target Note)", html)
        self.assertIn("<li>child with alias (Target Note)</li>", html)
        self.assertIn("[attachment: image.png]", html)
        self.assertIn("[attachment: Missing Note]", html)

    def test_title_heading_is_single_h1_and_body_h1_dropped(self):
        meta, body = nm.split_frontmatter(FIXTURE)
        html = nm.markdown_to_notes_html(body, title="Fixture Note", meta=meta)
        self.assertEqual(html.count("<h1>"), 1)
        self.assertTrue(html.startswith("<div><h1>Fixture Note</h1></div>"))
        other = nm.markdown_to_notes_html("# Different\n\ntext", title="stem")
        self.assertIn("<h1>stem</h1>", other)
        self.assertIn("<h2>Different</h2>", other)

    def test_block_constructs(self):
        meta, body = nm.split_frontmatter(FIXTURE)
        html = nm.markdown_to_notes_html(body, title="Fixture Note", meta=meta)
        self.assertIn("<blockquote><div><b>Tip: Chosen: <b>Option B</b></b></div>", html)
        self.assertIn("<table><tr><th>Pros</th><th>Cons</th></tr><tr><td>Fast | cheap</td><td>Needs <tt>setup</tt></td></tr></table>", html)
        self.assertIn("<li>☐ open task</li><li>☑ done task</li>", html)
        self.assertIn("<ul><li>child with alias (Target Note)</li></ul>", html)
        # Adjacent lists of different kinds are separated so Notes keeps numbering.
        self.assertIn("</ul><div><br></div><ol><li>one</li><li>two</li></ol>", html)
        self.assertIn('<div><tt>echo "hi" &amp;&amp; ls</tt></div>', html)
        self.assertIn('<a href="https://example.com/a?b=1&amp;c=2">link</a>', html)

    def test_notes_html_readback_normalizes_apple_markup(self):
        body = (
            '<div><b><font face=".AppleSystemUIFontBold"><span style="font-size: 24px">Title</span></font></b></div>\n'
            '<div><b><span style="font-size: 18px">Section</span></b><br></div>\n'
            '<div>Text with <font face="Courier"><span style="font-size: 12px">code</span></font>.</div>\n'
            '<div><object><table><tbody><tr><td><div>a | b</div></td><td><div>c</div></td></tr></tbody></table></object><br></div>\n'
            '<ul><li>one</li></ul>\n'
            '<div><font face="Courier"><tt>ls -la</tt></font><span style="font-size: 13px"><tt><br></tt></span></div>\n'
            '<div><img src="data:image/png;base64,AAAA"/></div>'
        )
        markdown = nm.notes_html_to_markdown(body)
        self.assertIn("# Title\n", markdown)
        self.assertIn("## Section\n", markdown)
        self.assertIn("Text with `code`.", markdown)
        self.assertIn("| a \\| b | c |", markdown)
        self.assertIn("- one", markdown)
        self.assertIn("```\nls -la\n```", markdown)
        self.assertIn("[image]", markdown)
        self.assertNotIn("base64", markdown)
        self.assertIn('base64,[omitted]', nm.scrub_data_uris(body))

    def test_stage_markdown(self):
        staged, meta, embeds = nm.stage_markdown(FIXTURE, title="Fixture Note")
        self.assertEqual(embeds, ["image.png", "Missing Note"])
        self.assertNotIn("---\ntags:", staged)
        self.assertNotIn("[[", staged)
        self.assertNotIn("# Fixture Note", staged)
        self.assertIn("> **Tip: Chosen: Option B**", staged)
        self.assertIn("Tags: area/tools, type/exploration", staged)


EXPECT_BUNDLE = "com.test.apple-notes-pkm-helper"
EXPECT_CN = "Test Notes Signer"

# Stub codesign: emits codesign -dv shape on stderr. Its identifier/authority
# and signed-ness are driven by env so tests can force mismatch / unsigned.
STUB_CODESIGN = (
    "#!/usr/bin/env python3\n"
    "import os,sys\n"
    "mode=os.environ.get('STUB_CODESIGN_MODE','ok')\n"
    "if mode=='unsigned':\n"
    "    sys.stderr.write('code object is not signed at all\\n'); sys.exit(1)\n"
    "ident=os.environ.get('STUB_CODESIGN_IDENT', %r)\n"
    "auth=os.environ.get('STUB_CODESIGN_AUTH', %r)\n"
    "sys.stderr.write('Executable=/x\\nIdentifier=%%s\\nAuthority=%%s\\n' %% (ident, auth))\n"
    "sys.exit(0)\n"
) % (EXPECT_BUNDLE, EXPECT_CN)

# Stub native helper: logs the exact request it received on stdin, then echoes a
# canned per-op response. Modes force malformed / nonzero / hanging output.
STUB_HELPER = (
    "#!/usr/bin/env python3\n"
    "import json,sys,os,time\n"
    "raw=sys.stdin.read()\n"
    "req=json.loads(raw) if raw.strip() else {}\n"
    f"open({{log!r}},'a').write(json.dumps(req)+'\\n')\n"
    "mode=os.environ.get('STUB_HELPER_MODE','json')\n"
    "if mode=='malformed':\n"
    "    print('this is not json'); sys.exit(0)\n"
    "if mode=='nonzero':\n"
    "    sys.stderr.write('boom'); sys.exit(3)\n"
    "if mode=='sleep':\n"
    "    time.sleep(5); print('{}'); sys.exit(0)\n"
    "canned=json.loads(os.environ.get('STUB_RESPONSE','{}'))\n"
    "print(json.dumps(canned.get(req.get('op'), {'ok': True})))\n"
)


class HelperContractTests(unittest.TestCase):
    """The Python CLI against a stub *native helper* (never osascript) and a
    stub codesign, exercising the fixed-path transport, signature gate, and
    fail-closed exit codes."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.log = self.tmp / "requests.jsonl"
        self.helper_bin = self.tmp / "apple-notes-pkm-helper"
        self.helper_bin.write_text(STUB_HELPER.replace("{log!r}", repr(str(self.log))))
        self.helper_bin.chmod(self.helper_bin.stat().st_mode | stat.S_IEXEC)
        self.codesign = self.tmp / "codesign"
        self.codesign.write_text(STUB_CODESIGN)
        self.codesign.chmod(self.codesign.stat().st_mode | stat.S_IEXEC)

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def run_helper(self, *args, responses=None, env=None, helper_bin=None):
        environment = os.environ | {
            "APPLE_NOTES_PKM_HELPER_BIN": str(helper_bin if helper_bin is not None else self.helper_bin),
            "APPLE_NOTES_PKM_CODESIGN": str(self.codesign),
            "APPLE_NOTES_PKM_EXPECT_BUNDLE": EXPECT_BUNDLE,
            "APPLE_NOTES_PKM_EXPECT_CN": EXPECT_CN,
            "STUB_RESPONSE": json.dumps(responses or {}),
        }
        environment.update(env or {})
        proc = subprocess.run([sys.executable, str(HELPER), *args], capture_output=True, text=True, env=environment, check=False)
        return proc.returncode, json.loads(proc.stdout)

    def requests(self):
        return [json.loads(line) for line in self.log.read_text().splitlines()]

    def test_source_never_shells_out_to_osascript(self):
        source = HELPER.read_text()
        self.assertNotIn("osascript", source)
        self.assertIn("APPLE_NOTES_PKM_HELPER_BIN", source)

    def test_scope_defaults_and_env_override(self):
        rc, out = self.run_helper("health", responses={"health": {"ok": True, "accounts": ["iCloud"], "rootFound": True}})
        self.assertEqual(rc, 0)
        self.assertEqual(self.requests()[0]["root"], "Second Brain")
        self.assertEqual(self.requests()[0]["account"], "iCloud")
        rc, out = self.run_helper("health", responses={"health": {"ok": True}}, env={"APPLE_NOTES_PKM_ROOT": "Second Brain Pilot"})
        self.assertEqual(self.requests()[1]["root"], "Second Brain Pilot")

    def test_search_is_bounded(self):
        rc, out = self.run_helper("search", "drz", "--limit", "500", responses={"search": {"ok": True, "results": []}})
        self.assertEqual(rc, 0)
        self.assertEqual(self.requests()[0]["limit"], 500)  # JXA clamps to 25; wrapper passes intent through
        self.assertEqual(self.requests()[0]["op"], "search")

    def test_untrusted_input_cannot_select_a_script_path_or_command(self):
        # A hostile query string is carried verbatim as data; the request the
        # helper receives never grows a field that could redirect execution.
        payload = "'; do shell script \"rm -rf ~\" -- /etc/passwd"
        rc, out = self.run_helper("search", payload, responses={"search": {"ok": True, "results": []}})
        self.assertEqual(rc, 0)
        sent = self.requests()[0]
        self.assertEqual(sent["query"], payload)
        for forbidden in ("script", "application", "path", "command", "osascript", "exec"):
            self.assertNotIn(forbidden, sent, f"request must not carry an executable selector: {forbidden}")

    def test_stale_and_refused_exit_codes(self):
        rc, out = self.run_helper("append", "x-id", "--revision", "r1", "--body", "hi",
                                  responses={"append": {"ok": False, "error": "stale revision", "errorNumber": "stale"}})
        self.assertEqual((rc, out["code"]), (3, 3))
        rc, out = self.run_helper("replace", "x-id", "--revision", "r1", "--body", "hi",
                                  responses={"read": {"ok": True, "note": {"id": "x-id", "title": "T", "folder": "", "body": "<div>x</div>", "plaintext": "x", "attachments": []}},
                                             "replace": {"ok": False, "error": "refusing", "errorNumber": "unsafe"}})
        self.assertEqual((rc, out["code"]), (4, 4))

    def test_permission_denied_maps_to_exit_5(self):
        rc, out = self.run_helper("health", responses={"health": {"ok": False, "error": "Not authorized to send Apple events to Notes. (-1743)"}})
        self.assertEqual(rc, 5)
        self.assertIn("Apple Notes PKM Helper", out["error"])

    def test_probe_denial_fails_overall(self):
        # A denied probe used to return ok:true because each step caught its own
        # error. It must now surface the permission exit code.
        probe = {"ok": True, "steps": {
            "running": {"ok": True, "value": True, "ms": 1},
            "accounts.length": {"ok": False, "error": "Error: Not authorized to send Apple events (-1743)", "ms": 2},
        }}
        rc, out = self.run_helper("health", "--probe", responses={"probe": probe})
        self.assertEqual(rc, 5)
        self.assertIn("Automation is denied", out["error"])

    def test_missing_helper_fails_closed(self):
        rc, out = self.run_helper("health", helper_bin=self.tmp / "does-not-exist",
                                  responses={"health": {"ok": True}})
        self.assertEqual((rc, out["code"]), (7, 7))
        self.assertIn("not installed", out["error"])

    def test_unsigned_helper_fails_closed(self):
        rc, out = self.run_helper("health", responses={"health": {"ok": True}}, env={"STUB_CODESIGN_MODE": "unsigned"})
        self.assertEqual((rc, out["code"]), (7, 7))
        self.assertIn("unsigned", out["error"])

    def test_wrong_bundle_identity_fails_closed(self):
        rc, out = self.run_helper("health", responses={"health": {"ok": True}}, env={"STUB_CODESIGN_IDENT": "com.evil.other"})
        self.assertEqual((rc, out["code"]), (7, 7))
        self.assertIn("bundle identity mismatch", out["error"])

    def test_wrong_signing_authority_fails_closed(self):
        rc, out = self.run_helper("health", responses={"health": {"ok": True}}, env={"STUB_CODESIGN_AUTH": "Some Other Signer"})
        self.assertEqual((rc, out["code"]), (7, 7))
        self.assertIn("signing identity mismatch", out["error"])

    def test_malformed_helper_output_fails_closed(self):
        rc, out = self.run_helper("health", env={"STUB_HELPER_MODE": "malformed"})
        self.assertEqual(rc, 1)
        self.assertIn("unparseable", out["error"])

    def test_nonzero_helper_result_fails_closed(self):
        rc, out = self.run_helper("health", env={"STUB_HELPER_MODE": "nonzero"})
        self.assertEqual((rc, out["code"]), (7, 7))

    def test_timeout_fails_closed(self):
        rc, out = self.run_helper("health", env={"STUB_HELPER_MODE": "sleep", "APPLE_NOTES_PKM_TIMEOUT": "0.4"})
        self.assertEqual(rc, 1)
        self.assertIn("timed out", out["error"])

    def test_create_requires_folder_and_verifies_title(self):
        note = {"id": "x-id", "title": "Wrong", "folder": "Inbox", "body": "<div>x</div>", "plaintext": "x", "attachments": []}
        rc, out = self.run_helper("create", "--folder", "Inbox", "--title", "Right", "--body", "hello",
                                  responses={"create": {"ok": True, "note": note}, "read": {"ok": True, "note": note}})
        self.assertEqual(rc, 6)
        self.assertIn("title mismatch", out["error"])
        sent = self.requests()[0]
        self.assertEqual(sent["folder"], "Inbox")
        self.assertTrue(sent["body"].startswith("<div><h1>Right</h1></div>"))

    def test_no_delete_command(self):
        proc = subprocess.run([sys.executable, str(HELPER), "delete", "x"], capture_output=True, text=True, check=False)
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("invalid choice", proc.stderr)


class MigrationManifestTests(unittest.TestCase):
    def test_manifest_collapses_identical_duplicates_and_keeps_divergent(self):
        migrate = load(MIGRATE, "migrate")
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "vault"
            staging = Path(tmp) / "staging"
            (source / "Journal" / "2025").mkdir(parents=True)
            (source / "Archive" / "Journal" / "2025").mkdir(parents=True)
            (source / "Manuals").mkdir()
            (source / "Attachments").mkdir()
            (source / ".obsidian").mkdir()
            (source / ".hermes" / "desktop-attachments").mkdir(parents=True)
            (source / "AGENTS.md").write_text("agents\n")
            (source / ".obsidian" / "app.md").write_text("x\n")
            (source / ".hermes" / "desktop-attachments" / "secret.pdf").write_bytes(b"%PDF")
            (source / "Journal" / "2025" / "Same.md").write_text("identical\n")
            (source / "Archive" / "Journal" / "2025" / "Same.md").write_text("identical\n")
            (source / "README.md").write_text("root readme\n")
            (source / "Journal" / "README.md").write_text("journal readme\n")
            (source / "Hub.md").write_text("# Hub\n\n![[pic.png]] and [[Manuals/manual.pdf|the manual]]\n")
            (source / "Attachments" / "pic.png").write_bytes(b"png")
            (source / "Attachments" / "orphan.png").write_bytes(b"png2")
            (source / "Manuals" / "manual.pdf").write_bytes(b"%PDF")
            manifest = migrate.build_manifest(source, staging)
            counts = manifest["counts"]
            self.assertEqual(counts["source_markdown_files"], 5)
            self.assertEqual(counts["unique_title_content_pairs"], 4)
            self.assertEqual(counts["duplicate_instances_omitted"], 1)
            self.assertEqual(counts["notes_to_import"], 4)
            omitted = [e for e in manifest["entries"] if e["disposition"] == "duplicate-omitted"]
            self.assertEqual(omitted[0]["source_path"], "Archive/Journal/2025/Same.md")
            self.assertEqual(omitted[0]["duplicate_of"], "Journal/2025/Same.md")
            readmes = [e for e in manifest["entries"] if e["title"] == "README"]
            self.assertTrue(all(e["disposition"] == "import" and e["same_title_divergent"] for e in readmes))
            hub = next(e for e in manifest["entries"] if e["title"] == "Hub")
            self.assertEqual(hub["attachments"], [{"name": "pic.png", "source_path": "Attachments/pic.png", "resolved": True}])
            files = {f["source_path"]: f for f in manifest["files"]}
            self.assertEqual(files["Attachments/pic.png"]["disposition"], "attached-to-referencing-note")
            self.assertEqual(files["Attachments/orphan.png"]["disposition"], "archive-only-unreferenced")
            self.assertEqual(files["Manuals/manual.pdf"]["kind"], "attachment-note")
            self.assertEqual(files["Manuals/manual.pdf"]["referenced_by"], ["Hub.md"])
            self.assertNotIn(".hermes/desktop-attachments/secret.pdf", files)
            self.assertNotIn("AGENTS", [e["title"] for e in manifest["entries"]])
            self.assertIn("Inbox", manifest["expected_folders"])
            self.assertIn("Manuals", manifest["expected_folders"])
            self.assertTrue((staging / "notes" / "Hub.md").exists())
            self.assertFalse((staging / "notes" / "Archive" / "Journal" / "2025" / "Same.md").exists())


if __name__ == "__main__":
    unittest.main()
