#!/usr/bin/env bash
# Integration tests for host-guarded Nix update and upgrade functions.

set -u

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FUNCTIONS="$REPO_ROOT/dot-config/zsh/functions.zsh"
ALIASES="$REPO_ROOT/dot-config/zsh/aliases.zsh"
TMP_ROOT="$(mktemp -d "${TMPDIR:-/tmp}/nix-host-guards-test-XXXXXX")"
trap 'rm -rf "$TMP_ROOT"' EXIT

mkdir -p "$TMP_ROOT/bin" "$TMP_ROOT/home/code/nix-configs"

cat > "$TMP_ROOT/bin/scutil" <<'EOF'
#!/usr/bin/env bash
[[ "${1:-}" == "--get" && "${2:-}" == "LocalHostName" ]] || exit 64
printf '%s\n' "${STUB_LOCAL_HOSTNAME:-unknown}"
EOF

cat > "$TMP_ROOT/bin/sudo" <<'EOF'
#!/usr/bin/env bash
printf 'sudo %s\n' "$*" >> "$COMMAND_LOG"
EOF

cat > "$TMP_ROOT/bin/nix" <<'EOF'
#!/usr/bin/env bash
printf 'nix %s\n' "$*" >> "$COMMAND_LOG"
EOF

chmod +x "$TMP_ROOT/bin/scutil" "$TMP_ROOT/bin/sudo" "$TMP_ROOT/bin/nix"

COMMAND_LOG="$TMP_ROOT/commands.log"
: > "$COMMAND_LOG"

output="$(
    printf 'y\n' | \
        HOME="$TMP_ROOT/home" \
        PATH="$TMP_ROOT/bin:/usr/bin:/bin" \
        COMMAND_LOG="$COMMAND_LOG" \
        STUB_LOCAL_HOSTNAME="Bryans-MacBook-Pro" \
        FUNCTIONS="$FUNCTIONS" \
        ALIASES="$ALIASES" \
        /bin/zsh -f -c 'source "$FUNCTIONS"; source "$ALIASES"; eval update-studio' 2>&1
)"
status=$?

if [[ $status -eq 0 ]]; then
    echo "FAIL: update-studio succeeded on the MacBook Pro" >&2
    exit 1
fi
if [[ -s "$COMMAND_LOG" ]]; then
    echo "FAIL: update-studio invoked a command on the MacBook Pro" >&2
    cat "$COMMAND_LOG" >&2
    exit 1
fi
if [[ "$output" != *"MacBook Pro"* || "$output" != *"studio"* ]]; then
    echo "FAIL: mismatch message did not identify the current machine and target" >&2
    printf '%s\n' "$output" >&2
    exit 1
fi

echo "ok   update-studio refuses to run on the MacBook Pro"

: > "$COMMAND_LOG"
output="$(
    HOME="$TMP_ROOT/home" \
        PATH="$TMP_ROOT/bin:/usr/bin:/bin" \
        COMMAND_LOG="$COMMAND_LOG" \
        STUB_LOCAL_HOSTNAME="Bryans-Mac-Studio" \
        FUNCTIONS="$FUNCTIONS" \
        ALIASES="$ALIASES" \
        /bin/zsh -f -c 'source "$FUNCTIONS"; source "$ALIASES"; update-studio' \
        </dev/null 2>&1
)"
status=$?

if [[ $status -eq 0 ]]; then
    echo "FAIL: update-studio proceeded without confirmation" >&2
    exit 1
fi
if [[ -s "$COMMAND_LOG" ]]; then
    echo "FAIL: update-studio invoked a command after confirmation was declined" >&2
    cat "$COMMAND_LOG" >&2
    exit 1
fi
if [[ "$output" != *"Studio"* || "$output" != *"Continue"* || "$output" != *"[Y/n]"* ]]; then
    echo "FAIL: confirmation prompt did not identify Studio and ask to continue" >&2
    printf '%s\n' "$output" >&2
    exit 1
fi

echo "ok   update-studio cancels when no interactive answer is available"

: > "$COMMAND_LOG"
printf '\n' | \
    HOME="$TMP_ROOT/home" \
    PATH="$TMP_ROOT/bin:/usr/bin:/bin" \
    COMMAND_LOG="$COMMAND_LOG" \
    STUB_LOCAL_HOSTNAME="Bryans-Mac-Studio" \
    FUNCTIONS="$FUNCTIONS" \
    ALIASES="$ALIASES" \
    /bin/zsh -f -c 'source "$FUNCTIONS"; source "$ALIASES"; update-studio' \
    >/dev/null 2>&1
