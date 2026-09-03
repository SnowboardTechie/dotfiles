#!/usr/bin/env bash
# Integration tests for scripts/reconcile-herdr-omarchy.sh.
# All writes are isolated inside temporary HOME directories, removed on exit.

set -u

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RECONCILER="$REPO_ROOT/scripts/reconcile-herdr-omarchy.sh"
TEMPLATE="$REPO_ROOT/dot-config/herdr/config-omarchy.toml"
MODULES=(claude-usage.sh codex-usage.py openrouter-spend.py host-label.sh)

TESTS=0
FAILURES=0
TMP_HOMES=()

cleanup() {
    local h
    for h in "${TMP_HOMES[@]-}"; do
        [[ -n "$h" ]] || continue
        rm -rf "$h"
    done
}
trap cleanup EXIT

new_home() {
    local h
    h="$(mktemp -d "${TMPDIR:-/tmp}/herdr-omarchy-test-home-XXXXXX")"
    TMP_HOMES+=("$h")
    echo "$h"
}

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

# --- Stock Omarchy config: check is read-only, apply backs up and manages -------
H="$(new_home)"
mkdir -p "$H/.config/herdr"
printf '%s\n' 'onboarding = false' '[ui]' 'tab_bar_right = [{ type = "zoom" }, { type = "hostname" }]' > "$H/.config/herdr/config.toml"
before="$(cat "$H/.config/herdr/config.toml")"
out="$(HOME="$H" "$RECONCILER" --check 2>&1)"; rc=$?
check "stock check exits 0"                    test "$rc" -eq 0
check "stock check reports config replacement" bash -c 'grep -q "would manage: config.toml" <<<"$1"' _ "$out"
check "stock check reports module links"       bash -c 'grep -q "would link: host-label.sh" <<<"$1"' _ "$out"
check "stock check does not mutate config"     test "$before" = "$(cat "$H/.config/herdr/config.toml")"

out="$(HOME="$H" "$RECONCILER" --apply 2>&1)"; rc=$?
check "stock apply exits 0"                    test "$rc" -eq 0
check "config becomes template symlink"        test -L "$H/.config/herdr/config.toml"
check "config resolves to Omarchy template"    test "$(realpath "$H/.config/herdr/config.toml")" = "$(realpath "$TEMPLATE")"
check "stock config backup is preserved"       test "$(cat "$H/.config/herdr/config.toml.omarchy-backup")" = "$before"
for module in "${MODULES[@]}"; do
    check "$module is linked" test -L "$H/.config/herdr/$module"
done

# --- Idempotence ----------------------------------------------------------------
snap="$(find "$H/.config/herdr" -maxdepth 1 -print0 | xargs -0 stat -f '%N %Y' 2>/dev/null || find "$H/.config/herdr" -maxdepth 1 -printf '%p %l\n')"
out="$(HOME="$H" "$RECONCILER" --apply 2>&1)"; rc=$?
check "second apply exits 0"                  test "$rc" -eq 0
check "second apply reports managed config"   bash -c 'grep -q "ok: config.toml" <<<"$1"' _ "$out"
check "second apply changes nothing"          test "$snap" = "$(find "$H/.config/herdr" -maxdepth 1 -print0 | xargs -0 stat -f '%N %Y' 2>/dev/null || find "$H/.config/herdr" -maxdepth 1 -printf '%p %l\n')"

# --- Unknown config and foreign module are preserved ----------------------------
H2="$(new_home)"
mkdir -p "$H2/.config/herdr"
printf '%s\n' '[ui]' 'tab_bar_right = [{ type = "text", text = "custom" }]' > "$H2/.config/herdr/config.toml"
printf '# foreign module\n' > "$H2/.config/herdr/host-label.sh"
before_config="$(cat "$H2/.config/herdr/config.toml")"
before_module="$(cat "$H2/.config/herdr/host-label.sh")"
out="$(HOME="$H2" "$RECONCILER" --apply 2>&1)"; rc=$?
check "collision apply exits 0"               test "$rc" -eq 0
check "custom config is warned"               bash -c 'grep -q "preserved custom config" <<<"$1"' _ "$out"
check "custom config is unchanged"            test "$before_config" = "$(cat "$H2/.config/herdr/config.toml")"
check "foreign module is unchanged"           test "$before_module" = "$(cat "$H2/.config/herdr/host-label.sh")"
check "non-colliding module is linked"         test -L "$H2/.config/herdr/claude-usage.sh"

# --- Argument handling ----------------------------------------------------------
H3="$(new_home)"
out="$(HOME="$H3" "$RECONCILER" 2>&1)"; rc=$?
check "no arguments fails"                    test "$rc" -ne 0
out="$(HOME="$H3" "$RECONCILER" --bogus 2>&1)"; rc=$?
check "unknown argument fails"                test "$rc" -ne 0
check "failed invocations create nothing"     test ! -e "$H3/.config/herdr"

echo ""
echo "$TESTS tests, $FAILURES failures"
[[ $FAILURES -eq 0 ]]
