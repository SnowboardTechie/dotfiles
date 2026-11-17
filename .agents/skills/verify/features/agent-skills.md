# Agent skill links

`scripts/reconcile-agent-skills.sh` links the curated skills in `dot-agents/skills/` into each harness's skills directory:
`~/.claude/skills`, `~/.config/opencode/skills`, `~/.agents/skills` (Codex, also read by Pi), `~/.pi/agent/skills` and
`~/.hermes/skills/personal`. The `*_SKILLS` arrays in the script decide which tool gets which skill. Both setup scripts
run it.

## Sub-features

- `check`: reports the links it would make and writes nothing, not even the directories.
- `apply`: `ship` links into the pool for each of the five harnesses; `draw-it` reaches Pi and none of the other four.
  Other curated names are not asserted one by one. Matt Pocock's skills are not in any list here: his checkout serves
  every harness through `scripts/reconcile-mattpocock-skills.sh` (see `omarchy-setup.md` and `platform-setup.md`).
- `repeat`: a second apply changes no path; a check after apply proposes nothing.
- `foreign`: an uncurated real directory, a real directory on a curated name (`~/.pi/agent/skills/ship`), a regular
  file on a curated name (`~/.config/opencode/skills/ship`), a foreign link on a curated name and a broken foreign link
  are kept as they were, with their contents; both real collisions are reported; a pool link no longer curated is
  pruned, and so are dangling links to retired pool skills, including the six adapted from Matt Pocock's that retired
  on 2026-11-16 (`grilling`, `guided-learning` seeded); a link into Matt Pocock's checkout is kept and counted on one
  line (`1 links to Matt Pocock's skills left to scripts/reconcile-mattpocock-skills.sh`), not listed as foreign.

## How to get to it (user POV)

- `scripts/reconcile-agent-skills.sh --check` or `--apply`; also step one of `scripts/setup-omarchy.sh` and the
  "Setting up agent skills" step of `setup-platform-configs.sh`.

## Driving it with dotfiles-verify

Preconditions:

- `doctor` passes. No stubs needed: the script uses only bash and perl.

- **Check.** `$V run agent-skills`. On an empty home, `--check` exits 0, names `would create link: ship`, and the
  `before` and `after-check` trees are identical.
- **Apply.** `ship` links into the pool in all five directories; `.pi/agent/skills/draw-it` exists and no
  `draw-it` exists in the Claude, OpenCode, Codex or Hermes directories.
- **Repeat.** The trees after the first and second apply are identical, and a further check prints no `would `.
- **Foreign.** A lived-in home holds `~/.pi/agent/skills/my-own/` (real), `~/.pi/agent/skills/ship/SKILL.md` (real,
  `my own ship`), `~/.config/opencode/skills/ship` (a regular file), `~/.claude/skills/ship` → a directory of the
  home's own, `~/.claude/skills/omarchy` → `/nowhere/omarchy`, `~/.claude/skills/gamedev` → the pool (not curated for
  Claude), `~/.claude/skills/vault-capture`, `~/.agents/skills/grilling` and `~/.hermes/skills/personal/guided-learning`
  → retired pool paths (dangling), and `~/.claude/skills/zoom-out` → `~/.local/share/mattpocock-skills/skills/engineering/zoom-out`.
  After check (tree unchanged) and apply:
  `my-own` keeps its content, the real Pi `ship` and the OpenCode `ship` file keep theirs and both are reported
  (`exists and is not a symlink; preserved`), Claude's `ship` still points where it did and `Claude/ship is a foreign symlink; preserved` is
  printed, `omarchy` is still a link, `gamedev` and the three retired links are gone, `zoom-out` still points into his
  checkout and is counted, not listed as `preserved (foreign symlink)`.

## Gotchas

- On macOS, `perl`'s `Cwd::abs_path` resolves a dangling link whose parent directory exists, so a dangling link into the
  pool is pruned as a "stale pool link" before `RETIRED_POOL_TARGETS` is consulted. Removing a name from that list
  therefore changes nothing here; it matters only where the parent is gone. No break targets the list itself.

- The journey reads the curation from the script only through what lands in the home. It does not re-derive the
  arrays, so a skill added to one tool's array passes unless a claim names it.
- `RECONCILE_HERMES_SKILLS=0` (set by `setup-omarchy.sh`) and `RECONCILE_OPENCODE_SKILLS=0` (Gnarbox) are not driven
  here; `omarchy-setup` covers the first, `tests/test-gnarbox-dotfiles-profile.sh` the second.
