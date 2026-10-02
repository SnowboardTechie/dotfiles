#!/usr/bin/env python3
"""Test the default Hermes shell command at its executable boundary."""

import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
ALIASES = ROOT / "dot-config/shell/aliases.sh"


class HermesShellLaunchTests(unittest.TestCase):
    def test_herdr_hint_and_argument_forwarding(self):
        cases = [
            (shell, in_herdr, inherited_hint)
            for shell in ("bash", "zsh")
            for in_herdr in (True, False)
            for inherited_hint in (None, "custom-agent")
        ]
        for shell, in_herdr, inherited_hint in cases:
            executable = shutil.which(shell)
            if not executable:
                continue
            with self.subTest(shell=shell, in_herdr=in_herdr, inherited_hint=inherited_hint), tempfile.TemporaryDirectory() as directory:
                stub = Path(directory) / "hermes"
                stub.write_text(
                    f"#!{shutil.which('python3')}\n"
                    "import json, os, sys\n"
                    "print(json.dumps({'hint': os.getenv('HERDR_AGENT'), 'args': sys.argv[1:]}))\n"
                    "sys.exit(17)\n"
                )
                stub.chmod(0o755)
                env = dict(os.environ, PATH=directory + os.pathsep + os.environ["PATH"])
                env.pop("HERDR_AGENT", None)
                env.pop("HERDR_ENV", None)
                if inherited_hint is not None:
                    env["HERDR_AGENT"] = inherited_hint
                if in_herdr:
                    env["HERDR_ENV"] = "1"
                command = 'source "$1"; hermes --resume "session with spaces"; rc=$?; printf "parent_hint=%s\\n" "${HERDR_AGENT-unset}"; exit "$rc"'
                result = subprocess.run(
                    [executable, "-c", command, "test", str(ALIASES)],
                    env=env, capture_output=True, text=True,
                )
                self.assertEqual(result.returncode, 17, result.stderr)
                lines = result.stdout.splitlines()
                self.assertEqual(json.loads(lines[0]), {
                    "hint": "hermes" if in_herdr else inherited_hint,
                    "args": ["--resume", "session with spaces"],
                })
                self.assertEqual(lines[1], "parent_hint=" + (inherited_hint or "unset"))


if __name__ == "__main__":
    unittest.main()
