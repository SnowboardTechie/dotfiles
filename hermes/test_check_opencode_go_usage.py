#!/usr/bin/env python3
"""Tests for the OpenCode Go allowance watcher."""

from __future__ import annotations

import datetime as dt
import importlib.util
import sqlite3
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
SCRIPT = HERE / "scripts" / "check-opencode-go-usage.py"

spec = importlib.util.spec_from_file_location("check_opencode_go_usage", SCRIPT)
assert spec is not None and spec.loader is not None
usage = importlib.util.module_from_spec(spec)
spec.loader.exec_module(usage)

NOW = dt.datetime(2026, 11, 12, 20, 0, tzinfo=dt.timezone.utc)  # Thursday, off-peak for DeepSeek


def make_db(path: Path, rows: list[tuple]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path)
    connection.execute(
        "CREATE TABLE session_model_usage (session_id TEXT, model TEXT, billing_provider TEXT,"
        " input_tokens INTEGER, output_tokens INTEGER, cache_read_tokens INTEGER,"
        " cache_write_tokens INTEGER, first_seen REAL, last_seen REAL)"
    )
    connection.executemany("INSERT INTO session_model_usage VALUES (?,?,?,?,?,?,?,?,?)", rows)
    connection.commit()
    connection.close()


def row(model: str, out_tokens: int, hours_ago: float, provider: str = "opencode-go") -> tuple:
    seen = (NOW - dt.timedelta(hours=hours_ago)).timestamp()
    return ("s", model, provider, 0, out_tokens, 0, 0, seen, seen)


class AllowanceTests(unittest.TestCase):
    def test_weighting_follows_listed_limit(self) -> None:
        base = {"input_tokens": 0, "output_tokens": 1_000_000, "cache_read_tokens": 0, "cache_write_tokens": 0}
        # $60 model at face value, $15 model four times, $100 model 0.6 times.
        self.assertAlmostEqual(usage.allowance_usd({**base, "model": "glm-5.3-flash"}), 0.50)
        self.assertAlmostEqual(usage.allowance_usd({**base, "model": "gpt-6-luna"}), 2.00)
        self.assertAlmostEqual(usage.allowance_usd({**base, "model": "deepseek-v4.1-flash"}), 0.36)

    def test_free_and_unknown_models(self) -> None:
        base = {"input_tokens": 0, "output_tokens": 1_000_000, "cache_read_tokens": 0, "cache_write_tokens": 0}
        self.assertEqual(usage.allowance_usd({**base, "model": "beam-free"}), 0.0)
        self.assertAlmostEqual(usage.allowance_usd({**base, "model": "some-new-model"}), 60.0)

    def test_deepseek_peak_doubles(self) -> None:
        peak = dt.datetime(2026, 11, 12, 7, 0, tzinfo=dt.timezone.utc).timestamp()
        base = {"model": "deepseek-v4.1-flash", "input_tokens": 0, "output_tokens": 1_000_000,
                "cache_read_tokens": 0, "cache_write_tokens": 0, "last_seen": peak}
        self.assertAlmostEqual(usage.allowance_usd(base), 0.72)


class WindowTests(unittest.TestCase):
    def test_windows_profiles_and_provider_filter(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            # 12M output on GLM-5.3-Flash = $6 face, 2 hours ago: inside every window.
            make_db(root / "state.db", [row("glm-5.3-flash", 12_000_000, 2),
                                        row("claude-opus-5-5", 50_000_000, 1, provider="claude")])
            # 1M output on GPT-6 Luna = $2 weighted, 3 days ago: weekly and monthly only.
            make_db(root / "profiles" / "home" / "state.db", [row("gpt-6-luna", 1_000_000, 72)])
            measured = usage.measure(root, NOW, 60.0, 4)
            five = measured["windows"]["5-hour"]
            self.assertAlmostEqual(five["used_usd"], 6.0)
            self.assertAlmostEqual(five["share"], 0.5)
            week = measured["windows"]["weekly"]
            self.assertAlmostEqual(week["used_usd"], 8.0)
            self.assertEqual(set(week["by_profile"]), {"default", "home"})
            self.assertAlmostEqual(measured["windows"]["monthly"]["share"], round(8.0 / 60, 4))

    def test_cycle_start(self) -> None:
        self.assertEqual(usage.cycle_start(NOW, 4).date(), dt.date(2026, 11, 4))
        early = dt.datetime(2026, 12, 2, 12, tzinfo=dt.timezone.utc)
        self.assertEqual(usage.cycle_start(early, 4).date(), dt.date(2026, 11, 4))


class AlertTests(unittest.TestCase):
    def measured(self, share: float) -> dict:
        window = {"used_usd": share * 12, "limit_usd": 12.0, "share": share, "by_model": {"glm-5.3-flash": share * 12}}
        return {"windows": {"5-hour": window}}

    def test_alerts_once_per_level_and_rearms(self) -> None:
        state, messages = usage.evaluate({}, self.measured(0.2))
        self.assertEqual(messages, [])
        state, messages = usage.evaluate(state, self.measured(0.55))
        self.assertEqual(len(messages), 1)
        self.assertNotIn(usage.MENTION, messages[0])
        state, messages = usage.evaluate(state, self.measured(0.6))
        self.assertEqual(messages, [])
        state, messages = usage.evaluate(state, self.measured(0.85))
        self.assertIn(usage.MENTION, messages[0])
        state, messages = usage.evaluate(state, self.measured(0.1))
        self.assertEqual(messages, [])
        state, messages = usage.evaluate(state, self.measured(0.52))
        self.assertEqual(len(messages), 1)


if __name__ == "__main__":
    unittest.main()
