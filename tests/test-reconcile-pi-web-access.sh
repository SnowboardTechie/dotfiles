#!/usr/bin/env bash
# Tests for scripts/reconcile-pi-web-access.sh. Uses a stub `pi` command and
# temporary HOME directories, removed on exit.

set -u

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RECON="$REPO_ROOT/scripts/reconcile-pi-web-access.sh"
PKG="$(sed -n 's/^PACKAGE="npm:\$NAME@\(.*\)"$/npm:pi-web-access@\1/p' "$RECON")"
TMP="$(mktemp -d "${TMPDIR:-/tmp}/pi-web-access-test-XXXXXX")"
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

# Stub pi: install appends, remove deletes, both edit settings.json and log the call.
mkdir -p "$TMP/bin" "$TMP/bin-nopi"
cat >"$TMP/bin/pi" <<'EOF'
#!/usr/bin/env bash
echo "$*" >>"$HOME/pi-calls"
python3 - "$HOME/.pi/agent/settings.json" "$1" "$2" <<'PY'
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
chmod +x "$TMP/bin/pi"

mkdir -p "$TMP/sys"
for tool in bash python3 grep; do ln -s "$(command -v "$tool")" "$TMP/sys/$tool"; done
BASH_BIN="$(command -v bash)"
run() { # <home> <bin-dir> <mode>
    env -i HOME="$1" PATH="$2:$TMP/sys" "$BASH_BIN" "$RECON" "$3"
}
packages() { # <home>
    python3 -c 'import json,sys; print(json.dumps(json.load(open(sys.argv[1])).get("packages")))' \
        "$1/.pi/agent/settings.json"
}

check "pin parsed from the script" "yes" "$([[ "$PKG" == npm:pi-web-access@[0-9]* ]] && echo yes || echo no)"

# Fresh host with another package already installed.
H="$TMP/home-fresh"
mkdir -p "$H/.pi/agent"
printf '{"theme": "dark", "packages": ["https://github.com/earendil-works/pi-claude-code"]}\n' >"$H/.pi/agent/settings.json"

out="$(run "$H" "$TMP/bin" --check)"; rc=$?
check "check exits 0 with drift" "0" "$rc"
check "check reports missing package" "yes" "$(grep -q "MISSING package $PKG" <<<"$out" && echo yes || echo no)"
check "check does not call pi" "no" "$([[ -f "$H/pi-calls" ]] && echo yes || echo no)"

out="$(run "$H" "$TMP/bin" --apply)"; rc=$?
check "apply exits 0" "0" "$rc"
check "apply installs the pin" "install $PKG" "$(cat "$H/pi-calls")"
check "apply keeps other packages" "[\"https://github.com/earendil-works/pi-claude-code\", \"$PKG\"]" "$(packages "$H")"

out="$(run "$H" "$TMP/bin" --apply)"
check "second apply calls nothing" "1" "$(wc -l <"$H/pi-calls" | tr -d ' ')"
check "second apply reports ok" "yes" "$(grep -q "ok: package $PKG" <<<"$out" && echo yes || echo no)"

# An older pin and an unpinned source are replaced.
H="$TMP/home-old"
mkdir -p "$H/.pi/agent"
printf '{"packages": ["npm:pi-web-access@0.40.0", "npm:pi-web-access", "npm:pi-web-access-lazy@0.1.3"]}\n' >"$H/.pi/agent/settings.json"
out="$(run "$H" "$TMP/bin" --check)"
check "check names the old pin" "yes" "$(grep -q 'WOULD REMOVE npm:pi-web-access@0.40.0' <<<"$out" && echo yes || echo no)"
run "$H" "$TMP/bin" --apply >/dev/null
check "apply swaps old versions, keeps similarly named package" "[\"npm:pi-web-access-lazy@0.1.3\", \"$PKG\"]" "$(packages "$H")"

# No settings.json at all.
H="$TMP/home-empty"
mkdir -p "$H"
run "$H" "$TMP/bin" --apply >/dev/null
check "empty host gets the pin" "[\"$PKG\"]" "$(packages "$H")"

# Without pi nothing happens.
H="$TMP/home-nopi"
mkdir -p "$H"
out="$(run "$H" "$TMP/bin-nopi" --apply)"; rc=$?
check "no pi: exits 0" "0" "$rc"
check "no pi: skipped" "yes" "$(grep -q Skipped <<<"$out" && echo yes || echo no)"

check "bad usage exits 2" "2" "$(bash "$RECON" >/dev/null 2>&1; echo $?)"
check "setup-omarchy registers reconciler" "yes" "$(grep -qF 'reconcile-pi-web-access.sh' "$REPO_ROOT/scripts/setup-omarchy.sh" && echo yes || echo no)"
check "setup-platform-configs runs reconciler" "yes" "$(grep -qF 'reconcile-pi-web-access.sh' "$REPO_ROOT/setup-platform-configs.sh" && echo yes || echo no)"

echo "$TESTS tests, $FAILURES failures"
[[ $FAILURES -eq 0 ]]
