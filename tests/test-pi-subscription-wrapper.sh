#!/usr/bin/env bash
# Tests the `pi` subscription wrapper in dot-config/shell/aliases.sh under bash and zsh.
# A fake `pi` on PATH prints the subscription variable it received. Temporary HOMEs only.

set -u

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ALIASES="$REPO_ROOT/dot-config/shell/aliases.sh"
TESTS=0
FAILURES=0
TMP="$(cd "$(mktemp -d "${TMPDIR:-/tmp}/pi-subscription-test-XXXXXX")" && pwd -P)"
trap 'rm -rf "$TMP"' EXIT

mkdir -p "$TMP/bin"
cat >"$TMP/bin/pi" <<'EOF'
#!/bin/sh
echo "subscription=${PI_CLAUDE_CODE_CONFIG_DIR:-unset} args=$*"
EOF
chmod +x "$TMP/bin/pi"

check() { # <description> <expected> <actual>
    TESTS=$((TESTS + 1))
    if [[ "$2" == "$3" ]]; then
        echo "ok   $1"
    else
        echo "FAIL $1: expected '$2', got '$3'"
        FAILURES=$((FAILURES + 1))
    fi
}

# Skip startup files so the machine's PATH and real pi stay out.
shell_opts() { [[ "$1" == zsh ]] && echo -f || echo --norc; }

# run <shell> <home> <dir> <extra env...> -- prints the fake pi's output
run() {
    local sh="$1" home="$2" dir="$3"; shift 3
    env -i PATH="$TMP/bin:/usr/bin:/bin" HOME="$home" "$@" \
        "$sh" "$(shell_opts "$sh")" -c 'source "$1" && cd "$2" && pi -p hello' _ "$ALIASES" "$dir" 2>/dev/null
}

H="$TMP/home"
mkdir -p "$H/.claude-personal" "$H/code/sgg/HHS/repo" "$H/code/other" "$H/code/sgg-not"
NOPERS="$TMP/nopersonal"
mkdir -p "$NOPERS/code/other"

for sh in bash zsh; do
    command -v "$sh" >/dev/null 2>&1 || { echo "skip $sh (not installed)"; continue; }
    check "$sh: outside sgg uses personal plan" \
        "subscription=$H/.claude-personal args=-p hello" "$(run "$sh" "$H" "$H/code/other")"
    check "$sh: home dir uses personal plan" \
        "subscription=$H/.claude-personal args=-p hello" "$(run "$sh" "$H" "$H")"
    check "$sh: under sgg uses work subscription" \
        "subscription=unset args=-p hello" "$(run "$sh" "$H" "$H/code/sgg/HHS/repo")"
    check "$sh: sgg root uses work subscription" \
        "subscription=unset args=-p hello" "$(run "$sh" "$H" "$H/code/sgg")"
    check "$sh: sibling of sgg is not sgg" \
        "subscription=$H/.claude-personal args=-p hello" "$(run "$sh" "$H" "$H/code/sgg-not")"
    check "$sh: explicit subscription wins" \
        "subscription=/x args=-p hello" "$(run "$sh" "$H" "$H/code/other" PI_CLAUDE_CODE_CONFIG_DIR=/x)"
    check "$sh: explicit CLAUDE_CONFIG_DIR is left alone" \
        "subscription=unset args=-p hello" "$(run "$sh" "$H" "$H/code/other" CLAUDE_CONFIG_DIR=/y)"
    check "$sh: no personal login, no wrapper" \
        "subscription=unset args=-p hello" "$(run "$sh" "$NOPERS" "$NOPERS/code/other")"
    check "$sh: command pi bypasses the wrapper" \
        "subscription=unset args=" "$(env -i PATH="$TMP/bin:/usr/bin:/bin" HOME="$H" "$sh" "$(shell_opts "$sh")" -c 'source "$1" && cd "$2" && command pi' _ "$ALIASES" "$H/code/other" 2>/dev/null)"
done

