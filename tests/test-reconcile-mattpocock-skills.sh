#!/usr/bin/env bash
# Tests for scripts/reconcile-mattpocock-skills.sh. Uses a stub `pi`, a local
# stand-in git repository for upstream and a copy of the script beside its own
# ledger, all under one temporary directory removed on exit. No network.

set -u

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TMP="$(mktemp -d "${TMPDIR:-/tmp}/mattpocock-skills-test-XXXXXX")"
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
yn() { "$@" && echo yes || echo no; }

# Stand-in upstream with two commits.
UP="$TMP/upstream"
git init --quiet "$UP"
gitc() { git -C "$UP" -c user.name=t -c user.email=t@example.invalid -c commit.gpgsign=false "$@"; }
mkdir -p "$UP/skills/engineering/tdd" "$UP/skills/productivity/teach" "$UP/skills/misc/x"
for s in engineering/tdd productivity/teach misc/x; do
    printf -- '---\nname: %s\ndescription: d\n---\n' "${s#*/}" >"$UP/skills/$s/SKILL.md"
done
gitc add -A && gitc commit --quiet -m one
C1="$(git -C "$UP" rev-parse HEAD)"
echo "more" >>"$UP/skills/engineering/tdd/SKILL.md"
gitc commit --quiet -am two
C2="$(git -C "$UP" rev-parse HEAD)"

# The script reads its ledger relative to itself, so give it a copy whose pin
# and upstream the tests control.
SCRIPTS="$TMP/repo/scripts"
LEDGER="$TMP/repo/dot-agents/upstreams/mattpocock-skills.json"
mkdir -p "$SCRIPTS" "${LEDGER%/*}"
cp "$REPO_ROOT/scripts/reconcile-mattpocock-skills.sh" "$SCRIPTS/"
pin() { # <commit>
    python3 - "$REPO_ROOT/dot-agents/upstreams/mattpocock-skills.json" "$LEDGER" "$UP" "$1" <<'PY'
import json, sys
src, dst, up, commit = sys.argv[1:]
d = json.load(open(src))
d["upstream"], d["commit"] = up, commit
json.dump(d, open(dst, "w"), indent=2)
PY
}

mkdir -p "$TMP/bin" "$TMP/bin-nopi" "$TMP/sys"
printf '#!/usr/bin/env bash\necho "pi $*" >>"$HOME/pi-calls"\n' >"$TMP/bin/pi"
chmod +x "$TMP/bin/pi"
for tool in bash python3 git grep mkdir mv rm cat; do ln -s "$(command -v "$tool")" "$TMP/sys/$tool"; done
BASH_BIN="$(command -v bash)"
run() { # <home> <bin-dir> <mode>
    env -i HOME="$1" PATH="$2:$TMP/sys" "$BASH_BIN" "$SCRIPTS/reconcile-mattpocock-skills.sh" "$3"
}
settings() { # <home>
    python3 -c 'import json,sys; print(json.dumps(json.load(open(sys.argv[1])), sort_keys=True))' \
        "$1/.pi/agent/settings.json"
}
snapshot() { # <home>: every path and content hash under it
    (cd "$1" && find . -print0 | LC_ALL=C sort -z | xargs -0 ls -ld 2>/dev/null | awk '{print $1, $5, $NF}'
     find . -type f -print0 | LC_ALL=C sort -z | xargs -0 cat 2>/dev/null | shasum)
}

check "real ledger pin is a full SHA" "yes" \
    "$(yn grep -qE '"commit": "[0-9a-f]{40}"' "$REPO_ROOT/dot-agents/upstreams/mattpocock-skills.json")"
check "the pin lives only in the ledger" "no" \
    "$(yn grep -qE '[0-9a-f]{40}' "$REPO_ROOT/scripts/reconcile-mattpocock-skills.sh")"

pin "$C1"
H="$TMP/home-fresh"
CO="$H/.pi/agent/upstreams/mattpocock-skills"
ENG="$CO/skills/engineering"
PROD="$CO/skills/productivity"
mkdir -p "$H/.pi/agent"
printf '{"theme": "dark", "packages": ["npm:pi-web-access@0.48.0"], "skills": ["/opt/other-skills"]}\n' \
    >"$H/.pi/agent/settings.json"

before="$(snapshot "$H")"
out="$(run "$H" "$TMP/bin" --check)"; rc=$?
check "check exits 0 with drift" "0" "$rc"
check "check reports the pin" "yes" "$(yn grep -qF "pin: $C1" <<<"$out")"
check "check reports the missing checkout" "yes" "$(yn grep -q 'checkout: missing' <<<"$out")"
check "check reports missing engineering entry" "yes" "$(yn grep -qF "MISSING settings entry $ENG" <<<"$out")"
check "check reports missing productivity entry" "yes" "$(yn grep -qF "MISSING settings entry $PROD" <<<"$out")"
check "check changes nothing" "$before" "$(snapshot "$H")"

