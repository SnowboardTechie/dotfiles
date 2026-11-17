# Agent commands on PATH

`scripts/reconcile-agent-commands.sh` links each executable in `dot-agents/bin/` (today `forgejo-map`) into
`~/.local/bin`. It repairs its own stale links, and refuses, with exit 1 in both modes, to replace anything else.

## Sub-features

- `link`: check reports `MISSING … (would link)` and writes nothing; apply links; a second apply reports `OK`.
- `runs-through-link`: the linked `forgejo-map` finds the Wayfinder adapter through the link (`--help`), and outside a
  Git repository without `--origin` it stops with exit 2 and says to pass `--origin`.
- `stale`: a dangling link whose target ends in `dot-agents/bin/forgejo-map` (a removed worktree) is called `STALE` by
  check, left by check, and repointed here by apply.
- `foreign`: a regular file, and a live link into another checkout, are reported as `CONFLICT` with exit 1 in check
  and apply, and the home is unchanged.

## How to get to it (user POV)

- `scripts/reconcile-agent-commands.sh --check|--apply`; the last reconciler of `setup-omarchy.sh` and a step of
  `setup-platform-configs.sh`. Then `forgejo-map …` from any shell with `~/.local/bin` on `PATH`.

## Driving it with dotfiles-verify

Preconditions:

- `doctor` passes. No stubs.

- `$V run agent-commands`. Each sub-feature is one step. The `foreign` step runs once with a file and once with a live
  link, compares trees before and after both modes, and checks each exit code.

## Gotchas

- `forgejo-map frontier` is driven only to its no-origin refusal; nothing reaches Forgejo (the sandbox has no network).
  The adapter's own behaviour is tested in `dot-agents/skills/wayfinder/tests/test_forgejo_wayfinder.py`.
- The `PATH` note (`~/.local/bin is not on PATH`) always prints here; nothing asserts on it.
