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
for name in AGENTS.md agents opencode.json plugins; do
    ln -s "$REPO_ROOT/dot-config/opencode/$name" "$TEST_HOME/.config/opencode/$name"
done
printf 'app-owned\n' > "$TEST_HOME/.config/opencode/package.json"

HOME="$TEST_HOME" OSTYPE=linux-gnu PATH="$TEST_HOME/bin:$PATH" \
    /bin/bash "$REPO_ROOT/setup-platform-configs.sh" > "$TEST_HOME/setup.log"

test ! -L "$TEST_HOME/.config/opencode/AGENTS.md"
for name in agents opencode.json plugins; do
    test ! -L "$TEST_HOME/.config/opencode/$name"
done
test ! -L "$TEST_HOME/.config/opencode/skills/ship"
test -L "$TEST_HOME/.config/opencode/skills/foreign"
test "$(<"$TEST_HOME/.config/opencode/package.json")" = app-owned
test -L "$TEST_HOME/.pi/agent/skills/ship"
test -L "$TEST_HOME/.hermes/skills/personal/ship"

echo "ok   Gnarbox setup retires OpenCode links and keeps Pi/Hermes skills"

WHOLE_HOME="$(mktemp -d "${TMPDIR:-/tmp}/gnarbox-whole-link-test-XXXXXX")"
trap 'rm -rf "$TEST_HOME" "$WHOLE_HOME"' EXIT
mkdir -p "$WHOLE_HOME/.config/alacritty" "$WHOLE_HOME/.config"
ln -s "$REPO_ROOT/dot-config/opencode" "$WHOLE_HOME/.config/opencode"
HOME="$WHOLE_HOME" OSTYPE=linux-gnu PATH="$TEST_HOME/bin:$PATH" \
    /bin/bash "$REPO_ROOT/setup-platform-configs.sh" > "$WHOLE_HOME/setup.log"
test ! -L "$WHOLE_HOME/.config/opencode"
test -f "$REPO_ROOT/dot-config/opencode/opencode.json"
test -L "$WHOLE_HOME/.pi/agent/skills/ship"

echo "ok   Gnarbox setup replaces only a repo-owned whole OpenCode link"
