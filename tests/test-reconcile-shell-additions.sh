#!/usr/bin/env bash
# Integration tests for scripts/reconcile-shell-additions.sh.
# All writes are isolated inside temporary HOME directories, removed on exit.

set -u

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RECONCILER="$REPO_ROOT/scripts/reconcile-shell-additions.sh"
ALIASES_SRC="$REPO_ROOT/dot-config/shell/aliases.sh"

TESTS=0
FAILURES=0
TMP_HOMES=()

cleanup() {
    local h
    for h in "${TMP_HOMES[@]}"; do
        rm -rf "$h"
    done
}
trap cleanup EXIT

new_home() {
    local h
    h="$(mktemp -d "${TMPDIR:-/tmp}/shell-add-test-home-XXXXXX")"
    TMP_HOMES+=("$h")
    echo "$h"
}

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

count_refs() { grep -cF "dot-config/shell/aliases.sh" "$1" 2>/dev/null || true; }

# --- No ~/.bashrc: never created ----------------------------------------------
H="$(new_home)"
out="$(HOME="$H" "$RECONCILER" --apply 2>&1)"; rc=$?
check "missing bashrc: apply exits 0"          test "$rc" -eq 0
check "missing bashrc: warns and skips"        bash -c 'grep -q "does not exist" <<<"$1"' _ "$out"
check "missing bashrc: file is not created"    test ! -e "$H/.bashrc"

# --- Existing bashrc: check reports, apply appends once ------------------------
H2="$(new_home)"
printf '# my bashrc\nexport FOO=bar\n' > "$H2/.bashrc"
before="$(cat "$H2/.bashrc")"
out="$(HOME="$H2" "$RECONCILER" --check 2>&1)"; rc=$?
check "check exits 0"                          test "$rc" -eq 0
check "check reports the pending append"       bash -c 'grep -q "would append" <<<"$1"' _ "$out"
check "check does not mutate bashrc"           test "$before" = "$(cat "$H2/.bashrc")"

out="$(HOME="$H2" "$RECONCILER" --apply 2>&1)"; rc=$?
check "apply exits 0"                          test "$rc" -eq 0
check "apply appends the source line"          bash -c 'grep -qxF "$2" "$1/.bashrc"' _ "$H2" "[[ -f \"$ALIASES_SRC\" ]] && source \"$ALIASES_SRC\""
check "apply keeps prior content"              bash -c 'grep -q "export FOO=bar" "$1/.bashrc"' _ "$H2"
check "apply adds the managed marker"          bash -c 'grep -qF "managed by scripts/reconcile-shell-additions.sh" "$1/.bashrc"' _ "$H2"

# --- Idempotence ---------------------------------------------------------------
snap="$(cat "$H2/.bashrc")"
out="$(HOME="$H2" "$RECONCILER" --apply 2>&1)"; rc=$?
check "second apply exits 0"                   test "$rc" -eq 0
check "second apply reports ok"                bash -c 'grep -q "already present" <<<"$1"' _ "$out"
check "second apply changes nothing"           test "$snap" = "$(cat "$H2/.bashrc")"
check "exactly one reference to aliases file"  test "$(count_refs "$H2/.bashrc")" -eq 1

# --- Foreign reference is preserved, not duplicated ----------------------------
H3="$(new_home)"
printf 'source /somewhere/else/dot-config/shell/aliases.sh\n' > "$H3/.bashrc"
before="$(cat "$H3/.bashrc")"
out="$(HOME="$H3" "$RECONCILER" --apply 2>&1)"; rc=$?
check "foreign reference: apply exits 0"       test "$rc" -eq 0
check "foreign reference: warned"              bash -c 'grep -q "unexpected line" <<<"$1"' _ "$out"
check "foreign reference: bashrc untouched"    test "$before" = "$(cat "$H3/.bashrc")"

# --- The shared aliases file actually sources cleanly in bash ------------------
out="$(bash --noprofile --norc -c "set -e; shopt -s expand_aliases; source '$ALIASES_SRC'; alias gs; alias herder-imachy; type grb >/dev/null" 2>&1)"; rc=$?
check "aliases.sh sources cleanly in bash"     test "$rc" -eq 0
check "aliases.sh defines gs and grb"          bash -c 'grep -q "git status" <<<"$1"' _ "$out"
check "aliases.sh defines herder-imachy"       bash -c 'grep -q "herdr --remote bryan@imachy" <<<"$1"' _ "$out"

# --- Argument handling ----------------------------------------------------------
H4="$(new_home)"
printf '# rc\n' > "$H4/.bashrc"
out="$(HOME="$H4" "$RECONCILER" 2>&1)"; rc=$?
check "no arguments fails"                     test "$rc" -ne 0
out="$(HOME="$H4" "$RECONCILER" --bogus 2>&1)"; rc=$?
check "unknown argument fails"                 test "$rc" -ne 0
check "failed invocations did not mutate"      test "$(cat "$H4/.bashrc")" = "# rc"

echo ""
echo "$TESTS tests, $FAILURES failures"
if [[ $FAILURES -gt 0 ]]; then
    exit 1
fi
