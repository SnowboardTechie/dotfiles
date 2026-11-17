# Dotfiles setup: verification map

The maintained list of what to verify in this repository's setup entry points and reconcilers. Read this index before you drive them, then
use the matching feature file as the recipe. The harness is `dotfiles-verify`, the control command in
`../scripts/dotfiles-verify` (see `../SKILL.md`).

## Baseline preconditions

- `$V doctor` prints no `FAIL`.
- `DOTFILES_VERIFY_EVIDENCE`, if set, is outside the repository.
- Every journey starts from empty homes it makes itself, seeded in the journey with what a machine would already hold.
- Never point a journey at a real home. There is no shared instance to drive.

## Driving conventions

- One journey per run; each starts from empty homes.
- Drive the setup entry point or reconciler a machine runs (`setup-platform-configs.sh`, `scripts/setup-omarchy.sh`, a reconciler) with its
  real flags. Seed state with plain shell; never call into a script's functions.
- Every `--check` claim compares home trees before and after. Every idempotence claim compares trees after two
  applies.

## Proof and skip reporting

- Report the run directory and journey with every claim.
- Name what the stubs stood in for (`pi`, `claude`, `omarchy`, `launchctl`, the network). Those are not proven.
- A script a journey does not drive is not verified by another one. Say which ones were driven.
- A precondition a home cannot provide fails the journey. Record why in that feature's Gotchas; never weaken the
  journey to make it pass.

## Feature entry contract

Each feature file starts with an H1 title and one paragraph on what the machine sees. Four H2 sections follow, in this
order: `Sub-features`, `How to get to it (user POV)`, `Driving it with dotfiles-verify` (starting with
`Preconditions:`) and `Gotchas`.

## Features

| Feature | Journey | Last proved |
| --- | --- | --- |
| [Agent skill links](./agent-skills.md) | `agent-skills` | 2026-11-16 |
| [Omarchy additive setup](./omarchy-setup.md) | `omarchy-setup` | 2026-11-16 |
| [macOS setup after Stow](./platform-setup.md) | `platform-setup` | 2026-11-17 |
| [Agent commands on PATH](./agent-commands.md) | `agent-commands` | 2026-11-16 |
| [Shell additions in ~/.bashrc](./shell-additions.md) | `shell-additions` | 2026-11-16 |

"Last proved" means the journey passed on the unbroken checkout and failed at the predicted claim on each break below,
on that date (`prove-breaks`: 60 of 60 caught).

## Breaks each journey catches

Each row is one entry in `../scripts/breaks.json`: a temporary edit to the file, the journey run against it, the file
restored. Rerun them all with `../scripts/prove-breaks`. Add a row and an entry whenever a journey gains a claim.

