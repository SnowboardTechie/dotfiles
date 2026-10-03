# Explicit per-worker YOLO control from Matrix

## Authority and relationship

Bryan explicitly approved adding this capability in the coordinator conversation:
he does not want YOLO enabled by default, but does not want the private encrypted
Matrix control room's functionality unnecessarily blocked. The parent proposed
smart approvals by default, explicit per-worker YOLO requests through Matrix,
no autonomous coordinator toggles, acknowledgement and actual-mode verification;
Bryan answered yes (`yp`).

This amends only the earlier blanket no-YOLO policy for explicitly authorized
existing Hermes workers. Default startup remains smart, frozen process bypass
false, no --yolo flag, no arbitrary launch arguments. Preserve the original
workflow, guarded-admission scope, exact runtime identity, origin ownership and
all installation/restart/live-canary/publication boundaries. No activation is
implied. This is a newly approved feature, not permission to reopen original
consumed correction passes or disguise another correction-budget reset.

The already-running first guarded-admission correction must finish first. Its
runtime-identity correction remains required. Restricting native commands in
model-controlled task fields is compatible with this feature only when a human
control path is supplied: task text is not the privileged-control API. Do not
remove Hermes's native capabilities or make global permission-policy changes.

Correction 1 has now completed. Parent fresh-process handler probes reproduced
a newly introduced ordinary-task restriction: digit- and quote-prefixed briefs
are rejected by the worker's letter-first rule. A narrowly conditional second
and FINAL guarded-admission correction is governed separately by
`/Users/bryan/.hermes/cache/scratch/matrix-herdr-admission/correction2-contract.md`.
It may be performed in the same next worker turn as this approved feature, but
the two scopes and budgets remain distinct. Neither permits a third correction
of guarded admission or changes to unchanged original Claude behavior.

## Intended user interaction

Register a native plugin command:

    /herdr-yolo <worker-id> on
    /herdr-yolo <worker-id> off
    /herdr-yolo <worker-id> status

This acts on an existing admitted Hermes worker owned by that exact Matrix
room/thread/user. It is not a model tool. The coordinator may explain the
command and identify the owned worker, but may not invoke the control operation
on its own or in response to worker output. A native command typed by Bryan
bypasses the model and acknowledges the observed worker mode back to that
conversation. Ordinary task briefs/follow-ups continue through existing tools.

Only idle, settled admitted workers are eligible for mode changes. Do not send
control text into a running task or approval dialog. Explain that human pane
interaction remains available when a worker is blocked; do not promise mid-turn
or dialog handling that native APIs cannot prove. YOLO applies to that existing
worker/session until explicitly disabled or closed; it never becomes the default
for other workers. Status/acknowledgements must clearly show when bypass is active.

## Inspected native API

Installed clean Hermes source: 4ed093cb6be8a2fadb39e770898f6989fc67201d.

- hermes_cli/plugins.py:678 register_command accepts a sync or async raw-args
  handler; a slash command is separate from model tool registration.
- gateway/run_inbound.py:1085-1143 dispatches plugin commands before the agent
  turn, binds build_session_context(source, config) under _session_env_scope,
  derives the source session key, and carries ContextVars to sync handlers in
  the executor. No fake caller/environment identity or new core hook is needed.
- hermes_cli/cli_session_mixin.py:884-919 implements /yolo as a per-session toggle,
  not global config mutation. /status reports actual engine mode/bypass. The
  native toggle best-effort persists its session flag; preserve existing sessions.
- Existing plugin trusted-context/default-denial policy and ownership ledger are
  the enforcement seam. No raw environment fallback, no model-supplied origin.

Do not modify installed Hermes/Herdr source or invent an alternative dispatch
path. Fail closed if this supported gateway command-context boundary is absent.

## Required behavior

1. Keep all six existing tool schemas free of arbitrary command, permission or
   YOLO-toggle parameters. Register this as one native slash command, with
   strict worker/action parsing and concise usage on invalid input.
2. Require actual trusted Matrix origin and configured user/room/project scope,
   exact owned worker, supported Hermes kind, unchanged endpoint/pane/terminal/
   process/session/Git identity and lifecycle/session leases. Refuse delegated,
   cron, unbound CLI, foreign room/user/thread or revoked-project control.
3. Status is read-only. For on/off, observe the actual current mode through the
   existing identity-checked native status path before any toggle. Validate smart
   base approvals; accept only recognized smart/no-bypass or smart/YOLO suffix.
   Do not accept approvals off, different model/profile/session or wrong runtime.
4. Repeating the same desired on/off request is idempotent. Send native /yolo at
   most once when observed mode differs. Read actual mode afterwards with exact
   process/session fencing; only observed desired mode permits a success claim.
   Lost acknowledgement does not justify another toggle. Interrupted/ambiguous
   changes preserve ownership and durable recoverable uncertainty; resolve with
   observation, not blind retries or configuration rewrites.
5. Persist a strict per-worker authorized/verified mode and any minimal pending
   control state needed for crash-safe reconciliation in the existing private
   ledger. Fresh worker mode is smart/no-bypass. Model task input revalidation
   must recognize an explicitly authorized, verified active bypass for that same
   worker; it must not reject all later tasks merely because YOLO is on.
   Unrequested policy drift is still surfaced/refused, not silently adopted.
6. Expose mode in worker status/acknowledgements so Bryan and coordinator can tell
   which worker is running YOLO. Preserve owned-only cleanup and useful session
   locators. Do not apply mode choice to other workers or future startup defaults.
7. Update package guidance/security assessment to distinguish a safe default
   from explicitly user-selected capability. Private encryption and exact-user
   scope are meaningful authorization controls. State accepted native same-user
   residual risk without adding unrelated hardening or claiming a sandbox.

## Implementation and acceptance bounds

Use the SAME visible matrix-herdr-admission Claude Opus/xhigh worker after its
current turn settles. One bounded feature implementation turn, one bundled
correction and one narrowly conditional second correction for this feature only.
The original and guarded-admission correction counts remain recorded separately.
No new implementation worker or nested agent is authorized by this amendment.

Worker may edit only hermes/plugins/herdr-gateway/** and
hermes/test_herdr_gateway_plugin.py. Parent owns this authority document,
integrated acceptance, deployment wiring, security review, activation approval,
live proof and publication. All prior prohibitions remain: no worker staging,
commit/push, installs, activation/settings/restarts/messages/live canaries,
runtime/source updates, new dependencies, credentials/crypto/soul/memory edits,
destructive Git/history rewriting or unrelated changes.

Test RED/GREEN through registered native command handlers and public task tools
with real filesystem/external fake Herdr boundaries. Exercise default startup
unchanged; authorized on/off/status; idempotent requests; task follow-up with
explicitly enabled mode; wrong ownership/principal/thread; missing/ambiguous
context; unsupported kind, wrong runtime/session/base approvals; running/blocked
workers; observed mode drift; lost acknowledgements and interrupted/reloaded
control state; concurrent control/task/close; exact cleanup. Add a focused
installed-runtime dispatch-context proof where possible without activating a
plugin or running a model. Synthetic dispatch proof is not live Matrix evidence.

Run full host and available installed-Python suite, plugin doctor/validate and
git diff --check. Report exact RED/GREEN and gate output. Parent independently
reviews the complete stabilized candidate and obtains targeted Risk review,
then requests the still-separate specific install/config/restart/Matrix-canary
approval. No READY TO TEST claim without actual user-origin workflow proof.
