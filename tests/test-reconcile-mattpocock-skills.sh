#!/usr/bin/env bash
# Tests for scripts/reconcile-mattpocock-skills.sh: the shared checkout, Pi's
# settings and the Claude Code and OpenCode links. Uses a stub `pi`, a local
# fake of his repository (the skill source) and a copy of the script beside its
# own source record, all under one temporary directory removed on exit. No network.

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

# A fake of the skill source's repository with two commits.
UP="$TMP/skill-source"
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

# The script reads its source record relative to itself, so give it a copy whose pin
# and skill source the tests control.
SCRIPTS="$TMP/repo/scripts"
SOURCE_RECORD="$TMP/repo/dot-agents/skill-sources/mattpocock-skills.json"
mkdir -p "$SCRIPTS" "${SOURCE_RECORD%/*}"
cp "$REPO_ROOT/scripts/reconcile-mattpocock-skills.sh" "$SCRIPTS/"
pin() { # <commit>
    python3 - "$REPO_ROOT/dot-agents/skill-sources/mattpocock-skills.json" "$SOURCE_RECORD" "$UP" "$1" <<'PY'
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
for tool in bash python3 git grep mkdir mv rm cat sed readlink rmdir ln; do ln -s "$(command -v "$tool")" "$TMP/sys/$tool"; done
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

check "real source record pin is a full SHA" "yes" \
    "$(yn grep -qE '"commit": "[0-9a-f]{40}"' "$REPO_ROOT/dot-agents/skill-sources/mattpocock-skills.json")"
check "the pin lives only in the source record" "no" \
    "$(yn grep -qE '[0-9a-f]{40}' "$REPO_ROOT/scripts/reconcile-mattpocock-skills.sh")"

# More history in the skill source: C3 changes teach; C4 drops teach and promotes zoom-out.
echo "three" >>"$UP/skills/productivity/teach/SKILL.md"
gitc commit --quiet -am three
C3="$(git -C "$UP" rev-parse HEAD)"
gitc rm --quiet -r skills/productivity/teach
mkdir -p "$UP/skills/engineering/zoom-out"
printf -- '---\nname: zoom-out\ndescription: d\n---\n' >"$UP/skills/engineering/zoom-out/SKILL.md"
gitc add -A && gitc commit --quiet -m four
C4="$(git -C "$UP" rev-parse HEAD)"
git -C "$UP" -c advice.detachedHead=false checkout --quiet --detach "$C1"   # the skill source's own checkout must not matter

run_env() { # <home> <bin-dir> <mode> [VAR=value...]
    local h="$1" b="$2" m="$3"; shift 3
    env -i HOME="$h" PATH="$b:$TMP/sys" "$@" "$BASH_BIN" "$SCRIPTS/reconcile-mattpocock-skills.sh" "$m"
}
links() { # <dir>: "name -> target" for every link in it
    local l
    for l in "$1"/*; do [[ -L "$l" ]] && echo "${l##*/} -> $(readlink "$l")"; done
}

pin "$C1"
H="$TMP/home-fresh"
CO="$H/.local/share/mattpocock-skills"
ENG="$CO/skills/engineering"
PROD="$CO/skills/productivity"
CL="$H/.claude/skills"
OC="$H/.config/opencode/skills"
mkdir -p "$H/.pi/agent"
printf '{"theme": "dark", "packages": ["npm:pi-web-access@0.48.0"], "skills": ["/opt/other-skills"]}\n' \
    >"$H/.pi/agent/settings.json"

before="$(snapshot "$H")"
out="$(run "$H" "$TMP/bin" --check)"; rc=$?
check "check exits 0 with drift" "0" "$rc"
check "check reports the pin" "yes" "$(yn grep -qF "pin: $C1" <<<"$out")"
check "check reports the missing checkout" "yes" "$(yn grep -qF "checkout: missing ($CO)" <<<"$out")"
check "check reports missing engineering entry" "yes" "$(yn grep -qF "MISSING Pi settings entry $ENG" <<<"$out")"
check "check reports missing productivity entry" "yes" "$(yn grep -qF "MISSING Pi settings entry $PROD" <<<"$out")"
check "check without a checkout says links wait for one" "yes" "$(yn grep -q 'promoted list is unknown' <<<"$out")"
check "check changes nothing" "$before" "$(snapshot "$H")"

