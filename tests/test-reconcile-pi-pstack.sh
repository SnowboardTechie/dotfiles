#!/usr/bin/env bash
# Tests for scripts/reconcile-pi-pstack.sh. Uses stub `pi` and `claude`
# commands and temporary HOME directories, removed on exit.

set -u

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RECON="$REPO_ROOT/scripts/reconcile-pi-pstack.sh"
CC="https://github.com/earendil-works/pi-claude-code"
PIN="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["commit"])' "$REPO_ROOT/dot-agents/upstreams/pstack-claude.json")"
PSTACK="git:github.com/michael-denyer/pstack-claude@$PIN"
SHEET="$REPO_ROOT/dot-agents/pstack-forgejo/pstack-models.md"
INSTRUCTIONS="$REPO_ROOT/dot-pi/agent/AGENTS.md"
TMP="$(mktemp -d "${TMPDIR:-/tmp}/pi-pstack-test-XXXXXX")"
trap 'rm -rf "$TMP"' EXIT

TESTS=0
FAILURES=0
check() { # <description> <expected> <actual>
    TESTS=$((TESTS + 1))
    if [[ "$2" == "$3" ]]; then
        echo "ok   $1"
    else
        echo "FAIL $1: expected [$2], got [$3]"
        FAILURES=$((FAILURES + 1))
    fi
}
yes_if() { if "$@"; then echo yes; else echo no; fi; }

# Stub pi: install appends, remove deletes, in $PI_CODING_AGENT_DIR/settings.json;
# each call is logged with the agent directory it was given.
mkdir -p "$TMP/bin" "$TMP/bin-noclaude"
cat >"$TMP/bin/pi" <<'EOF'
#!/usr/bin/env bash
echo "${PI_CODING_AGENT_DIR:-<unset>} $*" >>"$HOME/pi-calls"
python3 - "${PI_CODING_AGENT_DIR:-$HOME/.pi/agent}/settings.json" "$1" "$2" <<'PY'
import json, os, sys
p, op, src = sys.argv[1:]
os.makedirs(os.path.dirname(p), exist_ok=True)
d = json.load(open(p)) if os.path.exists(p) else {}
pk = d.setdefault("packages", [])
if op == "install":
    pk.append(src)
elif op == "remove":
    d["packages"] = [x for x in pk if x != src]
json.dump(d, open(p, "w"), indent=2)
PY
EOF
printf '#!/usr/bin/env bash\nexit 0\n' >"$TMP/bin/claude"
chmod +x "$TMP/bin/pi" "$TMP/bin/claude"
cp "$TMP/bin/pi" "$TMP/bin-noclaude/pi"

mkdir -p "$TMP/sys"
for tool in bash python3 grep mkdir ln readlink stat chmod cat dirname; do
    ln -s "$(command -v "$tool")" "$TMP/sys/$tool"
done
BASH_BIN="$(command -v bash)"
run() { # <home> <bin-dir> <mode>
    env -i HOME="$1" PATH="$2:$TMP/sys" "$BASH_BIN" "$RECON" "$3"
}
setting() { # <home> <key>
    python3 -c 'import json,sys; print(json.dumps(json.load(open(sys.argv[1])).get(sys.argv[2])))' \
        "$1/.pi/pstack/settings.json" "$2"
}
tree() { # <home>: every path under the home with its type, mode and link target
    (cd "$1" && find . -print | sort | while IFS= read -r p; do
        if [[ -L "$p" ]]; then echo "$p -> $(readlink "$p")"
        else echo "$p $(stat -c %a "$p" 2>/dev/null || stat -f %Lp "$p") $( [[ -f "$p" ]] && cksum <"$p")"; fi
    done)
}
mode_of() { stat -c %a "$1" 2>/dev/null || stat -f %Lp "$1"; }

check "pin read from the ledger is a full commit" "yes" "$(yes_if grep -qE '^[0-9a-f]{40}$' <<<"$PIN")"
check "the script does not copy the pin" "no" "$(yes_if grep -qF "$PIN" "$RECON")"
check "the sheet turns the session hook off" "yes" "$(yes_if grep -qx 'session hook: off' "$SHEET")"
check "the sheet maps sonnet to claude-sonnet-5-5" "yes" "$(yes_if grep -q 'sonnet=claude-code/claude-sonnet-5-5' "$SHEET")"

