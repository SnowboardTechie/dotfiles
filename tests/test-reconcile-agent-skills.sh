#!/usr/bin/env bash
# Integration tests for scripts/reconcile-agent-skills.sh.
#
# Runs the reconciler against throwaway homes; the real checked-out
# skill pool is used read-only as the source. All writes are isolated inside
# the throwaway homes, which are removed on exit.

set -u

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RECONCILER="$REPO_ROOT/scripts/reconcile-agent-skills.sh"
SKILL_POOL="$(cd "$REPO_ROOT/dot-agents/skills" && pwd -P)"

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

links_into_skill_pool() { # count symlinks in <dir> that resolve into the skill pool
    local dir="$1" count=0 entry tgt
    if [[ -d "$dir" ]]; then
        for entry in "$dir"/*; do
            if [[ -L "$entry" ]]; then
                tgt="$(readlink -f "$entry" 2>/dev/null || true)"
                case "$tgt" in
                    "$SKILL_POOL"/*) count=$((count + 1)) ;;
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

# --- Test 1: expected curated links are created for all five harnesses -------
H="$(new_home)"
TMP_HOMES+=("$H")
out="$(HOME="$H" "$RECONCILER" --apply 2>&1)"; rc=$?
check "t1: apply exits 0 on a fresh home" test "$rc" -eq 0
check "t1: Codex receives 23 skill pool links" test "$(links_into_skill_pool "$H/.agents/skills")" -eq 23
check "t1: no harness gets a retired adapted skill" bash -c 'for d in "$1/.agents/skills" "$1/.claude/skills" "$1/.config/opencode/skills" "$1/.pi/agent/skills" "$1/.hermes/skills/personal"; do for n in grilling wayfinder tdd diagnosing-bugs codebase-architecture guided-learning; do [[ ! -e "$d/$n" && ! -L "$d/$n" ]] || exit 1; done; done' _ "$H"
check "t1: Codex gets ADR coaching" link_resolves_to "$H/.agents/skills/adr-and-spec-coach" "$SKILL_POOL/adr-and-spec-coach"
check "t1: Codex gets conforming specs" link_resolves_to "$H/.agents/skills/conforming-tech-specs" "$SKILL_POOL/conforming-tech-specs"
check "t1: Codex gets shared handoff" link_resolves_to "$H/.agents/skills/session-handoff" "$SKILL_POOL/session-handoff"
check "t1: Codex gets teammate PR review" link_resolves_to "$H/.agents/skills/teammate-pr-review" "$SKILL_POOL/teammate-pr-review"
check "t1: Codex excludes Hermes orchestration" test ! -e "$H/.agents/skills/coding-agent-handoff-supervision"
check "t1: Claude receives 22 skill pool links"   test "$(links_into_skill_pool "$H/.claude/skills")" -eq 22
check "t1: OpenCode receives 20 skill pool links" test "$(links_into_skill_pool "$H/.config/opencode/skills")" -eq 20
check "t1: Pi receives 25 skill pool links"       test "$(links_into_skill_pool "$H/.pi/agent/skills")" -eq 25
check "t1: Hermes receives 33 skill pool links"   test "$(links_into_skill_pool "$H/.hermes/skills/personal")" -eq 33
check "t1: Claude-only skill is linked"     link_resolves_to "$H/.claude/skills/dx-target" "$SKILL_POOL/dx-target"
check "t1: Claude excludes non-Claude common" test ! -e "$H/.claude/skills/obsidian"
check "t1: Pi keeps non-Claude common"      link_resolves_to "$H/.pi/agent/skills/obsidian" "$SKILL_POOL/obsidian"
check "t1: Claude gets Ponytail workflow"     link_resolves_to "$H/.claude/skills/pr-self-review" "$SKILL_POOL/pr-self-review"
check "t1: Claude gets teammate PR review" link_resolves_to "$H/.claude/skills/teammate-pr-review" "$SKILL_POOL/teammate-pr-review"
check "t1: OpenCode gets Ponytail workflow"   link_resolves_to "$H/.config/opencode/skills/pr-self-review" "$SKILL_POOL/pr-self-review"
check "t1: OpenCode gets teammate PR review" link_resolves_to "$H/.config/opencode/skills/teammate-pr-review" "$SKILL_POOL/teammate-pr-review"
check "t1: Pi gets teammate PR review"      link_resolves_to "$H/.pi/agent/skills/teammate-pr-review" "$SKILL_POOL/teammate-pr-review"
check "t1: Hermes gets Ponytail workflow"     link_resolves_to "$H/.hermes/skills/personal/pr-self-review" "$SKILL_POOL/pr-self-review"
check "t1: Hermes gets teammate PR review" link_resolves_to "$H/.hermes/skills/personal/teammate-pr-review" "$SKILL_POOL/teammate-pr-review"
check "t1: Hermes gets multiagent PR review" link_resolves_to "$H/.hermes/skills/personal/multiagent-pr-review" "$SKILL_POOL/multiagent-pr-review"
check "t1: Claude excludes multiagent PR review" test ! -e "$H/.claude/skills/multiagent-pr-review"
check "t1: OpenCode excludes multiagent PR review" test ! -e "$H/.config/opencode/skills/multiagent-pr-review"
check "t1: Pi gets multiagent PR review"  link_resolves_to "$H/.pi/agent/skills/multiagent-pr-review" "$SKILL_POOL/multiagent-pr-review"
check "t1: Hermes gets handoff supervision" link_resolves_to "$H/.hermes/skills/personal/coding-agent-handoff-supervision" "$SKILL_POOL/coding-agent-handoff-supervision"
check "t1: OpenCode gets gamedev"           link_resolves_to "$H/.config/opencode/skills/gamedev" "$SKILL_POOL/gamedev"
check "t1: Pi gets issue-work"              link_resolves_to "$H/.pi/agent/skills/issue-work" "$SKILL_POOL/issue-work"
check "t1: Pi gets handoff supervision"     link_resolves_to "$H/.pi/agent/skills/coding-agent-handoff-supervision" "$SKILL_POOL/coding-agent-handoff-supervision"
check "t1: Pi gets manual-merge"            link_resolves_to "$H/.pi/agent/skills/manual-merge" "$SKILL_POOL/manual-merge"
check "t1: Hermes excludes obsidian"        test ! -e "$H/.hermes/skills/personal/obsidian"
check "t1: Hermes excludes vault-pkm"       test ! -e "$H/.hermes/skills/personal/vault-pkm"
check "t1: every harness gets knowledge-capture" bash -c 'for d in "$1/.agents/skills" "$1/.claude/skills" "$1/.config/opencode/skills" "$1/.pi/agent/skills" "$1/.hermes/skills/personal"; do [[ -L "$d/knowledge-capture" ]] || exit 1; done' _ "$H"
check "t1: no harness gets retired apple-notes-pkm" bash -c 'for d in "$1/.agents/skills" "$1/.claude/skills" "$1/.config/opencode/skills" "$1/.pi/agent/skills" "$1/.hermes/skills/personal"; do [[ ! -e "$d/apple-notes-pkm" ]] || exit 1; done' _ "$H"
check "t1: every harness gets black-box-verification" bash -c 'for d in "$1/.agents/skills" "$1/.claude/skills" "$1/.config/opencode/skills" "$1/.pi/agent/skills" "$1/.hermes/skills/personal"; do [[ -L "$d/black-box-verification" ]] || exit 1; done' _ "$H"
check "t1: no harness gets retired local code-review" bash -c 'for d in "$1/.agents/skills" "$1/.claude/skills" "$1/.config/opencode/skills" "$1/.pi/agent/skills" "$1/.hermes/skills/personal"; do [[ ! -e "$d/code-review" ]] || exit 1; done' _ "$H"
check "t1: no harness gets retired vault-capture" bash -c 'for d in "$1/.agents/skills" "$1/.claude/skills" "$1/.config/opencode/skills" "$1/.pi/agent/skills" "$1/.hermes/skills/personal"; do [[ ! -e "$d/vault-capture" ]] || exit 1; done' _ "$H"

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

# Codex preserves its existing user skills and bundled system directory.
# Remove only fixture-owned links before constructing collisions.
rm "$H2/.agents/skills/adr-and-spec-coach" "$H2/.agents/skills/conforming-tech-specs"
mkdir -p "$H2/.agents/skills/adr-and-spec-coach" "$H2/.codex/skills/.system"
printf 'local ADR skill\n' > "$H2/.agents/skills/adr-and-spec-coach/marker"
printf 'bundled\n' > "$H2/.codex/skills/.system/marker"
ln -s "$H2/missing-foreign" "$H2/.agents/skills/conforming-tech-specs"
ln -s "$SKILL_POOL/gamedev" "$H2/.agents/skills/gamedev"
before_codex="$(snapshot "$H2")"
out="$(HOME="$H2" "$RECONCILER" --check 2>&1)"
check "Codex: dry run preserves all entries" test "$before_codex" = "$(snapshot "$H2")"
out="$(HOME="$H2" "$RECONCILER" --apply 2>&1)"
check "Codex: real skill conflict preserved" test -f "$H2/.agents/skills/adr-and-spec-coach/marker"
check "Codex: broken foreign conflict preserved" test "$(readlink "$H2/.agents/skills/conforming-tech-specs")" = "$H2/missing-foreign"
check "Codex: conflict warning emitted" bash -c 'grep -q "Codex/conforming-tech-specs is a foreign symlink" <<<"$1"' _ "$out"
check "Codex: stale skill pool link pruned" test ! -L "$H2/.agents/skills/gamedev"
check "Codex: bundled skills untouched" test -f "$H2/.codex/skills/.system/marker"

# Links an older curation left for the six skills adapted from Matt Pocock's,
# now retired and gone from the skill pool: reported under check, pruned under apply,
# in every harness. A same-named link to his checkout is not the skill pool's and stays.
RETIRED_ADAPTED="grilling wayfinder tdd diagnosing-bugs codebase-architecture guided-learning"
mkdir -p "$H2/his/tdd" "$H2/.config/opencode/skills" "$H2/.hermes/skills/personal"
for d in "$H2/.agents/skills" "$H2/.claude/skills" "$H2/.config/opencode/skills" "$H2/.pi/agent/skills" "$H2/.hermes/skills/personal"; do
    for n in $RETIRED_ADAPTED; do [[ -e "$d/$n" || -L "$d/$n" ]] || ln -s "$SKILL_POOL/$n" "$d/$n"; done
done
rm "$H2/.claude/skills/tdd"; ln -s "$H2/his/tdd" "$H2/.claude/skills/tdd"
before_retired="$(snapshot "$H2")"
out="$(HOME="$H2" "$RECONCILER" --check 2>&1)"
check "retired adapted: check reports every stale link" test "$(grep -cE "would prune (stale|retired) skill pool link: (${RETIRED_ADAPTED// /|})$" <<<"$out")" -eq 29
check "retired adapted: check changes nothing" test "$before_retired" = "$(snapshot "$H2")"
out="$(HOME="$H2" "$RECONCILER" --apply 2>&1)"
check "retired adapted: apply prunes them in every harness" bash -c 'for d in "$1/.agents/skills" "$1/.claude/skills" "$1/.config/opencode/skills" "$1/.pi/agent/skills" "$1/.hermes/skills/personal"; do for n in $2; do [[ "$d/$n" == "$1/.claude/skills/tdd" ]] && continue; [[ ! -L "$d/$n" ]] || exit 1; done; done' _ "$H2" "$RETIRED_ADAPTED"
check "retired adapted: a same-named link elsewhere survives" link_resolves_to "$H2/.claude/skills/tdd" "$H2/his/tdd"

# Links into Matt Pocock's checkout belong to scripts/reconcile-mattpocock-skills.sh:
# kept, and counted in one line rather than listed as foreign.
mkdir -p "$H2/.local/share/mattpocock-skills/skills/engineering/zoom-out"
ln -s "$H2/.local/share/mattpocock-skills/skills/engineering/zoom-out" "$H2/.claude/skills/zoom-out"
out="$(HOME="$H2" "$RECONCILER" --apply 2>&1)"
check "his links: kept" test -L "$H2/.claude/skills/zoom-out"
check "his links: counted, not listed as foreign" bash -c 'grep -q "1 links to Matt Pocock'"'"'s skills left to scripts/reconcile-mattpocock-skills.sh" <<<"$1" && ! grep -q "preserved (foreign symlink): zoom-out" <<<"$1"' _ "$out"

# --- Tests 5/6/7: stale skill pool links prune under apply, not check ---------------
# gamedev is in the skill pool but not curated for Pi, so a Pi link to it is stale.
ln -s "$SKILL_POOL/gamedev" "$H2/.pi/agent/skills/gamedev"
before="$(snapshot "$H2")"
out="$(HOME="$H2" "$RECONCILER" --check 2>&1)"; rc=$?
after="$(snapshot "$H2")"
check "t6: check exits 0"                        test "$rc" -eq 0
check "t6: check reports the stale link"         bash -c 'grep -q "would prune stale skill pool link: gamedev" <<<"$1"' _ "$out"
check "t6: check does not mutate the filesystem" test "$before" = "$after"
check "t6: stale link still present after check" test -L "$H2/.pi/agent/skills/gamedev"

out="$(HOME="$H2" "$RECONCILER" --apply 2>&1)"; rc=$?
check "t5: apply exits 0"                        test "$rc" -eq 0
check "t5: stale skill pool link is pruned by apply"   test ! -e "$H2/.pi/agent/skills/gamedev" -a ! -L "$H2/.pi/agent/skills/gamedev"
check "t7: foreign symlink survives apply"       test -L "$H2/.claude/skills/omarchy"
check "t7: broken foreign symlink survives apply" test -L "$H2/.claude/skills/diagnose-crash"

# --- Test 9: invocation outside the repository root ---------------------------
H3="$(new_home)"
TMP_HOMES+=("$H3")
out="$(cd / && HOME="$H3" "$RECONCILER" --check 2>&1)"; rc=$?
check "t9: check from outside the repo exits 0"  test "$rc" -eq 0
check "t9: source skill pool resolves independent of cwd" bash -c 'grep -q "would create link: ship" <<<"$1"' _ "$out"
check "t9: check on a fresh home creates nothing"   test -z "$(find "$H3" -mindepth 1)"

# --- Test 11: retired skill pool links prune even when resolution is blind ---------
# `Cwd::abs_path` returns empty for a dangling link whose parent is missing, so a
# resolution-based classifier would call these "foreign" and keep them forever.
H11="$(new_home)"
TMP_HOMES+=("$H11")
mkdir -p "$H11/.claude/skills" "$H11/other-pack"
GONE_POOL="$H11/never-existed/dot-agents/skills"
ln -s "$GONE_POOL/agent-workspace" "$H11/.claude/skills/agent-workspace"
# Same retired names, but pointing at THIS repo's skill pool (also missing now).
ln -s "$SKILL_POOL/agent-workspace" "$H11/.claude/skills/legacy-in-pool"
ln -s "$SKILL_POOL/git-master"      "$H11/.claude/skills/legacy-in-pool-2"
ln -s "$SKILL_POOL/vault-capture"   "$H11/.claude/skills/vault-capture"
mkdir -p "$H11/.pi/agent/skills"
ln -s "$SKILL_POOL/code-review"     "$H11/.pi/agent/skills/code-review"
# Unrelated broken and foreign links that must survive.
ln -s "$H11/nowhere"    "$H11/.claude/skills/diagnose-crash"
ln -s "$H11/other-pack" "$H11/.claude/skills/omarchy"

out="$(HOME="$H11" "$RECONCILER" --check 2>&1)"; rc=$?
check "t11: check exits 0 with dangling legacy links" test "$rc" -eq 0
# Either branch is a correct prune: where `Cwd::abs_path` can still resolve a
# dangling leaf it lands in the stale skill pool link branch, and where it returns empty the
# raw-target allowlist catches it. The raw-target rule is what makes the outcome
# the same on every platform, so assert the outcome, not which branch reported it.
check "t11: check plans a prune for the retired link"  bash -c 'grep -qE "would prune (stale|retired) skill pool link: legacy-in-pool$" <<<"$1"' _ "$out"
check "t11: check plans the second retired prune"      bash -c 'grep -qE "would prune (stale|retired) skill pool link: legacy-in-pool-2$" <<<"$1"' _ "$out"
check "t11: check plans the local code-review prune" bash -c 'grep -qE "would prune (stale|retired) skill pool link: code-review$" <<<"$1"' _ "$out"
check "t11: check plans the vault-capture prune"       bash -c 'grep -qE "would prune (stale|retired) skill pool link: vault-capture$" <<<"$1"' _ "$out"
check "t11: unrelated broken link is preserved"       bash -c 'grep -q "preserved (foreign symlink): diagnose-crash" <<<"$1"' _ "$out"
check "t11: foreign package link is preserved"        bash -c 'grep -q "preserved (foreign symlink): omarchy" <<<"$1"' _ "$out"
check "t11: another skill pool path is preserved"           bash -c 'grep -q "preserved (foreign symlink): agent-workspace" <<<"$1"' _ "$out"
check "t11: check did not mutate"                     test -L "$H11/.claude/skills/legacy-in-pool"

out="$(HOME="$H11" "$RECONCILER" --apply 2>&1)"; rc=$?
check "t11: apply exits 0"                            test "$rc" -eq 0
check "t11: retired skill pool link is gone"                test ! -L "$H11/.claude/skills/legacy-in-pool"
check "t11: second retired skill pool link is gone"         test ! -L "$H11/.claude/skills/legacy-in-pool-2"
check "t11: retired local code-review link is gone"  test ! -L "$H11/.pi/agent/skills/code-review"
check "t11: retired vault-capture link is gone"       test ! -L "$H11/.claude/skills/vault-capture"
check "t11: unrelated broken link survived apply"     test -L "$H11/.claude/skills/diagnose-crash"
check "t11: foreign package link survived apply"      test -L "$H11/.claude/skills/omarchy"
check "t11: another skill pool path survived apply"         test -L "$H11/.claude/skills/agent-workspace"

before11="$(snapshot "$H11")"
out="$(HOME="$H11" "$RECONCILER" --apply 2>&1)"; rc=$?
after11="$(snapshot "$H11")"
check "t11: second apply exits 0"                     test "$rc" -eq 0
check "t11: prune is idempotent"                      test "$before11" = "$after11"
check "t11: second apply plans no legacy prune"        bash -c '! grep -qE "prune (stale|retired) skill pool link: legacy-in-pool" <<<"$1"' _ "$out"

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

# --- Test 12: a machine retiring OpenCode prunes only its skill pool links ---
H12="$(new_home)"
TMP_HOMES+=("$H12")
HOME="$H12" "$RECONCILER" --apply >/dev/null 2>&1
ln -s "$H12/foreign-skill" "$H12/.config/opencode/skills/foreign"
before12="$(snapshot "$H12")"
out="$(HOME="$H12" RECONCILE_OPENCODE_SKILLS=0 "$RECONCILER" --check 2>&1)"; rc=$?
check "t12: disabled OpenCode check exits 0" test "$rc" -eq 0
check "t12: disabled OpenCode check plans prune" bash -c 'grep -q "would prune stale skill pool link: ship" <<<"$1"' _ "$out"
check "t12: disabled OpenCode check does not mutate" test "$before12" = "$(snapshot "$H12")"
out="$(HOME="$H12" RECONCILE_OPENCODE_SKILLS=0 "$RECONCILER" --apply 2>&1)"; rc=$?
check "t12: disabled OpenCode apply exits 0" test "$rc" -eq 0
check "t12: OpenCode skill pool links are removed" test "$(links_into_skill_pool "$H12/.config/opencode/skills")" -eq 0
check "t12: foreign OpenCode link survives" test -L "$H12/.config/opencode/skills/foreign"
check "t12: Pi links are retained" test "$(links_into_skill_pool "$H12/.pi/agent/skills")" -eq 25

# --- Test 13: RECONCILE_HERMES_SKILLS=0 leaves Hermes untouched ----------------
H13="$(new_home)"
TMP_HOMES+=("$H13")
out="$(HOME="$H13" RECONCILE_HERMES_SKILLS=0 "$RECONCILER" --apply 2>&1)"; rc=$?
check "t13: Hermes-skipped apply exits 0" test "$rc" -eq 0
check "t13: Hermes skip is reported" bash -c 'grep -q "Hermes: skipped" <<<"$1"' _ "$out"
check "t13: no Hermes links are created" test ! -e "$H13/.hermes/skills/personal"
check "t13: Pi links are still created" test "$(links_into_skill_pool "$H13/.pi/agent/skills")" -eq 25
HOME="$H13" "$RECONCILER" --apply >/dev/null 2>&1
n13="$(links_into_skill_pool "$H13/.hermes/skills/personal")"
HOME="$H13" RECONCILE_HERMES_SKILLS=0 "$RECONCILER" --apply >/dev/null 2>&1
check "t13: existing Hermes links are not pruned" test "$(links_into_skill_pool "$H13/.hermes/skills/personal")" -eq "$n13"

echo ""
echo "$TESTS tests, $FAILURES failures"
if [[ $FAILURES -gt 0 ]]; then
    exit 1
fi
