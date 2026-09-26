#!/usr/bin/env bash
# Gnarbox's full-ownership setup must retire OpenCode, not resurrect it.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TEST_HOME="$(mktemp -d "${TMPDIR:-/tmp}/gnarbox-profile-test-XXXXXX")"
trap 'rm -rf "$TEST_HOME"' EXIT
mkdir -p "$TEST_HOME/bin" "$TEST_HOME/.config/alacritty" "$TEST_HOME/.config/opencode/skills"
printf '#!/bin/sh\nprintf "gnarbox\\n"\n' > "$TEST_HOME/bin/hostname"
chmod +x "$TEST_HOME/bin/hostname"
ln -s "$REPO_ROOT/dot-agents/skills/ship" "$TEST_HOME/.config/opencode/skills/ship"
ln -s "$TEST_HOME/foreign" "$TEST_HOME/.config/opencode/skills/foreign"

HOME="$TEST_HOME" OSTYPE=linux-gnu PATH="$TEST_HOME/bin:$PATH" \
    /bin/bash "$REPO_ROOT/setup-platform-configs.sh" > "$TEST_HOME/setup.log"

test ! -L "$TEST_HOME/.config/opencode/AGENTS.md"
test ! -L "$TEST_HOME/.config/opencode/skills/ship"
test -L "$TEST_HOME/.config/opencode/skills/foreign"
test -L "$TEST_HOME/.pi/agent/skills/ship"
test -L "$TEST_HOME/.hermes/skills/personal/ship"

echo "ok   Gnarbox setup retires OpenCode links and keeps Pi/Hermes skills"
