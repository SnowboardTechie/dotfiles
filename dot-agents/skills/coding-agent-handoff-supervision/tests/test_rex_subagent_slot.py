from __future__ import annotations

import importlib.util
from pathlib import Path
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "rex_subagent_slot.py"
CALLER = "block:caller"


def load_module():
    spec = importlib.util.spec_from_file_location("rex_subagent_slot", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


slot = load_module()


# A split tree is a block id or ("h"|"v", before, after); "h" is side by side.
def layout(node, rect=(0.0, 0.0, 1.0, 1.0)):
    x, y, w, h = rect
    if isinstance(node, str):
        return {"rect": list(rect), "block_id": node}
    kind, before, after = node
    if kind == "h":
        r1, r2 = (x, y, w / 2, h), (x + w / 2, y, w / 2, h)
    else:
        r1, r2 = (x, y, w, h / 2), (x, y + h / 2, w, h / 2)
    return {"rect": list(rect), "split": {"before": layout(before, r1), "after": layout(after, r2)}}


def blocks(node):
    return [node] if isinstance(node, str) else blocks(node[1]) + blocks(node[2])


def window(wid, label, tree):
    return {
        "window_id": wid,
        "label": label,
        "layers": [{"kind": "tiled", "layout": layout(tree), "blocks": [{"block_id": b} for b in blocks(tree)]}],
    }


def split(tree, anchor, direction, new):
    if tree == anchor:
        return ("h", anchor, new) if direction == "right" else ("v", anchor, new)
    if isinstance(tree, str):
        return tree
    return (tree[0], split(tree[1], anchor, direction, new), split(tree[2], anchor, direction, new))


def close(tree, block):
    if isinstance(tree, str):
        return None if tree == block else tree
    a, b = close(tree[1], block), close(tree[2], block)
    if a is None:
        return b
    if b is None:
        return a
    return (tree[0], a, b)


def rects(tree):
    out = {}

    def walk(node):
        if "block_id" in node:
            out[node["block_id"]] = tuple(node["rect"])
        else:
            walk(node["split"]["before"])
            walk(node["split"]["after"])

    walk(layout(tree))
    return out


def listing(*windows):
    return {"windows": [window("window:caller", "Pi Durable", CALLER), *windows]}


QUADRANTS = {(0.0, 0.0, 0.5, 0.5), (0.5, 0.0, 0.5, 0.5), (0.0, 0.5, 0.5, 0.5), (0.5, 0.5, 0.5, 0.5)}


class ChooseTest(unittest.TestCase):
    def fill(self, tree, names):
        for name in names:
            got = slot.choose(listing(window("window:sub", "Pi Durable Sub Agents", tree)), CALLER)
            self.assertEqual(got["action"], "split")
            tree = split(tree, got["anchor"], got["direction"], name)
        return tree

    def test_no_tab_means_a_new_tab_named_after_the_caller(self):
        self.assertEqual(slot.choose(listing(), CALLER), {"action": "new", "tab_label": "Pi Durable Sub Agents"})

    def test_four_workers_make_a_two_by_two_grid(self):
        tree = self.fill("w1", ["w2", "w3", "w4"])
        self.assertEqual(set(rects(tree).values()), QUADRANTS)

    def test_two_workers_sit_side_by_side(self):
        tree = self.fill("w1", ["w2"])
        self.assertEqual(rects(tree), {"w1": (0.0, 0.0, 0.5, 1.0), "w2": (0.5, 0.0, 0.5, 1.0)})

    def test_a_full_tab_sends_the_fifth_worker_to_a_numbered_tab(self):
        tree = self.fill("w1", ["w2", "w3", "w4"])
        got = slot.choose(listing(window("window:sub", "Pi Durable Sub Agents", tree)), CALLER)
        self.assertEqual(got, {"action": "new", "tab_label": "Pi Durable Sub Agents 2"})

    def test_a_closed_worker_quadrant_is_refilled(self):
        tree = self.fill("w1", ["w2", "w3", "w4"])
        for gone in ["w1", "w2", "w3", "w4"]:
            refilled = self.fill(close(tree, gone), ["w5"])
            self.assertEqual(set(rects(refilled).values()), QUADRANTS, gone)

    def test_the_first_tab_with_room_wins(self):
        full = self.fill("w1", ["w2", "w3", "w4"])
        got = slot.choose(
            listing(
                window("window:sub3", "Pi Durable Sub Agents 3", "x1"),
                window("window:sub", "Pi Durable Sub Agents", full),
                window("window:sub2", "Pi Durable Sub Agents 2", ("h", "y1", "y2")),
            ),
            CALLER,
        )
        self.assertEqual((got["window_id"], got["anchor"], got["direction"]), ("window:sub2", "y1", "below"))

    def test_other_tabs_are_never_targets(self):
        got = slot.choose(
            listing(window("window:o", "Hermes Sub Agents", "z1"), window("window:p", "Pi Durable Sub Agents old", "z2")),
            CALLER,
        )
        self.assertEqual(got, {"action": "new", "tab_label": "Pi Durable Sub Agents"})

    def test_unknown_caller_fails(self):
        with self.assertRaises(SystemExit):
            slot.choose(listing(), "block:missing")


if __name__ == "__main__":
    unittest.main()
