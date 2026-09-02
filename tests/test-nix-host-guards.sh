#!/usr/bin/env bash
# Integration tests for host-guarded Nix update and upgrade functions.

set -u

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FUNCTIONS="$REPO_ROOT/dot-config/zsh/functions.zsh"
ALIASES="$REPO_ROOT/dot-config/zsh/aliases.zsh"
TMP_ROOT="$(mktemp -d "${TMPDIR:-/tmp}/nix-host-guards-test-XXXXXX")"
trap 'rm -rf "$TMP_ROOT"' EXIT

mkdir -p "$TMP_ROOT/bin" "$TMP_ROOT/home/code/nix-configs/scripts"

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

cat > "$TMP_ROOT/home/code/nix-configs/scripts/update-hindsight-locks.py" <<'EOF'
#!/usr/bin/env bash
printf 'hindsight update\n' >> "$COMMAND_LOG"
exit "${HINDSIGHT_UPDATE_STATUS:-0}"
EOF

chmod +x "$TMP_ROOT/bin/scutil" "$TMP_ROOT/bin/sudo" "$TMP_ROOT/bin/nix" \
    "$TMP_ROOT/home/code/nix-configs/scripts/update-hindsight-locks.py"

COMMAND_LOG="$TMP_ROOT/commands.log"
: > "$COMMAND_LOG"

output="$(
    printf '\n' | \
        HOME="$TMP_ROOT/home" \
        PATH="$TMP_ROOT/bin:/usr/bin:/bin" \
        COMMAND_LOG="$COMMAND_LOG" \
        STUB_LOCAL_HOSTNAME="Bryans-Mac-Studio" \
        FUNCTIONS="$FUNCTIONS" \
        ALIASES="$ALIASES" \
        /bin/zsh -f -c 'source "$FUNCTIONS"; source "$ALIASES"; update-system' 2>&1
)"
status=$?

expected="sudo darwin-rebuild switch --flake $TMP_ROOT/home/code/nix-configs/#studio"
actual="$(<"$COMMAND_LOG")"
if [[ $status -ne 0 || "$actual" != "$expected" ]]; then
    echo "FAIL: update-system did not rebuild the detected Studio target" >&2
    echo "  want: $expected" >&2
    echo "  got:  ${actual:-<no command>}" >&2
    printf '%s\n' "$output" >&2
    exit 1
fi
if [[ "$output" != *"System: Mac Studio (studio)"* || \
      "$output" != *"Flake:  $TMP_ROOT/home/code/nix-configs#studio"* || \
      "$output" != *"Action: rebuild using the current flake inputs"* || \
      "$output" != *"Continue with update-system? [Y/n]"* ]]; then
    echo "FAIL: update-system did not preview the detected system, flake, and action" >&2
    printf '%s\n' "$output" >&2
    exit 1
fi

echo "ok   update-system previews and rebuilds the detected Studio target"

: > "$COMMAND_LOG"
output="$(
    printf 'y\n' | \
        HOME="$TMP_ROOT/home" \
        PATH="$TMP_ROOT/bin:/usr/bin:/bin" \
        COMMAND_LOG="$COMMAND_LOG" \
        STUB_LOCAL_HOSTNAME="mystery-host" \
        FUNCTIONS="$FUNCTIONS" \
        ALIASES="$ALIASES" \
        /bin/zsh -f -c 'source "$FUNCTIONS"; source "$ALIASES"; update-system' 2>&1
)"
status=$?

if [[ $status -eq 0 ]]; then
    echo "FAIL: update-system accepted an unknown hostname" >&2
    exit 1
fi
if [[ -s "$COMMAND_LOG" ]]; then
    echo "FAIL: update-system invoked a command for an unknown hostname" >&2
    cat "$COMMAND_LOG" >&2
    exit 1
