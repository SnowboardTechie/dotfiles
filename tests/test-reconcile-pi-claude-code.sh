#!/usr/bin/env bash
# Tests for scripts/reconcile-pi-claude-code.sh. Uses stub `pi` and `claude`
# commands and temporary HOME directories, removed on exit.

set -u

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RECON="$REPO_ROOT/scripts/reconcile-pi-claude-code.sh"
PKG="https://github.com/earendil-works/pi-claude-code"
TMP="$(mktemp -d "${TMPDIR:-/tmp}/pi-claude-code-test-XXXXXX")"
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

# Stub pi: `pi install <src>` appends src to settings.json packages and logs the call.
mkdir -p "$TMP/bin" "$TMP/bin-noclaude"
cat >"$TMP/bin/pi" <<'EOF'
#!/usr/bin/env bash
echo "$*" >>"$HOME/pi-calls"
[[ "$1" == install ]] || exit 0
python3 - "$HOME/.pi/agent/settings.json" "$2" <<'PY'
import json, os, sys
p, src = sys.argv[1], sys.argv[2]
os.makedirs(os.path.dirname(p), exist_ok=True)
d = json.load(open(p)) if os.path.exists(p) else {}
d.setdefault("packages", []).append(src)
json.dump(d, open(p, "w"), indent=2)
PY
EOF
printf '#!/usr/bin/env bash\nexit 0\n' >"$TMP/bin/claude"
chmod +x "$TMP/bin/pi" "$TMP/bin/claude"
cp "$TMP/bin/pi" "$TMP/bin-noclaude/pi"

# Only the tools the reconciler and stubs need, so a real pi/claude can't leak in.
mkdir -p "$TMP/sys"
for tool in bash python3 mkdir; do ln -s "$(command -v "$tool")" "$TMP/sys/$tool"; done
BASH_BIN="$(command -v bash)"
run() { # <home> <bin-dir> <mode>
    env -i HOME="$1" PATH="$2:$TMP/sys" "$BASH_BIN" "$RECON" "$3"
}
setting() { # <home> <key>
    python3 -c 'import json,sys; d=json.load(open(sys.argv[1])); v=d.get(sys.argv[2]); print(json.dumps(v))' \
        "$1/.pi/agent/settings.json" "$2"
}

# Fresh host: anthropic default, direct subscription login.
H="$TMP/home-anthropic"
mkdir -p "$H/.pi/agent"
printf '{\n  "theme": "dark",\n  "defaultProvider": "anthropic"\n}\n' >"$H/.pi/agent/settings.json"
printf '{"anthropic": {"type": "oauth", "access": "x"}}\n' >"$H/.pi/agent/auth.json"
chmod 600 "$H/.pi/agent/settings.json"

out="$(run "$H" "$TMP/bin" --check)"; rc=$?
check "check exits 0 with drift" "0" "$rc"
check "check reports missing package" "yes" "$(grep -q "MISSING package $PKG" <<<"$out" && echo yes || echo no)"
check "check reports provider switch" "yes" "$(grep -q 'WOULD SET defaultProvider anthropic -> claude-code' <<<"$out" && echo yes || echo no)"
check "check notes the direct login" "yes" "$(grep -q '/logout' <<<"$out" && echo yes || echo no)"
check "check does not call pi install" "no" "$([[ -f "$H/pi-calls" ]] && echo yes || echo no)"
check "check leaves provider" '"anthropic"' "$(setting "$H" defaultProvider)"

out="$(run "$H" "$TMP/bin" --apply)"; rc=$?
check "apply exits 0" "0" "$rc"
check "apply installs the package" "install $PKG" "$(cat "$H/pi-calls")"
check "apply sets claude-code" '"claude-code"' "$(setting "$H" defaultProvider)"
check "apply keeps other settings" '"dark"' "$(setting "$H" theme)"
check "apply keeps settings mode" "600" "$(stat -c %a "$H/.pi/agent/settings.json" 2>/dev/null || stat -f %Lp "$H/.pi/agent/settings.json")"
check "apply leaves auth.json alone" "yes" "$(grep -q oauth "$H/.pi/agent/auth.json" && echo yes || echo no)"

out="$(run "$H" "$TMP/bin" --apply)"
check "second apply installs nothing" "1" "$(wc -l <"$H/pi-calls" | tr -d ' ')"
check "second apply reports ok" "2" "$(grep -c '  ok:' <<<"$out")"

# Explicit non-anthropic provider is left alone.
H="$TMP/home-other"
mkdir -p "$H/.pi/agent"
printf '{"defaultProvider": "ollama", "packages": ["%s"]}\n' "$PKG" >"$H/.pi/agent/settings.json"
run "$H" "$TMP/bin" --apply >/dev/null
check "explicit provider kept" '"ollama"' "$(setting "$H" defaultProvider)"

# No settings.json at all: provider is set.
H="$TMP/home-empty"
mkdir -p "$H"
run "$H" "$TMP/bin" --apply >/dev/null
check "unset provider set" '"claude-code"' "$(setting "$H" defaultProvider)"

# Without the claude CLI nothing changes.
H="$TMP/home-noclaude"
mkdir -p "$H/.pi/agent"
printf '{"defaultProvider": "anthropic"}\n' >"$H/.pi/agent/settings.json"
out="$(run "$H" "$TMP/bin-noclaude" --apply)"; rc=$?
check "no claude: exits 0" "0" "$rc"
check "no claude: skipped" "yes" "$(grep -q Skipped <<<"$out" && echo yes || echo no)"
check "no claude: provider kept" '"anthropic"' "$(setting "$H" defaultProvider)"

check "bad usage exits 2" "2" "$(bash "$RECON" >/dev/null 2>&1; echo $?)"
check "setup-omarchy registers reconciler" "yes" "$(grep -qF 'reconcile-pi-claude-code.sh' "$REPO_ROOT/scripts/setup-omarchy.sh" && echo yes || echo no)"

echo "$TESTS tests, $FAILURES failures"
[[ $FAILURES -eq 0 ]]
