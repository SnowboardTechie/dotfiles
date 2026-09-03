#!/usr/bin/env bash
# Integration tests for dot-config/herdr/claude-usage.sh.
# Credentials, commands, and cache state are isolated in a temporary directory.

set -u

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TRACKER="$REPO_ROOT/dot-config/herdr/claude-usage.sh"
TMP_ROOT="$(mktemp -d "${TMPDIR:-/tmp}/herdr-claude-usage-test-XXXXXX")"
trap 'rm -rf "$TMP_ROOT"' EXIT

mkdir -p "$TMP_ROOT/home/.claude" "$TMP_ROOT/bin" "$TMP_ROOT/runtime"
printf '%s\n' '{"claudeAiOauth":{"accessToken":"fallback-token"}}' > "$TMP_ROOT/home/.claude/.credentials.json"

cat > "$TMP_ROOT/bin/security" <<'EOF'
#!/usr/bin/env bash
# Simulate a Keychain item whose secret is unavailable noninteractively.
exit 44
EOF

cat > "$TMP_ROOT/bin/curl" <<'EOF'
#!/usr/bin/env bash
expected='Authorization: Bearer fallback-token'
previous=''
found=false
for argument in "$@"; do
    if [[ "$previous" == "-H" && "$argument" == "$expected" ]]; then
        found=true
    fi
    previous="$argument"
done
[[ "$found" == true ]] || exit 64
printf '%s\r\n' \
    'HTTP/2 200' \
    'anthropic-ratelimit-unified-5h-utilization: 0.42' \
    'anthropic-ratelimit-unified-5h-reset: 4102444800' \
    ''
EOF
chmod +x "$TMP_ROOT/bin/security" "$TMP_ROOT/bin/curl"

out="$(
    HOME="$TMP_ROOT/home" \
    XDG_RUNTIME_DIR="$TMP_ROOT/runtime" \
    OSTYPE=darwin24 \
    PATH="$TMP_ROOT/bin:$PATH" \
    "$TRACKER"
)"

if [[ "$out" != " 42% ↻"* ]]; then
    echo "FAIL: expected the tracker to use file credentials when Keychain access fails" >&2
    echo "  got: ${out:-<no output>}" >&2
    exit 1
fi

echo "ok   macOS falls back to ~/.claude/.credentials.json"
