#!/usr/bin/env bash
# Local Git identity and signing policy must override the shared defaults.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TEST_HOME="$(mktemp -d "${TMPDIR:-/tmp}/git-local-override-XXXXXX")"
trap 'rm -rf "$TEST_HOME"' EXIT

if [[ "$(HOME="$TEST_HOME" git config --includes --file "$REPO_ROOT/dot-gitconfig" --get commit.gpgsign)" != true ]]; then
    echo "FAIL: default signing must remain enabled" >&2
    exit 1
fi

printf '[user]\n\temail = bryan@snowboardtechie.com\n[commit]\n\tgpgsign = false\n' > "$TEST_HOME/.gitconfig.local"
if [[ "$(HOME="$TEST_HOME" git config --includes --file "$REPO_ROOT/dot-gitconfig" --get commit.gpgsign)" != false ]]; then
    echo "FAIL: local signing policy did not override shared defaults" >&2
    exit 1
fi
if [[ "$(HOME="$TEST_HOME" git config --includes --file "$REPO_ROOT/dot-gitconfig" --get user.email)" != bryan@snowboardtechie.com ]]; then
    echo "FAIL: local Git identity was not loaded" >&2
    exit 1
fi

echo "ok   local Git identity and signing policy override shared defaults"