fi
if [[ "$output" != *"Refusing update-system"* || "$output" != *"not a recognized nix-configs host"* ]]; then
    echo "FAIL: update-system did not explain the unknown-host refusal" >&2
    printf '%s\n' "$output" >&2
    exit 1
fi

echo "ok   update-system refuses an unknown hostname"

: > "$COMMAND_LOG"
output="$(
    printf 'yes\n' | \
        HOME="$TMP_ROOT/home" \
        PATH="$TMP_ROOT/bin:/usr/bin:/bin" \
        COMMAND_LOG="$COMMAND_LOG" \
        STUB_LOCAL_HOSTNAME="Bryans-MacBook-Pro" \
        FUNCTIONS="$FUNCTIONS" \
        ALIASES="$ALIASES" \
        /bin/zsh -f -c 'source "$FUNCTIONS"; source "$ALIASES"; upgrade-system' 2>&1
)"
status=$?

expected=$(printf '%s\n%s' \
    "nix flake update --flake $TMP_ROOT/home/code/nix-configs" \
    "sudo darwin-rebuild switch --flake $TMP_ROOT/home/code/nix-configs/#mbp")
actual="$(<"$COMMAND_LOG")"
if [[ $status -ne 0 || "$actual" != "$expected" ]]; then
    echo "FAIL: upgrade-system did not update the flake before rebuilding the detected target" >&2
    echo "  want:" >&2
    printf '%s\n' "$expected" >&2
    echo "  got:" >&2
    printf '%s\n' "${actual:-<no command>}" >&2
    printf '%s\n' "$output" >&2
    exit 1
fi
if [[ "$output" != *"System: MacBook Pro (mbp)"* || \
      "$output" != *"Flake:  $TMP_ROOT/home/code/nix-configs#mbp"* || \
      "$output" != *"Action: update flake inputs, then rebuild"* || \
      "$output" != *"Continue with upgrade-system? [Y/n]"* ]]; then
    echo "FAIL: upgrade-system did not preview the detected system, flake, and action" >&2
    printf '%s\n' "$output" >&2
    exit 1
fi

echo "ok   upgrade-system previews, upgrades, and rebuilds the detected target"

: > "$COMMAND_LOG"
output="$(
    printf 'yes\n' | \
        HOME="$TMP_ROOT/home" \
        PATH="$TMP_ROOT/bin:/usr/bin:/bin" \
        COMMAND_LOG="$COMMAND_LOG" \
        STUB_LOCAL_HOSTNAME="Bryans-Mac-Studio" \
        FUNCTIONS="$FUNCTIONS" \
        ALIASES="$ALIASES" \
        /bin/zsh -f -c 'source "$FUNCTIONS"; source "$ALIASES"; upgrade-system' 2>&1
)"
status=$?

expected=$(printf '%s\n%s\n%s' \
    "nix flake update --flake $TMP_ROOT/home/code/nix-configs" \
    "hindsight update" \
    "sudo darwin-rebuild switch --flake $TMP_ROOT/home/code/nix-configs/#studio")
actual="$(<"$COMMAND_LOG")"
if [[ $status -ne 0 || "$actual" != "$expected" ]]; then
    echo "FAIL: Studio upgrade-system did not update Hindsight between flake refresh and rebuild" >&2
    echo "  want:" >&2
    printf '%s\n' "$expected" >&2
    echo "  got:" >&2
    printf '%s\n' "${actual:-<no command>}" >&2
    printf '%s\n' "$output" >&2
    exit 1
fi
if [[ "$output" != *"Action: update flake inputs and Hindsight, then rebuild"* ]]; then
    echo "FAIL: Studio upgrade-system preview did not include Hindsight" >&2
    printf '%s\n' "$output" >&2
    exit 1
fi

echo "ok   Studio upgrade-system refreshes coordinated Hindsight locks"

