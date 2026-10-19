#!/usr/bin/env bash
# The global pre-commit hook must block staged secrets and degrade to a warning
# where gitleaks is not installed. Repositories live in a temporary directory.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
HOOKS="$REPO_ROOT/dot-git-hooks"
TMP_ROOT="$(mktemp -d "${TMPDIR:-/tmp}/pre-commit-hook-XXXXXX")"
trap 'rm -rf "$TMP_ROOT"' EXIT

export GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_NOSYSTEM=1

new_repo() {
    local repo="$TMP_ROOT/$1"
    git init -q "$repo"
    git -C "$repo" config core.hooksPath "$HOOKS"
    git -C "$repo" config user.name "Hook Test"
    git -C "$repo" config user.email hook-test@example.invalid
    git -C "$repo" config commit.gpgsign false
    printf '%s\n' "$repo"
}

# Built at runtime so this file never contains a token-shaped literal.
fake_token="ghp_$(openssl rand -hex 18)"

no_gitleaks_path="$TMP_ROOT/bin"
mkdir -p "$no_gitleaks_path"
for tool in git bash env sh dirname cat; do
    ln -s "$(command -v "$tool")" "$no_gitleaks_path/$tool"
done

repo="$(new_repo missing)"
printf 'token = "%s"\n' "$fake_token" > "$repo/config.env"
git -C "$repo" add config.env
if ! output="$(PATH="$no_gitleaks_path" git -C "$repo" commit -q -m "No scanner" 2>&1)"; then
    echo "FAIL: a host without gitleaks must not block commits" >&2
    echo "$output" >&2
    exit 1
fi
if [[ "$output" != *"gitleaks not installed"* ]]; then
    echo "FAIL: a host without gitleaks must warn that nothing was scanned" >&2
    exit 1
fi
echo "ok   missing gitleaks warns without blocking"

if ! command -v gitleaks >/dev/null 2>&1; then
    echo "skip gitleaks is not installed; secret-blocking cases not exercised"
    exit 0
fi

repo="$(new_repo clean)"
printf 'name = "example"\n' > "$repo/config.env"
git -C "$repo" add config.env
if ! git -C "$repo" commit -q -m "Clean change" >/dev/null 2>&1; then
    echo "FAIL: a clean staged change was blocked" >&2
    exit 1
fi
echo "ok   clean staged change commits"

repo="$(new_repo leak)"
printf 'token = "%s"\n' "$fake_token" > "$repo/config.env"
git -C "$repo" add config.env
if output="$(git -C "$repo" commit -q -m "Leak" 2>&1)"; then
    echo "FAIL: a staged GitHub token was committed" >&2
    exit 1
fi
if [[ "$output" == *"$fake_token"* ]]; then
    echo "FAIL: the hook printed the unredacted secret" >&2
    exit 1
fi
if git -C "$repo" rev-parse -q --verify HEAD >/dev/null; then
    echo "FAIL: the blocked commit was still created" >&2
    exit 1
fi
echo "ok   staged secret is blocked and redacted"
