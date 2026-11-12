#!/usr/bin/env python3
"""Show a PNG in a Rex pane beside the calling agent, via the kitty graphics protocol.

    show.py IMAGE.png [--ratio PCT] [--split right|below|left|above]

Splits the caller's pane (``REX_BLOCK``), draws the image there scaled to fit
the new pane, redraws it whenever the pane is resized, and leaves focus where it
was. Pressing q in the drawing pane closes it. An earlier drawing pane in the same
tab is closed first, so repeated calls replace the picture instead of stacking
panes. Prints one JSON object; exit 0 only when the terminal confirmed the image.

Standard library only. The pane runs this same file with ``--emit``.
"""

from __future__ import annotations

import argparse
import base64
import json
import math
import os
import select
import signal
import struct
import subprocess
import sys
import tempfile
import termios
import time
import tty
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "lib"))
import terminal_host  # noqa: E402

LABEL = "draw-it"
PNG_MAGIC = b"\x89PNG\r\n\x1a\n"
MAX_BYTES = 20 * 1024 * 1024
FALLBACK_CELL = (8, 16)  # width, height in pixels


def png_size(path: Path) -> tuple[int, int]:
    """Pixel width and height from the PNG header. ValueError if not a PNG."""
    with open(path, "rb") as fh:
        head = fh.read(24)
    if len(head) < 24 or head[:8] != PNG_MAGIC or head[12:16] != b"IHDR":
        raise ValueError(f"{path} is not a PNG")
    width, height = struct.unpack(">II", head[16:24])
    if not width or not height:
        raise ValueError(f"{path} has an empty PNG header")
    return width, height


def fit(img: tuple[int, int], grid: tuple[int, int], cell: tuple[int, int]) -> str:
    """The kitty placement key that fills the pane without overflowing it.

    Giving only columns (or only rows) makes the terminal keep the aspect ratio.
    Fill the width unless that would run past the last row; then fill the height.
    """
    cols, rows = grid
    usable_rows = max(1, rows - 1)
    height_px = cols * cell[0] * img[1] / img[0]
    if math.ceil(height_px / cell[1]) <= usable_rows:
        return f"c={cols}"
    return f"r={usable_rows}"


def _ask(fd: int, query: bytes, end: bytes, timeout: float) -> bytes:
    os.write(fd, query)
    buf = b""
    deadline = time.monotonic() + timeout
    while not buf.endswith(end):
        left = deadline - time.monotonic()
        if left <= 0 or not select.select([fd], [], [], left)[0]:
            break
        buf += os.read(fd, 256)
    return buf


def _draw(fd: int, image: Path, img: tuple[int, int], data: list[bytes]) -> dict:
    size = os.get_terminal_size(fd)
    reply = _ask(fd, b"\x1b[16t", b"t", 0.5)  # -> CSI 6 ; height ; width t
    try:
        _, cell_h, cell_w = (int(n) for n in reply[2:-1].split(b";"))
        cell = (cell_w, cell_h) if cell_w and cell_h else FALLBACK_CELL
    except ValueError:
        cell = FALLBACK_CELL
    place = fit(img, (size.columns, size.lines), cell)
    # Hide the cursor, drop the old picture, clear, then send the new one.
    payload = bytearray(b"\x1b[?25l\x1b_Ga=d,d=A,q=2\x1b\\\x1b[2J\x1b[H")
    for n, chunk in enumerate(data):
        more = int(n < len(data) - 1)
        keys = f"a=T,f=100,i=1,C=1,{place},m={more}" if n == 0 else f"m={more}"
        payload += b"\x1b_G" + keys.encode() + b";" + chunk + b"\x1b\\"
    answer = _ask(fd, bytes(payload), b"\x1b\\", 5.0).decode("ascii", "replace")
    status = answer.partition(";")[2].removesuffix("\x1b\\")
    return {"ok": status == "OK", "terminal_reply": status or "none",
            "pane": {"columns": size.columns, "rows": size.lines}, "placement": place}


def emit(image: Path, result: Path | None) -> int:
    """Runs inside the drawing pane: draw, report once, then redraw on every resize.

    A new pane starts at 80x24 and gets its real size only when Rex lays it out,
    so the first draw is rarely the last. The process stays until the pane closes.
    """
    resized = [False]
    signal.signal(signal.SIGWINCH, lambda *_: resized.__setitem__(0, True))
    try:
        img = png_size(image)
        encoded = base64.standard_b64encode(image.read_bytes())
        data = [encoded[i : i + 4096] for i in range(0, len(encoded), 4096)]
        fd = os.open("/dev/tty", os.O_RDWR)
        saved = termios.tcgetattr(fd)
        tty.setcbreak(fd)
        out = _draw(fd, image, img, data)
    except Exception as exc:  # the pane has no one to raise to
        out = {"ok": False, "error": f"{type(exc).__name__}: {exc}"}
    if result:
        tmp = result.with_suffix(".tmp")
        tmp.write_text(json.dumps(out))
        tmp.replace(result)
    if not out["ok"]:
        return 1
    try:
        while True:
            if resized[0]:
                resized[0] = False
                time.sleep(0.05)  # let a drag settle
                _draw(fd, image, img, data)
            try:
                if select.select([fd], [], [], 1.0)[0] and os.read(fd, 256) in (b"", b"q"):
                    break  # q closes the pane
            except InterruptedError:
                pass
    except (OSError, KeyboardInterrupt):
        pass
    finally:
        try:
            os.write(fd, b"\x1b[?25h")
            termios.tcsetattr(fd, termios.TCSANOW, saved)
        except OSError:
            pass
    return 0


