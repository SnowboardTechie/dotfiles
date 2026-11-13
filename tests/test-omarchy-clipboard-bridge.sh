#!/usr/bin/env bash
# Tests for omarchy/clipboard-bridge/clipboard-bridge.sh (the part that decides
# what leaves this machine) and scripts/reconcile-omarchy-clipboard-bridge.sh.
# Everything runs in temporary directories with stub wl-paste and systemctl;
# no clipboard, network, or systemd is touched.

set -u

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BRIDGE="$REPO_ROOT/omarchy/clipboard-bridge/clipboard-bridge.sh"
RECONCILER="$REPO_ROOT/scripts/reconcile-omarchy-clipboard-bridge.sh"

TESTS=0
FAILURES=0
TMP="$(mktemp -d "${TMPDIR:-/tmp}/clipboard-bridge-test-XXXXXX")"
trap 'rm -rf "$TMP"' EXIT

check() { # <description> <command...>
    local desc="$1"; shift
    TESTS=$((TESTS + 1))
    if "$@"; then
        echo "ok   $desc"
    else
        echo "FAIL $desc"
        FAILURES=$((FAILURES + 1))
    fi
}

# --- Stubs ---------------------------------------------------------------------
BIN="$TMP/bin"
mkdir -p "$BIN"
cat > "$BIN/wl-paste" <<'EOF'
#!/usr/bin/env bash
# Only --list-types is used by the code under test.
cat "$STUB_TYPES_FILE" 2>/dev/null
EOF
cat > "$BIN/wl-copy" <<'EOF'
#!/usr/bin/env bash
exit 0
EOF
cat > "$BIN/systemctl" <<'EOF'
#!/usr/bin/env bash
echo "$*" >> "$STUB_SYSTEMCTL_LOG"
case "$*" in
    *is-enabled*|*is-active*) [[ -e "$STUB_SYSTEMCTL_LOG.enabled" ]] ;;
    *"enable --now"*) touch "$STUB_SYSTEMCTL_LOG.enabled" ;;
esac
EOF
chmod +x "$BIN"/*

# --- What leaves this machine --------------------------------------------------
RUN="$TMP/run"
mkdir -p "$RUN"
export STUB_TYPES_FILE="$TMP/types"
printf 'text/plain\n' > "$STUB_TYPES_FILE"

encode() { # stdin: copied text; extra env as arguments
    env PATH="$BIN:$PATH" XDG_RUNTIME_DIR="$RUN" "$@" "$BRIDGE" _encode
}

out="$(printf 'hello ✓' | encode)"
check "plain text is sent as one base64 line"  test "$(printf %s "$out" | base64 -d)" = "hello ✓"
check "the line count is one"                  test "$(printf '%s\n' "$out" | wc -l)" -eq 1

out="$(printf 'hello ✓' | encode)"
check "the same entry is not sent twice"       test -z "$out"

out="$(printf 'line one\nline two\n' | encode)"
check "newlines survive"                       test "$(printf %s "$out" | base64 -d | wc -l)" -eq 2

out="$(printf 'secret' | encode CLIPBOARD_STATE=sensitive)"
check "a sensitive entry is not sent"          test -z "$out"

printf 'text/plain\nx-kde-passwordManagerHint\n' > "$STUB_TYPES_FILE"
out="$(printf 'secret two' | encode)"
check "a password-manager entry is not sent"   test -z "$out"
printf 'text/plain\n' > "$STUB_TYPES_FILE"

out="$(head -c 999999 /dev/zero | tr '\0' 'a' | encode)"
check "an entry at the size cap is sent"       test -n "$out"
out="$(head -c 1000000 /dev/zero | tr '\0' 'b' | encode)"
check "an entry over the size cap is not sent" test -z "$out"

out="$(printf '' | encode)"
check "an empty entry is not sent"             test -z "$out"

# --- Reconciler ----------------------------------------------------------------
reconcile() { # <home> <mode>
    env HOME="$1" PATH="$BIN:$PATH" \
        CLIPBOARD_BRIDGE_SYSTEMCTL="$BIN/systemctl" \
        STUB_SYSTEMCTL_LOG="$1/systemctl.log" \
        "$RECONCILER" "$2" 2>&1
}
UNIT_REL=".config/systemd/user/clipboard-bridge.service"

H="$TMP/home-none"; mkdir -p "$H"
out="$(reconcile "$H" --apply)"; rc=$?
check "no Mac configured: apply exits 0"       test "$rc" -eq 0
check "no Mac configured: says how to turn on" bash -c 'grep -q "no Mac configured" <<<"$1"' _ "$out"
check "no Mac configured: no unit written"     test ! -e "$H/$UNIT_REL"
check "no Mac configured: systemctl not run"   test ! -e "$H/systemctl.log"

H2="$TMP/home-host"; mkdir -p "$H2/.config/clipboard-bridge"
echo "some-mac" > "$H2/.config/clipboard-bridge/host"
out="$(reconcile "$H2" --check)"; rc=$?
check "check exits 0"                          test "$rc" -eq 0
check "check reports the unit to write"        bash -c 'grep -q "would write" <<<"$1"' _ "$out"
check "check writes nothing"                   test ! -e "$H2/$UNIT_REL"
check "check does not change systemd"          bash -c '! grep -q -E "enable --now|daemon-reload|try-restart" "$1" 2>/dev/null' _ "$H2/systemctl.log"

out="$(reconcile "$H2" --apply)"; rc=$?
check "apply exits 0"                          test "$rc" -eq 0
check "apply writes the unit"                  test -f "$H2/$UNIT_REL"
check "the unit runs the repository script"    grep -qxF "ExecStart=$BRIDGE" "$H2/$UNIT_REL"
check "the unit does not name the Mac"         bash -c '! grep -q "some-mac" "$1"' _ "$H2/$UNIT_REL"
check "apply enables and starts the service"   grep -q "enable --now clipboard-bridge.service" "$H2/systemctl.log"

snap="$(cat "$H2/$UNIT_REL")"
: > "$H2/systemctl.log"
out="$(reconcile "$H2" --apply)"; rc=$?
check "second apply exits 0"                   test "$rc" -eq 0
check "second apply reports everything ok"     bash -c 'grep -q "0 changed, 2 ok" <<<"$1"' _ "$out"
check "second apply leaves the unit alone"     test "$snap" = "$(cat "$H2/$UNIT_REL")"
check "second apply does not restart"          bash -c '! grep -q -E "enable --now|try-restart|daemon-reload" "$1"' _ "$H2/systemctl.log"

H3="$TMP/home-foreign"; mkdir -p "$H3/.config/clipboard-bridge" "$H3/.config/systemd/user"
echo "some-mac" > "$H3/.config/clipboard-bridge/host"
printf '[Service]\nExecStart=/bin/true\n' > "$H3/$UNIT_REL"
before="$(cat "$H3/$UNIT_REL")"
out="$(reconcile "$H3" --apply)"; rc=$?
check "foreign unit: apply exits 0"            test "$rc" -eq 0
check "foreign unit: warned"                   bash -c 'grep -q "not managed by this script" <<<"$1"' _ "$out"
check "foreign unit: left untouched"           test "$before" = "$(cat "$H3/$UNIT_REL")"

out="$(reconcile "$H2" --bogus)"; rc=$?
check "an unknown flag exits 2"                test "$rc" -eq 2

echo
echo "$TESTS tests, $FAILURES failures"
[[ $FAILURES -eq 0 ]]
