#!/usr/bin/env bash
# Integration tests for scripts/reconcile-agent-skills.sh.
#
# Runs the reconciler against temporary HOME directories; the real checked-out
# skill pool is used read-only as the source. All writes are isolated inside
# the temporary homes, which are removed on exit.

set -u

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RECONCILER="$REPO_ROOT/scripts/reconcile-agent-skills.sh"
POOL="$(cd "$REPO_ROOT/dot-agents/skills" && pwd)"

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
    h="$(mktemp -d "${TMPDIR:-/tmp}/skills-test-home-XXXXXX")"
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

links_into_pool() { # count symlinks in <dir> that resolve into the pool
    local dir="$1" count=0 entry tgt
    if [[ -d "$dir" ]]; then
        for entry in "$dir"/*; do
            if [[ -L "$entry" ]]; then
                tgt="$(readlink -f "$entry" 2>/dev/null || true)"
                case "$tgt" in
                    "$POOL"/*) count=$((count + 1)) ;;
                esac
            fi
        done
    fi
    echo "$count"
}

snapshot() { # stable listing of a home's tree, including link targets
    # Portable: BSD/macOS find has no -printf, and an empty snapshot would make
    # the idempotency comparison below pass vacuously.
    local entry
    find "$1" -mindepth 1 | sort | while IFS= read -r entry; do
        if [[ -L "$entry" ]]; then
            echo "$entry -> $(readlink "$entry")"
        else
            echo "$entry"
        fi
    done
}

link_resolves_to() { # <link> <expected-target>
    [[ -L "$1" && "$(readlink -f "$1")" == "$(readlink -f "$2")" ]]
}

# --- Test 1: expected curated links are created for all four tools -----------
H="$(new_home)"
TMP_HOMES+=("$H")
out="$(HOME="$H" "$RECONCILER" --apply 2>&1)"; rc=$?
check "t1: apply exits 0 on a fresh home" test "$rc" -eq 0
check "t1: Claude receives 29 pool links"   test "$(links_into_pool "$H/.claude/skills")" -eq 29
check "t1: OpenCode receives 23 pool links" test "$(links_into_pool "$H/.config/opencode/skills")" -eq 23
check "t1: Pi receives 9 pool links"        test "$(links_into_pool "$H/.pi/agent/skills")" -eq 9
check "t1: Hermes receives 29 pool links"   test "$(links_into_pool "$H/.hermes/skills/personal")" -eq 29
check "t1: Claude-only skill is linked"     link_resolves_to "$H/.claude/skills/find-skills" "$POOL/find-skills"
check "t1: Claude gets Ponytail workflow"     link_resolves_to "$H/.claude/skills/pr-self-review" "$POOL/pr-self-review"
check "t1: Claude gets shared review contract" link_resolves_to "$H/.claude/skills/code-review" "$POOL/code-review"
check "t1: OpenCode gets Ponytail workflow"   link_resolves_to "$H/.config/opencode/skills/pr-self-review" "$POOL/pr-self-review"
check "t1: OpenCode gets shared review contract" link_resolves_to "$H/.config/opencode/skills/code-review" "$POOL/code-review"
check "t1: Pi gets shared review contract"   link_resolves_to "$H/.pi/agent/skills/code-review" "$POOL/code-review"
check "t1: Hermes gets Ponytail workflow"     link_resolves_to "$H/.hermes/skills/personal/pr-self-review" "$POOL/pr-self-review"
check "t1: Hermes gets shared review contract" link_resolves_to "$H/.hermes/skills/personal/code-review" "$POOL/code-review"
check "t1: Hermes gets multiagent PR review" link_resolves_to "$H/.hermes/skills/personal/multiagent-pr-review" "$POOL/multiagent-pr-review"
check "t1: Claude excludes multiagent PR review" test ! -e "$H/.claude/skills/multiagent-pr-review"
check "t1: OpenCode excludes multiagent PR review" test ! -e "$H/.config/opencode/skills/multiagent-pr-review"
check "t1: Pi excludes multiagent PR review" test ! -e "$H/.pi/agent/skills/multiagent-pr-review"
check "t1: Hermes gets handoff supervision" link_resolves_to "$H/.hermes/skills/personal/coding-agent-handoff-supervision" "$POOL/coding-agent-handoff-supervision"
check "t1: OpenCode gets gamedev"           link_resolves_to "$H/.config/opencode/skills/gamedev" "$POOL/gamedev"
check "t1: Pi does not get manual-merge"    test ! -e "$H/.pi/agent/skills/manual-merge"
check "t1: Hermes excludes obsidian"        test ! -e "$H/.hermes/skills/personal/obsidian"
check "t1: Hermes excludes vault-pkm"       test ! -e "$H/.hermes/skills/personal/vault-pkm"

# --- Test 8: re-running --apply is idempotent --------------------------------
before="$(snapshot "$H")"
out="$(HOME="$H" "$RECONCILER" --apply 2>&1)"; rc=$?
after="$(snapshot "$H")"
check "t8: second apply exits 0"                 test "$rc" -eq 0
check "t8: second apply changes nothing on disk" test "$before" = "$after"
check "t8: second apply plans no creates"        bash -c '! grep -q "create link" <<<"$1"' _ "$out"
check "t8: second apply plans no prunes"         bash -c '! grep -q "prune stale" <<<"$1"' _ "$out"

# --- Tests 2/3/4: foreign and real entries are preserved ----------------------
H2="$(new_home)"
TMP_HOMES+=("$H2")
FOREIGN_DIR="$H2/fake-package/omarchy-skill"
mkdir -p "$FOREIGN_DIR" "$H2/.claude/skills" "$H2/.pi/agent/skills"
# t2: Omarchy-like foreign symlink (non-curated name) in a skill directory
ln -s "$FOREIGN_DIR" "$H2/.claude/skills/omarchy"
# t2b: broken foreign symlink
ln -s "$H2/does-not-exist" "$H2/.claude/skills/diagnose-crash"
# t3: real directory colliding with a curated name
mkdir -p "$H2/.claude/skills/ship"
echo "local content" > "$H2/.claude/skills/ship/marker"
# t4: foreign regular files, one colliding with a curated name, one not
echo "keep me" > "$H2/.claude/skills/worktrunk"
echo "keep me too" > "$H2/.pi/agent/skills/notes.txt"

out="$(HOME="$H2" "$RECONCILER" --apply 2>&1)"; rc=$?
check "t2: apply exits 0 with foreign entries present" test "$rc" -eq 0
check "t2: foreign symlink is preserved"        test "$(readlink "$H2/.claude/skills/omarchy")" = "$FOREIGN_DIR"
check "t2: broken foreign symlink is preserved" test "$(readlink "$H2/.claude/skills/diagnose-crash")" = "$H2/does-not-exist"
check "t3: colliding real directory is preserved" test -f "$H2/.claude/skills/ship/marker" -a ! -L "$H2/.claude/skills/ship"
check "t3: collision is warned about"           bash -c 'grep -q "Claude/ship exists and is not a symlink" <<<"$1"' _ "$out"
check "t4: colliding regular file is preserved" test -f "$H2/.claude/skills/worktrunk" -a ! -L "$H2/.claude/skills/worktrunk"
check "t4: non-colliding regular file is preserved" test -f "$H2/.pi/agent/skills/notes.txt"

# --- Tests 5/6/7: stale pool links prune under apply, not check ---------------
# gamedev is in the pool but not curated for Pi, so a Pi link to it is stale.
ln -s "$POOL/gamedev" "$H2/.pi/agent/skills/gamedev"
before="$(snapshot "$H2")"
out="$(HOME="$H2" "$RECONCILER" --check 2>&1)"; rc=$?
after="$(snapshot "$H2")"
check "t6: check exits 0"                        test "$rc" -eq 0
check "t6: check reports the stale link"         bash -c 'grep -q "would prune stale pool link: gamedev" <<<"$1"' _ "$out"
check "t6: check does not mutate the filesystem" test "$before" = "$after"
check "t6: stale link still present after check" test -L "$H2/.pi/agent/skills/gamedev"

out="$(HOME="$H2" "$RECONCILER" --apply 2>&1)"; rc=$?
check "t5: apply exits 0"                        test "$rc" -eq 0
check "t5: stale pool link is pruned by apply"   test ! -e "$H2/.pi/agent/skills/gamedev" -a ! -L "$H2/.pi/agent/skills/gamedev"
check "t7: foreign symlink survives apply"       test -L "$H2/.claude/skills/omarchy"
check "t7: broken foreign symlink survives apply" test -L "$H2/.claude/skills/diagnose-crash"

# --- Test 9: invocation outside the repository root ---------------------------
H3="$(new_home)"
TMP_HOMES+=("$H3")
out="$(cd / && HOME="$H3" "$RECONCILER" --check 2>&1)"; rc=$?
check "t9: check from outside the repo exits 0"  test "$rc" -eq 0
check "t9: source pool resolves independent of cwd" bash -c 'grep -q "would create link: ship" <<<"$1"' _ "$out"
check "t9: check on a fresh home creates nothing"   test -z "$(find "$H3" -mindepth 1)"

# --- Test 11: retired pool links prune even when resolution is blind ---------
# `Cwd::abs_path` returns empty for a dangling link whose parent is missing, so a
# resolution-based classifier would call these "foreign" and keep them forever.
H11="$(new_home)"
TMP_HOMES+=("$H11")
mkdir -p "$H11/.claude/skills" "$H11/other-pack"
GONE_POOL="$H11/never-existed/dot-agents/skills"
ln -s "$GONE_POOL/agent-workspace" "$H11/.claude/skills/agent-workspace"
# Same retired names, but pointing at THIS repo's pool (also missing now).
ln -s "$POOL/agent-workspace" "$H11/.claude/skills/legacy-in-pool"
ln -s "$POOL/git-master"      "$H11/.claude/skills/legacy-in-pool-2"
# Unrelated broken and foreign links that must survive.
ln -s "$H11/nowhere"    "$H11/.claude/skills/diagnose-crash"
ln -s "$H11/other-pack" "$H11/.claude/skills/omarchy"

out="$(HOME="$H11" "$RECONCILER" --check 2>&1)"; rc=$?
check "t11: check exits 0 with dangling legacy links" test "$rc" -eq 0
# Either branch is a correct prune: where `Cwd::abs_path` can still resolve a
# dangling leaf it lands in the stale-pool branch, and where it returns empty the
# raw-target allowlist catches it. The raw-target rule is what makes the outcome
# the same on every platform, so assert the outcome, not which branch reported it.
check "t11: check plans a prune for the retired link"  bash -c 'grep -qE "would prune (stale|retired) pool link: legacy-in-pool$" <<<"$1"' _ "$out"
check "t11: check plans the second retired prune"      bash -c 'grep -qE "would prune (stale|retired) pool link: legacy-in-pool-2$" <<<"$1"' _ "$out"
check "t11: unrelated broken link is preserved"       bash -c 'grep -q "preserved (foreign symlink): diagnose-crash" <<<"$1"' _ "$out"
check "t11: foreign package link is preserved"        bash -c 'grep -q "preserved (foreign symlink): omarchy" <<<"$1"' _ "$out"
check "t11: another pool path is preserved"           bash -c 'grep -q "preserved (foreign symlink): agent-workspace" <<<"$1"' _ "$out"
check "t11: check did not mutate"                     test -L "$H11/.claude/skills/legacy-in-pool"

out="$(HOME="$H11" "$RECONCILER" --apply 2>&1)"; rc=$?
check "t11: apply exits 0"                            test "$rc" -eq 0
check "t11: retired pool link is gone"                test ! -L "$H11/.claude/skills/legacy-in-pool"
check "t11: second retired pool link is gone"         test ! -L "$H11/.claude/skills/legacy-in-pool-2"
check "t11: unrelated broken link survived apply"     test -L "$H11/.claude/skills/diagnose-crash"
check "t11: foreign package link survived apply"      test -L "$H11/.claude/skills/omarchy"
check "t11: another pool path survived apply"         test -L "$H11/.claude/skills/agent-workspace"

before11="$(snapshot "$H11")"
out="$(HOME="$H11" "$RECONCILER" --apply 2>&1)"; rc=$?
after11="$(snapshot "$H11")"
check "t11: second apply exits 0"                     test "$rc" -eq 0
check "t11: prune is idempotent"                      test "$before11" = "$after11"
check "t11: second apply plans no legacy prune"        bash -c '! grep -qE "prune (stale|retired) pool link: legacy-in-pool" <<<"$1"' _ "$out"

# --- Test 10: missing or malformed arguments fail without mutation ------------
H4="$(new_home)"
TMP_HOMES+=("$H4")
out="$(HOME="$H4" "$RECONCILER" 2>&1)"; rc=$?
check "t10: no arguments fails"                  test "$rc" -ne 0
check "t10: no arguments prints usage"           bash -c 'grep -q "Usage:" <<<"$1"' _ "$out"
out="$(HOME="$H4" "$RECONCILER" --bogus 2>&1)"; rc=$?
check "t10: unknown argument fails"              test "$rc" -ne 0
out="$(HOME="$H4" "$RECONCILER" --check --apply 2>&1)"; rc=$?
check "t10: conflicting modes fail"              test "$rc" -ne 0
check "t10: failed invocations did not mutate"   test -z "$(find "$H4" -mindepth 1)"

echo ""
echo "$TESTS tests, $FAILURES failures"
if [[ $FAILURES -gt 0 ]]; then
    exit 1
fi
