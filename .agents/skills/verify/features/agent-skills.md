# Agent skill links

`scripts/reconcile-agent-skills.sh` links the curated skills in `dot-agents/skills/` into each tool's skills directory:
`~/.claude/skills`, `~/.config/opencode/skills`, `~/.agents/skills` (Codex, also read by Pi), `~/.pi/agent/skills` and
`~/.hermes/skills/personal`. The `*_SKILLS` arrays in the script decide which tool gets which skill. Both setup scripts
run it.

## Sub-features

- `check`: reports the links it would make and writes nothing, not even the directories.
- `apply`: `ship` links into the pool for each of the five tools; `draw-it` reaches Pi and none of the other four;
  `grilling`, `tdd`, `wayfinder` and `diagnosing-bugs`, kept out of `~/.agents/skills` so Matt Pocock's copies win in
  Pi, are absent there. Other curated names are not asserted one by one.
- `repeat`: a second apply changes no path; a check after apply proposes nothing.
- `foreign`: an uncurated real directory, a real directory on a curated name (`~/.pi/agent/skills/ship`), a regular
  file on a curated name (`~/.config/opencode/skills/ship`), a foreign link on a curated name and a broken foreign link
  are kept as they were, with their contents; both real collisions are reported; a pool link no longer curated and a
  dangling link to a retired pool skill are pruned.

## How to get to it (user POV)

- `scripts/reconcile-agent-skills.sh --check` or `--apply`; also step one of `scripts/setup-omarchy.sh` and the
  "Setting up agent skills" step of `setup-platform-configs.sh`.

## Driving it with dotfiles-verify

Preconditions:

- `doctor` passes. No stubs needed: the script uses only bash and perl.

- **Check.** `$V run agent-skills`. On an empty home, `--check` exits 0, names `would create link: ship`, and the
  `before` and `after-check` trees are identical.
- **Apply.** `ship` links into the pool in all five directories; `.pi/agent/skills/draw-it` exists and no
  `draw-it` exists in the Claude, OpenCode, Codex or Hermes directories; none of the four Matt Pocock names exists in
  `.agents/skills`.
- **Repeat.** The trees after the first and second apply are identical, and a further check prints no `would `.
- **Foreign.** A lived-in home holds `~/.pi/agent/skills/my-own/` (real), `~/.pi/agent/skills/ship/SKILL.md` (real,
  `my own ship`), `~/.config/opencode/skills/ship` (a regular file), `~/.claude/skills/ship` → a directory of the
  home's own, `~/.claude/skills/omarchy` → `/nowhere/omarchy`, `~/.claude/skills/gamedev` → the pool (not curated for
  Claude) and `~/.claude/skills/vault-capture` → the retired pool path. After check (tree unchanged) and apply:
  `my-own` keeps its content, the real Pi `ship` and the OpenCode `ship` file keep theirs and both are reported
  (`exists and is not a symlink; preserved`), Claude's `ship` still points where it did and `Claude/ship is a foreign symlink; preserved` is
  printed, `omarchy` is still a link, `gamedev` and `vault-capture` are gone.

## Gotchas

- The journey reads the curation from the script only through what lands in the home. It does not re-derive the
  arrays, so a skill added to one tool's array passes unless a claim names it.
- `RECONCILE_HERMES_SKILLS=0` (set by `setup-omarchy.sh`) and `RECONCILE_OPENCODE_SKILLS=0` (Gnarbox) are not driven
  here; `omarchy-setup` covers the first, `tests/test-gnarbox-dotfiles-profile.sh` the second.