out="$(run "$H" "$TMP/bin" --apply)"; rc=$?
check "apply exits 0" "0" "$rc"
check "apply clones at the pin into ~/.local/share" "$C1" "$(git -C "$CO" rev-parse HEAD 2>/dev/null)"
check "apply's checkout is clean" "" "$(git -C "$CO" status --porcelain 2>&1)"
check "apply keeps other keys and skills entries, adds both" \
    "{\"packages\": [\"npm:pi-web-access@0.48.0\"], \"skills\": [\"/opt/other-skills\", \"$ENG\", \"$PROD\"], \"theme\": \"dark\"}" \
    "$(settings "$H")"
check "apply calls no pi command" "no" "$(yn test -f "$H/pi-calls")"
check "no partial clone left behind" "" "$(ls "$H/.local/share" | grep partial)"
check "nothing left under ~/.pi/agent/upstreams" "no" "$(yn test -e "$H/.pi/agent/upstreams")"
check "fresh home: Claude Code gets a link per promoted skill" \
    "$(printf 'tdd -> %s\nteach -> %s' "$ENG/tdd" "$PROD/teach")" "$(links "$CL")"
check "fresh home: OpenCode gets a link per promoted skill" \
    "$(printf 'tdd -> %s\nteach -> %s' "$ENG/tdd" "$PROD/teach")" "$(links "$OC")"
check "fresh home: links resolve to a SKILL.md" "yes yes" \
    "$(yn test -f "$CL/tdd/SKILL.md") $(yn test -f "$OC/teach/SKILL.md")"
check "fresh home: the unpromoted skill gets no link" "no no" "$(yn test -e "$CL/x") $(yn test -e "$OC/x")"

before="$(snapshot "$H")"
out="$(run "$H" "$TMP/bin" --apply)"; rc=$?
check "second apply exits 0" "0" "$rc"
check "second apply changes nothing" "$before" "$(snapshot "$H")"
check "second apply reports ok" "yes" "$(yn grep -q 'ok: checkout at the pin' <<<"$out")"
check "second apply creates, repoints and removes nothing" "2" \
    "$(grep -c 'summary: 0 create, 0 repoint, 2 ok, 0 remove, 0 kept' <<<"$out")"

out="$(run "$H" "$TMP/bin" --check)"
check "check after apply: both entries ok" "2" "$(grep -c 'ok: Pi settings entry' <<<"$out")"
check "check after apply: no link to change" "0" "$(grep -c 'would ' <<<"$out")"

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

# A pin the checkout has never seen is fetched from the skill source.
pin "$C3"
out="$(run "$H" "$TMP/bin" --apply)"; rc=$?
check "unseen pin: fetched and moved" "0 $C3" "$rc $(git -C "$CO" rev-parse HEAD)"

# Foreign entries of the same names survive and are reported; links stay put.
H="$TMP/home-foreign-links"
mkdir -p "$H/.claude/skills/tdd" "$H/elsewhere/teach" "$H/.config/opencode/skills"
echo mine >"$H/.claude/skills/tdd/SKILL.md"
ln -s "$H/elsewhere/teach" "$H/.claude/skills/teach"
ln -s "$H/elsewhere/teach" "$H/.config/opencode/skills/tdd"
pin "$C1"
out="$(run "$H" "$TMP/bin" --apply)"; rc=$?
check "foreign entries: apply exits 0" "0" "$rc"
check "foreign entries: real directory kept" "mine" "$(cat "$H/.claude/skills/tdd/SKILL.md")"
check "foreign entries: foreign link kept" "$H/elsewhere/teach" "$(readlink "$H/.claude/skills/teach")"
check "foreign entries: OpenCode foreign link kept" "$H/elsewhere/teach" "$(readlink "$H/.config/opencode/skills/tdd")"
check "foreign entries: directory reported" "yes" \
    "$(yn grep -qF "WARNING: $H/.claude/skills/tdd exists and is not a link; kept" <<<"$out")"
check "foreign entries: link reported" "yes" \
    "$(yn grep -qF "WARNING: $H/.claude/skills/teach is a link to $H/elsewhere/teach; kept" <<<"$out")"
check "foreign entries: the free name is still linked" \
    "$H/.local/share/mattpocock-skills/skills/productivity/teach" "$(readlink "$H/.config/opencode/skills/teach")"
out="$(run "$H" "$TMP/bin" --check)"
check "foreign entries: check reports them too" "3" "$(grep -c 'WARNING: .* kept' <<<"$out")"

