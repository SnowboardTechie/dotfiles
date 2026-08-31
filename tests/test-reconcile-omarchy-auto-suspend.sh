#!/usr/bin/env bash
# Integration tests for scripts/reconcile-omarchy-auto-suspend.sh.
# All writes are isolated inside a temporary HOME tree.

set -u

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RECONCILER="$REPO_ROOT/scripts/reconcile-omarchy-auto-suspend.sh"
PLUGIN_ID="snowboardtechie.auto-suspend"
SOURCE="$REPO_ROOT/omarchy/plugins/$PLUGIN_ID"
TMP_ROOT="$(mktemp -d "${TMPDIR:-/tmp}/auto-suspend-test-XXXXXX")"
trap 'rm -rf "$TMP_ROOT"' EXIT

TESTS=0
FAILURES=0

check() {
    local desc="$1"; shift
    TESTS=$((TESTS + 1))
    if "$@"; then
        echo "ok   $desc"
    else
        echo "FAIL $desc"
        FAILURES=$((FAILURES + 1))
    fi
}

run_reconciler() {
    local home="$1"; shift
    HOME="$home" OMARCHY_AUTO_SUSPEND_SKIP_RELOAD=1 "$RECONCILER" "$@"
}

# --- Valid config: check is read-only, apply links and enables additively -------
H="$TMP_ROOT/home-valid"
mkdir -p "$H/.config/omarchy"
cat > "$H/.config/omarchy/shell.json" <<'JSON'
{
  "version": 1,
  "idle": {"screensaver": 150, "lock": 300},
  "bar": {"custom": "preserve-me"},
  "plugins": [{"id": "foreign.service", "setting": 7}]
}
JSON
chmod 600 "$H/.config/omarchy/shell.json"
before="$(sha256sum "$H/.config/omarchy/shell.json")"
out="$(run_reconciler "$H" --check 2>&1)"; rc=$?
check "check exits 0"                          test "$rc" -eq 0
check "check reports pending link"             bash -c 'grep -q "would link" <<<"$1"' _ "$out"
check "check reports pending enablement"       bash -c 'grep -q "would enable" <<<"$1"' _ "$out"
check "check does not mutate shell config"     test "$before" = "$(sha256sum "$H/.config/omarchy/shell.json")"
check "check does not create plugin link"      test ! -e "$H/.config/omarchy/plugins/$PLUGIN_ID"

original="$(cat "$H/.config/omarchy/shell.json")"
out="$(run_reconciler "$H" --apply 2>&1)"; rc=$?
check "apply exits 0"                          test "$rc" -eq 0
check "plugin target is a symlink"             test -L "$H/.config/omarchy/plugins/$PLUGIN_ID"
check "plugin link resolves to repo source"    test "$(realpath "$H/.config/omarchy/plugins/$PLUGIN_ID")" = "$(realpath "$SOURCE")"
check "service entry is enabled once"          test "$(jq --arg id "$PLUGIN_ID" '[.plugins[] | select(.id == $id)] | length' "$H/.config/omarchy/shell.json")" -eq 1
check "foreign plugin entry survives"          bash -c 'jq -e '\''.plugins[] | select(.id == "foreign.service" and .setting == 7)'\'' "$1" >/dev/null' _ "$H/.config/omarchy/shell.json"
check "unrelated shell config survives"        bash -c 'jq -e '\''.bar.custom == "preserve-me" and .idle.lock == 300'\'' "$1" >/dev/null' _ "$H/.config/omarchy/shell.json"
check "shell config mode is preserved"         test "$(stat -c %a "$H/.config/omarchy/shell.json")" = 600
check "pre-change backup is exact"             test "$original" = "$(cat "$H/.config/omarchy/shell.json.pre-auto-suspend")"

# --- Idempotence ----------------------------------------------------------------
snapshot="$(find "$H/.config/omarchy" -printf '%P %y %l %s\n' | sort; sha256sum "$H/.config/omarchy/shell.json"*)"
out="$(run_reconciler "$H" --apply 2>&1)"; rc=$?
check "second apply exits 0"                   test "$rc" -eq 0
check "second apply reports link and config ok" bash -c 'grep -q "ok: plugin link" <<<"$1" && grep -q "ok: service enabled" <<<"$1"' _ "$out"
check "second apply changes nothing"           test "$snapshot" = "$(find "$H/.config/omarchy" -printf '%P %y %l %s\n' | sort; sha256sum "$H/.config/omarchy/shell.json"*)"

# --- Foreign plugin collision: preserve it and do not enable our id -------------
H2="$TMP_ROOT/home-collision"
mkdir -p "$H2/.config/omarchy/plugins/$PLUGIN_ID"
printf 'foreign\n' > "$H2/.config/omarchy/plugins/$PLUGIN_ID/Service.qml"
printf '{"version":1,"plugins":[]}\n' > "$H2/.config/omarchy/shell.json"
before_config="$(cat "$H2/.config/omarchy/shell.json")"
out="$(run_reconciler "$H2" --apply 2>&1)"; rc=$?
check "collision apply exits 0"                test "$rc" -eq 0
check "collision is warned"                    bash -c 'grep -q "preserved foreign plugin path" <<<"$1"' _ "$out"
check "foreign plugin source survives"         grep -qxF foreign "$H2/.config/omarchy/plugins/$PLUGIN_ID/Service.qml"
check "collision does not enable plugin id"    test "$before_config" = "$(cat "$H2/.config/omarchy/shell.json")"

# --- Unsupported shell config: link is safe, config is preserved ----------------
H3="$TMP_ROOT/home-invalid"
mkdir -p "$H3/.config/omarchy"
printf '{"version":99,"plugins":[]}\n' > "$H3/.config/omarchy/shell.json"
before_config="$(cat "$H3/.config/omarchy/shell.json")"
out="$(run_reconciler "$H3" --apply 2>&1)"; rc=$?
check "unsupported config apply exits 0"       test "$rc" -eq 0
check "unsupported config is warned"           bash -c 'grep -q "invalid or unsupported" <<<"$1"' _ "$out"
check "unsupported config is unchanged"        test "$before_config" = "$(cat "$H3/.config/omarchy/shell.json")"
check "unsupported config still gets safe link" test -L "$H3/.config/omarchy/plugins/$PLUGIN_ID"

# --- Missing shell config: never synthesize Omarchy-owned configuration ---------
H4="$TMP_ROOT/home-missing"
mkdir -p "$H4"
out="$(run_reconciler "$H4" --apply 2>&1)"; rc=$?
check "missing config apply exits 0"            test "$rc" -eq 0
check "missing config is warned"                bash -c 'grep -q "does not exist" <<<"$1"' _ "$out"
check "missing shell config is not created"     test ! -e "$H4/.config/omarchy/shell.json"
check "missing config still gets plugin link"   test -L "$H4/.config/omarchy/plugins/$PLUGIN_ID"

# --- Argument handling and deployment registration ------------------------------
out="$(run_reconciler "$H4" 2>&1)"; rc=$?
check "no arguments fails"                     test "$rc" -ne 0
out="$(run_reconciler "$H4" --bogus 2>&1)"; rc=$?
check "unknown argument fails"                 test "$rc" -ne 0
check "setup-omarchy registers reconciler"     grep -qF 'reconcile-omarchy-auto-suspend.sh' "$REPO_ROOT/scripts/setup-omarchy.sh"
check "Omarchy payload is excluded from Stow"  grep -qxF '^/omarchy$' "$REPO_ROOT/.stow-local-ignore"

echo ""
echo "$TESTS tests, $FAILURES failures"
[[ $FAILURES -eq 0 ]]
