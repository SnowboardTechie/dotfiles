# Guarded Hermes worker admission

## Authority and relationship to existing work

Bryan explicitly approved this new scope in the resumed coordinator session on
2026-10-02: guarded Hermes admission plus one new visible Claude Opus implementation
worker. This is an additive architecture decision, not a third correction of the
closed original worker. The original contract and implementation remain in
`matrix-first-herdr.md`; the current takeover facts are in
`matrix-first-herdr-handoff.md`. All their exclusions remain binding.

The original implementation's two correction passes remain consumed. This new
scope has one implementation turn, one bundled correction, and one conditional
bounded second correction for defects in this new scope only. A blocking defect
in unchanged original behavior must be reported to the coordinator, not silently
fixed or used to reset that original budget.

## Approved outcome

Subsequent explicit user authorization is in `matrix-first-herdr-yolo.md`:
smart/no-bypass remains mandatory for fresh startup, but Bryan may explicitly
change one admitted worker's session mode through a native Matrix command.
That exception supersedes blanket rejection of later user-authorized YOLO.
It does not authorize autonomous model toggles or weaken runtime identity.

The plugin must support an operator-configured Hermes worker through existing
local Herdr APIs. Before layout creation, validate the intended configuration,
permission/model policy, endpoint and supported launcher. A bounded owned startup
may then occur. Before the task brief is sent, independently verify the actual
foreground runtime, default profile, effective smart approvals with no YOLO
bypass, exact configured model/provider, and session identity. Refuse the task on
any uncertainty; close only the exact owned pane when identity permits verified
cleanup, otherwise retain recoverable ownership. No model task may be used to
establish admission.

This deliberately changes requirement 3's timing for Hermes: full actual-runtime
admission proof is required before task submission, not before layout creation.
Claude's capacity-before-layout and existing permission behavior do not change.
No hard sandbox is promised. Same-user shell and plugin execution remain the
accepted native guardrail posture.

## Observed viable boundary

A user-approved fresh startup through `herdr agent start --kind hermes` succeeded
on Herdr 0.9.3 with `idle`, `interactive_ready: true`, and an actual foreground
argv matching the installed managed launcher. The two public launchers generate
identical `--print-runtime-command` arrays. `workspace create --env KEY=VALUE`
is supported; `agent.start` accepts kind/pane/arguments but not an executable.

The native CLI `/status` command performs no model turn or configuration write.
It exposes session id, profile path, exact model/provider, actual approval mode
and a YOLO-bypass suffix when bypass is active. The observed fresh output had
smart approvals, zero tokens and no running agent. Its implementation is
`hermes_cli/cli_session_mixin.py::_show_session_status`, including the actual
approval engine's `is_approval_bypass_active_for_session` check. Do not send
`/config` or dump environments/authentication stores.

At fresh CLI startup, Herdr has no `agent_session`; `herdr-agent-state` v5's session
hook executes at first conversation. Use the inspected native status evidence to
bind the initial session, then require Herdr's reported session to agree once it
becomes available. Do not fabricate an integration report or resume an unrelated
session. Do not treat slash-command submission as observed model work: it has no
working transition and must not use the task activity gate.

Current installed Hermes clean source is
`4ed093cb6be8a2fadb39e770898f6989fc67201d`. Reinspect its public APIs before use.
No modification or update to that installed source is authorized.

## Implementation bounds

Worker edits only:
- `hermes/plugins/herdr-gateway/**`
- `hermes/test_herdr_gateway_plugin.py`

Preserve and adapt the existing package; no rebuild. Personal paths, room/user ids
and model selection stay in local operator settings, not shared-package code.
Define strict operator Hermes presets with exact model/provider, supported
reasoning effort, an absolute intended launcher and default profile/home
identity. Support only the classic CLI and default profile in this scope; fail
closed instead of implementing other profiles, TUI, arbitrary launch args or
fallback providers. Keep Claude presets unchanged.

Requirements:
1. Preflight rejects invalid presets, unsafe approvals, forbidden bypass flags,
   missing/incompatible endpoint or uninspectable launcher before layout creation.
   Validate the intended launcher's canonical runtime command and preserve the
   evidence needed to compare the actual launched foreground process.
2. Create an owned no-focus layout with narrowly pinned default-home/no-YOLO
   environment; never inject a fake caller pane or broaden inherited environment.
   Use native `agent start`; no raw pane-run startup bypass.
3. Hold the existing lifecycle lease throughout startup, status admission and
   first task submission. Verify exact pane/terminal/cwd and foreground runtime
   before and after the read-only status query. Require clean, fresh, unambiguous
   status evidence; repeated or stale status output must not admit a different
   worker. Ignore incidental words in the banner or prompt suggestions.
4. Persist strictly validated actual process/session identity in the existing
   owner-only crash-safe ledger before the task brief. Revalidate actual runtime
   and effective policy before later task input. Initial absent Herdr session is
   not grounds to guess; any later disagreement with the bound session refuses.
5. Never send the model task until every admission requirement passes. On failed
   admission, verified exact-owned cleanup or retained cleanup_required state is
   mandatory. Timeouts/lost acknowledgements must not resend slash commands or
   task briefs blindly, resurrect closed records, or discard ownership.
6. Keep origin/thread/user isolation, project revocation, capacity behavior for
   Claude, turn serialization, actual activity/settlement and owned-only cleanup.
   No tool answering arbitrary approval dialogs; blocked startup remains honest.
7. Update package manifest/docs/security assessment to distinguish preflight,
   post-start native status admission, initial session binding and residual
   same-user risk. Retain MIT provenance. No new dependencies, listeners,
   installers, hooks altering core, auto-update or persistent background loop.

## Acceptance seam and verification

Use the existing registered public handlers and external Herdr/launcher/context
boundaries. Tests use real filesystem state and fake external executables, not
internal collaborator mocks. Work RED/GREEN in vertical slices and retain the
actual failing/passing output.

Exercise successful admitted startup with no initial Herdr session; subsequent
matching session report; wrong executable/argv/profile/model/provider/session;
smart disabled or YOLO effective; malformed/ambiguous/stale status; unsafe preset;
preflight refusal before layout; admission refusal with brief unsent and exact
cleanup; startup blocked/unknown; process replacement around status and later
input; lost status acknowledgement; concurrency and ledger validation of new
fields. Existing tests must continue to pass, except the explicitly superseded
blanket Hermes-refusal assertion is replaced by real fail-closed admission tests.

Worker runs host and installed managed-Python tests, plugin doctor and validate,
and reports exact output and remaining limitations. These are not live Matrix
acceptance. No live worker canary or model turn is authorized for the worker.
The parent independently inspects the integrated artifact, runs the integrated
Standards/Spec/Risk/Ponytail review plus targeted independent Risk review, and
obtains specific activation/restart/Matrix-canary approval before deployment.

## Permissions

Visible Claude `claude-opus-5-5`, xhigh, auto permissions, no fallback or nested
agents. No worker commit/push/staging, changes outside allowed paths, destructive
Git operations or history rewriting, new dependencies/installations, activation,
configuration edits, gateway restart, external messages, runtime updates,
credential/crypto-store/soul/memory changes, or upstream contact. Preserve all
unrelated work. The parent owns the eventual direct-main publication and exact
remote readback per repository policy, only after full acceptance and live proof.
