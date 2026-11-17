# platform-setup.sh
# setup-platform-configs.sh on a macOS home after Stow: repo-owned links only, foreign files kept, launchd watcher installed through launchctl, a rerun changes nothing.
S="$REPO/setup-platform-configs.sh"
stub_pi
mattpocock_upstream
# launchctl: `print` says "not loaded" until a bootstrap, as the real one does.
stub launchctl 'echo "$*" >>"__CALLS__"
state="$(dirname "__CALLS__")/$(basename "$HOME")-launchd-loaded"
case "$1" in
    bootstrap) touch "$state" ;;
    bootout) rm -f "$state" ;;
    print) [[ -e "$state" ]] || exit 113 ;;
esac'

step "a lived-in home"
H="$(new_home mac)"
mkdir -p "$H/.config/opencode" "$H/.tmux" "$H/.claude"
ln -s "$REPO/dot-tmux.conf" "$H/.tmux.conf"                     # retired repo-owned tmux link
ln -s "/opt/elsewhere/claude-usage.sh" "$H/.tmux/claude-usage.sh" # foreign link under a retired name
# Claude settings with one retired Hindsight hook and one retired plugin beside Bryan's own entries.
cat >"$H/.claude/settings.json" <<'JSON'
{"model": "opus",
 "hooks": {"Stop": [{"hooks": [{"type": "command", "command": "node /home/peer/.hindsight/coding-agents/dist/claude-stop-hook.js"},
                               {"type": "command", "command": "afplay done.aiff"}]}]},
 "enabledPlugins": {"context-mode@context-mode": true, "context7@claude-plugins-official": true}}
JSON
printf '{"packages": ["npm:pi-web-access@0.40.0", "npm:pi-web-access-extras"], "defaultProvider": "anthropic"}\n' >"$H/.pi-settings-seed"
mkdir -p "$H/.pi/agent" && mv "$H/.pi-settings-seed" "$H/.pi/agent/settings.json"
cp "$REPO/dot-config/opencode/AGENTS.md" "$H/.config/opencode/AGENTS.md"   # an identical copy: becomes a link
capture "$H" before

step "first run"
drive setup "$H" "${GIT_UPSTREAM_ENV[@]}" -- "$S"
expect "exits 0" test "$RC" -eq 0
expect "runs to the end" has "$OUT" "Platform-specific configuration complete!"
expect "the retired repo-owned tmux link is removed" test ! -L "$H/.tmux.conf"
expect "a foreign link under a retired tmux name is kept" test "$(readlink "$H/.tmux/claude-usage.sh")" = /opt/elsewhere/claude-usage.sh
expect "~/.secrets is created private" test "$(stat -f %Lp "$H/.secrets")" = 700
expect "an identical OpenCode AGENTS.md copy becomes the repo link" links_to "$H/.config/opencode/AGENTS.md" "$REPO/dot-config/opencode/AGENTS.md"
expect "skills linked for Claude and Hermes" bash -c '[[ -L "$1/.claude/skills/ship" && -L "$1/.hermes/skills/personal/ship" ]]' _ "$H"
P="$H/Library/LaunchAgents/com.snowboardtechie.rex-agent-sessions.plist"
expect "the Rex watcher plist is written" test -f "$P"
expect "the plist names this checkout and this home, no placeholders left" \
    bash -c 'grep -qF "$2/scripts/rex-agent-sessions.py" "$1" && grep -qF "$3" "$1" && ! grep -q "__REPO__\|__HOME__" "$1"' _ "$P" "$REPO" "$H"
expect "the plist is valid" plutil -lint -s "$P"
expect "launchd was asked to load it" has "$(calls "$H" launchctl)" "bootstrap gui/$(id -u) $P"
expect "Pi's anthropic default switches to claude-code" test "$(jq -r .defaultProvider "$H/.pi/agent/settings.json")" = claude-code
expect "the old pi-web-access pin is replaced by the pinned one" \
    test "$(jq -c '[.packages[] | select(startswith("npm:pi-web-access@"))]' "$H/.pi/agent/settings.json")" = "[\"npm:$(grep -oE 'pi-web-access@[0-9.]+' "$REPO/scripts/reconcile-pi-packages.sh")\"]"
expect "another package whose name starts with a pinned one is kept" has "$(jq -r '.packages[]' "$H/.pi/agent/settings.json")" "npm:pi-web-access-extras"
expect "the retired Hindsight hook and context-mode plugin are removed, Bryan's hook, plugin and model kept" \
    test "$(jq -c '[.model, [.hooks.Stop[].hooks[].command], (.enabledPlugins | keys)]' "$H/.claude/settings.json")" = '["opus",["afplay done.aiff"],["context7@claude-plugins-official"]]'
expect "Hermes's Studio-only assets are skipped on another host" has "$OUT" "Skipped (Studio-only assets)"
expect "nothing ran stow, sudo or brew" test -z "$(calls "$H" stow)$(calls "$H" sudo)$(calls "$H" brew)"
capture "$H" after-first; FIRST="$TREE"
LOADS="$(calls "$H" launchctl | grep -c '^bootstrap')"

step "second run"
drive setup-again "$H" "${GIT_UPSTREAM_ENV[@]}" -- "$S"
expect "exits 0" test "$RC" -eq 0
capture "$H" after-second
expect "every path and file is unchanged" same_file "$FIRST" "$TREE"
expect "launchd is not reloaded" test "$(calls "$H" launchctl | grep -c '^bootstrap')" -eq "$LOADS"
expect "pi installed nothing more" lacks "$OUT" "Installed"

step "an OpenCode AGENTS.md of Bryan's own is kept"
H="$(new_home own-agents)"
mkdir -p "$H/.config/opencode"
echo "my own rules" >"$H/.config/opencode/AGENTS.md"
drive setup-own "$H" "${GIT_UPSTREAM_ENV[@]}" -- "$S"
expect "exits 0" test "$RC" -eq 0
expect "the file is untouched" test "$(cat "$H/.config/opencode/AGENTS.md")" = "my own rules"
