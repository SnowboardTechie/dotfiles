# Git-backed Hermes assets

This directory preserves Bryan-authored Hermes assets without treating the mutable
`~/.hermes` runtime as dotfiles.

## Managed here

- `skills/`: the Hermes-local skills reported by `hermes skills list --source local`.
- `scripts/`: authored automation source. Compiled binaries remain local.
- `automations/`: declarative prompts and schedules for named cron jobs.
- `orchestrators/`: reusable durable-goal contract templates and validation.
- `webhooks/`: bounded event-trigger pilot contracts and activation gates.
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
6. Binds continuable Matrix jobs to one explicit room and the single local
   `MATRIX_ALLOWED_USERS` principal without committing that account identifier.

## Monitor jobs

A cron job may declare `monitorScript`: a bare filename under `scripts/` that
the scheduler runs **before** the agent, on every tick. It hashes the script's
exact stdout bytes and suppresses the whole run — no model call, no delivery —
when they are unchanged. That makes a monitor job nearly free on quiet weeks and
loud only when its source actually moves.

Two rules follow, and both are enforced rather than documented and hoped for:

- **The output must be stable.** No timestamp, no dict-order leakage, no local
  path. Anything that varies run to run makes every tick look like a change and
  turns the job into noise.
- **A source failure must exit non-zero.** The scheduler records it as an error;
  a monitor that returns success after failing to reach its source reports
  "nothing changed", which is the one lie that matters here.

`reconcile_cron.py` validates `monitorScript` before calling the API — a bare
filename, no path, never combined with `noAgent` — because the scheduler's own
rejection arrives after the reconciler would have reported the job synchronized.
It is verified on readback like every other field, and sent on *every* job
(empty to clear) so dropping the key from a manifest entry actually removes the
live monitor.

**A monitor script must be in `copiedScripts`.** `_run_job_script` resolves the
path and then requires containment in `HERMES_HOME/scripts`; `.resolve()`
follows symlinks, so a symlink into this repository resolves outside the sandbox
and is rejected at fire time. A copied script cannot locate repository files
from `__file__` either — it should use the job's `workdir`, which the scheduler
sets as the process cwd, or an explicit non-secret environment variable.

Continuable jobs require an existing per-user Matrix session in the target
room. Send one message in the room before the first scheduled delivery. The
installer preserves finite repeat progress while reconciling delivery,
`attach_to_session`, and the local continuation origin.

Run directly when needed:

```bash
python3 hermes/install.py --adopt-identical
```

For validation against a temporary home, use `--force-host` and optionally
`--skip-cron`. The manifest intentionally contains no credentials or mutable job
state.
