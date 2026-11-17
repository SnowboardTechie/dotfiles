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
    # Pi settings left by an old install: the retired Hindsight extension beside one of Bryan's.
    mkdir -p "$h/.pi/agent"
    printf '{"extensions": ["/home/peer/.hindsight/coding-agents/dist/pi.js", "/opt/pi/mine.js"]}\n' >"$h/.pi/agent/settings.json"
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
# Each reconciler setup-omarchy.sh lists runs, in check mode, and proposes its change.
while IFS='|' read -r header proposal; do
    expect "check runs $header" has "$OUT" "$header"
    [[ -z "$proposal" ]] || expect "check proposes: $proposal" has "$OUT" "$proposal"
done <<'LIST'
Reconciling agent skills (check)|would create link: ship
Shell additions (check)|would append: marked source line
Bash enhancements (check)|would append: guarded Ble.sh source line
Omarchy auto suspend (check)|would enable: snowboardtechie.auto-suspend in shell.json
Clipboard bridge (check)|
Pi extensions (check)|MISSING
Pi Claude Code provider (check)|WOULD SET defaultProvider <unset> -> claude-code
Pi packages (check)|MISSING package npm:pi-web-access@
Matt Pocock's skills in Pi (check)|checkout: missing
Retired agent-memory cleanup (check)|would remove from
Agent commands (check)|(would link)
LIST
expect "check ran no apply step" lacks "$OUT" "(apply)"
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
expect "the pinned Pi packages are installed" test "$(jq -c '[.packages[] | select(startswith("npm:"))]' "$H/.pi/agent/settings.json")" = \
    "$(grep -oE '"(pi-web-access|@deathbeam/pi-hashline)@[^"]+"' "$REPO/scripts/reconcile-pi-packages.sh" | tr -d '"' | sed 's/^/npm:/' | jq -Rsc 'split("\n") | map(select(. != ""))')"
expect "the retired Hindsight extension is removed from Pi's settings, Bryan's kept" \
    test "$(jq -c .extensions "$H/.pi/agent/settings.json")" = '["/opt/pi/mine.js"]'
expect "Omarchy's shell was restarted to load the plugin" test "$(calls "$H" omarchy)" = "omarchy restart shell"
expect "Pi's default provider is claude-code" test "$(jq -r .defaultProvider "$H/.pi/agent/settings.json")" = claude-code
expect "Matt Pocock's checkout is at the pin" test "$(git -C "$H/.pi/agent/upstreams/mattpocock-skills" rev-parse HEAD)" = "$MATTPOCOCK_PIN"
expect "forgejo-map linked into ~/.local/bin" links_to "$H/.local/bin/forgejo-map" "$REPO/dot-agents/bin/forgejo-map"
expect "no clipboard bridge unit without a configured Mac" test ! -e "$H/.config/systemd/user/clipboard-bridge.service"
expect "nothing ran stow, sudo or systemctl" test -z "$(calls "$H" stow)$(calls "$H" sudo)$(calls "$H" systemctl)"
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
