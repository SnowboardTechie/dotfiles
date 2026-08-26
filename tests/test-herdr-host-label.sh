#!/usr/bin/env bash
# Integration tests for dot-config/herdr/host-label.sh.
# Hardware and hostname lookups are stubbed on PATH in a temporary directory.

set -u

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LABELER="$REPO_ROOT/dot-config/herdr/host-label.sh"
TMP_ROOT="$(mktemp -d "${TMPDIR:-/tmp}/herdr-host-label-test-XXXXXX")"
trap 'rm -rf "$TMP_ROOT"' EXIT

mkdir -p "$TMP_ROOT/bin"

cat > "$TMP_ROOT/bin/sysctl" <<'EOF'
#!/usr/bin/env bash
printf '%s\n' "${STUB_HW_MODEL:-}"
EOF

cat > "$TMP_ROOT/bin/uname" <<'EOF'
#!/usr/bin/env bash
[[ "${1:-}" == "-n" ]] || exit 64
printf '%s\n' "${STUB_HOSTNAME:-}"
EOF

chmod +x "$TMP_ROOT/bin/sysctl" "$TMP_ROOT/bin/uname"

failures=0

expect() {
    local description="$1" ostype="$2" model="$3" hostname="$4" want="$5" got
    got="$(
        OSTYPE="$ostype" \
        STUB_HW_MODEL="$model" \
        STUB_HOSTNAME="$hostname" \
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
    darwin24 "Mac14,14" "Bryans-Mac-Studio.local" "󰒋 Studio"
expect "MacBook reports the laptop glyph" \
    darwin24 "MacBookPro18,3" "Bryans-MacBook-Pro.local" "󰌢 MBP"
# Non-Arch, non-macOS: a box reached over remote attach keeps its own hostname.
expect "unknown host falls back to the server glyph and its hostname" \
    linux-gnu "" "gnarbox" "󰒋 gnarbox"

# The Arch branch keys off /etc/arch-release, which cannot be stubbed on PATH.
if [[ -f /etc/arch-release ]]; then
    expect "Arch host reports the Omarchy glyph" \
        linux-gnu "" "gnarchy" "󰣇 gnarchy"
else
    echo "skip Arch glyph (no /etc/arch-release on this host)"
fi

[[ $failures -eq 0 ]] || exit 1
