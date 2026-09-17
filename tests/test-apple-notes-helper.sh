#!/usr/bin/env bash
# Build/identity tests for the native "Apple Notes PKM Helper".
#
# These do NOT contact Notes.app (that needs a signed helper and a human TCC
# grant): notes.jxa rejects an unknown op before it resolves any Notes object,
# so the bad-op request below never sends an Apple Event or triggers a TCC
# prompt. They prove the buildable surface: the source compiles with notes.jxa
# embedded, the helper's stdin/argument contract fails closed, the reconciler
# refuses to install without a stable signing identity, and no binary or signing
# secret is committed.
set -u

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
HELPER_DIR="$REPO_ROOT/dot-agents/skills/apple-notes-pkm/helper"
JXA="$REPO_ROOT/dot-agents/skills/apple-notes-pkm/scripts/notes.jxa"
RECONCILER="$REPO_ROOT/scripts/reconcile-apple-notes-helper.sh"
TMP="$(mktemp -d "${TMPDIR:-/tmp}/apple-notes-helper-test.XXXXXX")"
trap 'rm -rf "$TMP"' EXIT

TESTS=0
FAILURES=0
check() {
    local desc="$1"; shift
    TESTS=$((TESTS + 1))
    if "$@"; then echo "ok   $desc"; else echo "FAIL $desc"; FAILURES=$((FAILURES + 1)); fi
}

if [[ "$(uname -s)" != "Darwin" ]]; then
    echo "SKIP: native helper build tests require macOS"
    exit 0
fi

# --- Build the helper (unsigned) so the compile + embed path is exercised ------
BIN="$TMP/apple-notes-pkm-helper"
if xcrun clang -fobjc-arc -O2 -framework Foundation -framework OSAKit \
        -Wl,-sectcreate,__TEXT,__notes_jxa,"$JXA" \
        -o "$BIN" "$HELPER_DIR/main.m" 2>"$TMP/build.log"; then
    echo "ok   helper compiles with notes.jxa embedded"
    TESTS=$((TESTS + 1))
else
    echo "FAIL helper compiles with notes.jxa embedded"; cat "$TMP/build.log"
    echo "1 failure(s)"; exit 1
fi

# The embedded program is present in the built Mach-O section.
check "notes.jxa is embedded in __TEXT,__notes_jxa" \
    bash -c 'otool -s __TEXT __notes_jxa "$1" | grep -q .' _ "$BIN"

# --- stdin / argument contract (no Notes contact) ------------------------------
# Arguments are rejected (the helper takes only stdin).
out="$(printf '' | "$BIN" some-arg 2>/dev/null)"; rc=$?
check "rejects command-line arguments (exit 2)" test "$rc" -eq 2
check "argument rejection is JSON ok:false" bash -c 'echo "$1" | grep -q "\"ok\":false"' _ "$out"

# Non-object stdin is rejected.
check "rejects non-JSON stdin (exit 2)" bash -c 'echo nope | "$1" >/dev/null 2>&1; test $? -eq 2' _ "$BIN"
check "rejects JSON array stdin (exit 2)" bash -c 'echo "[1]" | "$1" >/dev/null 2>&1; test $? -eq 2' _ "$BIN"
check "rejects empty stdin (exit 2)" bash -c '"$1" </dev/null >/dev/null 2>&1; test $? -eq 2' _ "$BIN"

# A well-formed request for a non-Notes op runs the embedded program end to end
# (JSON parse + dispatch) and returns its structured error without touching Notes.
out="$(echo '{"op":"nonsense"}' | "$BIN" 2>/dev/null)"; rc=$?
check "dispatches embedded program for a bad op (exit 0)" test "$rc" -eq 0
check "embedded program reports unknown op" bash -c 'echo "$1" | grep -q "unknown op: nonsense"' _ "$out"

# --- Entitlements: hardened runtime may send Apple Events only with this one ----
check "entitlements.plist is valid" plutil -lint -s "$HELPER_DIR/entitlements.plist"
check "entitlements grant only apple-events" bash -c '
    keys="$(plutil -convert json -o - "$1" | python3 -c "import json,sys;print(\"\\n\".join(sorted(json.load(sys.stdin))))")"
    [[ "$keys" == "com.apple.security.automation.apple-events" ]]' _ "$HELPER_DIR/entitlements.plist"
check "reconciler signs with the entitlements and verifies them" bash -c '
    grep -q -- "--entitlements \"\$ENTITLEMENTS\"" "$1" && grep -q "APPLE_EVENTS_ENTITLEMENT" "$1"' _ "$RECONCILER"

# --- Reconciler fails closed without a stable signing identity -----------------
FAKE_HOME="$TMP/home"; mkdir -p "$FAKE_HOME"
# Point the signing-identity file at a nonexistent location under the fake home.
out="$(HOME="$FAKE_HOME" APPLE_NOTES_HELPER_SIGNING_ID_FILE="$FAKE_HOME/.secrets/apple-notes-pkm/signing-identity" \
    "$RECONCILER" --apply 2>&1)"; rc=$?
check "reconciler --apply refuses without a signing identity (nonzero)" test "$rc" -ne 0
check "reconciler names the missing setup decision" bash -c 'echo "$1" | grep -q "no stable code-signing identity"' _ "$out"
check "reconciler installs nothing without identity" bash -c '! test -e "$1/Applications/Apple Notes PKM Helper.app"' _ "$FAKE_HOME"
check "reconciler never signs ad-hoc" bash -c '! echo "$1" | grep -qi "sign.*-.*ad-hoc\|--sign -"' _ "$out"

# --- No binary or signing secret is committed ----------------------------------
cd "$REPO_ROOT"
check "no compiled Mach-O tracked under the helper dir" bash -c '
    for f in $(git ls-files "dot-agents/skills/apple-notes-pkm/helper"); do
        [[ "$(file -b "$f")" == *"Mach-O"* ]] && { echo "tracked binary: $f"; exit 1; }
    done; exit 0'
check "no .p12/.key/.cer signing material tracked" bash -c '
    ! git ls-files "dot-agents/skills/apple-notes-pkm" | grep -qiE "\.(p12|key|cer|pem|pfx)$"'

echo ""
if [[ $FAILURES -eq 0 ]]; then
    echo "All $TESTS native-helper checks passed."
    exit 0
fi
echo "$FAILURES of $TESTS native-helper checks failed."
exit 1
