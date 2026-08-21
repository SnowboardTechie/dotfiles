#!/usr/bin/env python3
"""Tests for how the local Qwen worker gets its canonical skills.

The worker runs with `HERMES_HOME` pointed at `~/.hermes/local-qwen-worker`,
which has no `skills/` directory — so reconciling the normal home cannot supply
`tdd` and `diagnosing-bugs`. It reaches them through `skills.external_dirs`
pointed at the repository pool, read-only.

Two failure modes these lock down, both silent without a check:

* Hermes does not error on an unresolvable `--skills` name, so a missing pool
  would produce a worker running *without* the discipline the loop claims.
* A copied pool would drift from the one the rest of the fleet reconciles.

Run: python3 -m unittest hermes/skills/software-development/codex-qwen-implementation-loop/tests/test_qwen_worker_skills.py
"""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

SCRIPT = (
    Path(__file__).resolve().parents[1] / "scripts" / "qwen_worker.py"
)
SPEC = importlib.util.spec_from_file_location("qwen_worker", SCRIPT)
assert SPEC and SPEC.loader
QW = importlib.util.module_from_spec(SPEC)
sys.modules["qwen_worker"] = QW
SPEC.loader.exec_module(QW)

# tests / <skill> / software-development / skills / hermes / <repo root>
REPO_ROOT = Path(__file__).resolve().parents[5]
REAL_POOL = REPO_ROOT / "dot-agents" / "skills"


def fake_pool(root: Path, *names: str) -> Path:
    pool = root / "dot-agents" / "skills"
    for name in names:
        (pool / name).mkdir(parents=True, exist_ok=True)
        (pool / name / "SKILL.md").write_text(
            f"---\nname: {name}\ndescription: stub\n---\n", encoding="utf-8"
        )
    pool.mkdir(parents=True, exist_ok=True)
    return pool


class SkillSelectionTest(unittest.TestCase):
    def test_the_worker_selects_exactly_the_adapted_cores(self) -> None:
        self.assertEqual(QW.WORKER_SKILLS, ("tdd", "diagnosing-bugs"))

    def test_the_command_passes_exactly_tdd_and_diagnosing_bugs(self) -> None:
        """Assert the literal value after `--skills`, not just its presence."""
        command = QW.build_hermes_command(
            hermes_bin="/usr/bin/hermes", prompt="p", max_turns=5, session_id=None
        )
        self.assertIn("--skills", command)
        value = command[command.index("--skills") + 1]
        self.assertEqual(value, "tdd,diagnosing-bugs")

    def test_the_command_names_no_retired_bundled_skill(self) -> None:
        command = QW.build_hermes_command(
            hermes_bin="/usr/bin/hermes", prompt="p", max_turns=5, session_id=None
        )
        joined = " ".join(command)
        for retired in ("test-driven-development", "systematic-debugging"):
            with self.subTest(skill=retired):
                self.assertNotIn(retired, joined)

    def test_resume_keeps_the_same_skill_selection(self) -> None:
        command = QW.build_hermes_command(
            hermes_bin="/usr/bin/hermes", prompt="p", max_turns=5, session_id="s-1"
        )
        self.assertEqual(command[command.index("--skills") + 1], "tdd,diagnosing-bugs")
        self.assertIn("--resume", command)