# A skill the skill source no longer promotes loses its link; a new one gains one; own
# stale links are repointed.
H="$TMP/home-dropped"
mkdir -p "$H"
pin "$C3"
run "$H" "$TMP/bin" --apply >/dev/null
CO="$H/.local/share/mattpocock-skills"
ln -sfn "$H/.local/share/mattpocock-skills/skills/productivity/tdd" "$H/.claude/skills/tdd"   # own, wrong group
pin "$C4"
out="$(run "$H" "$TMP/bin" --check)"
check "dropped: check plans the removal" "yes" "$(yn grep -qF 'would remove: Claude Code/teach (no longer promoted)' <<<"$out")"
check "dropped: check plans the new link" "yes" "$(yn grep -qF "would create: OpenCode/zoom-out -> $CO/skills/engineering/zoom-out" <<<"$out")"
check "dropped: check plans the repoint" "yes" "$(yn grep -qF "would repoint: Claude Code/tdd -> $CO/skills/engineering/tdd" <<<"$out")"
check "dropped: check leaves the link" "yes" "$(yn test -L "$H/.claude/skills/teach")"
out="$(run "$H" "$TMP/bin" --apply)"; rc=$?
check "dropped: apply exits 0" "0" "$rc"
check "dropped: Claude Code links follow the skill source" \
    "$(printf 'tdd -> %s\nzoom-out -> %s' "$CO/skills/engineering/tdd" "$CO/skills/engineering/zoom-out")" "$(links "$H/.claude/skills")"
check "dropped: OpenCode links follow the skill source" \
    "$(printf 'tdd -> %s\nzoom-out -> %s' "$CO/skills/engineering/tdd" "$CO/skills/engineering/zoom-out")" "$(links "$H/.config/opencode/skills")"

# RECONCILE_OPENCODE_SKILLS=0 leaves OpenCode without links of this script's,
# removes its old ones and keeps everything else there.
H="$TMP/home-no-opencode"
mkdir -p "$H/.config/opencode/skills/mine"
pin "$C1"
run_env "$H" "$TMP/bin" --apply RECONCILE_OPENCODE_SKILLS=0 >/dev/null
check "no OpenCode: no links created there" "" "$(links "$H/.config/opencode/skills")"
check "no OpenCode: Claude Code still linked" "2" "$(links "$H/.claude/skills" | grep -c .)"
run "$H" "$TMP/bin" --apply >/dev/null
check "OpenCode on again: linked" "2" "$(links "$H/.config/opencode/skills" | grep -c .)"
out="$(run_env "$H" "$TMP/bin" --apply RECONCILE_OPENCODE_SKILLS=0)"
check "no OpenCode: own links removed" "" "$(links "$H/.config/opencode/skills")"
check "no OpenCode: other entries kept" "yes" "$(yn test -d "$H/.config/opencode/skills/mine")"
H2="$TMP/home-no-opencode-fresh"
mkdir -p "$H2"
run_env "$H2" "$TMP/bin" --apply RECONCILE_OPENCODE_SKILLS=0 >/dev/null
check "no OpenCode: its directory is not created" "no" "$(yn test -e "$H2/.config/opencode")"

# The old Pi-only checkout moves to the new place; Pi's entries are replaced.
H="$TMP/home-migrate"
OLD="$H/.pi/agent/upstreams/mattpocock-skills"
NEW="$H/.local/share/mattpocock-skills"
mkdir -p "${OLD%/*}" "$H/.claude/skills"
git -c advice.detachedHead=false clone --quiet "$UP" "$OLD" && git -C "$OLD" -c advice.detachedHead=false checkout --quiet --detach "$C1"
printf '{"theme": "dark", "skills": ["/opt/a", "%s", "/opt/b", "%s"]}\n' "$OLD/skills/engineering" "$OLD/skills/productivity" \
    >"$H/.pi/agent/settings.json"
ln -s "$OLD/skills/engineering/tdd" "$H/.claude/skills/tdd"   # an own link at the old place
pin "$C1"
before="$(snapshot "$H")"
out="$(run "$H" "$TMP/bin" --check)"
check "migrate: check plans the move" "yes" "$(yn grep -qF "would move $OLD to $NEW" <<<"$out")"
check "migrate: check names the old entries" "2" "$(grep -c 'OLD Pi settings entry' <<<"$out")"
check "migrate: check plans the repoint" "yes" "$(yn grep -qF "would repoint: Claude Code/tdd -> $NEW/skills/engineering/tdd" <<<"$out")"
check "migrate: check changes nothing" "$before" "$(snapshot "$H")"
out="$(run "$H" "$TMP/bin" --apply)"; rc=$?
check "migrate: apply exits 0" "0" "$rc"
check "migrate: checkout moved, not recloned" "$C1 no" "$(git -C "$NEW" rev-parse HEAD) $(yn test -e "$OLD")"
check "migrate: empty upstreams directory removed" "no" "$(yn test -e "$H/.pi/agent/upstreams")"
check "migrate: Pi has only the new entries, in place of the old" \
    "{\"skills\": [\"/opt/a\", \"$NEW/skills/engineering\", \"/opt/b\", \"$NEW/skills/productivity\"], \"theme\": \"dark\"}" \
    "$(settings "$H")"
