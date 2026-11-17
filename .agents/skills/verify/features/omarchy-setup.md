# Omarchy additive setup

`scripts/setup-omarchy.sh --check|--apply` is the only supported install on an Omarchy host. It runs a fixed list of
reconcilers that add to Omarchy's own configuration and never replace it: skill links, one marked line each in
`~/.bashrc` for the shared aliases and Ble.sh, the auto-suspend plugin in `shell.json`, the clipboard bridge (when a Mac
is configured), Pi's extensions, Claude Code provider and packages, Matt Pocock's pinned skills, the retired-memory
cleanup and `forgejo-map` in `~/.local/bin`.

## Sub-features

- `refused`: a host that does not identify as Omarchy (no `ID=omarchy` in `/etc/os-release`, no `omarchy` command) is
  refused with exit 1 and nothing written.
- `check`: every reconciler runs in check mode; the home is unchanged and no `pi` or `omarchy` command runs.
- `apply`: each reconciler's effect lands, Omarchy's own `.bashrc` lines stay first, Omarchy's plugin stays in
  `shell.json` with ours added once after a backup, a foreign `~/.pi/agent/AGENTS.md` is kept, Hermes is skipped, no
  clipboard unit without a configured Mac.
- `repeat`: a second apply changes no path, and a check after it proposes nothing.

## How to get to it (user POV)

- `./scripts/setup-omarchy.sh --check`, then `--apply`, on an Omarchy host (AGENTS.md, "DEPLOYMENT PROFILES").

## Driving it with dotfiles-verify

Preconditions:

- `doctor` passes.
- Matt Pocock's pinned commit is reachable (see Gotchas).
- The journey stubs `pi`/`claude` (`stub_pi`) and `omarchy`. The `omarchy` stub is what makes the host count as
  Omarchy, as the real command would; it also receives `restart shell` on apply.

- **Refused.** `$V run omarchy-setup`. With `PATH` lacking the stubs, `--apply` exits 1, says `does not identify as
  Omarchy`, and the home's tree is unchanged.
- **Check.** A stock home (`.bashrc` with Omarchy's lines, `shell.json` with `{"id": "omarchy.foreign"}`). `--check`
  leaves the tree unchanged, exits 0, reaches `Agent commands (check)`, and neither stub was called.
- **Apply.** `--apply` exits 0. Read back: Pi `ship` link; no `~/.hermes`; `.bashrc` line 2 is still Omarchy's
  `source`; the aliases line and the Ble.sh line once each; the plugin link; `shell.json` plugin ids
  `["omarchy.foreign","snowboardtechie.auto-suspend"]` and `shell.json.pre-auto-suspend`; the seeded
  `~/.pi/agent/AGENTS.md` still a file with its text; `worker-watch.ts` linked; `defaultProvider` `claude-code`; the
  Matt Pocock checkout's `HEAD` equals the ledger's pin; `forgejo-map` linked; no `clipboard-bridge.service`.
- **Repeat.** Trees after the first and second apply are identical; a check after prints none of `would `, `MISSING`,
  `WOULD`, `Installed`, `appended`, `linked:`, `Linked`.

## Gotchas

- The sandbox has no network. `mattpocock_upstream` gives git a local bare copy of the upstream, made from
  `~/.pi/agent/upstreams/mattpocock-skills` (read only) when that holds the pin, else cloned once outside the sandbox.
  The clone's fetch is therefore not proven, only the checkout at the pin and the settings entries.
- `pi install` is a stub that edits `settings.json`; nothing is downloaded. Whether Pi then loads the package is not
  proven.
- The clipboard bridge skips at `wl-paste is not installed`, before it reads the host file. Its unit writing is in
  `tests/test-omarchy-clipboard-bridge.sh`.
- macOS `bash` runs the scripts, not Omarchy's. GNU-only flags would pass here and fail there only where the script
  has no BSD fallback (the auto-suspend reconciler has one for `stat`).
