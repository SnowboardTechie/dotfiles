# Git-backed Hermes assets

This directory preserves Bryan-authored Hermes assets without treating the mutable
`~/.hermes` runtime as dotfiles.

## Managed here

- `skills/`: the Hermes-local skills reported by `hermes skills list --source local`.
- `scripts/`: authored automation source. Compiled binaries remain local.
- `automations/`: declarative prompts and schedules for named cron jobs.
- `manifest.json`: the explicit allowlist installed on Studio.

Hermes built-in skills are supplied by the Hermes installation and are not copied.
Hub-installed skills should be recorded by source identifier if any are added later.
Credentials, sessions, memories, databases, logs, Matrix crypto state, cron output,
locks, caches, and `cron/jobs.json` remain local and untracked.

## Installation

`setup-platform-configs.sh` invokes the installer on `Bryans-Mac-Studio`. It:

1. Links only manifest-listed local skills and source scripts into `~/.hermes`.
   The cron entry script is installed as a regular copy because Hermes rejects
   cron scripts whose symlinks resolve outside its scripts sandbox.
2. Refuses foreign symlinks or non-identical existing files/directories.
3. With `--adopt-identical`, backs up identical pre-existing content before linking;
   replaced installed copies are also backed up rather than silently discarded.
4. Compiles the EventKit Calendar collector locally.
5. Creates or updates cron jobs by exact name through Hermes's cron API.

Run directly when needed:

```bash
python3 hermes/install.py --adopt-identical
```

For validation against a temporary home, use `--force-host` and optionally
`--skip-cron`. The manifest intentionally contains no credentials or mutable job
state.
