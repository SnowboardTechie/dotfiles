#!/usr/bin/env bash
# reconcile-apple-notes-helper.sh — build, sign, and install the native
# "Apple Notes PKM Helper", the one process allowed to send Apple Events to
# Notes on behalf of the apple-notes-pkm skill.
#
# Why a native helper: macOS attributes an Apple Events (Automation) TCC grant
# to a process's *responsible* process. A Python interpreter under Herdr/Hermes
# is not a stable identity, so a grant there dies on the next runtime upgrade
# (the stale python3.11 rows). This helper disclaims responsibility for itself
# and carries a stable code signature, so the grant belongs to one named app.
#
# Hard signing gate: the helper is installed ONLY if it can be signed with a
# stable code-signing identity whose Common Name matches the repository-owned
# expected identity (helper/identity.json). If no such identity exists this
# script stops and reports the exact missing user-owned setup decision. It never
# falls back to an ad-hoc signature, whose cdhash changes every rebuild and would
# recreate the dead-TCC-row problem.
#
# macOS only. Notes.app does not exist elsewhere; on other platforms this is a
# no-op that reports "skipped".
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
HELPER_SRC_DIR="$REPO_ROOT/dot-agents/skills/apple-notes-pkm/helper"
JXA_PROGRAM="$REPO_ROOT/dot-agents/skills/apple-notes-pkm/scripts/notes.jxa"
IDENTITY_JSON="$HELPER_SRC_DIR/identity.json"

# Where the setup decision records which keychain identity to sign with. The
# file holds only a certificate Common Name (not a secret); absent means the
# decision has not been made.
SIGNING_ID_FILE="${APPLE_NOTES_HELPER_SIGNING_ID_FILE:-$HOME/.secrets/apple-notes-pkm/signing-identity}"

GREEN=$'\033[0;32m'; YELLOW=$'\033[1;33m'; RED=$'\033[0;31m'; BOLD=$'\033[1m'; NC=$'\033[0m'

usage() {
    cat <<'EOF'
Usage: reconcile-apple-notes-helper.sh (--check | --apply)

  --check   Report toolchain, expected identity, signing-identity availability,
            and whether the installed helper matches. Never mutates anything.
  --apply   Build, sign, and install the helper to ~/Applications, then verify.
            Requires a stable code-signing identity; stops if none is available.

The signing identity is read from a Common Name in:
  $HOME/.secrets/apple-notes-pkm/signing-identity   (override: APPLE_NOTES_HELPER_SIGNING_ID_FILE)
It must name a code-signing identity present in the login keychain
(`security find-identity -v -p codesigning`).
EOF
}

MODE=""
case "${1:-}" in
    --check) MODE="check" ;;
    --apply) MODE="apply" ;;
    -h|--help) usage; exit 0 ;;
    *) usage >&2; exit 2 ;;
esac

if [[ "$(uname -s)" != "Darwin" ]]; then
    echo "Apple Notes helper reconcile ($MODE): skipped (macOS only)"
    exit 0
fi

echo "Apple Notes helper reconcile ($MODE)"

# --- Expected identity ------------------------------------------------------
read_json() { /usr/bin/python3 -c 'import json,sys;print(json.load(open(sys.argv[1])).get(sys.argv[2],""))' "$1" "$2"; }
BUNDLE_ID="$(read_json "$IDENTITY_JSON" bundle_id)"
HELPER_NAME="$(read_json "$IDENTITY_JSON" name)"
EXECUTABLE="$(read_json "$IDENTITY_JSON" executable)"
EXPECT_CN="$(read_json "$IDENTITY_JSON" signing_common_name)"
APP_PATH_RAW="$(read_json "$IDENTITY_JSON" app_path)"
APP_PATH="${APP_PATH_RAW/#\~/$HOME}"
MACOS_DIR="$APP_PATH/Contents/MacOS"
INSTALLED_BIN="$MACOS_DIR/$EXECUTABLE"

echo "  expected: $HELPER_NAME ($BUNDLE_ID), signed by CN=$EXPECT_CN"
echo "  install path: $APP_PATH"

issues=0

# --- Toolchain --------------------------------------------------------------
if ! xcrun --find clang >/dev/null 2>&1; then
    echo "  ${RED}ERROR${NC}: no clang toolchain (install Xcode or the Command Line Tools)"
    exit 1
fi
[[ -f "$JXA_PROGRAM" ]] || { echo "  ${RED}ERROR${NC}: embedded program missing: $JXA_PROGRAM"; exit 1; }

# --- Signing identity resolution (metadata only) ----------------------------
# Prints the resolved CN on success, empty on failure. Never prints key material.
resolve_signing_identity() {
    local cn=""
    if [[ -f "$SIGNING_ID_FILE" ]]; then
        cn="$(tr -d '\r\n' < "$SIGNING_ID_FILE")"
    fi
    [[ -n "$cn" ]] || return 1
    # The named identity must actually be a valid code-signing identity.
    security find-identity -v -p codesigning 2>/dev/null | grep -Fq "$cn" || return 1
    printf '%s' "$cn"
}

SIGNING_CN=""
if SIGNING_CN="$(resolve_signing_identity)"; then
    echo "  ${GREEN}signing identity available${NC}: $SIGNING_CN"
    if [[ "$SIGNING_CN" != "$EXPECT_CN" ]]; then
        echo "  ${YELLOW}WARNING${NC}: configured identity CN ($SIGNING_CN) != expected ($EXPECT_CN);"
        echo "           installed helper would not match apple-notes-pkm.py's expected identity"
        issues=$((issues + 1))
    fi