# --- scripts/reconcile-pi-extensions.sh ----------------------------------------
RECON="$REPO_ROOT/scripts/reconcile-pi-extensions.sh"
EXT="$REPO_ROOT/dot-pi/agent/extensions/pi-subscription.ts"
RH="$TMP/recon-home"
mkdir -p "$RH"
PI_EXTENSIONS_HOME="$RH" "$RECON" --check >/dev/null; rc=$?
check "reconcile: check exits 0 with links missing" "0" "$rc"
check "reconcile: check reports the missing link" "yes" "$(PI_EXTENSIONS_HOME="$RH" "$RECON" --check | grep -q 'MISSING.*pi-subscription.ts' && echo yes || echo no)"
check "reconcile: check does not create the link" "absent" "$([[ -e "$RH/.pi/agent/extensions/pi-subscription.ts" ]] && echo present || echo absent)"
PI_EXTENSIONS_HOME="$RH" "$RECON" --apply >/dev/null; rc=$?
check "reconcile: apply exits 0" "0" "$rc"
check "reconcile: apply links the extension" "$EXT" "$(readlink "$RH/.pi/agent/extensions/pi-subscription.ts")"
check "reconcile: apply links pi-rex" "$REPO_ROOT/dot-pi/agent/extensions/pi-rex.ts" "$(readlink "$RH/.pi/agent/extensions/pi-rex.ts")"
check "reconcile: apply links pi-split" "$REPO_ROOT/dot-pi/agent/extensions/pi-split.ts" "$(readlink "$RH/.pi/agent/extensions/pi-split.ts")"
check "reconcile: apply links background-agent-watch" "$REPO_ROOT/dot-pi/agent/extensions/background-agent-watch.ts" "$(readlink "$RH/.pi/agent/extensions/background-agent-watch.ts")"
check "reconcile: apply links global AGENTS.md" "$REPO_ROOT/dot-pi/agent/AGENTS.md" "$(readlink "$RH/.pi/agent/AGENTS.md")"
PI_EXTENSIONS_HOME="$RH" "$RECON" --check >/dev/null; rc=$?
check "reconcile: check is clean after apply" "no" "$(PI_EXTENSIONS_HOME="$RH" "$RECON" --check | grep -q MISSING && echo yes || echo no)"
FH="$TMP/foreign-home"
mkdir -p "$FH/.pi/agent/extensions"
echo mine >"$FH/.pi/agent/extensions/pi-subscription.ts"
out="$(PI_EXTENSIONS_HOME="$FH" "$RECON" --apply)"
check "reconcile: foreign file is kept" "mine" "$(cat "$FH/.pi/agent/extensions/pi-subscription.ts")"
check "reconcile: foreign file is reported" "yes" "$(grep -q 'not managed' <<<"$out" && echo yes || echo no)"

# Renamed extensions: a link under the old name into this repository goes; anything else of that name stays.
SH="$TMP/stale-home"
mkdir -p "$SH/.pi/agent/extensions"
ln -s "$REPO_ROOT/dot-pi/agent/extensions/pi-seat.ts" "$SH/.pi/agent/extensions/pi-seat.ts"
ln -s "$REPO_ROOT/dot-pi/agent/extensions/worker-watch.ts" "$SH/.pi/agent/extensions/worker-watch.ts"
out="$(PI_EXTENSIONS_HOME="$SH" "$RECON" --check)"
check "reconcile: check reports a stale old-name link" "yes" "$(grep -q 'STALE.*pi-seat.ts' <<<"$out" && echo yes || echo no)"
check "reconcile: check keeps a stale old-name link" "link" "$([[ -L "$SH/.pi/agent/extensions/pi-seat.ts" ]] && echo link || echo gone)"
PI_EXTENSIONS_HOME="$SH" "$RECON" --apply >/dev/null
check "reconcile: apply removes the stale pi-seat link" "gone" "$([[ -L "$SH/.pi/agent/extensions/pi-seat.ts" ]] && echo link || echo gone)"
check "reconcile: apply removes the stale worker-watch link" "gone" "$([[ -L "$SH/.pi/agent/extensions/worker-watch.ts" ]] && echo link || echo gone)"
check "reconcile: apply links pi-subscription in its place" "$EXT" "$(readlink "$SH/.pi/agent/extensions/pi-subscription.ts")"
VH="$TMP/via-other-path-home"
mkdir -p "$VH/.pi/agent/extensions"
ln -s "$REPO_ROOT" "$TMP/dotfiles-alias"
ln -s "$TMP/dotfiles-alias/dot-pi/agent/extensions/pi-seat.ts" "$VH/.pi/agent/extensions/pi-seat.ts"
PI_EXTENSIONS_HOME="$VH" "$RECON" --apply >/dev/null
check "reconcile: a stale link made through another path to this checkout is removed" "gone" "$([[ -L "$VH/.pi/agent/extensions/pi-seat.ts" ]] && echo link || echo gone)"
OH="$TMP/old-name-foreign-home"
mkdir -p "$OH/.pi/agent/extensions" "$TMP/elsewhere"
echo mine >"$OH/.pi/agent/extensions/pi-seat.ts"
ln -s "$TMP/elsewhere/worker-watch.ts" "$OH/.pi/agent/extensions/worker-watch.ts"
out="$(PI_EXTENSIONS_HOME="$OH" "$RECON" --apply)"
check "reconcile: a foreign file of the old name is kept" "mine" "$(cat "$OH/.pi/agent/extensions/pi-seat.ts")"
check "reconcile: a foreign link of the old name is kept" "$TMP/elsewhere/worker-watch.ts" "$(readlink "$OH/.pi/agent/extensions/worker-watch.ts")"
check "reconcile: a foreign file of the old name is reported" "yes" "$(grep -q 'pi-seat.ts is not managed' <<<"$out" && echo yes || echo no)"

echo "$TESTS tests, $FAILURES failures"
[[ $FAILURES -eq 0 ]]
