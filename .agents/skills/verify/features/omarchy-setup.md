# Omarchy additive setup

`scripts/setup-omarchy.sh --check|--apply` is the only supported install on an Omarchy host. It runs a fixed list of
reconcilers that add to Omarchy's own configuration and never replace it: skill links, one marked line each in
`~/.bashrc` for the shared aliases and Ble.sh, the auto-suspend plugin in `shell.json`, the clipboard bridge (when a Mac
is configured), Pi's extensions, Claude Code provider and packages, Matt Pocock's pinned skills, the retired-memory
cleanup and `forgejo-map` in `~/.local/bin`.

## Sub-features

- `refused`: a host that does not identify as Omarchy (no `ID=omarchy` in `/etc/os-release`, no `omarchy` command) is
  refused with exit 1 and nothing written.
- `check`: each of the eleven reconcilers prints its check-mode header, each except the clipboard bridge (which skips)
  proposes its change, no `(apply)` header appears, the home is unchanged, and no `pi` or `omarchy` command runs.
- `apply`: each reconciler's effect lands (read back below), Omarchy's own `.bashrc` lines stay first, Omarchy's
  plugin stays in `shell.json` with ours added once after a backup, `omarchy restart shell` is called once, a foreign
  `~/.pi/agent/AGENTS.md` is kept, Hermes is skipped, no clipboard unit without a configured Mac, and no `stow`, `sudo`
  or `systemctl` call.
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
- **Check.** A stock home (`.bashrc` with Omarchy's lines, `shell.json` with `{"id": "omarchy.foreign"}`, and Pi
  settings holding the retired Hindsight extension beside `/opt/pi/mine.js`). `--check` leaves the tree unchanged and
  exits 0. For each reconciler the output has its header (`Reconciling agent skills (check)`, `Shell additions (check)`,
  …, `Agent commands (check)`) and its proposal (`would create link: ship`, `would append: …`, `would enable: …`,
  `MISSING`, `WOULD SET defaultProvider`, `MISSING package npm:pi-web-access@`, `checkout: missing`,
  `would remove from`, `(would link)`); no `(apply)` header; neither stub was called.
- **Apply.** `--apply` exits 0. Read back: Pi `ship` link; no `~/.hermes`; `.bashrc` line 2 is still Omarchy's
  `source`; the aliases line and the Ble.sh line once each; the plugin link; `shell.json` plugin ids
  `["omarchy.foreign","snowboardtechie.auto-suspend"]` and `shell.json.pre-auto-suspend`; the `omarchy` call log is
  exactly `omarchy restart shell`; Pi's `packages` holds exactly the two pins from `reconcile-pi-packages.sh`; Pi's
  `extensions` is `["/opt/pi/mine.js"]`; the seeded
  `~/.pi/agent/AGENTS.md` still a file with its text; `background-agent-watch.ts` linked; `defaultProvider` `claude-code`; the
  Matt Pocock checkout at `~/.local/share/mattpocock-skills` has `HEAD` at the ledger's pin and nothing is left under
  `~/.pi/agent/upstreams`; Pi's `skills` is exactly his `skills/engineering` and `skills/productivity` directories; his
  `tdd` is linked into both `~/.claude/skills` and `~/.config/opencode/skills`; `forgejo-map` linked; no `clipboard-bridge.service`; the
  `stow`, `sudo` and `systemctl` call logs are empty.
- **Repeat.** Trees after the first and second apply are identical; a check after prints none of `would `, `MISSING`,
  `WOULD`, `Installed`, `appended`, `linked:`, `Linked`.

## Gotchas

- The sandbox has no network. `mattpocock_upstream` gives git a local bare copy of the upstream, copied read-only
  from a local clone that holds the pin (see `../SKILL.md`, Gotchas). Without one the journey fails at setup; it never
  fetches. The real clone's fetch is not proven, only the checkout at the pin, the Pi settings entries and the links.
- Of his 27 promoted skills only `tdd` is read back as a link; the rest are covered by the repeat run's identical
  trees, not one by one. Moving a checkout from the old `~/.pi/agent/upstreams` path is not driven here;
  `tests/test-reconcile-mattpocock-skills.sh` covers it.
- `pi install` is a stub that edits `settings.json`; nothing is downloaded. Whether Pi then loads the package is not
  proven.
- The clipboard bridge skips at `wl-paste is not installed`, before it reads the host file. Its unit writing is in
  `tests/test-omarchy-clipboard-bridge.sh`.
- macOS `bash` runs the scripts, not Omarchy's. GNU-only flags would pass here and fail there only where the script
  has no BSD fallback (the auto-suspend reconciler has one for `stat`).
