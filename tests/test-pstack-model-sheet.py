#!/usr/bin/env python3
"""The pstack model sheet keeps OpenCode off its panels and keeps them two wide.

Only the scheduled ticket runner reads the sheet, and no scheduled job spends on
OpenCode Go (Bryan, 2026-11-17). Each panel keeps two different models.
"""

import re
import sys
import unittest
from pathlib import Path

SHEET = Path(__file__).resolve().parent.parent / "dot-agents/pstack-forgejo/pstack-models.md"
PANELS = ("arena runners", "arena cross-judge pool", "architect runners", "interrogate reviewers")


def read_roles(text):
    roles = {}
    for line in text.splitlines():
        role, sep, value = line.partition(":")
        if sep and value.strip() and not line.startswith("#") and len(role) < 60:
            roles[role.strip()] = value.strip()
    return roles


def aliases(roles):
    return dict(pair.strip().split("=", 1) for pair in roles["pi models"].split(","))


def panel_models(roles, role):
    names = aliases(roles)
    entries = [re.sub(r"\s*@\w+$", "", e.strip()) for e in roles[role].split(",")]
    return [names.get(e, e) for e in entries]


class ModelSheet(unittest.TestCase):
    def setUp(self):
        self.text = SHEET.read_text()
        self.roles = read_roles(self.text)

    def test_names_no_opencode_model(self):
        self.assertNotRegex(self.text, r"\bopencode(-go)?/")

    def test_panels_have_two_different_models(self):
        for role in PANELS:
            with self.subTest(role=role):
                self.assertIn(role, self.roles)
                models = panel_models(self.roles, role)
                self.assertGreaterEqual(len(set(models)), 2, f"{role}: {models}")


if __name__ == "__main__":
    sys.exit(0 if unittest.main(exit=False).result.wasSuccessful() else 1)
