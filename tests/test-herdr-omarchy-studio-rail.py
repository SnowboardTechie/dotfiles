#!/usr/bin/env python3
"""Exercise Omarchy's account usage commands at the shell/SSH boundary."""
import os
from pathlib import Path
import subprocess
import tempfile
import tomllib
import unittest

ROOT = Path(__file__).resolve().parents[1]


class StudioRailTests(unittest.TestCase):
    def test_account_modules_use_bounded_key_only_studio_ssh(self):
        config = tomllib.loads((ROOT / "dot-config/herdr/config-omarchy.toml").read_text())
        entries = config["ui"]["tab_bar_right"][:3]
        with tempfile.TemporaryDirectory() as tmp:
            ssh = Path(tmp) / "ssh"
            ssh.write_text("#!/bin/sh\nprintf '%s\\n' \"$@\" > \"$SSH_ARGS\"\nprintf 'usage-probe\\n'\n")
            ssh.chmod(0o700)
            for entry, module in zip(entries, ("claude-usage.sh", "codex-usage.py", "openrouter-spend.py")):
                with self.subTest(module=module):
                    args = Path(tmp) / "args"
                    env = dict(os.environ, HOME=tmp, PATH=tmp + os.pathsep + os.environ["PATH"], SSH_ARGS=str(args))
                    result = subprocess.run(entry["command"], shell=True, env=env, capture_output=True, text=True, timeout=12)
                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertEqual(result.stdout, "usage-probe\n")
                    self.assertEqual(args.read_text().splitlines(), ["-o", "BatchMode=yes", "-o", "ConnectTimeout=3", "bryan@bryans-mac-studio", "~/.config/herdr/" + module])
                    self.assertGreaterEqual(entry["timeout_seconds"], 8)


if __name__ == "__main__":
    unittest.main()
