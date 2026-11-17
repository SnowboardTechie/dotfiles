#!/usr/bin/env bash
# run-all.sh — run every test in this repository and summarise.
#
# Runs each tests/*.sh with bash, each tests/*.py with python3, each tests/*.ts
# with `node --test`, and the Forgejo Wayfinder adapter's unittest module. Prints
# one line per file, then the output of each failure and a summary. Exits 1 if
# any failed. Needs only PATH, HOME, TMPDIR and LANG: the ticket runner's merge
# gate runs it under `env -i` from a fresh clone.

set -u

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT" || exit 1
SELF="tests/$(basename "${BASH_SOURCE[0]}")"
LOGS="$(mktemp -d "${TMPDIR:-/tmp}/dotfiles-tests-XXXXXX")"
trap 'rm -rf "$LOGS"' EXIT

passed=0
failed=()

# run_one <label> <command...>
run_one() {
    local label="$1" log start secs
    shift
    log="$LOGS/$(printf '%s' "$label" | tr '/ ' '__').log"
    start=$SECONDS
    if "$@" </dev/null >"$log" 2>&1; then
        secs=$((SECONDS - start))
        printf 'PASS %s (%ss)\n' "$label" "$secs"
        passed=$((passed + 1))
    else
        secs=$((SECONDS - start))
        printf 'FAIL %s (%ss)\n' "$label" "$secs"
        failed+=("$label")
    fi
}

shopt -s nullglob
for t in tests/*.sh; do
    [[ "$t" == "$SELF" ]] && continue
    run_one "$t" bash "$t"
done
for t in tests/*.py; do
    run_one "$t" python3 "$t"
done
for t in tests/*.ts; do
    run_one "$t" node --test "$t"
done
run_one "dot-agents/forgejo-tracker/tests/test_forgejo_wayfinder.py" \
    python3 -m unittest dot-agents/forgejo-tracker/tests/test_forgejo_wayfinder.py

for label in "${failed[@]}"; do
    echo ""
    echo "===== $label ====="
    tail -n 40 "$LOGS/$(printf '%s' "$label" | tr '/ ' '__').log"
done

echo ""
echo "$((passed + ${#failed[@]})) test files: $passed passed, ${#failed[@]} failed"
[[ ${#failed[@]} -eq 0 ]]