out="$(run "$H" "$TMP/bin" --apply)"; rc=$?
check "apply exits 0" "0" "$rc"
check "apply clones at the pin" "$C1" "$(git -C "$CO" rev-parse HEAD 2>/dev/null)"
check "apply's checkout is clean" "" "$(git -C "$CO" status --porcelain 2>&1)"
check "apply keeps other keys and skills entries, adds both" \
    "{\"packages\": [\"npm:pi-web-access@0.48.0\"], \"skills\": [\"/opt/other-skills\", \"$ENG\", \"$PROD\"], \"theme\": \"dark\"}" \
    "$(settings "$H")"
check "apply calls no pi command" "no" "$(yn test -f "$H/pi-calls")"
check "no partial clone left behind" "" "$(ls "$H/.pi/agent/upstreams" | grep partial)"

before="$(snapshot "$H")"
out="$(run "$H" "$TMP/bin" --apply)"; rc=$?
check "second apply exits 0" "0" "$rc"
check "second apply changes nothing" "$before" "$(snapshot "$H")"
check "second apply reports ok" "yes" "$(yn grep -q 'ok: checkout at the pin' <<<"$out")"

out="$(run "$H" "$TMP/bin" --check)"
check "check after apply: both entries ok" "2" "$(grep -c 'ok: settings entry' <<<"$out")"

# A moved pin moves the checkout; --check reports it first without moving it.
pin "$C2"
out="$(run "$H" "$TMP/bin" --check)"
check "check names the stale checkout" "yes" "$(yn grep -qF "checkout: $C1 (not the pin)" <<<"$out")"
check "check does not move the checkout" "$C1" "$(git -C "$CO" rev-parse HEAD)"
out="$(run "$H" "$TMP/bin" --apply)"; rc=$?
check "moved pin: apply exits 0" "0" "$rc"
check "moved pin: checkout follows" "$C2" "$(git -C "$CO" rev-parse HEAD)"
check "moved pin: entries not duplicated" "2" \
    "$(python3 -c 'import json,sys; s=json.load(open(sys.argv[1]))["skills"]; print(len([x for x in s if "mattpocock" in x]))' "$H/.pi/agent/settings.json")"

# A pin the checkout has never seen is fetched from upstream.
pin "$C1"
run "$H" "$TMP/bin" --apply >/dev/null
echo "three" >>"$UP/skills/productivity/teach/SKILL.md"
gitc commit --quiet -am three
C3="$(git -C "$UP" rev-parse HEAD)"
pin "$C3"
out="$(run "$H" "$TMP/bin" --apply)"; rc=$?
check "unseen pin: fetched and moved" "0 $C3" "$rc $(git -C "$CO" rev-parse HEAD)"

# A dirty checkout stops with a report and keeps the modification.
pin "$C2"
echo "local edit" >>"$CO/skills/engineering/tdd/SKILL.md"
out="$(run "$H" "$TMP/bin" --apply 2>&1)"; rc=$?
check "dirty: apply fails" "1" "$rc"
check "dirty: reports local modifications" "yes" "$(yn grep -q 'STOPPED: .* has local modifications' <<<"$out")"
check "dirty: checkout not moved" "$C3" "$(git -C "$CO" rev-parse HEAD)"
check "dirty: modification kept" "yes" "$(yn grep -q 'local edit' "$CO/skills/engineering/tdd/SKILL.md")"
out="$(run "$H" "$TMP/bin" --check)"; rc=$?
check "dirty: check exits 0 and reports it" "0 yes" "$rc $(yn grep -q 'with local modifications' <<<"$out")"

# An untracked file counts as a local modification.
H="$TMP/home-untracked"
mkdir -p "$H"
pin "$C1"
run "$H" "$TMP/bin" --apply >/dev/null
touch "$H/.pi/agent/upstreams/mattpocock-skills/notes.txt"
pin "$C2"
out="$(run "$H" "$TMP/bin" --apply 2>&1)"; rc=$?
check "untracked file: apply stops" "1 $C1" "$rc $(git -C "$H/.pi/agent/upstreams/mattpocock-skills" rev-parse HEAD)"

# Some other repository in the checkout's place stops with a report.
H="$TMP/home-foreign"
mkdir -p "$H/.pi/agent/upstreams/mattpocock-skills"
git init --quiet "$H/.pi/agent/upstreams/mattpocock-skills"
git -C "$H/.pi/agent/upstreams/mattpocock-skills" remote add origin https://example.invalid/other.git
out="$(run "$H" "$TMP/bin" --apply 2>&1)"; rc=$?
check "foreign repository: apply fails" "1" "$rc"
check "foreign repository: reported" "yes" "$(yn grep -q 'is not a checkout of' <<<"$out")"
check "foreign repository: origin untouched" "https://example.invalid/other.git" \
    "$(git -C "$H/.pi/agent/upstreams/mattpocock-skills" config remote.origin.url)"
