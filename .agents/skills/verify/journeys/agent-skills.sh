# agent-skills.sh
# Skill links for every harness: check writes nothing, apply links the curated pool, repeats are no-ops, foreign entries survive.
R="$REPO/scripts/reconcile-agent-skills.sh"
POOL="$REPO/dot-agents/skills"

step "fresh home: check reports, writes nothing"
H="$(new_home fresh)"
capture "$H" before; BEFORE="$TREE"
drive check-fresh "$H" -- "$R" --check
expect "check exits 0" test "$RC" -eq 0
expect "check names a link it would create" has "$OUT" "would create link: ship"
capture "$H" after-check
expect "check left the home unchanged" same_file "$BEFORE" "$TREE"

step "fresh home: apply links the curated pool for each tool"
drive apply-fresh "$H" -- "$R" --apply
expect "apply exits 0" test "$RC" -eq 0
for d in .claude/skills .config/opencode/skills .agents/skills .pi/agent/skills .hermes/skills/personal; do
    expect "$d/ship links into the pool" links_to "$H/$d/ship" "$POOL/ship"
done
expect "Pi gets draw-it (Pi-only)" links_to "$H/.pi/agent/skills/draw-it" "$POOL/draw-it"
for d in .claude/skills .config/opencode/skills .agents/skills .hermes/skills/personal; do
    expect "$d does not get draw-it" test ! -e "$H/$d/draw-it" -a ! -L "$H/$d/draw-it"
done
capture "$H" after-apply; APPLIED="$TREE"

step "repeat: a second apply and a check change nothing"
drive apply-again "$H" -- "$R" --apply
expect "second apply exits 0" test "$RC" -eq 0
capture "$H" after-second-apply
expect "second apply left the tree identical" same_file "$APPLIED" "$TREE"
drive check-applied "$H" -- "$R" --check
expect "check after apply proposes nothing" lacks "$OUT" "would "

step "foreign entries and stale links"
H="$(new_home lived-in)"
mkdir -p "$H/.pi/agent/skills/my-own" "$H/.claude/skills" "$H/elsewhere/ship"
echo mine >"$H/.pi/agent/skills/my-own/SKILL.md"
mkdir -p "$H/.pi/agent/skills/ship"                                # a real directory on a curated name
echo "my own ship" >"$H/.pi/agent/skills/ship/SKILL.md"
mkdir -p "$H/.config/opencode/skills"
echo "a note, not a skill" >"$H/.config/opencode/skills/ship"      # a regular file on a curated name
ln -s "$H/elsewhere/ship" "$H/.claude/skills/ship"            # foreign link on a curated name
ln -s "/nowhere/omarchy" "$H/.claude/skills/omarchy"          # broken foreign link
ln -s "$POOL/gamedev" "$H/.claude/skills/gamedev"             # pool link Claude no longer curates
ln -s "$POOL/vault-capture" "$H/.claude/skills/vault-capture" # retired pool skill, dangling
# The six skills adapted from Matt Pocock's retired from the pool on 2026-11-16;
# an upgraded home still has dangling links to them.
mkdir -p "$H/.agents/skills" "$H/.hermes/skills/personal"
ln -s "$POOL/grilling" "$H/.agents/skills/grilling"
ln -s "$POOL/guided-learning" "$H/.hermes/skills/personal/guided-learning"
# A link of reconcile-mattpocock-skills.sh's own, into his checkout.
ln -s "$H/.local/share/mattpocock-skills/skills/engineering/zoom-out" "$H/.claude/skills/zoom-out"
capture "$H" lived-before; LIVED="$TREE"
drive check-lived "$H" -- "$R" --check
capture "$H" lived-after-check
expect "check left the lived-in home unchanged" same_file "$LIVED" "$TREE"
drive apply-lived "$H" -- "$R" --apply
expect "apply exits 0" test "$RC" -eq 0
expect "a real skill directory survives with its content" test "$(cat "$H/.pi/agent/skills/my-own/SKILL.md")" = mine
expect "a real directory on a curated name is kept with its content" \
    bash -c '[[ -d "$1" && ! -L "$1" && "$(cat "$1/SKILL.md")" == "my own ship" ]]' _ "$H/.pi/agent/skills/ship"
expect "a regular file on a curated name is kept with its content" \
    bash -c '[[ -f "$1" && ! -L "$1" && "$(cat "$1")" == "a note, not a skill" ]]' _ "$H/.config/opencode/skills/ship"
expect "both collisions are reported" bash -c 'grep -qF "Pi/ship exists and is not a symlink; preserved" <<<"$1" && grep -qF "OpenCode/ship exists and is not a symlink; preserved" <<<"$1"' _ "$OUT"
expect "a foreign link on a curated name is kept, pointing where it did" test "$(readlink "$H/.claude/skills/ship")" = "$H/elsewhere/ship"
expect "the collision is reported" has "$OUT" "Claude/ship is a foreign symlink; preserved"
expect "a broken foreign link is kept" test -L "$H/.claude/skills/omarchy"
expect "an uncurated pool link is pruned" test ! -e "$H/.claude/skills/gamedev" -a ! -L "$H/.claude/skills/gamedev"
expect "dangling links to retired pool skills (vault-capture, grilling, guided-learning) are pruned" \
    test ! -L "$H/.claude/skills/vault-capture" -a ! -L "$H/.agents/skills/grilling" -a ! -L "$H/.hermes/skills/personal/guided-learning"
expect "a link into Matt Pocock's checkout is kept" test "$(readlink "$H/.claude/skills/zoom-out")" = "$H/.local/share/mattpocock-skills/skills/engineering/zoom-out"
expect "his link is counted, not listed as foreign" \
    bash -c 'grep -qF "1 links to Matt Pocock'"'"'s skills left to scripts/reconcile-mattpocock-skills.sh" <<<"$1" && ! grep -qF "preserved (foreign symlink): zoom-out" <<<"$1"' _ "$OUT"
capture "$H" lived-after-apply
