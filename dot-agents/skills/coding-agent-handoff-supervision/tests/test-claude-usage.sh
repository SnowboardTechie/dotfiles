#!/usr/bin/env bash
# Integration tests for scripts/claude-usage.sh.
# Credentials, commands, and cache state are isolated in a temporary directory.

set -u

SKILL_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TRACKER="$SKILL_ROOT/scripts/claude-usage.sh"
TMP_ROOT="$(mktemp -d "${TMPDIR:-/tmp}/claude-usage-test-XXXXXX")"
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
    # The token must never appear on the command line, where ps can read it.
    [[ "$argument" == *fallback-token* ]] && exit 65
    if [[ "$previous" == "-H" && "$argument" == "@-" ]]; then
        while IFS= read -r line; do
            [[ "$line" == "$expected" ]] && found=true
        done
    fi
    previous="$argument"
done
[[ "$found" == true ]] || exit 64
if [[ "${MOCK_NO_HEADERS:-0}" == 1 ]]; then
    printf '%s\r\n' 'HTTP/2 503' ''
    exit 0
fi
# MOCK_WINDOWS picks the headers: 5h (the default), 7d (a weekly-only seat), or both.
printf '%s\r\n' 'HTTP/2 200'
if [[ "${MOCK_WINDOWS:-5h}" == 5h || "${MOCK_WINDOWS:-5h}" == both ]]; then
    printf '%s\r\n' \
        "anthropic-ratelimit-unified-5h-utilization: ${MOCK_UTILIZATION:-0.42}" \
        "anthropic-ratelimit-unified-5h-reset: ${MOCK_RESET_EPOCH:-4102444800}"
fi
if [[ "${MOCK_WINDOWS:-5h}" == 7d || "${MOCK_WINDOWS:-5h}" == both ]]; then
    printf '%s\r\n' \
        'anthropic-ratelimit-unified-representative-claim: seven_day' \
        "anthropic-ratelimit-unified-7d-reset: ${MOCK_WEEKLY_RESET_EPOCH:-4102444800}" \
        'anthropic-ratelimit-unified-7d-status: allowed' \
        "anthropic-ratelimit-unified-7d-utilization: ${MOCK_WEEKLY_UTILIZATION:-0.25}" \
        'anthropic-ratelimit-unified-status: allowed'
fi
printf '%s\r\n' ''
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

rm -f "$TMP_ROOT/runtime/claude-usage-cache"
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

rm -f "$TMP_ROOT/runtime/claude-usage-cache"
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

rm -f "$TMP_ROOT/runtime/claude-usage-cache"
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

# --- Weekly-only seats (a plan with no 5-hour window) ---