status=$?

expected="sudo darwin-rebuild switch --flake $TMP_ROOT/home/code/nix-configs/#studio"
actual="$(<"$COMMAND_LOG")"
if [[ $status -ne 0 || "$actual" != "$expected" ]]; then
    echo "FAIL: update-studio did not default to yes on an empty answer" >&2
    echo "  want: $expected" >&2
    echo "  got:  ${actual:-<no command>}" >&2
    exit 1
fi

echo "ok   update-studio defaults to yes on Studio"

: > "$COMMAND_LOG"
output="$(
    printf 'y\n' | \
        HOME="$TMP_ROOT/home" \
        PATH="$TMP_ROOT/bin:/usr/bin:/bin" \
        COMMAND_LOG="$COMMAND_LOG" \
        STUB_LOCAL_HOSTNAME="Bryans-MacBook-Pro" \
        FUNCTIONS="$FUNCTIONS" \
        ALIASES="$ALIASES" \
        /bin/zsh -f -c 'source "$FUNCTIONS"; source "$ALIASES"; eval upgrade-studio' 2>&1
)"
status=$?

if [[ $status -eq 0 ]]; then
    echo "FAIL: upgrade-studio succeeded on the MacBook Pro" >&2
    exit 1
fi
if [[ -s "$COMMAND_LOG" ]]; then
    echo "FAIL: upgrade-studio changed the flake before checking the host" >&2
    cat "$COMMAND_LOG" >&2
    exit 1
fi
if [[ "$output" != *"MacBook Pro"* || "$output" != *"studio"* ]]; then
    echo "FAIL: upgrade mismatch did not identify the current machine and target" >&2
    printf '%s\n' "$output" >&2
    exit 1
fi

echo "ok   upgrade-studio checks the host before changing the flake"

: > "$COMMAND_LOG"
printf 'yes\n' | \
    HOME="$TMP_ROOT/home" \
    PATH="$TMP_ROOT/bin:/usr/bin:/bin" \
    COMMAND_LOG="$COMMAND_LOG" \
    STUB_LOCAL_HOSTNAME="Bryans-MacBook-Pro" \
    FUNCTIONS="$FUNCTIONS" \
    ALIASES="$ALIASES" \
    /bin/zsh -f -c 'source "$FUNCTIONS"; source "$ALIASES"; upgrade-mbp' \
    >/dev/null 2>&1
status=$?

expected=$(printf '%s\n%s' \
    "nix flake update --flake $TMP_ROOT/home/code/nix-configs" \
    "sudo darwin-rebuild switch --flake $TMP_ROOT/home/code/nix-configs/#mbp")
actual="$(<"$COMMAND_LOG")"
if [[ $status -ne 0 || "$actual" != "$expected" ]]; then
    echo "FAIL: confirmed upgrade-mbp did not update the flake before rebuilding" >&2
    echo "  want:" >&2
    printf '%s\n' "$expected" >&2
    echo "  got:" >&2
    printf '%s\n' "${actual:-<no command>}" >&2
    exit 1
fi

echo "ok   confirmed upgrade-mbp updates the flake before rebuilding"

while IFS='|' read -r target local_hostname rebuild; do
    : > "$COMMAND_LOG"
    printf 'y\n' | \
        HOME="$TMP_ROOT/home" \
        PATH="$TMP_ROOT/bin:/usr/bin:/bin" \
        COMMAND_LOG="$COMMAND_LOG" \
        STUB_LOCAL_HOSTNAME="$local_hostname" \
        FUNCTIONS="$FUNCTIONS" \
        ALIASES="$ALIASES" \
        TARGET="$target" \
        /bin/zsh -f -c 'source "$FUNCTIONS"; source "$ALIASES"; "update-$TARGET"' \
        >/dev/null 2>&1
    status=$?

    expected="sudo $rebuild switch --flake $TMP_ROOT/home/code/nix-configs/#$target"
    actual="$(<"$COMMAND_LOG")"
    if [[ $status -ne 0 || "$actual" != "$expected" ]]; then
        echo "FAIL: update-$target did not recognize $local_hostname" >&2
        echo "  want: $expected" >&2
        echo "  got:  ${actual:-<no command>}" >&2
        exit 1
    fi
done <<'EOF'
mbp|Bryans-MacBook-Pro|darwin-rebuild
a6mbp|A6-MacBook-Pro|darwin-rebuild
studio|Bryans-Mac-Studio|darwin-rebuild
gnarbox|gnarbox|nixos-rebuild
inix|inix|darwin-rebuild
EOF

echo "ok   every host command recognizes its own machine"
