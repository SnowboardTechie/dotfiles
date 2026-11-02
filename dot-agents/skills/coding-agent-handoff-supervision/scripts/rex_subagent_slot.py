#!/usr/bin/env python3
"""Choose where the next visible worker opens in Rex.

Reads `rex window ls -s SESSION --json` on stdin and prints one JSON object:

  {"action": "new", "tab_label": "<caller tab> Sub Agents[ N]"}
  {"action": "split", "window_id": ..., "tab_label": ..., "anchor": ..., "direction": "right"|"below", "workers": n}

Workers live in the caller's sub-agents tabs ("<caller tab label> Sub Agents",
then "... Sub Agents 2", "... 3"), at most four per tab, as a 2x2 grid. The
first worker is the tab's own root block (the tab is created with the worker's
command, so no empty shell is left in it). Each later worker splits the largest
pane: right when the pane is at least as wide as it is tall, otherwise below.
That gives 1 -> full tab, 2 -> side by side, 3 -> left column split,
4 -> 2x2, and refills a closed worker's quadrant first. The caller's own tab
is never a target.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from typing import Any

MAX_PER_TAB = 4


def tiled_leaves(window: dict[str, Any]) -> list[tuple[str, list[float]]]:
    leaves: list[tuple[str, list[float]]] = []

    def walk(node: dict[str, Any]) -> None:
        if "block_id" in node:
            leaves.append((node["block_id"], node["rect"]))
        elif "split" in node:
            walk(node["split"]["before"])
            walk(node["split"]["after"])

    for layer in window.get("layers", []):
        if layer.get("kind") == "tiled" and layer.get("layout"):
            walk(layer["layout"])
    return leaves


def choose(listing: dict[str, Any], caller_block: str) -> dict[str, Any]:
    windows = listing["windows"]
    caller = next(
        (w for w in windows if any(b["block_id"] == caller_block for layer in w.get("layers", []) for b in layer.get("blocks", []))),
        None,
    )
    if caller is None:
        raise SystemExit(f"caller block {caller_block} is in no window of this session")
    base = f"{caller['label']} Sub Agents"
    pattern = re.compile(rf"^{re.escape(base)}(?: (\d+))?$")

    tabs: list[tuple[int, dict[str, Any]]] = []
    for w in windows:
        if w["window_id"] == caller["window_id"]:
            continue
        m = pattern.match(w["label"])
        if m:
            tabs.append((int(m.group(1) or 1), w))
    tabs.sort(key=lambda t: t[0])

    for _, w in tabs:
        leaves = tiled_leaves(w)
        if not leaves or len(leaves) >= MAX_PER_TAB:
            continue
        anchor, (_x, _y, width, height) = max(
            leaves, key=lambda leaf: (round(leaf[1][2] * leaf[1][3], 6), -round(leaf[1][1], 6), -round(leaf[1][0], 6))
        )
        return {
            "action": "split",
            "window_id": w["window_id"],
            "tab_label": w["label"],
            "anchor": anchor,
            "direction": "right" if width >= height else "below",
            "workers": len(leaves),
        }

    used = {n for n, _ in tabs}
    n = 1
    while n in used:
        n += 1
    return {"action": "new", "tab_label": base if n == 1 else f"{base} {n}"}


def main() -> None:
    parser = argparse.ArgumentParser(description="Choose where the next visible worker opens in Rex.")
    parser.add_argument("--caller-block", required=True, help="the coordinator's own block ($REX_BLOCK)")
    args = parser.parse_args()
    print(json.dumps(choose(json.load(sys.stdin), args.caller_block)))


if __name__ == "__main__":
    main()