check "foreign repository: settings untouched" "no" "$(yn test -f "$H/.pi/agent/settings.json")"

# A plain directory in the checkout's place is foreign too.
H="$TMP/home-plain"
mkdir -p "$H/.pi/agent/upstreams/mattpocock-skills"
echo keep >"$H/.pi/agent/upstreams/mattpocock-skills/file"
out="$(run "$H" "$TMP/bin" --apply 2>&1)"; rc=$?
check "plain directory: apply stops, keeps file" "1 keep" "$rc $(cat "$H/.pi/agent/upstreams/mattpocock-skills/file")"

# A local copy of one of his promoted names is warned about, never removed.
H="$TMP/home-shadow"
mkdir -p "$H"
pin "$C1"
out="$(run "$H" "$TMP/bin" --apply)"
check "no colliding copy: apply prints no warning" "no" "$(yn grep -q WARNING <<<"$out")"
out="$(run "$H" "$TMP/bin" --check)"
check "no colliding copy: check prints no warning" "no" "$(yn grep -q WARNING <<<"$out")"
mkdir -p "$H/.agents/skills/tdd" "$H/.pi/agent/skills" "$H/pool/teach" "$H/.agents/skills/misc-x"
echo local >"$H/.agents/skills/tdd/SKILL.md"
ln -s "$H/pool/teach" "$H/.pi/agent/skills/teach"
ln -s "$H/pool/x" "$H/.agents/skills/x"   # unpromoted upstream name, and dangling
out="$(run "$H" "$TMP/bin" --check)"; rc=$?
check "colliding copy: check exits 0" "0" "$rc"
check "colliding copy: check warns about ~/.agents/skills" "yes" \
    "$(yn grep -qF "WARNING: $H/.agents/skills/tdd shares a name with his tdd" <<<"$out")"
check "colliding copy: check warns about ~/.pi/agent/skills" "yes" \
    "$(yn grep -qF "WARNING: $H/.pi/agent/skills/teach shares a name with his teach" <<<"$out")"
check "colliding copy: exactly those two warnings" "2" "$(grep -c WARNING <<<"$out")"
out="$(run "$H" "$TMP/bin" --apply)"; rc=$?
check "colliding copy: apply exits 0 and warns" "0 2" "$rc $(grep -c WARNING <<<"$out")"
check "colliding copy: nothing removed" "yes yes" \
    "$(yn test -f "$H/.agents/skills/tdd/SKILL.md") $(yn test -L "$H/.pi/agent/skills/teach")"

# No settings.json at all.
H="$TMP/home-empty"
mkdir -p "$H"
pin "$C1"
run "$H" "$TMP/bin" --apply >/dev/null
check "empty home: settings created with both entries" \
    "{\"skills\": [\"$H/.pi/agent/upstreams/mattpocock-skills/skills/engineering\", \"$H/.pi/agent/upstreams/mattpocock-skills/skills/productivity\"]}" \
    "$(settings "$H")"

# Without pi nothing happens.
H="$TMP/home-nopi"
mkdir -p "$H"
out="$(run "$H" "$TMP/bin-nopi" --apply)"; rc=$?
check "no pi: exits 0" "0" "$rc"
check "no pi: skipped" "yes" "$(yn grep -q 'Skipped (pi is not installed)' <<<"$out")"
check "no pi: nothing written" "" "$(ls -A "$H")"

# Without git nothing happens.
mkdir -p "$TMP/sys-nogit"
for tool in bash python3 grep; do ln -s "$(command -v "$tool")" "$TMP/sys-nogit/$tool"; done
H="$TMP/home-nogit"
mkdir -p "$H"
out="$(env -i HOME="$H" PATH="$TMP/bin:$TMP/sys-nogit" "$BASH_BIN" "$SCRIPTS/reconcile-mattpocock-skills.sh" --apply)"; rc=$?
check "no git: exits 0 and skips" "0 yes" "$rc $(yn grep -q 'Skipped (git is not installed)' <<<"$out")"

check "bad usage exits 2" "2" "$(bash "$REPO_ROOT/scripts/reconcile-mattpocock-skills.sh" >/dev/null 2>&1; echo $?)"
check "setup-omarchy registers reconciler after pi-packages" "yes" \
    "$(yn bash -c 'grep -A1 -F "reconcile-pi-packages.sh\"" "$1" | grep -qF reconcile-mattpocock-skills.sh' _ "$REPO_ROOT/scripts/setup-omarchy.sh")"
check "setup-platform-configs runs reconciler" "yes" \
    "$(yn grep -qF 'reconcile-mattpocock-skills.sh" --apply' "$REPO_ROOT/setup-platform-configs.sh")"

echo "$TESTS tests, $FAILURES failures"
[[ $FAILURES -eq 0 ]]