# Fresh host: a main Pi directory exists, no pstack directory.
H="$TMP/home-fresh"
mkdir -p "$H/.pi/agent"
printf '{"defaultProvider": "anthropic", "packages": []}\n' >"$H/.pi/agent/settings.json"
before_main="$(tree "$H/.pi/agent")"
before="$(tree "$H")"

out="$(run "$H" "$TMP/bin" --check)"; rc=$?
check "check exits 0" "0" "$rc"
check "check reports the claude-code package" "yes" "$(yes_if grep -qF "MISSING package $CC" <<<"$out")"
check "check reports the pinned port" "yes" "$(yes_if grep -qF "MISSING package $PSTACK" <<<"$out")"
check "check reports the default model" "yes" "$(yes_if grep -qF 'WOULD SET defaultModel <unset> -> claude-opus-5-5' <<<"$out")"
check "check reports auth.json" "yes" "$(yes_if grep -q 'MISSING .*/auth.json' <<<"$out")"
check "check changes nothing" "$before" "$(tree "$H")"

out="$(run "$H" "$TMP/bin" --apply)"; rc=$?
check "apply exits 0" "0" "$rc"
check "apply installs both packages into the pstack directory" \
    "$H/.pi/pstack install $CC|$H/.pi/pstack install $PSTACK" "$(paste -sd'|' "$H/pi-calls")"
check "apply lists both packages" "[\"$CC\", \"$PSTACK\"]" "$(setting "$H" packages)"
check "apply sets the provider" '"claude-code"' "$(setting "$H" defaultProvider)"
check "apply sets the model" '"claude-opus-5-5"' "$(setting "$H" defaultModel)"
check "apply links the model sheet" "$SHEET" "$(readlink "$H/.pi/pstack/pstack-models.md")"
check "apply links AGENTS.md" "$INSTRUCTIONS" "$(readlink "$H/.pi/pstack/AGENTS.md")"
check "auth.json is mode 600" "600" "$(mode_of "$H/.pi/pstack/auth.json")"
# shellcheck disable=SC2016 # the literal command Pi runs, not expanded here
check "auth.json reads the key with a command" '!cat "$HOME/.secrets/opencode-api-key"' \
    "$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["opencode-go"]["key"])' "$H/.pi/pstack/auth.json")"
check "auth.json entry is an api key" '"api_key"' \
    "$(python3 -c 'import json,sys; print(json.dumps(json.load(open(sys.argv[1]))["opencode-go"]["type"]))' "$H/.pi/pstack/auth.json")"
check "the main Pi directory is untouched" "$before_main" "$(tree "$H/.pi/agent")"

after="$(tree "$H")"
out="$(run "$H" "$TMP/bin" --apply)"
check "second apply changes nothing" "$after" "$(tree "$H")"
check "second apply calls pi for nothing" "2" "$(wc -l <"$H/pi-calls" | tr -d ' ')"
check "second apply reports only ok" "0" "$(grep -vc -e '  ok:' -e '^Pi pstack' <<<"$out")"
out="$(run "$H" "$TMP/bin" --check)"
check "check after apply reports only ok" "0" "$(grep -vc -e '  ok:' -e '^Pi pstack' <<<"$out")"

# Existing directory: another pin of the port, foreign files, an auth.json
# without the entry, and a foreign AGENTS.md.
H="$TMP/home-existing"
D="$H/.pi/pstack"
mkdir -p "$D/sessions"
OLD="git:github.com/michael-denyer/pstack-claude@963781d11834918bf0951202d721c2e144777a70"
printf '{"theme": "dark", "defaultProvider": "ollama", "packages": ["%s", "npm:pi-web-access@0.48.0"]}\n' "$OLD" >"$D/settings.json"
printf '{"openai": {"type": "api_key", "key": "sk-test-secret"}}\n' >"$D/auth.json"
chmod 600 "$D/auth.json"
auth_before="$(cksum <"$D/auth.json")"
echo "mine" >"$D/AGENTS.md"
echo "notes" >"$D/sessions/keep.txt"
echo "local" >"$D/models-store.json"