class PoolResolutionTest(unittest.TestCase):
    def test_the_default_pool_is_the_repository_pool(self) -> None:
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop(QW.CANONICAL_SKILL_POOL_ENV, None)
            self.assertEqual(
                QW.resolve_canonical_skill_pool(), QW.DEFAULT_CANONICAL_SKILL_POOL
            )
        self.assertEqual(QW.DEFAULT_CANONICAL_SKILL_POOL.name, "skills")
        self.assertEqual(QW.DEFAULT_CANONICAL_SKILL_POOL.parent.name, "dot-agents")

    def test_an_explicit_override_wins(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with patch.dict(os.environ, {QW.CANONICAL_SKILL_POOL_ENV: tmp}):
                self.assertEqual(
                    QW.resolve_canonical_skill_pool(), Path(tmp).resolve()
                )

    def test_the_real_repository_pool_carries_both_worker_skills(self) -> None:
        for name in QW.WORKER_SKILLS:
            with self.subTest(skill=name):
                self.assertTrue((REAL_POOL / name / "SKILL.md").is_file())

    def test_a_missing_pool_is_refused(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(QW.WorkerError) as caught:
                QW.verify_canonical_skill_pool(Path(tmp) / "absent")
            self.assertIn(QW.CANONICAL_SKILL_POOL_ENV, str(caught.exception))

    def test_a_pool_missing_a_worker_skill_is_refused(self) -> None:
        """Hermes does not error on an unresolvable --skills name; this must."""
        with tempfile.TemporaryDirectory() as tmp:
            pool = fake_pool(Path(tmp), "tdd")
            with self.assertRaises(QW.WorkerError) as caught:
                QW.verify_canonical_skill_pool(pool)
            self.assertIn("diagnosing-bugs", str(caught.exception))

    def test_a_complete_pool_passes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            pool = fake_pool(Path(tmp), *QW.WORKER_SKILLS)
            QW.verify_canonical_skill_pool(pool)  # must not raise


class WorkerConfigTest(unittest.TestCase):
    def test_the_config_declares_the_pool_as_an_external_dir(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            pool = fake_pool(Path(tmp), *QW.WORKER_SKILLS)
            text = QW.worker_config_text(pool)
        self.assertIn("skills:", text)
        self.assertIn(f"external_dirs: {pool}", text)

    def test_the_config_still_pins_the_local_model_route(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            text = QW.worker_config_text(fake_pool(Path(tmp), *QW.WORKER_SKILLS))
        self.assertIn(QW.MODEL, text)
        self.assertIn(QW.BASE_URL, text)
        self.assertIn("127.0.0.1", text)

    def test_the_config_is_deterministic(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            pool = fake_pool(Path(tmp), *QW.WORKER_SKILLS)
            self.assertEqual(QW.worker_config_text(pool), QW.worker_config_text(pool))


class ResolutionVerificationTest(unittest.TestCase):
    """Presence in the pool is not resolution.

    Hermes scans the worker home's own `skills/` directory *before* the external
    pool and takes the first match, and it does not error on a shadowed or
    unresolvable `--skills` name. So a stale copy left by an earlier experiment
    silently wins, and the worker runs with the wrong skill while reporting
    success. These tests hold the real check in place.
    """

    def probe(self, mapping: dict[str, list[str]]):
        """A runner that answers as Hermes's discovery probe would."""

        class Result:
            returncode = 0
            stdout = json.dumps(mapping)
            stderr = ""

        return lambda *a, **k: Result()

    def pool_path(self, pool: Path, name: str) -> str:
        return str(pool / name / "SKILL.md")

    def test_one_canonical_candidate_per_name_passes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            pool = fake_pool(Path(tmp), *QW.WORKER_SKILLS)
            confirmed = QW.verify_worker_skill_resolution(
                Path(tmp) / "home",
                pool,
                source_root=Path(tmp),
                runner=self.probe(
                    {name: [self.pool_path(pool, name)] for name in QW.WORKER_SKILLS}
                ),
            )
        self.assertEqual(sorted(confirmed), sorted(QW.WORKER_SKILLS))

    def test_a_shadowing_candidate_fails(self) -> None:
        """The synthetic-shadow case: worker-home/skills/tdd beats the pool."""
        with tempfile.TemporaryDirectory() as tmp:
            pool = fake_pool(Path(tmp), *QW.WORKER_SKILLS)
            home = Path(tmp) / "home"
            shadow = str(home / "skills" / "tdd" / "SKILL.md")
            with self.assertRaises(QW.WorkerError) as caught:
                QW.verify_worker_skill_resolution(
                    home,
                    pool,
                    source_root=Path(tmp),
                    runner=self.probe(
                        {
                            "tdd": [shadow, self.pool_path(pool, "tdd")],
                            "diagnosing-bugs": [self.pool_path(pool, "diagnosing-bugs")],
                        }
                    ),
                )
        message = str(caught.exception)
        self.assertIn("shadows the canonical", message)
        self.assertIn("tdd", message)

    def test_a_name_that_does_not_resolve_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            pool = fake_pool(Path(tmp), *QW.WORKER_SKILLS)
            with self.assertRaises(QW.WorkerError) as caught:
                QW.verify_worker_skill_resolution(
                    Path(tmp) / "home",
                    pool,
                    source_root=Path(tmp),
                    runner=self.probe(
                        {"tdd": [self.pool_path(pool, "tdd")], "diagnosing-bugs": []}
                    ),
                )
        self.assertIn("does not resolve", str(caught.exception))

    def test_resolving_to_a_non_pool_file_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            pool = fake_pool(Path(tmp), *QW.WORKER_SKILLS)
            with self.assertRaises(QW.WorkerError) as caught:
                QW.verify_worker_skill_resolution(
                    Path(tmp) / "home",
                    pool,
                    source_root=Path(tmp),
                    runner=self.probe(
                        {
                            "tdd": ["/somewhere/else/tdd/SKILL.md"],
                            "diagnosing-bugs": [self.pool_path(pool, "diagnosing-bugs")],
                        }
                    ),
                )
        self.assertIn("not the canonical", str(caught.exception))

    def test_a_failing_probe_fails_closed(self) -> None:
        class Failed:
            returncode = 1
            stdout = ""
            stderr = "ImportError: no agent.skill_utils"

        with tempfile.TemporaryDirectory() as tmp:
            pool = fake_pool(Path(tmp), *QW.WORKER_SKILLS)
            with self.assertRaises(QW.WorkerError) as caught:
                QW.verify_worker_skill_resolution(
                    Path(tmp) / "home", pool,
                    source_root=Path(tmp), runner=lambda *a, **k: Failed(),
                )
        self.assertIn("probe failed", str(caught.exception))

    def test_a_missing_hermes_source_root_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            pool = fake_pool(Path(tmp), *QW.WORKER_SKILLS)
            with self.assertRaises(QW.WorkerError) as caught:
                QW.verify_worker_skill_resolution(
                    Path(tmp) / "home", pool, source_root=Path(tmp) / "absent"
                )
        self.assertIn("HERMES_SOURCE_ROOT", str(caught.exception))


@unittest.skipUnless(
    (Path.home() / ".hermes" / "hermes-agent" / "agent" / "skill_utils.py").is_file(),
    "requires a local Hermes installation",
)
class LiveResolutionTest(unittest.TestCase):
    """Resolve through Hermes's real discovery code, in a real isolated home."""

    def home_with_config(self, tmp: Path) -> Path:
        home = tmp / "worker-home"
        home.mkdir(parents=True)
        (home / "config.yaml").write_text(
            QW.worker_config_text(REAL_POOL), encoding="utf-8"
        )
        return home

    def test_both_skills_resolve_to_the_canonical_pool_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            home = self.home_with_config(Path(tmp))
            confirmed = QW.verify_worker_skill_resolution(home, REAL_POOL)
        self.assertEqual(sorted(confirmed), sorted(QW.WORKER_SKILLS))
        for name, path in confirmed.items():
            with self.subTest(skill=name):
                self.assertEqual(Path(path), (REAL_POOL / name / "SKILL.md").resolve())

    def test_a_real_stale_shadow_fails_before_launch(self) -> None:
        """Write an actual `worker-home/skills/tdd` and prove Hermes prefers it."""
        with tempfile.TemporaryDirectory() as tmp:
            home = self.home_with_config(Path(tmp))
            shadow = home / "skills" / "tdd"
            shadow.mkdir(parents=True)
            (shadow / "SKILL.md").write_text(
                "---\nname: tdd\ndescription: stale shadow\n---\n", encoding="utf-8"
            )
            with self.assertRaises(QW.WorkerError) as caught:
                QW.verify_worker_skill_resolution(home, REAL_POOL)
        message = str(caught.exception)
        self.assertIn("shadows the canonical", message)
        self.assertIn("tdd", message)

    def test_the_probe_reports_exactly_one_candidate_per_name(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            home = self.home_with_config(Path(tmp))
            resolved = QW.probe_skill_resolution(home, QW.WORKER_SKILLS)
        for name in QW.WORKER_SKILLS:
            with self.subTest(skill=name):
                self.assertEqual(len(resolved[name]), 1)
                self.assertTrue(resolved[name][0].endswith(f"{name}/SKILL.md"))


if __name__ == "__main__":
    unittest.main()
