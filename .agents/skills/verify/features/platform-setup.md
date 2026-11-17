# macOS setup after Stow

`setup-platform-configs.sh` does what Stow can't on a fully owned macOS or NixOS machine: removes retired tmux links,
makes `~/.secrets` private, links OpenCode's `AGENTS.md`, then runs the skill, Rex agent-session, Pi extension, Claude
Code provider, Pi package, pstack Pi directory, Matt Pocock skill, agent command and Pi trust reconcilers and the
retired-memory cleanup. It has no flags: every run applies.

## Sub-features

- `first-run`: on a lived-in home, the retired repo-owned tmux link goes and a foreign one under a retired name stays;
  `~/.secrets` is `700`; an identical OpenCode `AGENTS.md` copy becomes the repo link; skills reach Claude and Hermes;
  the Rex watcher plist is written with this checkout's and this home's paths, lints, and is handed to
  `launchctl bootstrap`; Pi's `anthropic` default becomes `claude-code`; an older `pi-web-access` pin is replaced and a
  package with a similar name is kept; a retired Hindsight hook and context-mode plugin leave Claude's settings while
  Bryan's hook, plugin and model stay; Matt Pocock's checkout is at the pin in `~/.local/share/mattpocock-skills`,
  his `grilling` is linked into `~/.claude/skills` and `~/.config/opencode/skills` after the old dangling skill pool
  `grilling` link is pruned, and Bryan's own `~/.claude/skills/tdd` link on one of his names is kept; Hermes's
  Studio-only step skips; no `stow`, `sudo` or `brew`; pstack's own Pi directory `~/.pi/pstack` holds pi-claude-code
  and the pstack port at the commit in `dot-agents/skill-sources/pstack-claude.json` (and nothing else) in its
  `settings.json` with `defaultProvider` `claude-code` and `defaultModel` `claude-opus-5-5`, links `pstack-models.md`
  and `AGENTS.md` into this checkout, and has an `auth.json` at mode `600` whose `opencode-go` key is the
  `!cat "$HOME/.secrets/opencode-api-key"` command; the main Pi directory's packages hold no pstack port.
- `second-run`: no path changes (both Pi directories included), launchd is not bootstrapped again, nothing is
  installed.
- `own-agents`: an OpenCode `AGENTS.md` that differs from the repository's is left as it is, and so is an existing
  `~/.pi/pstack/auth.json` without an `opencode-go` entry (byte for byte), which setup reports.

## How to get to it (user POV)

- `stow . --dotfiles --target $HOME` then `./setup-platform-configs.sh` (AGENTS.md, "COMMANDS"). Stow itself is never
  driven here.

## Driving it with dotfiles-verify

Preconditions:

- `doctor` passes; Matt Pocock's pin is reachable (see `omarchy-setup.md`, Gotchas).
- The journey stubs `pi`/`claude` and replaces the default `launchctl` stub with one whose `print` fails until a
  `bootstrap`, as launchd does for an unloaded job. The `pi` stub edits the `settings.json` of the directory in
  `PI_CODING_AGENT_DIR`, as the real `pi` does, else `~/.pi/agent`; the pstack reconciler depends on that.

- **First run.** `$V run platform-setup`. Exit 0 and `Platform-specific configuration complete!`. Each sub-feature
  above is one claim, read back from the home with `readlink`, `stat -f %Lp`, `jq`, `plutil -lint -s` and the
  `launchctl` call log (`bootstrap gui/<uid> <plist>`).
- **Second run.** Identical trees; the count of `bootstrap` calls unchanged; no `Installed` in the output.
- **Own AGENTS.md and auth.json.** A fresh home with `~/.config/opencode/AGENTS.md` reading `my own rules` and a
  `~/.pi/pstack/auth.json` holding another entry; after the run both are as they were, and the output has
  `has no opencode-go entry`.

## Gotchas

- `$OSTYPE` is bash's own, so the run always takes the macOS branch. Linux and the Gnarbox profile are not driven.
- `scutil` answers `verify-host`, so `hermes/install.py` never runs. Its own tests cover it.
- The `~/.secrets/personal-weather-location` hint is printed, not created; nothing asserts on it.
- The launchd job is never really loaded. The plist is linted and its paths checked; whether launchd runs
  `rex-agent-sessions.py` from it is not proven.
- `reconcile-pi-bots-trust.mjs` skips (`no bot directories`).
- `pi install` is the stub: whether the real `pi` fetches pstack's port into `~/.pi/pstack` is not proven, and nor is
  the `!cat` key command working (the home has no `~/.secrets/opencode-api-key`). `tests/test-reconcile-pi-pstack.sh`
  covers the reconciler's other branches (another pin removed, links from another checkout repointed, `--check`).