check "migrate: own link repointed" "$NEW/skills/engineering/tdd" "$(readlink "$H/.claude/skills/tdd")"
before="$(snapshot "$H")"
run "$H" "$TMP/bin" --apply >/dev/null
check "migrate: second apply changes nothing" "$before" "$(snapshot "$H")"

# Both places hold a clean checkout: the old one goes when its origin has its commits.
H="$TMP/home-both"
OLD="$H/.pi/agent/upstreams/mattpocock-skills"
mkdir -p "${OLD%/*}"
pin "$C1"
run "$H" "$TMP/bin" --apply >/dev/null
git -c advice.detachedHead=false clone --quiet "$UP" "$OLD" && git -C "$OLD" -c advice.detachedHead=false checkout --quiet --detach "$C2"
out="$(run "$H" "$TMP/bin" --apply)"; rc=$?
check "both clean: old copy removed" "0 no" "$rc $(yn test -e "$OLD")"

# ... and stays, with a stop, when it holds a commit its origin lacks.
git -c advice.detachedHead=false clone --quiet "$UP" "$OLD" && git -C "$OLD" -c advice.detachedHead=false checkout --quiet --detach "$C2"
git -C "$OLD" -c user.name=t -c user.email=t@example.invalid -c commit.gpgsign=false commit --quiet --allow-empty -m local
local_head="$(git -C "$OLD" rev-parse HEAD)"
out="$(run "$H" "$TMP/bin" --apply 2>&1)"; rc=$?
check "both, old has a local commit: apply stops" "1" "$rc"
check "both, old has a local commit: kept" "$local_head" "$(git -C "$OLD" rev-parse HEAD)"
check "both, old has a local commit: reported" "yes" "$(yn grep -q 'has commits its origin lacks' <<<"$out")"

# A dirty old checkout is never moved or deleted.
H="$TMP/home-old-dirty"
OLD="$H/.pi/agent/upstreams/mattpocock-skills"
mkdir -p "${OLD%/*}"
git -c advice.detachedHead=false clone --quiet "$UP" "$OLD" && git -C "$OLD" -c advice.detachedHead=false checkout --quiet --detach "$C1"
echo "local edit" >>"$OLD/skills/engineering/tdd/SKILL.md"
out="$(run "$H" "$TMP/bin" --apply 2>&1)"; rc=$?
check "old dirty: apply stops" "1" "$rc"
check "old dirty: kept in place with its edit" "yes no" \
    "$(yn grep -q 'local edit' "$OLD/skills/engineering/tdd/SKILL.md") $(yn test -e "$H/.local/share/mattpocock-skills")"
check "old dirty: reported" "yes" "$(yn grep -q 'STOPPED: .* has local modifications; nothing was moved' <<<"$out")"

# A dirty checkout stops with a report and keeps the modification.
H="$TMP/home-dirty"
CO="$H/.local/share/mattpocock-skills"
mkdir -p "$H"
pin "$C1"
run "$H" "$TMP/bin" --apply >/dev/null
echo "local edit" >>"$CO/skills/engineering/tdd/SKILL.md"
pin "$C2"
out="$(run "$H" "$TMP/bin" --apply 2>&1)"; rc=$?
check "dirty: apply fails" "1" "$rc"
check "dirty: reports local modifications" "yes" "$(yn grep -q 'STOPPED: .* has local modifications' <<<"$out")"
check "dirty: checkout not moved" "$C1" "$(git -C "$CO" rev-parse HEAD)"
check "dirty: modification kept" "yes" "$(yn grep -q 'local edit' "$CO/skills/engineering/tdd/SKILL.md")"
out="$(run "$H" "$TMP/bin" --check)"; rc=$?
check "dirty: check exits 0 and reports it" "0 yes" "$rc $(yn grep -q 'with local modifications' <<<"$out")"

# An untracked file counts as a local modification.
H="$TMP/home-untracked"
mkdir -p "$H"
pin "$C1"
run "$H" "$TMP/bin" --apply >/dev/null
touch "$H/.local/share/mattpocock-skills/notes.txt"
pin "$C2"
out="$(run "$H" "$TMP/bin" --apply 2>&1)"; rc=$?
check "untracked file: apply stops" "1 $C1" "$rc $(git -C "$H/.local/share/mattpocock-skills" rev-parse HEAD)"