else
    echo "  ${RED}no stable code-signing identity is available${NC}"
    echo "  Required user-owned setup decision (not automated, not done on your behalf):"
    echo "    1. Create ONE self-signed code-signing certificate whose Common Name is"
    echo "       exactly: $EXPECT_CN"
    echo "       (Keychain Access > Certificate Assistant > Create a Certificate,"
    echo "        Identity Type: Self Signed Root, Certificate Type: Code Signing),"
    echo "       or provide a Developer ID Application identity."
    echo "    2. Record its Common Name in: $SIGNING_ID_FILE (mode 0600)."
    echo "  Then re-run with --apply. This script will not sign ad-hoc."
    SIGNING_CN=""
fi

# --- Report installed state -------------------------------------------------
report_installed() {
    if [[ ! -f "$INSTALLED_BIN" ]]; then
        echo "  installed: no"
        return
    fi
    local info identifier authority verify_rc
    info="$(codesign -dv --verbose=4 "$INSTALLED_BIN" 2>&1 || true)"
    identifier="$(printf '%s\n' "$info" | sed -n 's/^Identifier=//p' | head -1)"
    authority="$(printf '%s\n' "$info" | sed -n 's/^Authority=//p' | head -1)"
    if codesign --verify --deep --strict "$APP_PATH" >/dev/null 2>&1; then verify_rc="valid"; else verify_rc="INVALID"; fi
    echo "  installed: yes (identifier=$identifier, authority=$authority, signature=$verify_rc)"
    if [[ "$identifier" != "$BUNDLE_ID" ]]; then
        echo "  ${YELLOW}WARNING${NC}: installed bundle id ($identifier) != expected ($BUNDLE_ID)"
        issues=$((issues + 1))
    fi
    if [[ -n "$EXPECT_CN" && "$authority" != *"$EXPECT_CN"* ]]; then
        echo "  ${YELLOW}WARNING${NC}: installed signing authority ($authority) does not include $EXPECT_CN"
        issues=$((issues + 1))
    fi
}
report_installed

if [[ "$MODE" == "check" ]]; then
    if [[ $issues -gt 0 ]]; then
        echo "${YELLOW}Apple Notes helper: $issues issue(s) to resolve.${NC}"
        exit 1
    fi
    echo "${GREEN}Apple Notes helper: check complete.${NC}"
    exit 0
fi

# --- Apply: build, sign, install, verify ------------------------------------
if [[ -z "$SIGNING_CN" ]]; then
    echo "${RED}Stopping: no stable code-signing identity. Nothing built or installed.${NC}" >&2
    exit 1
fi

BUILD_DIR="$(mktemp -d "${TMPDIR:-/tmp}/apple-notes-helper-build.XXXXXX")"
trap 'rm -rf "$BUILD_DIR"' EXIT
STAGE_APP="$BUILD_DIR/$(basename "$APP_PATH")"
mkdir -p "$STAGE_APP/Contents/MacOS"
cp "$HELPER_SRC_DIR/Info.plist" "$STAGE_APP/Contents/Info.plist"

echo "  compiling $EXECUTABLE (embedding notes.jxa)"
xcrun clang -fobjc-arc -O2 -Wall -Wextra \
    -framework Foundation -framework OSAKit \
    -Wl,-sectcreate,__TEXT,__notes_jxa,"$JXA_PROGRAM" \
    -o "$STAGE_APP/Contents/MacOS/$EXECUTABLE" \
    "$HELPER_SRC_DIR/main.m"

echo "  signing with $SIGNING_CN"
codesign --force --sign "$SIGNING_CN" --identifier "$BUNDLE_ID" \
    --options runtime --timestamp=none "$STAGE_APP"

echo "  verifying staged signature"
codesign --verify --deep --strict --verbose=2 "$STAGE_APP"
staged_info="$(codesign -dv --verbose=4 "$STAGE_APP/Contents/MacOS/$EXECUTABLE" 2>&1)"
staged_id="$(printf '%s\n' "$staged_info" | sed -n 's/^Identifier=//p' | head -1)"
staged_auth="$(printf '%s\n' "$staged_info" | sed -n 's/^Authority=//p' | head -1)"
[[ "$staged_id" == "$BUNDLE_ID" ]] || { echo "${RED}ERROR${NC}: staged bundle id $staged_id != $BUNDLE_ID" >&2; exit 1; }
[[ "$staged_auth" == *"$EXPECT_CN"* ]] || { echo "${RED}ERROR${NC}: staged authority $staged_auth lacks $EXPECT_CN" >&2; exit 1; }

echo "  installing to $APP_PATH"
mkdir -p "$(dirname "$APP_PATH")"
rm -rf "$APP_PATH"
mv "$STAGE_APP" "$APP_PATH"

echo "${GREEN}Installed $HELPER_NAME.${NC}"
echo "  ${BOLD}Next (human action):${NC} the first run will prompt for Notes Automation."
echo "  Approve “$HELPER_NAME” in System Settings > Privacy & Security > Automation."
echo "  Verify identity: codesign -dv --verbose=4 \"$INSTALLED_BIN\""
exit 0
