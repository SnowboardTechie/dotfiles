#!/usr/bin/env bash
# Tests for scripts/reconcile-pi-packages.sh. Uses a stub `pi` command and
# temporary HOME directories, removed on exit.

set -u

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RECON="$REPO_ROOT/scripts/reconcile-pi-packages.sh"
WEB="npm:$(grep -oE '"pi-web-access@[^"]+"' "$RECON" | tr -d '"')"
HASH="npm:$(grep -oE '"@deathbeam/pi-hashline@[^"]+"' "$RECON" | tr -d '"')"
TMP="$(mktemp -d "${TMPDIR:-/tmp}/pi-packages-test-XXXXXX")"
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
mkdir -p "$TMP/bin" "$TMP/bin-nopi" "$TMP/bin-rg"
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
cp "$TMP/bin/pi" "$TMP/bin-rg/pi"
printf '#!/usr/bin/env bash\nexit 0\n' >"$TMP/bin-rg/rg"
chmod +x "$TMP/bin-rg/rg"

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

check "web pin parsed from the script" "yes" "$([[ "$WEB" == npm:pi-web-access@[0-9]* ]] && echo yes || echo no)"
check "hashline pin parsed from the script" "yes" "$([[ "$HASH" == npm:@deathbeam/pi-hashline@[0-9]* ]] && echo yes || echo no)"

# Fresh host with another package already installed.
H="$TMP/home-fresh"
mkdir -p "$H/.pi/agent"
printf '{"theme": "dark", "packages": ["https://github.com/earendil-works/pi-claude-code"]}\n' >"$H/.pi/agent/settings.json"

out="$(run "$H" "$TMP/bin-rg" --check)"; rc=$?
check "check exits 0 with drift" "0" "$rc"
check "check reports missing web package" "yes" "$(grep -q "MISSING package $WEB" <<<"$out" && echo yes || echo no)"
check "check reports missing hashline" "yes" "$(grep -q "MISSING package $HASH" <<<"$out" && echo yes || echo no)"
check "check does not call pi" "no" "$([[ -f "$H/pi-calls" ]] && echo yes || echo no)"

out="$(run "$H" "$TMP/bin-rg" --apply)"; rc=$?
check "apply exits 0" "0" "$rc"
check "apply installs both pins" "install $WEB|install $HASH" "$(paste -sd'|' "$H/pi-calls")"
check "apply keeps other packages" "[\"https://github.com/earendil-works/pi-claude-code\", \"$WEB\", \"$HASH\"]" "$(packages "$H")"
check "no rg warning when rg exists" "no" "$(grep -q 'rg (ripgrep)' <<<"$out" && echo yes || echo no)"

out="$(run "$H" "$TMP/bin-rg" --apply)"
check "second apply calls nothing" "2" "$(wc -l <"$H/pi-calls" | tr -d ' ')"
check "second apply reports both ok" "2" "$(grep -c '  ok: package' <<<"$out")"

# An older pin and an unpinned source are replaced; similarly named packages stay.
H="$TMP/home-old"
mkdir -p "$H/.pi/agent"
printf '{"packages": ["npm:pi-web-access@0.40.0", "npm:pi-web-access", "npm:pi-web-access-lazy@0.1.3", "npm:@deathbeam/pi-hashline@0.0.10", "npm:pi-hashline-edit@1.0.0"]}\n' >"$H/.pi/agent/settings.json"
out="$(run "$H" "$TMP/bin-rg" --check)"
check "check names the old web pin" "yes" "$(grep -q 'WOULD REMOVE npm:pi-web-access@0.40.0' <<<"$out" && echo yes || echo no)"
check "check names the old hashline pin" "yes" "$(grep -q 'WOULD REMOVE npm:@deathbeam/pi-hashline@0.0.10' <<<"$out" && echo yes || echo no)"
run "$H" "$TMP/bin-rg" --apply >/dev/null
check "apply swaps old versions, keeps similarly named packages" \
    "[\"npm:pi-web-access-lazy@0.1.3\", \"npm:pi-hashline-edit@1.0.0\", \"$WEB\", \"$HASH\"]" "$(packages "$H")"

# No settings.json at all, and no rg.
H="$TMP/home-empty"
mkdir -p "$H"
out="$(run "$H" "$TMP/bin" --apply)"
check "empty host gets both pins" "[\"$WEB\", \"$HASH\"]" "$(packages "$H")"
check "missing rg is reported" "yes" "$(grep -q 'WARNING: rg (ripgrep) is not installed' <<<"$out" && echo yes || echo no)"

# Without pi nothing happens.
H="$TMP/home-nopi"
mkdir -p "$H"
out="$(run "$H" "$TMP/bin-nopi" --apply)"; rc=$?
check "no pi: exits 0" "0" "$rc"
check "no pi: skipped" "yes" "$(grep -q Skipped <<<"$out" && echo yes || echo no)"

check "bad usage exits 2" "2" "$(bash "$RECON" >/dev/null 2>&1; echo $?)"
check "setup-omarchy registers reconciler" "yes" "$(grep -qF 'reconcile-pi-packages.sh' "$REPO_ROOT/scripts/setup-omarchy.sh" && echo yes || echo no)"
check "setup-platform-configs runs reconciler" "yes" "$(grep -qF 'reconcile-pi-packages.sh' "$REPO_ROOT/setup-platform-configs.sh" && echo yes || echo no)"
check "reconcile-pi-extensions links stream-rules" "yes" "$(grep -qF 'extensions/stream-rules.ts' "$REPO_ROOT/scripts/reconcile-pi-extensions.sh" && echo yes || echo no)"

echo "$TESTS tests, $FAILURES failures"
[[ $FAILURES -eq 0 ]]