# Some other repository in the checkout's place stops with a report.
H="$TMP/home-foreign"
F="$H/.local/share/mattpocock-skills"
mkdir -p "$F"
git init --quiet "$F"
git -C "$F" remote add origin https://example.invalid/other.git
out="$(run "$H" "$TMP/bin" --apply 2>&1)"; rc=$?
check "foreign repository: apply fails" "1" "$rc"
check "foreign repository: reported" "yes" "$(yn grep -q 'is not a checkout of' <<<"$out")"
check "foreign repository: origin untouched" "https://example.invalid/other.git" "$(git -C "$F" config remote.origin.url)"
check "foreign repository: settings untouched" "no" "$(yn test -f "$H/.pi/agent/settings.json")"

# A plain directory in the checkout's place is foreign too.
H="$TMP/home-plain"
mkdir -p "$H/.local/share/mattpocock-skills"
echo keep >"$H/.local/share/mattpocock-skills/file"
out="$(run "$H" "$TMP/bin" --apply 2>&1)"; rc=$?
check "plain directory: apply stops, keeps file" "1 keep" "$rc $(cat "$H/.local/share/mattpocock-skills/file")"

# A local copy of one of his promoted names is warned about, never removed.
H="$TMP/home-shadow"
mkdir -p "$H"
pin "$C1"
out="$(run "$H" "$TMP/bin" --apply)"
check "no colliding copy: apply prints no warning" "no" "$(yn grep -q WARNING <<<"$out")"
out="$(run "$H" "$TMP/bin" --check)"
check "no colliding copy: check prints no warning" "no" "$(yn grep -q WARNING <<<"$out")"
mkdir -p "$H/.agents/skills/tdd" "$H/.pi/agent/skills" "$H/skill-pool/teach" "$H/.agents/skills/misc-x"
echo local >"$H/.agents/skills/tdd/SKILL.md"
ln -s "$H/skill-pool/teach" "$H/.pi/agent/skills/teach"
ln -s "$H/skill-pool/x" "$H/.agents/skills/x"   # a name he does not promote, and dangling
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
    "{\"skills\": [\"$H/.local/share/mattpocock-skills/skills/engineering\", \"$H/.local/share/mattpocock-skills/skills/productivity\"]}" \
    "$(settings "$H")"

# Without pi, Pi's settings are left alone; Claude Code and OpenCode still get links.
H="$TMP/home-nopi"
mkdir -p "$H"
out="$(run "$H" "$TMP/bin-nopi" --apply)"; rc=$?
check "no pi: exits 0" "0" "$rc"
check "no pi: Pi skipped" "yes" "$(yn grep -q 'Pi: skipped (pi is not installed)' <<<"$out")"
check "no pi: no Pi settings written" "no" "$(yn test -e "$H/.pi")"
check "no pi: Claude Code still linked" "2" "$(links "$H/.claude/skills" | grep -c .)"

# Without git nothing happens.
mkdir -p "$TMP/sys-nogit"
for tool in bash python3 grep; do ln -s "$(command -v "$tool")" "$TMP/sys-nogit/$tool"; done
H="$TMP/home-nogit"
mkdir -p "$H"
out="$(env -i HOME="$H" PATH="$TMP/bin:$TMP/sys-nogit" "$BASH_BIN" "$SCRIPTS/reconcile-mattpocock-skills.sh" --apply)"; rc=$?
check "no git: exits 0 and skips" "0 yes" "$rc $(yn grep -q 'Skipped (git is not installed)' <<<"$out")"
check "no git: nothing written" "" "$(ls -A "$H")"

check "bad usage exits 2" "2" "$(bash "$REPO_ROOT/scripts/reconcile-mattpocock-skills.sh" >/dev/null 2>&1; echo $?)"
check "setup-omarchy registers reconciler after pi-packages" "yes" \
    "$(yn bash -c 'grep -A1 -F "reconcile-pi-packages.sh\"" "$1" | grep -qF reconcile-mattpocock-skills.sh' _ "$REPO_ROOT/scripts/setup-omarchy.sh")"
check "setup-platform-configs runs reconciler" "yes" \
    "$(yn grep -qF 'reconcile-mattpocock-skills.sh" --apply' "$REPO_ROOT/setup-platform-configs.sh")"
check "setup-platform-configs runs it after the skill pool's reconciler" "yes" \
    "$(yn python3 -c 'import sys; t=open(sys.argv[1]).read(); sys.exit(0 if t.index("reconcile-agent-skills.sh\" --apply") < t.index("reconcile-mattpocock-skills.sh\" --apply") else 1)' "$REPO_ROOT/setup-platform-configs.sh")"

echo "$TESTS tests, $FAILURES failures"
[[ $FAILURES -eq 0 ]]
