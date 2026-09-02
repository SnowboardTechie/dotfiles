#!/usr/bin/env bash
# Integration tests for dot-config/herdr/host-label.sh.
# Hardware and hostname lookups are stubbed on PATH in a temporary directory.

set -u

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LABELER="$REPO_ROOT/dot-config/herdr/host-label.sh"
TMP_ROOT="$(mktemp -d "${TMPDIR:-/tmp}/herdr-host-label-test-XXXXXX")"
trap 'rm -rf "$TMP_ROOT"' EXIT

mkdir -p "$TMP_ROOT/bin"

cat > "$TMP_ROOT/bin/pmset" <<'EOF'
#!/usr/bin/env bash
[[ "${1:-}" == "-g" && "${2:-}" == "batt" ]] || exit 64
printf '%s\n' "${STUB_BATTERY_STATUS:-}"
EOF

cat > "$TMP_ROOT/bin/uname" <<'EOF'
#!/usr/bin/env bash
[[ "${1:-}" == "-n" ]] || exit 64
printf '%s\n' "${STUB_HOSTNAME:-}"
EOF

chmod +x "$TMP_ROOT/bin/pmset" "$TMP_ROOT/bin/uname"

failures=0

expect() {
    local description="$1" ostype="$2" battery_status="$3" hostname="$4" arch_release="$5" want="$6" got
    got="$(
        OSTYPE="$ostype" \
        STUB_BATTERY_STATUS="$battery_status" \
        STUB_HOSTNAME="$hostname" \
        HERDR_ARCH_RELEASE_PATH="$arch_release" \
        PATH="$TMP_ROOT/bin:$PATH" \
        "$LABELER"
    )"
    if [[ "$got" == "$want" ]]; then
        echo "ok   $description"
    else
        echo "FAIL: $description" >&2
        echo "  want: $want" >&2
        echo "  got:  ${got:-<no output>}" >&2
        failures=$((failures + 1))
    fi
}

# A Mac Studio is a server; a MacBook is a laptop. Both drop the Apple-assigned
# hostname for a short label.
expect "Mac Studio reports the server glyph" \
    darwin24 "Now drawing from 'AC Power'" "Bryans-Mac-Studio.local" \
    "$TMP_ROOT/no-arch-release" "󰒋 Studio"
expect "MacBook reports the laptop glyph" \
    darwin24 $'Now drawing from \'AC Power\'\n -InternalBattery-0 (id=1234567)' \
    "Bryans-MacBook-Pro.local" "$TMP_ROOT/no-arch-release" "󰌢 MBP"
# Non-Arch, non-macOS: a box reached over remote attach keeps its own hostname.
expect "unknown host falls back to the server glyph and its hostname" \
    linux-gnu "" "linux-server" "$TMP_ROOT/no-arch-release" "󰒋 linux-server"

touch "$TMP_ROOT/arch-release"
expect "Arch/Omarchy host reports the desktop glyph" \
    linux-gnu "" "imachy" "$TMP_ROOT/arch-release" "󰍹 imachy"

[[ $failures -eq 0 ]] || exit 1
