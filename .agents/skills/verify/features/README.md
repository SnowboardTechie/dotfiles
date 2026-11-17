# Dotfiles setup: verification map

The maintained list of what to verify in this repository's setup scripts. Read this index before you drive them, then
use the matching feature file as the recipe. The harness is `dotfiles-verify`, the control command in
`../scripts/dotfiles-verify` (see `../SKILL.md`).

## Baseline preconditions

- `$V doctor` prints no `FAIL`.
- `DOTFILES_VERIFY_EVIDENCE`, if set, is outside the repository.
- Every journey starts from empty homes it makes itself, seeded in the journey with what a host would already hold.
- Never point a journey at a real home. There is no shared instance to drive.

## Driving conventions

- One journey per run; each starts from empty homes.
- Drive the entry point a host runs (`setup-platform-configs.sh`, `scripts/setup-omarchy.sh`, a reconciler) with its
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

Each feature file starts with an H1 title and one paragraph on what the host sees. Four H2 sections follow, in this
order: `Sub-features`, `How to get to it (user POV)`, `Driving it with dotfiles-verify` (starting with
`Preconditions:`) and `Gotchas`.

## Features

| Feature | Journey | Last proved |
| --- | --- | --- |
| [Agent skill links](./agent-skills.md) | `agent-skills` | 2026-11-16 |
| [Omarchy additive setup](./omarchy-setup.md) | `omarchy-setup` | 2026-11-16 |
| [macOS setup after Stow](./platform-setup.md) | `platform-setup` | 2026-11-16 |
| [Agent commands on PATH](./agent-commands.md) | `agent-commands` | 2026-11-16 |
| [Shell additions in ~/.bashrc](./shell-additions.md) | `shell-additions` | 2026-11-16 |

"Last proved" means the journey passed on the unbroken checkout and failed at the predicted claim on each break below,
on that date (`prove-breaks`: 28 of 28 caught).

## Breaks each journey catches

Each row is one entry in `../scripts/breaks.json`: a temporary edit to the file, the journey run against it, the file
restored. Rerun them all with `../scripts/prove-breaks`. Add a row and an entry whenever a journey gains a claim.

| Break | File | Journey | Fails at |
| --- | --- | --- | --- |
| `--check` creates the tool directories | `scripts/reconcile-agent-skills.sh` | `agent-skills` | check left the home unchanged |
| draw-it dropped from Pi's curation | `scripts/reconcile-agent-skills.sh` | `agent-skills` | Pi gets draw-it (Pi-only) |
| grilling added to Codex's `~/.agents/skills`, where it beats Matt Pocock's copy in Pi | `scripts/reconcile-agent-skills.sh` | `agent-skills` | Codex (~/.agents/skills) gets no grilling, … |
| a foreign or broken link is pruned instead of kept | `scripts/reconcile-agent-skills.sh` | `agent-skills` | a broken foreign link is kept |
| a foreign link on a curated name is overwritten | `scripts/reconcile-agent-skills.sh` | `agent-skills` | a foreign link on a curated name is kept, … |
| a pool link no longer curated is kept, not pruned | `scripts/reconcile-agent-skills.sh` | `agent-skills` | an uncurated pool link is pruned |
| every host counts as Omarchy | `scripts/setup-omarchy.sh` | `omarchy-setup` | exits 1 |
| `--check` runs every reconciler with `--apply` | `scripts/setup-omarchy.sh` | `omarchy-setup` | check left the home unchanged |
| the Pi extensions reconciler dropped from the list | `scripts/setup-omarchy.sh` | `omarchy-setup` | Pi extensions linked |
| enabling replaces Omarchy's plugin list instead of adding to it | `scripts/reconcile-omarchy-auto-suspend.sh` | `omarchy-setup` | shell.json keeps Omarchy's plugin and adds ours once |
| the existing-entry count ignored, so every apply adds the service again | `scripts/reconcile-omarchy-auto-suspend.sh` | `omarchy-setup` | second apply left every path and file identical |
| a foreign file in `~/.pi/agent` is replaced by the repo link | `scripts/reconcile-pi-extensions.sh` | `omarchy-setup` | Bryan's own Pi AGENTS.md is kept |
| a fresh clone is checked out one commit off the pin | `scripts/reconcile-mattpocock-skills.sh` | `omarchy-setup` | Matt Pocock's checkout is at the pin |
| `~/.secrets` created world-readable | `setup-platform-configs.sh` | `platform-setup` | ~/.secrets is created private |
| a differing OpenCode AGENTS.md is replaced by the link | `setup-platform-configs.sh` | `platform-setup` | the file is untouched |
| the watcher is bootstrapped into launchd on every run | `scripts/reconcile-rex-agent-sessions.sh` | `platform-setup` | launchd is not reloaded |
| an anthropic default is treated as an explicit choice and left | `scripts/reconcile-pi-claude-code.sh` | `platform-setup` | Pi's anthropic default switches to claude-code |
| a package whose name merely starts with a pinned name counts as another version of it | `scripts/reconcile-pi-packages.sh` | `platform-setup` | another package whose name starts with a pinned one is kept |
| every hook counts as the retired cache-heal hook | `scripts/retire-agent-memory.py` | `platform-setup` | the retired Hindsight hook and context-mode plugin are removed, … |
| a retired tmux link of this repository's is kept | `setup-platform-configs.sh` | `platform-setup` | the retired repo-owned tmux link is removed |
| conflicts reported but the run exits 0 | `scripts/reconcile-agent-commands.sh` | `agent-commands` | file, check: exits 1 |
| a live link into another checkout is treated as stale and repointed | `scripts/reconcile-agent-commands.sh` | `agent-commands` | live-link, check: exits 1 |
| forgejo-map no longer follows its own link to find the adapter | `dot-agents/bin/forgejo-map` | `agent-commands` | --help exits 0 |
| a stale link left by a removed worktree is reported but not repaired | `scripts/reconcile-agent-commands.sh` | `agent-commands` | the link now points here |
| `~/.bashrc` created when missing | `scripts/reconcile-shell-additions.sh` | `shell-additions` | ~/.bashrc still does not exist |
| the line appended on every apply | `scripts/reconcile-shell-additions.sh` | `shell-additions` | a second apply appends nothing |
| the shared aliases stop loading in bash | `dot-config/shell/aliases.sh` | `shell-additions` | gs is git status |
| Bryan's own Ble.sh settings replaced by the link | `scripts/reconcile-bash-enhancements.sh` | `shell-additions` | warns and keeps the file |

Not mapped yet, but the repository's tests cover them: the Gnarbox profile (`tests/test-gnarbox-dotfiles-profile.sh`),
the clipboard bridge (`tests/test-omarchy-clipboard-bridge.sh`), Pi trust for the bots (`tests/test-bot-alias.sh`),
and a moved or dirty Matt Pocock checkout (`tests/test-reconcile-mattpocock-skills.sh`). Hermes's Studio-only
installer (`hermes/install.py`) has no journey: it runs only on the Studio host name.
