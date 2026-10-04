#!/usr/bin/env python3
"""Guidance-contract regressions; not a model or live Matrix execution test."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "dot-agents/skills/coding-agent-handoff-supervision/SKILL.md"


class MatrixRoutingContract(unittest.TestCase):
    def test_shared_and_native_guidance_agree_on_right_sizing(self):
        for path in (SKILL, ROOT / "hermes/plugins/herdr-gateway/skills/workflow/SKILL.md"):
            with self.subTest(path=path):
                text = " ".join(path.read_text().split())
                self.assertIn("Simple questions stay with", text)
                self.assertIn("lightweight", text)
                self.assertIn("explicit runtime selection overrides", text)
                self.assertIn("Do not expand a simple question into an audit", text)
                self.assertNotIn("Hermes requires Bryan's explicit selection", text)

    def test_matrix_transport_is_selected_before_cli_prerequisites(self):
        text = SKILL.read_text()
        section = text.split("## Select the execution surface first", 1)[1].split("## When to Use", 1)[0]
        self.assertIn("herdr_start", section)
        self.assertIn("herdr-gateway:workflow", section)
        self.assertIn("No injected caller pane is expected in Matrix", section)
        self.assertIn("do not offer a background fallback", section)
        self.assertIn("Do not fabricate", section)

    def test_natural_read_only_requests_do_not_require_internal_dispatch_details(self):
        text = SKILL.read_text()
        section = text.split("## Select the execution surface first", 1)[1].split("## When to Use", 1)[0]
        self.assertIn("resolve the project directory and configured preset", section)
        self.assertIn("bounded read-only review", section)
        self.assertIn("user's request is the brief authority", section)
        self.assertIn("only when that changes the work", " ".join(section.split()))


if __name__ == "__main__":
    unittest.main()
