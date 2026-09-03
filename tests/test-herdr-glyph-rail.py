#!/usr/bin/env python3

"""Regression guard for the Herdr Glyph Rail's non-ASCII contract.

U+E0B3, the Powerline soft divider, lives in the BMP Private Use Area and is
stripped by text pipelines far more readily than the Plane-15 Nerd Font glyphs
beside it. It silently degraded to two plain spaces once already, in both
config.toml and README.md, without breaking `herdr config check`.

Every expected character here is built with chr(), never pasted literally: a
test file carrying the raw glyph could be stripped by the same pipeline and
would then assert two spaces against two spaces, passing while the rail is
broken.

Run: python3 tests/test-herdr-glyph-rail.py
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
CONFIG = REPO_ROOT / "dot-config/herdr/config.toml"
OMARCHY_CONFIG = REPO_ROOT / "dot-config/herdr/config-omarchy.toml"
README = REPO_ROOT / "README.md"
CLAUDE_USAGE = REPO_ROOT / "dot-config/herdr/claude-usage.sh"
CODEX_USAGE = REPO_ROOT / "dot-config/herdr/codex-usage.py"

DIVIDER = chr(0xE0B3)  # Powerline soft divider
CLOCK = chr(0xF0954)  # Nerd Font clock, the datetime module's glyph
OPENAI = chr(0xEC81)  # Nerd Fonts cod-openai
CLAUDE = chr(0xEC82)  # Nerd Fonts cod-claude

# Entry types that render bare text. The rail is glyph-led, so none belong in
# it; `hostname` also cannot carry a prefix glyph, which is why host identity
# is a command entry.
BARE_TEXT_TYPES = ("zoom", "text", "hostname")

failures: list[str] = []


def check(description: str, ok: bool, detail: str = "") -> None:
    if ok:
        print("ok   %s" % description)
    else:
        print("FAIL: %s" % description, file=sys.stderr)
        if detail:
            print("  %s" % detail, file=sys.stderr)
        failures.append(description)


def decode_toml_escapes(value: str) -> str:
    """Resolve the \\uXXXX escapes a TOML basic string may use.

    Handles both spellings, so the assertions hold whether the config stores
    the divider as an escape or as a raw character.
    """
    return re.sub(
        r"\\u([0-9a-fA-F]{4})", lambda m: chr(int(m.group(1), 16)), value
    )


config_text = CONFIG.read_text(encoding="utf-8")
omarchy_config_text = OMARCHY_CONFIG.read_text(encoding="utf-8")
readme_text = README.read_text(encoding="utf-8")
claude_usage_text = CLAUDE_USAGE.read_text(encoding="utf-8")
codex_usage_text = CODEX_USAGE.read_text(encoding="utf-8")

# 1. The separator is exactly one divider, padded by one space on each side.
match = re.search(
    r'^tab_bar_right_separator = "(.*)"$', config_text, re.MULTILINE
)
if match is None:
    check("config.toml declares tab_bar_right_separator", False)
else:
    separator = decode_toml_escapes(match.group(1))
    check(
        "separator is a space-padded U+E0B3 divider",
        separator == " %s " % DIVIDER,
        "got %r (codepoints: %s)"
        % (separator, " ".join("U+%04X" % ord(c) for c in separator)),
    )

# 2. The clock module keeps its glyph, the same failure mode one entry over.
datetime_match = re.search(r'\{ type = "datetime", format = "(.*?)"', config_text)
if datetime_match is None:
    check("config.toml declares a datetime entry", False)
else:
    fmt = decode_toml_escapes(datetime_match.group(1))
    check(
        "datetime format leads with the U+F0954 clock glyph",
        fmt.startswith(CLOCK),
        "got %r" % fmt,
    )

# 3. The rail stays glyph-led: no bare-text entry types.
for entry_type in BARE_TEXT_TYPES:
    check(
        'no bare-text "%s" entry in the rail' % entry_type,
        ('type = "%s"' % entry_type) not in config_text,
        "the per-tab Z marker already shows zoom state independently"
        if entry_type == "zoom"
        else "",
    )

# 4. The Omarchy-specific template carries the same Glyph Rail contract.
omarchy_separator_match = re.search(
    r'^tab_bar_right_separator = "(.*)"$', omarchy_config_text, re.MULTILINE
)
check(
    "config-omarchy.toml keeps the U+E0B3 divider",
    omarchy_separator_match is not None
    and decode_toml_escapes(omarchy_separator_match.group(1)) == " %s " % DIVIDER,
)
omarchy_datetime_match = re.search(
    r'\{ type = "datetime", format = "(.*?)"', omarchy_config_text
)
check(
    "config-omarchy.toml keeps the clock glyph",
    omarchy_datetime_match is not None
    and decode_toml_escapes(omarchy_datetime_match.group(1)).startswith(CLOCK),
)
for entry_type in BARE_TEXT_TYPES:
    check(
        'config-omarchy.toml has no bare-text "%s" rail entry' % entry_type,
        ('type = "%s"' % entry_type) not in omarchy_config_text,
    )

# 5. Usage modules keep their dedicated provider glyphs.
check(
    "Claude usage leads with the U+EC82 Claude glyph",
    CLAUDE in claude_usage_text,
)
codex_command = 'command = "~/.config/herdr/codex-usage.py"'
check("config.toml includes Codex usage", codex_command in config_text)
check(
    "config-omarchy.toml includes Codex usage",
    codex_command in omarchy_config_text,
)
check(
    "Codex usage leads with the U+EC81 OpenAI glyph",
    OPENAI in codex_usage_text,
)

# 6. README documents the rail with real dividers, not collapsed spaces.
check(
    "README.md shows the U+E0B3 divider",
    DIVIDER in readme_text,
    "the divider code span and the sample rail must hold the real character",
)

if failures:
    print("\n%d check(s) failed" % len(failures), file=sys.stderr)
    sys.exit(1)