def _rex(host: terminal_host.Host, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run([host.binary, *args], capture_output=True, text=True, timeout=20)


def _size(host: terminal_host.Host, block: str) -> dict | None:
    done = _rex(host, "block", "call", "-s", host.session, "-b", block, "size")
    try:
        return json.loads(done.stdout) if done.returncode == 0 else None
    except json.JSONDecodeError:
        return None


def _claim_size(host: terminal_host.Host, pane: str, ratio: int, split: str) -> dict | None:
    """Give an unowned new pane the size its place in the layout implies.

    Rex leaves a pane at 80x24 until a client takes it over, which a pane that
    never gets focus may wait a long time for. The caller's pane has already
    shrunk to make room, so its size says how big the new one is. The pane
    redraws on the resize, and again if a client later sets the true size.
    """
    new, caller = _size(host, pane), _size(host, host.pane)
    if not new or not caller or new.get("owner") or not caller.get("columns"):
        return new and {"columns": new["columns"], "rows": new["rows"]}
    share = ratio / (100 - ratio)
    cols, rows = caller["columns"], caller["rows"]
    if split in ("right", "left"):
        cols = max(20, round(cols * share) - 1)
    else:
        rows = max(5, round(rows * share) - 1)
    want = {"columns": cols, "rows": rows}
    done = _rex(host, "block", "call", "-s", host.session, "-b", pane, "resize", json.dumps(want))
    return want if done.returncode == 0 else {"columns": new["columns"], "rows": new["rows"]}


def show(image: Path, ratio: int, split: str) -> tuple[int, dict]:
    host = terminal_host.detect()
    if host is None:
        return 1, {"ok": False, "error": "not in a Rex pane (REX_BLOCK and REX_SESSION are unset)",
                   "image": str(image)}
    try:
        png_size(image)
    except (OSError, ValueError) as exc:
        return 1, {"ok": False, "error": str(exc)}
    if image.stat().st_size > MAX_BYTES:
        return 1, {"ok": False, "error": f"{image} is over {MAX_BYTES // 2**20} MB"}

    # Replace an earlier drawing in this tab rather than stacking panes.
    listed = _rex(host, "block", "ls", "-s", host.session, "--json")
    if listed.returncode != 0:
        return 1, {"ok": False, "error": f"rex block ls failed: {listed.stderr.strip()}"}
    blocks = json.loads(listed.stdout).get("blocks", [])
    mine = next((b for b in blocks if b.get("block_id") == host.pane), None)
    if mine is None:
        return 1, {"ok": False, "error": f"calling pane {host.pane} not found in {host.session}"}
    stale = [b["block_id"] for b in blocks
             if b.get("label") == LABEL and b.get("window_id") == mine.get("window_id")]
    if stale:
        _rex(host, "block", "close", "-s", host.session, *stale)

    result = Path(tempfile.mkdtemp(prefix="draw-it-")) / "result.json"
    made = _rex(host, "split", "-s", host.session, "-b", host.pane, f"--split={split}",
                "--ratio", str(ratio), "--label", LABEL, "--focus=false", "--shell=none", "--json", "--", sys.executable, str(Path(__file__).resolve()),
                "--emit", str(image), "--result", str(result))
    if made.returncode != 0:
        return 1, {"ok": False, "error": f"rex split failed: {made.stderr.strip()}"}
    pane = json.loads(made.stdout)["block_ids"][0]

    deadline = time.monotonic() + 10
    while not result.exists() and time.monotonic() < deadline:
        time.sleep(0.1)
    if not result.exists():
        return 1, {"ok": False, "pane": pane, "error": "the drawing pane never reported back"}
    out = json.loads(result.read_text())
    out.update(pane_id=pane, image=str(image), replaced=stale)
    if out["ok"]:
        out["pane"] = _claim_size(host, pane, ratio, split) or out.get("pane")
        out.pop("placement", None)  # the pane re-fits itself after the resize
    return (0 if out["ok"] else 1), out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("image", type=Path)
    parser.add_argument("--ratio", type=int, default=50, help="percent of the split for the drawing (default 50)")
    parser.add_argument("--split", default="right", choices=("right", "below", "left", "above"))
    parser.add_argument("--emit", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--result", type=Path, help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.emit:
        return emit(args.image, args.result)
    if not 10 <= args.ratio <= 90:
        parser.error("--ratio must be between 10 and 90")
    code, out = show(args.image.expanduser().resolve(), args.ratio, args.split)
    print(json.dumps(out, indent=2))
    return code


if __name__ == "__main__":
    sys.exit(main())