: > "$COMMAND_LOG"
printf 'yes\n' | \
    HOME="$TMP_ROOT/home" \
    PATH="$TMP_ROOT/bin:/usr/bin:/bin" \
    COMMAND_LOG="$COMMAND_LOG" \
    STUB_LOCAL_HOSTNAME="Bryans-Mac-Studio" \
    HINDSIGHT_UPDATE_STATUS=9 \
    FUNCTIONS="$FUNCTIONS" \
    ALIASES="$ALIASES" \
    /bin/zsh -f -c 'source "$FUNCTIONS"; source "$ALIASES"; upgrade-system' \
    >/dev/null 2>&1
status=$?

actual="$(<"$COMMAND_LOG")"
if [[ $status -eq 0 || "$actual" == *"sudo darwin-rebuild"* ]]; then
    echo "FAIL: Studio upgrade-system rebuilt after the Hindsight lock refresh failed" >&2
    printf '%s\n' "${actual:-<no command>}" >&2
    exit 1
fi

echo "ok   Studio upgrade-system stops before rebuild when Hindsight refresh fails"

output="$(
    FUNCTIONS="$FUNCTIONS" /bin/zsh -f -c '
        source "$FUNCTIONS"
        for command_name in \
            update-mbp update-a6mbp update-studio update-gnarbox update-inix \
            upgrade-mbp upgrade-a6mbp upgrade-studio upgrade-gnarbox upgrade-inix; do
          if (( $+functions[$command_name] )); then
            print -r -- "$command_name"
          fi
        done
    '
)"

if [[ -n "$output" ]]; then
    echo "FAIL: legacy per-host commands are still defined:" >&2
    printf '%s\n' "$output" >&2
    exit 1
fi

echo "ok   legacy per-host commands are removed"

: > "$COMMAND_LOG"
output="$(
    HOME="$TMP_ROOT/home" \
        PATH="$TMP_ROOT/bin:/usr/bin:/bin" \
        COMMAND_LOG="$COMMAND_LOG" \
        STUB_LOCAL_HOSTNAME="Bryans-MacBook-Pro" \
        FUNCTIONS="$FUNCTIONS" \
        ALIASES="$ALIASES" \
        /bin/zsh -f -c 'source "$FUNCTIONS"; source "$ALIASES"; upgrade-system' \
        </dev/null 2>&1
)"
status=$?

if [[ $status -eq 0 ]]; then
    echo "FAIL: upgrade-system proceeded without confirmation" >&2
    exit 1
fi
if [[ -s "$COMMAND_LOG" ]]; then
    echo "FAIL: upgrade-system changed the flake without confirmation" >&2
    cat "$COMMAND_LOG" >&2
    exit 1
fi
if [[ "$output" != *"Continue with upgrade-system? [Y/n]"* || "$output" != *"Cancelled."* ]]; then
    echo "FAIL: upgrade-system did not show the preview before cancelling" >&2
    printf '%s\n' "$output" >&2
    exit 1
fi

echo "ok   upgrade-system cancels before mutation when no answer is available"

while IFS='|' read -r target local_hostname rebuild; do
    : > "$COMMAND_LOG"
    printf 'y\n' | \
        HOME="$TMP_ROOT/home" \
        PATH="$TMP_ROOT/bin:/usr/bin:/bin" \
        COMMAND_LOG="$COMMAND_LOG" \
        STUB_LOCAL_HOSTNAME="$local_hostname" \
        FUNCTIONS="$FUNCTIONS" \
        ALIASES="$ALIASES" \
        /bin/zsh -f -c 'source "$FUNCTIONS"; source "$ALIASES"; update-system' \
        >/dev/null 2>&1
    status=$?

    expected="sudo $rebuild switch --flake $TMP_ROOT/home/code/nix-configs/#$target"
    actual="$(<"$COMMAND_LOG")"
    if [[ $status -ne 0 || "$actual" != "$expected" ]]; then
        echo "FAIL: update-system did not map $local_hostname to $target" >&2
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

echo "ok   update-system maps every recognized machine to its own flake target"
