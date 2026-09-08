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
if [[ "${MOCK_NO_HEADERS:-0}" == 1 ]]; then
    printf '%s\r\n' 'HTTP/2 503' ''
    exit 0
fi
printf '%s\r\n' \
    'HTTP/2 200' \
    "anthropic-ratelimit-unified-5h-utilization: ${MOCK_UTILIZATION:-0.42}" \
    "anthropic-ratelimit-unified-5h-reset: ${MOCK_RESET_EPOCH:-4102444800}" \
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

rm -f "$TMP_ROOT/runtime/herdr-claude-usage-cache"
out="$(
    HOME="$TMP_ROOT/home" \
    XDG_RUNTIME_DIR="$TMP_ROOT/runtime" \
    OSTYPE=darwin24 \
    PATH="$TMP_ROOT/bin:$PATH" \
    MOCK_UTILIZATION=0.42 \
    "$TRACKER" --check-capacity
)"
if [[ "$out" != "Claude 5-hour capacity available: 42%;"* ]]; then
    echo "FAIL: expected a verified available-capacity result" >&2
    echo "  got: ${out:-<no output>}" >&2
    exit 1
fi
echo "ok   capacity check permits a fresh Claude turn below the limit"

rm -f "$TMP_ROOT/runtime/herdr-claude-usage-cache"
set +e
out="$(
    HOME="$TMP_ROOT/home" \
    XDG_RUNTIME_DIR="$TMP_ROOT/runtime" \
    OSTYPE=darwin24 \
    PATH="$TMP_ROOT/bin:$PATH" \
    MOCK_UTILIZATION=1 \
    "$TRACKER" --check-capacity 2>&1
)"
status=$?
set -e
if [[ $status -ne 75 || "$out" != *"capacity exhausted (100%)"* ]]; then
    echo "FAIL: expected exhausted capacity to exit 75" >&2
    echo "  status=$status output=${out:-<no output>}" >&2
    exit 1
fi
echo "ok   capacity check blocks a fresh Claude turn at 100%"

rm -f "$TMP_ROOT/runtime/herdr-claude-usage-cache"
set +e
out="$(
    HOME="$TMP_ROOT/home" \
    XDG_RUNTIME_DIR="$TMP_ROOT/runtime" \
    OSTYPE=darwin24 \
    PATH="$TMP_ROOT/bin:$PATH" \
    MOCK_NO_HEADERS=1 \
    "$TRACKER" --check-capacity 2>&1
)"
status=$?
set -e
if [[ $status -ne 69 || "$out" != *"could not be verified"* ]]; then
    echo "FAIL: expected an unverifiable capacity check to fail closed" >&2
    echo "  status=$status output=${out:-<no output>}" >&2
    exit 1
fi
echo "ok   capacity check fails closed when live usage is unavailable"
