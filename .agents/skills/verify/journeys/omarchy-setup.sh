# omarchy-setup.sh
# setup-omarchy.sh end to end: refuses a non-Omarchy host, check writes nothing, apply is additive and repeatable, Omarchy's own files survive.
S="$REPO/scripts/setup-omarchy.sh"
stub_pi
stub omarchy 'echo "omarchy $*" >>"__CALLS__"'   # makes the host identify as Omarchy
mattpocock_upstream

omarchy_home() { # <name>: a home as a stock Omarchy install leaves it
    local h; h="$(new_home "$1")"
    mkdir -p "$h/.config/omarchy"
    printf '# Omarchy default bashrc\nsource ~/.local/share/omarchy/default/bash/rc\n# Add your own exports, aliases, and functions here.\n' >"$h/.bashrc"
    printf '{\n  "version": 1,\n  "plugins": [{"id": "omarchy.foreign"}]\n}\n' >"$h/.config/omarchy/shell.json"
    echo "$h"
}

step "a host that is not Omarchy is refused"
H="$(omarchy_home not-omarchy)"
capture "$H" refused-before; BEFORE="$TREE"
drive refused "$H" PATH="$SCRATCH/tools:/usr/bin:/bin" -- "$S" --apply
expect "exits 1" test "$RC" -eq 1
expect "says why" has "$OUT" "does not identify as Omarchy"
capture "$H" refused-after
expect "nothing was written" same_file "$BEFORE" "$TREE"

step "check on a stock Omarchy home writes nothing"
H="$(omarchy_home omarchy)"
capture "$H" before; BEFORE="$TREE"
drive check "$H" "${GIT_UPSTREAM_ENV[@]}" -- "$S" --check
capture "$H" after-check
expect "check left the home unchanged" same_file "$BEFORE" "$TREE"
expect "check exits 0" test "$RC" -eq 0
expect "check reaches the last reconciler" has "$OUT" "Agent commands (check)"
expect "check ran no pi command" test -z "$(calls "$H" pi)"
expect "check restarted nothing" test -z "$(calls "$H" omarchy)"

step "apply"
mkdir -p "$H/.pi/agent"
echo "Bryan's own Pi rules" >"$H/.pi/agent/AGENTS.md"     # a foreign file where a repo link would go
drive apply "$H" "${GIT_UPSTREAM_ENV[@]}" -- "$S" --apply
expect "apply exits 0" test "$RC" -eq 0
expect "Pi skills linked" links_to "$H/.pi/agent/skills/ship" "$REPO/dot-agents/skills/ship"
expect "Hermes skipped on Omarchy" test ! -e "$H/.hermes"
expect ".bashrc keeps Omarchy's lines first" test "$(head -2 "$H/.bashrc" | tail -1)" = "source ~/.local/share/omarchy/default/bash/rc"
expect ".bashrc sources the shared aliases once" test "$(grep -cF "source \"$REPO/dot-config/shell/aliases.sh\"" "$H/.bashrc")" -eq 1
expect ".bashrc loads Ble.sh once" test "$(grep -cF '/usr/share/blesh/ble.sh' "$H/.bashrc")" -eq 1
expect "the auto-suspend plugin is linked" links_to "$H/.config/omarchy/plugins/snowboardtechie.auto-suspend" "$REPO/omarchy/plugins/snowboardtechie.auto-suspend"
expect "shell.json keeps Omarchy's plugin and adds ours once" \
    test "$(jq -c '[.plugins[].id]' "$H/.config/omarchy/shell.json")" = '["omarchy.foreign","snowboardtechie.auto-suspend"]'
expect "shell.json was backed up first" test -f "$H/.config/omarchy/shell.json.pre-auto-suspend"
expect "Bryan's own Pi AGENTS.md is kept" bash -c '[[ ! -L "$1" && "$(cat "$1")" == "Bryan'"'"'s own Pi rules" ]]' _ "$H/.pi/agent/AGENTS.md"
expect "Pi extensions linked" links_to "$H/.pi/agent/extensions/worker-watch.ts" "$REPO/dot-pi/agent/extensions/worker-watch.ts"
expect "Pi's default provider is claude-code" test "$(jq -r .defaultProvider "$H/.pi/agent/settings.json")" = claude-code
expect "Matt Pocock's checkout is at the pin" test "$(git -C "$H/.pi/agent/upstreams/mattpocock-skills" rev-parse HEAD)" = "$MATTPOCOCK_PIN"
expect "forgejo-map linked into ~/.local/bin" links_to "$H/.local/bin/forgejo-map" "$REPO/dot-agents/bin/forgejo-map"
expect "no clipboard bridge unit without a configured Mac" test ! -e "$H/.config/systemd/user/clipboard-bridge.service"
expect "nothing ran stow" lacks "$OUT" "stow:"
capture "$H" after-apply; APPLIED="$TREE"

step "repeat: apply and check again"
drive apply-again "$H" "${GIT_UPSTREAM_ENV[@]}" -- "$S" --apply
expect "second apply exits 0" test "$RC" -eq 0
capture "$H" after-second-apply
expect "second apply left every path and file identical" same_file "$APPLIED" "$TREE"
drive check-again "$H" "${GIT_UPSTREAM_ENV[@]}" -- "$S" --check
expect "check after apply exits 0" test "$RC" -eq 0
for word in "would " MISSING WOULD "Installed" "appended" "linked:" "Linked"; do
    expect "check after apply proposes nothing ($word)" lacks "$OUT" "$word"
done
