#!/usr/bin/env python3
"""Tests for dot-agents/skills/draw-it/scripts/show.py.

Rex is a fake executable and the drawing pane is a pty, so nothing here needs a
running Rex or draws anything.

Run: python3 -m unittest tests/test-draw-it.py
"""

from __future__ import annotations

import fcntl
import importlib.util
import json
import os
import pty
import select
import struct
import subprocess
import sys
import tempfile
import termios
import textwrap
import time
import unittest
import zlib
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "dot-agents" / "skills" / "draw-it" / "scripts" / "show.py"

spec = importlib.util.spec_from_file_location("draw_it_show", SCRIPT)
show = importlib.util.module_from_spec(spec)
spec.loader.exec_module(show)


def write_png(path: Path, width: int, height: int) -> Path:
    def chunk(kind: bytes, body: bytes) -> bytes:
        return struct.pack(">I", len(body)) + kind + body + struct.pack(">I", zlib.crc32(kind + body))

    rows = b"".join(b"\0" + b"\0\0\0" * width for _ in range(height))
    path.write_bytes(
        show.PNG_MAGIC
        + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(rows))
        + chunk(b"IEND", b"")
    )
    return path


FAKE_REX = textwrap.dedent(
    """\
    #!/usr/bin/env python3
    import json, os, sys
    args = sys.argv[1:]
    with open(os.environ["FAKE_LOG"], "a") as log:
        log.write(json.dumps(args) + "\\n")
    if args[:2] == ["block", "ls"]:
        print(open(os.environ["FAKE_BLOCKS"]).read())
    elif args[:2] == ["block", "close"]:
        pass
    elif args[:2] == ["block", "call"] and "size" in args and os.environ.get("FAKE_SIZES"):
        sizes = json.loads(os.environ["FAKE_SIZES"])
        print(json.dumps(sizes[args[args.index("-b") + 1]]))
    elif args[:2] == ["block", "call"] and "resize" in args:
        pass
    elif args[0] == "split":
        result = args[args.index("--result") + 1]
        if os.environ.get("FAKE_REPLY"):
            open(result, "w").write(os.environ["FAKE_REPLY"])
        print(json.dumps({"block_ids": ["block:new"]}))
    else:
        sys.exit(9)
    """
)


class PureTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="draw-it-test-"))

    def test_png_size_reads_the_header(self) -> None:
        self.assertEqual(show.png_size(write_png(self.tmp / "a.png", 110, 86)), (110, 86))

    def test_png_size_rejects_other_files(self) -> None:
        other = self.tmp / "a.jpg"
        other.write_bytes(b"\xff\xd8\xff" + b"\0" * 40)
        with self.assertRaises(ValueError):
            show.png_size(other)

    def test_fit_fills_the_width_when_the_height_allows(self) -> None:
        # 1100x860 at 80 columns of 8px is 640x500px: 32 rows of 16px.
        self.assertEqual(show.fit((1100, 860), (80, 40), (8, 16)), "c=80")

    def test_fit_fills_the_height_when_the_width_would_overflow(self) -> None:
        self.assertEqual(show.fit((1100, 860), (80, 24), (8, 16)), "r=23")


class ShowTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="draw-it-test-"))
        self.rex = self.tmp / "rex"
        self.rex.write_text(FAKE_REX)
        self.rex.chmod(0o755)
        self.log = self.tmp / "rex.log"
        self.blocks = self.tmp / "blocks.json"
        self.image = write_png(self.tmp / "my picture.png", 110, 86)
        self.set_blocks([{"block_id": "block:me", "label": "agent", "window_id": "window:1"}])

    def set_blocks(self, blocks: list) -> None:
        self.blocks.write_text(json.dumps({"blocks": blocks}))

    def run_show(self, *args: str, rex: bool = True, reply: str | None = '{"ok": true}',
                 sizes: dict | None = None):
        env = {k: v for k, v in os.environ.items() if not k.startswith("REX_")}
        env.update(FAKE_LOG=str(self.log), FAKE_BLOCKS=str(self.blocks))
        if sizes:
            env["FAKE_SIZES"] = json.dumps(sizes)
        if rex:
            env.update(REX_BLOCK="block:me", REX_SESSION="session:1", REX_BIN=str(self.rex))
        if reply:
            env["FAKE_REPLY"] = reply
        done = subprocess.run([sys.executable, str(SCRIPT), *args], capture_output=True, text=True, env=env)
        return done.returncode, json.loads(done.stdout)

    def calls(self) -> list[list[str]]:
        return [json.loads(line) for line in self.log.read_text().splitlines()] if self.log.exists() else []

    def test_refuses_outside_rex_and_names_the_image(self) -> None:
        code, out = self.run_show(str(self.image), rex=False)
        self.assertEqual(code, 1)
        self.assertIn("not in a Rex pane", out["error"])
        self.assertEqual(out["image"], str(self.image.resolve()))
        self.assertEqual(self.calls(), [])

    def test_refuses_a_file_that_is_not_a_png(self) -> None:
        other = self.tmp / "a.svg"
        other.write_text("<svg/>" * 10)
        code, out = self.run_show(str(other))
        self.assertEqual(code, 1)
        self.assertIn("not a PNG", out["error"])
        self.assertEqual(self.calls(), [])

    def test_splits_beside_the_caller_without_taking_focus(self) -> None:
        code, out = self.run_show(str(self.image), "--ratio", "40")
        self.assertEqual((code, out["ok"], out["pane_id"], out["replaced"]), (0, True, "block:new", []))
        split = next(c for c in self.calls() if c[0] == "split")
        self.assertEqual(split[split.index("-b") + 1], "block:me")
        self.assertEqual(split[split.index("--ratio") + 1], "40")
        self.assertIn("--focus=false", split)
        self.assertIn("--shell=none", split)  # so a path with spaces is never shell-split
        self.assertEqual(split[split.index("--emit") + 1], str(self.image.resolve()))

    def test_replaces_an_earlier_drawing_in_the_same_tab_only(self) -> None:
        self.set_blocks([
            {"block_id": "block:me", "label": "agent", "window_id": "window:1"},
            {"block_id": "block:old", "label": "draw-it", "window_id": "window:1"},
            {"block_id": "block:other-tab", "label": "draw-it", "window_id": "window:2"},
            {"block_id": "block:logs", "label": "Logs", "window_id": "window:1"},
        ])
        code, out = self.run_show(str(self.image))
        self.assertEqual((code, out["replaced"]), (0, ["block:old"]))
        closes = [c for c in self.calls() if c[:2] == ["block", "close"]]
        self.assertEqual(closes, [["block", "close", "-s", "session:1", "block:old"]])

    def test_sizes_an_unowned_new_pane_from_the_callers(self) -> None:
        # Rex leaves an unfocused new pane at 80x24; the caller already shrank.
        sizes = {"block:me": {"columns": 87, "rows": 49, "owner": "client:1"},
                 "block:new": {"columns": 80, "rows": 24, "owner": None}}
        code, out = self.run_show(str(self.image), sizes=sizes)
        self.assertEqual((code, out["pane"]), (0, {"columns": 86, "rows": 49}))
        resize = next(c for c in self.calls() if "resize" in c)
        self.assertEqual(resize[resize.index("-b") + 1], "block:new")
        self.assertEqual(json.loads(resize[-1]), {"columns": 86, "rows": 49})

    def test_leaves_a_pane_a_client_already_sized(self) -> None:
        sizes = {"block:me": {"columns": 87, "rows": 49, "owner": "client:1"},
                 "block:new": {"columns": 90, "rows": 50, "owner": "client:1"}}
        code, out = self.run_show(str(self.image), sizes=sizes)
        self.assertEqual((code, out["pane"]), (0, {"columns": 90, "rows": 50}))
        self.assertFalse([c for c in self.calls() if "resize" in c])

    def test_reports_a_terminal_that_refused_the_image(self) -> None:
        code, out = self.run_show(str(self.image), reply='{"ok": false, "terminal_reply": "EINVAL"}')
        self.assertEqual((code, out["ok"], out["terminal_reply"]), (1, False, "EINVAL"))


class EmitTest(unittest.TestCase):
    """The pane side, run on a pty that answers like a kitty-graphics terminal."""

    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="draw-it-test-"))
        self.image = write_png(self.tmp / "p.png", 1100, 860)
        self.result = self.tmp / "result.json"

    def resize(self, fd: int, cols: int, rows: int) -> None:
        fcntl.ioctl(fd, termios.TIOCSWINSZ, struct.pack("HHHH", rows, cols, 0, 0))

    def serve(self, fd: int, seconds: float) -> bytes:
        """Answer the pane's queries for a while; return everything it wrote."""
        seen = b""
        handled = 0
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            if not select.select([fd], [], [], 0.05)[0]:
                continue
            try:
                seen += os.read(fd, 65536)
            except OSError:
                break
            while True:
                size_query = seen.find(b"\x1b[16t", handled)
                image_end = seen.find(b"m=0;", handled)
                if size_query >= 0 and (image_end < 0 or size_query < image_end):
                    os.write(fd, b"\x1b[6;16;8t")
                    handled = size_query + 5
                elif image_end >= 0 and seen.find(b"\x1b\\", image_end) >= 0:
                    os.write(fd, b"\x1b_Gi=1;OK\x1b\\")
                    handled = seen.find(b"\x1b\\", image_end) + 2
                else:
                    break
        return seen

    def test_draws_reports_and_redraws_on_resize(self) -> None:
        pid, fd = pty.fork()
        if pid == 0:
            os.execv(sys.executable, [sys.executable, str(SCRIPT), "--emit", str(self.image),
                                      "--result", str(self.result)])
        try:
            self.resize(fd, 80, 24)
            first = self.serve(fd, 1.5)
            out = json.loads(self.result.read_text())
            self.assertEqual((out["ok"], out["placement"]), (True, "r=23"))
            self.assertIn(b"a=T,f=100,i=1,C=1,r=23,m=", first)

            self.resize(fd, 80, 40)  # tall enough now: fill the width instead
            second = self.serve(fd, 1.5)
            self.assertIn(b"a=d,d=A", second)
            self.assertIn(b"a=T,f=100,i=1,C=1,c=80,m=", second)

            os.write(fd, b"q")
            self.serve(fd, 0.5)
            self.assertEqual(os.waitpid(pid, 0)[1], 0)
            pid = 0
        finally:
            if pid:
                os.kill(pid, 9)
                os.waitpid(pid, 0)
            os.close(fd)


if __name__ == "__main__":
    unittest.main()
