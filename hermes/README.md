# Git-backed Hermes assets

This directory preserves Bryan-authored Hermes assets without treating the mutable
`~/.hermes` runtime as dotfiles.

## Managed here

- `skills/`: the Hermes-local skills reported by `hermes skills list --source local`.
- `scripts/`: authored automation source. Compiled binaries remain local.
- `automations/`: declarative prompts and schedules for named cron jobs.
- `orchestrators/`: reusable durable-goal contract templates and validation.
- `webhooks/`: bounded event-trigger pilot contracts and activation gates.
- `plugins/herdr-gateway/`: the origin-scoped, request-bound visible-worker
  integration being prepared for Matrix-first work. See
  [the workflow contract](workflows/matrix-first-herdr.md) and
  [the plugin's setup and security boundaries](plugins/herdr-gateway/README.md).
  The reviewed pilot is installed and enabled on Studio's default profile, scoped
  to the approved private Matrix room and this repository. Native runtime/status
  verification passed; the final user-origin Matrix workflow test is pending.
  It remains outside the automatic deployment manifest during this pilot.
  It adds no standing coordinator or network bridge.
- `matrix-native/` + `reconcile_matrix_native.py`: reproducible macOS-native
  Matrix dependencies, including the pinned encryption source and compiler fix.
- `manifest.json`: the explicit allowlist installed on Studio.

Hermes built-in skills are supplied by the Hermes installation and are not copied.
Hub-installed skills should be recorded by source identifier if any are added later.
Credentials, sessions, memories, databases, logs, Matrix crypto state, cron output,
locks, caches, and `cron/jobs.json` remain local and untracked.

## Memory

Hermes uses only its built-in memory (`MEMORY.md`, `USER.md`, session search,
and native compaction); no external memory provider is selected or installed.
The retired Hindsight provider, its `hindsight-scoped` adapter, and the
Granola-to-Hindsight import jobs were removed on 2026-09-29. The installer
retires their managed config link and copied importer (`removedLinks`,
`removedCopiedScripts`) but never deletes native memory. Granola remains the
source of record for meeting notes; the SGG morning brief reads it directly.

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
7. Reconciles the native Matrix dependency plugin on Studio without editing
   Hermes core, changing credentials, or deleting its encryption store.

## Native Matrix on Studio

Hermes's managed-runtime migration can leave a healthy gateway process without
Matrix dependencies. The upstream `matrix` extra is Linux-gated, but an enabled
dependency-only plugin can retain a native macOS override. This keeps chatting
and encryption on Studio; no Linux proxy or container is needed.

The tracked recipe downloads python-olm 3.2.16 with a pinned SHA256, fixes one
incorrectly const pointer in bundled libolm, and builds against the interpreter
selected by the current Hermes launcher. The wheel and a build receipt stay at
`~/.hermes/platforms/matrix/native/`; the generated dependency plugin is a frozen
copy at `~/.hermes/plugins/matrix-native-deps/`. No machine-specific path or build
output belongs in Git. The generated plugin uses `[tool.uv.sources]` because PM
filters direct-URL requirements from plugin manifests. Its declaration is included
in subsequent managed environment resolutions, rather than pip-installed into a
sealed generation. A changed Python minor version rebuilds the local wheel.

Requirements: macOS arm64, a managed Hermes source launcher, uv, and the Xcode
command-line C/C++ tools. libolm is statically built from the verified archive;
no Homebrew libolm is required. The build sets its macOS deployment target to 11.
Only Studio's current macOS/Python combination has been exercised end to end.

```bash
python3 hermes/reconcile_matrix_native.py --apply
python3 hermes/reconcile_matrix_native.py --check
python3 hermes/test_matrix_native.py
python3 hermes/test_install.py
```

The normal Studio installer invokes the same reconciler. Use
`--skip-native-matrix` and `--skip-plugin-activation` only for isolated installer
tests, where an asset-copy check must not initialize a real Hermes runtime.
`--check` is read-only
and verifies both the tracked installation and a fresh-runtime encryption round
trip. Applying backs up a changed installed plugin and never restarts the gateway
automatically. If dependencies changed, use `hermes gateway restart`, allow active
cron work to drain, then check for fresh cross-signing, E2EE, initial-sync, and
Matrix-connected log lines. If the restart CLI times out while draining and the
gateway subsequently exits cleanly, run `hermes gateway start`. Finish with a new
message and readable reply from the user's Matrix client: a startup notification
alone is not end-to-end proof.

Keep Matrix credentials and `platforms/matrix/store/crypto.db` unchanged for this
dependency repair. Removing the plugin's enabled state or deleting its local wheel
removes the override; restore it by running the tracked `--apply` command.

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

Every cron definition declares `deliveryIntent`. Recurring human briefings,
reports, orientations, and reminders use `briefing`; the reconciler requires
them to set `attachToSession: true` and provide Matrix continuation metadata,
so each delivery opens its own replyable thread with the briefing in context.
Fire-and-forget monitors and change notifications use `alert` and remain flat
room messages. This distinction is enforced during reconciliation rather than
left as a convention for future jobs.

Run directly when needed:

```bash
python3 hermes/install.py --adopt-identical
```

For validation against a temporary home, use `--force-host` and optionally
`--skip-cron`. The manifest intentionally contains no credentials or mutable job
state.