out="$(run "$H" "$TMP/bin" --check)"
check "check names the old pin" "yes" "$(yes_if grep -qF "WOULD REMOVE $OLD" <<<"$out")"
check "check never prints auth.json" "no" "$(yes_if grep -q 'sk-test-secret' <<<"$out")"

out="$(run "$H" "$TMP/bin" --apply)"
check "apply removes the old pin and keeps other packages" \
    "[\"npm:pi-web-access@0.48.0\", \"$CC\", \"$PSTACK\"]" "$(setting "$H" packages)"
check "apply replaces an explicit provider" '"claude-code"' "$(setting "$H" defaultProvider)"
check "apply keeps other settings" '"dark"' "$(setting "$H" theme)"
check "apply leaves an existing auth.json byte for byte" "$auth_before" "$(cksum <"$D/auth.json")"
check "apply reports auth.json lacks the entry" "yes" "$(yes_if grep -q 'no opencode-go entry' <<<"$out")"
check "apply never prints auth.json" "no" "$(yes_if grep -q 'sk-test-secret' <<<"$out")"
check "apply keeps a foreign AGENTS.md" "mine" "$(cat "$D/AGENTS.md")"
check "apply warns about the foreign AGENTS.md" "yes" "$(yes_if grep -q "WARNING: $D/AGENTS.md" <<<"$out")"
check "apply keeps foreign files" "notes local" "$(cat "$D/sessions/keep.txt") $(cat "$D/models-store.json")"

# Links into another checkout of this repository are repointed; others are kept.
H="$TMP/home-checkouts"
D="$H/.pi/pstack"
mkdir -p "$D"
ln -s /elsewhere/dotfiles/dot-pi/agent/AGENTS.md "$D/AGENTS.md"
ln -s /elsewhere/my-models.md "$D/pstack-models.md"
out="$(run "$H" "$TMP/bin" --check)"
check "check names the link to repoint" "yes" "$(yes_if grep -q "WOULD REPOINT $D/AGENTS.md" <<<"$out")"
check "check leaves the link" "/elsewhere/dotfiles/dot-pi/agent/AGENTS.md" "$(readlink "$D/AGENTS.md")"
run "$H" "$TMP/bin" --apply >/dev/null
check "apply repoints a link from another checkout" "$INSTRUCTIONS" "$(readlink "$D/AGENTS.md")"
check "apply keeps a link elsewhere" "/elsewhere/my-models.md" "$(readlink "$D/pstack-models.md")"

# PI_PSTACK_DIR moves the directory.
H="$TMP/home-override"
mkdir -p "$H"
env -i HOME="$H" PATH="$TMP/bin:$TMP/sys" PI_PSTACK_DIR="$H/elsewhere" "$BASH_BIN" "$RECON" --apply >/dev/null
check "PI_PSTACK_DIR is honoured" "yes" "$(yes_if test -f "$H/elsewhere/settings.json")"
check "PI_PSTACK_DIR leaves ~/.pi alone" "no" "$(yes_if test -e "$H/.pi")"

# Without the claude CLI nothing changes.
H="$TMP/home-noclaude"
mkdir -p "$H"
out="$(run "$H" "$TMP/bin-noclaude" --apply)"; rc=$?
check "no claude: exits 0 and skips" "0 yes" "$rc $(yes_if grep -q Skipped <<<"$out")"
check "no claude: no directory" "no" "$(yes_if test -e "$H/.pi/pstack")"

check "bad usage exits 2" "2" "$(bash "$RECON" >/dev/null 2>&1; echo $?)"
check "setup-platform-configs runs the reconciler" "yes" \
    "$(yes_if grep -qF 'scripts/reconcile-pi-pstack.sh" --apply' "$REPO_ROOT/setup-platform-configs.sh")"

echo "$TESTS tests, $FAILURES failures"
[[ $FAILURES -eq 0 ]]
