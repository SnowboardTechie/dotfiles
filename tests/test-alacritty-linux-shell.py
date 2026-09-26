#!/usr/bin/env python3
"""The Linux terminal must not inherit a stale pre-switch bash SHELL."""

from pathlib import Path
import subprocess

config_path = Path(__file__).resolve().parents[1] / "dot-config/alacritty/alacritty-linux.toml"


def config_value(option):
    expression = "(builtins.fromTOML (builtins.readFile %s)).%s" % (config_path, option)
    return subprocess.check_output(["nix", "eval", "--impure", "--raw", "--expr", expression], text=True)


expected = "/run/current-system/sw/bin/zsh"
assert config_value("terminal.shell.program") == expected
assert config_value("env.SHELL") == expected
print("ok   Alacritty Linux starts zsh even with a stale GNOME SHELL")
