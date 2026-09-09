# Scoped Hindsight memory

Select `memory.provider: hindsight-scoped` in the default Hermes profile.
The provider inherits the installed, bundled Hindsight implementation and reads
its normal profile-scoped `hindsight/config.json`. No additional dependencies,
services, credentials, banks, or transport implementations are introduced.

Primary interactive sessions use automatic recall and retention plus explicit
tools. Scheduled (`platform=cron`) and non-primary background contexts retain
explicit tools only; the scheduler's existing toolset allowlist still controls
whether those tools are exposed. Deliberate SGG collector/import API calls are
unchanged. Never disable the entire profile to restrict one automation.

Automatic recall runs through the supported `pre_llm_call` hook with a 25-second
API deadline, below Hermes's default 30-second hook deadline. The core memory
prefetch path has an unconfigurable eight-second deadline that can discard a
successful but slower Hindsight response. The adapter disables that duplicate
prefetch path; automatic retention still uses the normal provider lifecycle.
No bundled Hermes files are patched. Keep `plugins.hook_callback_timeout` at its
default or greater than 25 seconds.

`recall_sync` makes the first/current question receive relevant context rather
than waiting for a later turn. Recall includes observations and raw facts so a
new correction can be retrieved before asynchronous consolidation completes.
The request budget is 1,536 tokens; returned context is also capped to a ranked
prefix of 8,000 characters (or the configured lower hook-spill threshold).
This prevents generic head/tail spilling from discarding the useful middle and
making the model perform manual file reads to recover its own memory. Truncation
is explicit and deeper recall remains available. Live sources and the user's
current instructions remain authoritative.

## Deployment

`hermes/install.py` installs this directory through its managed plugin copier,
enables it, and selects the manifest's `memoryProvider` through Hermes's config
CLI. For a targeted repair, deploy/enable/select this provider BEFORE changing
the live Hindsight config from tools-only to hybrid. Do not run the unrelated
cron reconciler merely to change memory. Existing agents keep their initialized
provider; fresh CLI sessions and newly constructed gateway agents use the new
selection. Do not kill active sessions to reload it.

## Security boundary and verification

The adapter adds no transport implementation or filesystem writes and never
changes process-global environment or shared configuration. It restricts the
instance-local automatic-memory flags after upstream initialization, before any
turn can run. The recall hook checks host-supplied platform/parent-session fields,
the active provider selection, and the explicit recall opt-out before contacting
Hindsight. Skill scaffolding and trivial continuations are not recall queries.
The read-only hook creates and closes a native client; it never retains content.
Upstream remains responsible for API authentication, secret handling, retention,
and network failures. Missing/incompatible upstream imports must surface as
provider initialization failure, not a fallback to unscoped automatic retention.

The small compatibility surface is `HindsightMemoryProvider.initialize` plus
`_memory_mode`, `_auto_recall`, and `_auto_retain`. Run the real provider lifecycle
tests after Hermes upgrades, including cron session switch/shutdown, the recall
hook, inline context budgets, and concurrent interactive/cron instances:

    ~/.hermes/hermes-agent/venv/bin/python -m unittest discover -s hermes -p 'test_hindsight_scoped.py'

Tests stub only the remote Hindsight API and version probe. Live acceptance must
also verify real automatic retain, fresh-session recall, a superseding correction,
and zero automatic memory calls from a scheduled-agent lifecycle. Verify the
model-visible `api_content`, not just the provider response: timeout and output
spilling can both make a successful API call invisible to the model. Require a
fresh actual Hermes session to answer from injected memory with zero tool calls,
and read back its auto-retained document. Delete only disposable test banks and
verification-only documents; preserve real confirmed corrections and transcripts.
A green health endpoint or explicit recall alone does not prove automatic memory.

Rollback selects `memory.provider: hindsight` only AFTER disabling automatic
recall/retention in the shared Hindsight config; otherwise scheduled jobs would
inherit automatic memory. Preserve the server database and session history.