| Break | File | Journey | Fails at |
| --- | --- | --- | --- |
| `--check` creates the tool directories | `scripts/reconcile-agent-skills.sh` | `agent-skills` | check left the home unchanged |
| draw-it dropped from Pi's curation | `scripts/reconcile-agent-skills.sh` | `agent-skills` | Pi gets draw-it (Pi-only) |
| a dangling skill pool link is kept instead of pruned | `scripts/reconcile-agent-skills.sh` | `agent-skills` | dangling links to skills retired from the skill pool (vault-capture, grilling, guided-learni … |
| a foreign or broken link is pruned instead of kept | `scripts/reconcile-agent-skills.sh` | `agent-skills` | a broken foreign link is kept |
| a foreign link on a curated name is overwritten | `scripts/reconcile-agent-skills.sh` | `agent-skills` | a foreign link on a curated name is kept, pointing where it did |
| a skill pool link no longer curated is kept, not pruned | `scripts/reconcile-agent-skills.sh` | `agent-skills` | an uncurated skill pool link is pruned |
| a real directory on a curated name is deleted and replaced by the skill pool link | `scripts/reconcile-agent-skills.sh` | `agent-skills` | a real directory on a curated name is kept with its content |
| a regular file on a curated name is deleted and replaced by the skill pool link | `scripts/reconcile-agent-skills.sh` | `agent-skills` | a regular file on a curated name is kept with its content |
| draw-it also curated for Hermes | `scripts/reconcile-agent-skills.sh` | `agent-skills` | .hermes/skills/personal does not get draw-it |
| links into Matt Pocock's checkout listed as foreign instead of counted | `scripts/reconcile-agent-skills.sh` | `agent-skills` | his link is counted, not listed as foreign |
| every machine counts as Omarchy | `scripts/setup-omarchy.sh` | `omarchy-setup` | exits 1 |
| `--check` runs every reconciler with `--apply` | `scripts/setup-omarchy.sh` | `omarchy-setup` | check left the home unchanged |
| the Pi extensions reconciler dropped from the list | `scripts/setup-omarchy.sh` | `omarchy-setup` | check runs Pi extensions (check) |
| Pi extensions apply links nothing | `scripts/reconcile-pi-extensions.sh` | `omarchy-setup` | Pi extensions linked |
| enabling replaces Omarchy's plugin list instead of adding to it | `scripts/reconcile-omarchy-auto-suspend.sh` | `omarchy-setup` | shell.json keeps Omarchy's plugin and adds ours once |
| the existing-entry count ignored, so every apply adds the service again | `scripts/reconcile-omarchy-auto-suspend.sh` | `omarchy-setup` | second apply left every path and file identical |
| a foreign file in `~/.pi/agent` is replaced by the repo link | `scripts/reconcile-pi-extensions.sh` | `omarchy-setup` | Bryan's own Pi AGENTS.md is kept |
| a fresh clone is checked out one commit off the pin | `scripts/reconcile-mattpocock-skills.sh` | `omarchy-setup` | Matt Pocock's checkout is at the pin |
| the Pi packages reconciler dropped from the list | `scripts/setup-omarchy.sh` | `omarchy-setup` | check runs Pi packages (check) |
| Ble.sh check mode proposes nothing | `scripts/reconcile-bash-enhancements.sh` | `omarchy-setup` | check proposes: would append: guarded Ble.sh source line |
| the retired Hindsight Pi extension is no longer removed | `scripts/retire-agent-memory.py` | `omarchy-setup` | check proposes: would remove from |
| apply installs nothing | `scripts/reconcile-pi-packages.sh` | `omarchy-setup` | the pinned Pi packages are installed |
| Omarchy's shell is not restarted after enabling the plugin | `scripts/reconcile-omarchy-auto-suspend.sh` | `omarchy-setup` | Omarchy's shell was restarted to load the plugin |
| setup-omarchy.sh runs stow over the home | `scripts/setup-omarchy.sh` | `omarchy-setup` | nothing ran stow, sudo or systemctl |
| Pi settings entries not written | `scripts/reconcile-mattpocock-skills.sh` | `omarchy-setup` | Pi lists his two skill directories |
| the OpenCode links are never made | `scripts/reconcile-mattpocock-skills.sh` | `omarchy-setup` | his tdd is linked for OpenCode |
| `~/.secrets` created world-readable | `setup-platform-configs.sh` | `platform-setup` | ~/.secrets is created private |
| a differing OpenCode AGENTS.md is replaced by the link | `setup-platform-configs.sh` | `platform-setup` | the file is untouched |
| the watcher is bootstrapped into launchd on every run | `scripts/reconcile-rex-agent-sessions.sh` | `platform-setup` | launchd is not reloaded |
| an anthropic default is treated as an explicit choice and left | `scripts/reconcile-pi-claude-code.sh` | `platform-setup` | Pi's anthropic default switches to claude-code |
| a package whose name merely starts with a pinned name counts as another version of it, so it is removed | `scripts/reconcile-pi-packages.sh` | `platform-setup` | another package whose name starts with a pinned one is kept |
| every hook counts as the retired cache-heal hook | `scripts/retire-agent-memory.py` | `platform-setup` | the retired Hindsight hook and context-mode plugin are removed, Bryan's hook, … |
| a retired tmux link of this repository's is kept | `setup-platform-configs.sh` | `platform-setup` | the retired repo-owned tmux link is removed |
| Claude Code links to his skills are never made | `scripts/reconcile-mattpocock-skills.sh` | `platform-setup` | his grilling is linked for Claude Code |
| a foreign link on one of his names is repointed to his skill | `scripts/reconcile-mattpocock-skills.sh` | `platform-setup` | a foreign link on one of his names is kept |
| pi runs without PI_CODING_AGENT_DIR, so pstack's packages land in the main Pi directory | `scripts/reconcile-pi-pstack.sh` | `platform-setup` | pstack's port is not installed into the main Pi directory |
| the pstack port is never installed | `scripts/reconcile-pi-pstack.sh` | `platform-setup` | pstack's directory holds pi-claude-code and the port at its pin |
| pstack's default model is another one | `scripts/reconcile-pi-pstack.sh` | `platform-setup` | pstack's directory defaults to claude-code and claude-opus-5-5 |
| the model sheet is never linked | `scripts/reconcile-pi-pstack.sh` | `platform-setup` | pstack's model sheet is linked |
| pstack's AGENTS.md is never linked | `scripts/reconcile-pi-pstack.sh` | `platform-setup` | pstack's AGENTS.md is linked |
| auth.json created readable by everyone | `scripts/reconcile-pi-pstack.sh` | `platform-setup` | pstack's auth.json is mode 600 |
| auth.json holds a literal key instead of the !cat command | `scripts/reconcile-pi-pstack.sh` | `platform-setup` | pstack's auth.json reads the OpenCode key from ~/.secrets with !cat |
| an existing auth.json is rewritten | `scripts/reconcile-pi-pstack.sh` | `platform-setup` | Bryan's own pstack auth.json is not rewritten |
| an auth.json without the OpenCode entry is not reported | `scripts/reconcile-pi-pstack.sh` | `platform-setup` | the missing OpenCode entry is reported |
| installed packages are never recognised, so every run reinstalls them | `scripts/reconcile-pi-pstack.sh` | `platform-setup` | every path and file is unchanged |
| the stub pi ignores PI_CODING_AGENT_DIR and always edits the main Pi directory | `.agents/skills/verify/scripts/dotfiles-verify` | `platform-setup` | pstack's port is not installed into the main Pi directory |
| conflicts reported but the run exits 0 | `scripts/reconcile-agent-commands.sh` | `agent-commands` | file, check: exits 1 |
| a live link into another checkout is treated as stale and repointed | `scripts/reconcile-agent-commands.sh` | `agent-commands` | live-link, check: exits 1 |
| forgejo-map no longer follows its own link to find the adapter | `dot-agents/bin/forgejo-map` | `agent-commands` | --help exits 0 |
| a stale link left by a removed worktree is reported but not repaired | `scripts/reconcile-agent-commands.sh` | `agent-commands` | the link now points here |
| check creates `~/.local/bin` | `scripts/reconcile-agent-commands.sh` | `agent-commands` | check left the home unchanged |
| apply also drops a stray file into `~/.local` | `scripts/reconcile-agent-commands.sh` | `agent-commands` | apply changed nothing but the link |
| every apply rewrites a stamp file | `scripts/reconcile-agent-commands.sh` | `agent-commands` | second apply left the home identical |
| `~/.bashrc` created when missing | `scripts/reconcile-shell-additions.sh` | `shell-additions` | ~/.bashrc still does not exist |
| the line appended on every apply | `scripts/reconcile-shell-additions.sh` | `shell-additions` | a second apply appends nothing |
| the shared aliases stop loading in bash | `dot-config/shell/aliases.sh` | `shell-additions` | gs is git status |
| Bryan's own Ble.sh settings replaced by the link | `scripts/reconcile-bash-enhancements.sh` | `shell-additions` | warns and keeps the file |
| check creates `~/.config/blesh` | `scripts/reconcile-bash-enhancements.sh` | `shell-additions` | check left the home unchanged |
| apply also writes a backup of `~/.bashrc` | `scripts/reconcile-shell-additions.sh` | `shell-additions` | apply changed only ~/.bashrc and the Ble.sh settings link |
| every apply rewrites a stamp beside the Ble.sh settings | `scripts/reconcile-bash-enhancements.sh` | `shell-additions` | a second apply left the home identical |

Not mapped yet, but the repository's tests cover them: the Gnarbox profile (`tests/test-gnarbox-dotfiles-profile.sh`),
the clipboard bridge (`tests/test-omarchy-clipboard-bridge.sh`), Pi trust for the bots (`tests/test-bot-alias.sh`),
and a moved, dirty or old-path Matt Pocock checkout (`tests/test-reconcile-mattpocock-skills.sh`). Hermes's Studio-only
installer (`hermes/install.py`) has no journey: it runs only on the Studio host name.