CACHE="$TMP_ROOT/runtime/claude-usage-cache"
fail() {
    echo "FAIL: $1" >&2
    echo "  status=$status output=${out:-<no output>}" >&2
    exit 1
}
# run_tracker [ENV=VALUE...] -- [ARGS...]: sets $out (stdout and stderr) and $status.
run_tracker() {
    local env_args=()
    while [[ $# -gt 0 && "$1" != -- ]]; do env_args+=("$1"); shift; done
    [[ $# -gt 0 ]] && shift
    set +e
    out="$(
        env HOME="$TMP_ROOT/home" \
            XDG_RUNTIME_DIR="$TMP_ROOT/runtime" \
            OSTYPE=darwin24 \
            PATH="$TMP_ROOT/bin:$PATH" \
            ${env_args[@]+"${env_args[@]}"} \
            "$TRACKER" "$@" 2>&1
    )"
    status=$?
    set -e
}
# A cache older than the 300-second TTL, so the next render reads live headers.
age_cache() { touch -t 200001010000 "$CACHE"; }
first_pct() { printf '%s\n' "$1" | grep -oE '[0-9]+%' | head -1; }
NOW=$(date +%s)
# The Glyph Rail Claude icon, U+EC82, that begins every render line.
ICON=$(printf '\xee\xb2\x82')
SIX_DAYS=$(( NOW + 6 * 86400 + 3 * 3600 + 600 ))

rm -f "$CACHE"
run_tracker MOCK_WINDOWS=7d MOCK_WEEKLY_UTILIZATION=0.25 MOCK_WEEKLY_RESET_EPOCH="$SIX_DAYS" --
[[ $status -eq 0 && "$out" == "$ICON 25% weekly ↻6d 3h" ]] \
    || fail "expected a weekly-only render line"
[[ "$(first_pct "$out")" == "25%" ]] || fail "expected the callers' parse to read the weekly figure"
echo "ok   weekly-only seat renders the weekly window, and the parse reads it"

rm -f "$CACHE"
run_tracker MOCK_WINDOWS=7d MOCK_WEEKLY_UTILIZATION=0.25 MOCK_WEEKLY_RESET_EPOCH="$SIX_DAYS" -- --check-capacity
[[ $status -eq 0 && "$out" == "Claude weekly capacity available: 25%; reset in 6d 3h" ]] \
    || fail "expected weekly capacity to be available"
echo "ok   weekly-only capacity check permits a turn below the limit"

rm -f "$CACHE"
run_tracker MOCK_WINDOWS=7d MOCK_WEEKLY_UTILIZATION=1 MOCK_WEEKLY_RESET_EPOCH="$SIX_DAYS" -- --check-capacity
[[ $status -eq 75 && "$out" == "Claude weekly capacity exhausted (100%); reset in 6d 3h" ]] \
    || fail "expected exhausted weekly capacity to exit 75"
echo "ok   weekly-only capacity check blocks a turn at 100%"

rm -f "$CACHE"
run_tracker MOCK_WINDOWS=7d MOCK_WEEKLY_UTILIZATION=1.07 -- --check-capacity
[[ $status -eq 75 && "$out" == "Claude weekly capacity exhausted (107%);"* ]] \
    || fail "expected weekly capacity over 100% to exit 75"
echo "ok   weekly-only capacity check blocks a turn over 100%"

rm -f "$CACHE"
run_tracker MOCK_WINDOWS=7d MOCK_WEEKLY_UTILIZATION=0.25 \
    MOCK_WEEKLY_RESET_EPOCH=$(( NOW + 2 * 3600 + 300 )) --
[[ $status -eq 0 && "$out" =~ ^"$ICON"\ 25%\ weekly\ ↻2:0[45]$ ]] \
    || fail "expected a weekly reset under a day to read hours and minutes"
echo "ok   weekly reset under a day reads H:MM"

# Both windows: today's output, byte for byte.
rm -f "$CACHE"
run_tracker MOCK_WINDOWS=both MOCK_UTILIZATION=0.42 MOCK_WEEKLY_UTILIZATION=0.9 \
    MOCK_RESET_EPOCH=$(( NOW + 3600 + 1800 + 30 )) --
[[ $status -eq 0 && "$out" == "$ICON 42% ↻1:30" ]] || fail "expected the 5-hour line when both windows are present"
rm -f "$CACHE"
run_tracker MOCK_WINDOWS=both MOCK_UTILIZATION=0.42 MOCK_WEEKLY_UTILIZATION=0.9 \
    MOCK_RESET_EPOCH=$(( NOW + 3600 + 1800 + 30 )) -- --check-capacity
[[ $status -eq 0 && "$out" == "Claude 5-hour capacity available: 42%; reset in 1:30" ]] \
    || fail "expected the 5-hour capacity check when both windows are present"
rm -f "$CACHE"
run_tracker MOCK_WINDOWS=both MOCK_UTILIZATION=1 MOCK_WEEKLY_UTILIZATION=0.1 \
    MOCK_RESET_EPOCH=$(( NOW + 3600 + 1800 + 30 )) -- --check-capacity
[[ $status -eq 75 && "$out" == "Claude 5-hour capacity exhausted (100%); reset in 1:30" ]] \
    || fail "expected the 5-hour exhausted message when both windows are present"
echo "ok   both windows present: the 5-hour window is reported in today's words"

# Neither window: fail closed.
rm -f "$CACHE"
run_tracker MOCK_WINDOWS=none --
[[ $status -eq 0 && -z "$out" ]] || fail "expected render mode to print nothing with neither window"
run_tracker MOCK_WINDOWS=none -- --check-capacity
[[ $status -eq 69 && "$out" == "Claude capacity could not be verified" ]] \
    || fail "expected the capacity check to fail closed with neither window"
echo "ok   neither window: render prints nothing and the check exits 69"

# The cache records its window.
rm -f "$CACHE"
run_tracker MOCK_WINDOWS=7d MOCK_WEEKLY_UTILIZATION=0.25 --
[[ "$(sed -n '3p' "$CACHE")" == 7d ]] || fail "expected the cache to record the weekly window"
rm -f "$CACHE"
run_tracker MOCK_WINDOWS=5h MOCK_UTILIZATION=0.42 --
[[ "$(sed -n '3p' "$CACHE")" == 5h ]] || fail "expected the cache to record the 5-hour window"
echo "ok   the cache records which window its numbers are for"

# Today's two-line cache is a 5-hour reading, fresh or as a fallback.
printf '%s\n%s\n' 0.61 4102444800 > "$CACHE"
run_tracker MOCK_WINDOWS=7d MOCK_WEEKLY_UTILIZATION=0.25 --
[[ "$out" == "$ICON 61% ↻"* && "$out" != *weekly* ]] || fail "expected a fresh two-line cache to read as 5-hour"
printf '%s\n%s\n' 0.61 4102444800 > "$CACHE"
age_cache
run_tracker MOCK_NO_HEADERS=1 --
[[ "$out" == "$ICON 61% ↻"* && "$out" != *weekly* ]] || fail "expected a stale two-line fallback to read as 5-hour"
echo "ok   a two-line cache is read as a 5-hour reading"

# A seat moving from 5-hour to weekly-only.
rm -f "$CACHE"
run_tracker MOCK_WINDOWS=5h MOCK_UTILIZATION=0.42 --
age_cache
run_tracker MOCK_WINDOWS=7d MOCK_WEEKLY_UTILIZATION=0.25 MOCK_WEEKLY_RESET_EPOCH="$SIX_DAYS" --
[[ "$out" == "$ICON 25% weekly ↻6d 3h" ]] || fail "expected the weekly reading after a stale 5-hour cache"
age_cache
run_tracker MOCK_NO_HEADERS=1 --
[[ "$out" == "$ICON 25% weekly ↻6d 3h" ]] || fail "expected the weekly cache fallback to stay weekly"
run_tracker MOCK_WINDOWS=7d MOCK_WEEKLY_UTILIZATION=0.25 -- --check-capacity
[[ "$out" == "Claude weekly capacity available: 25%;"* ]] || fail "expected the live weekly check"
echo "ok   5-hour cache then weekly-only response: never mislabelled"

# And back from weekly-only to 5-hour.
rm -f "$CACHE"
run_tracker MOCK_WINDOWS=7d MOCK_WEEKLY_UTILIZATION=0.25 MOCK_WEEKLY_RESET_EPOCH="$SIX_DAYS" --
run_tracker MOCK_WINDOWS=5h MOCK_UTILIZATION=0.42 --
[[ "$out" == "$ICON 25% weekly ↻6d 3h" ]] || fail "expected a fresh weekly cache to keep its weekly label"
age_cache
run_tracker MOCK_WINDOWS=5h MOCK_UTILIZATION=0.42 --
[[ "$out" == "$ICON 42% ↻"* && "$out" != *weekly* ]] || fail "expected the 5-hour reading after a stale weekly cache"
age_cache
run_tracker MOCK_NO_HEADERS=1 --
[[ "$out" == "$ICON 42% ↻"* && "$out" != *weekly* ]] || fail "expected the 5-hour cache fallback to stay 5-hour"
run_tracker MOCK_WINDOWS=5h MOCK_UTILIZATION=0.42 -- --check-capacity
[[ "$out" == "Claude 5-hour capacity available: 42%;"* ]] || fail "expected the live 5-hour check"
echo "ok   weekly cache then 5-hour response: never mislabelled"
