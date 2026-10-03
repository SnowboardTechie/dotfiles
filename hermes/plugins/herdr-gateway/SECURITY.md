# Security assessment

Scope: this plugin directory as a candidate for one Hermes profile and one local
Herdr server on the same machine, reviewed against Hermes `f42f579`, with the Hermes
worker admission and `/herdr-yolo` command re-inspected against Hermes `4ed093c` plus
the repository's `hermes/runtime-patches/cli-status-session.patch`, and Herdr 0.9.3
(protocol 22). This is the implementer's assessment, not the independent review that
activation requires.

## Execution privilege

Hermes plugins are not sandboxed. Once enabled, this code runs with the full
privileges of the Hermes process, and the workers it starts run as the same user
inside Herdr panes. Behavioral request authorization (origins, projects, presets,
ownership) is the boundary. It is not a kernel sandbox, and it does not prove that
a human approved any particular model-written text. The package is standard-library
Python with no dependencies, installers, listeners, daemons or update paths.

## Authorization

- **Default deny.** No `herdr_bin`, no `origins` or any malformed setting means
  every tool refuses before contacting Herdr.
- **Delegated children.** Before anything else, the gateway asks Hermes's own
  delegation boundary (`agent.delegation_context.is_delegated_child_process_context`,
  which covers the in-process child ContextVar and the spawned-descendant
  environment marker). Children are refused (`delegated_child_refused`). A runtime
  without that module cannot rule children out and is refused (`runtime_unsupported`).
- **Trusted origin.** Platform, chat, thread, user and session key are read only from
  the ContextVars the Hermes gateway binds for the current turn, enumerated through
  `contextvars.copy_context()`. `get_session_env` is deliberately not used because it
  falls back to `os.environ`. Missing or cleared values, duplicate bindings, a bound
  session id that differs from the dispatching session, and cron turns all fail
  closed. Tool schemas carry no origin, kind, model, permission, mode or launch fields,
  and handlers reject any argument the schema does not define.
- **The one control command.** `/herdr-yolo` is a native plugin command, not a tool.
  Hermes's gateway dispatches it before any agent turn
  (`gateway/run_inbound.py::_hm_dispatch_quick_and_plugin_commands`), binding the
  message's source with `build_session_context` under `_session_env_scope`. It runs a
  sync handler on a pool thread with those ContextVars copied. The handler applies
  exactly the tools' checks: delegated child, cron, unbound, ambiguous, other room,
  user or thread, revoked project, unowned id. The classic CLI calls plugin commands with
  no source bound, so there it is `origin_unbound`. Any other surface must still match a
  configured origin.
- **Scope.** An origin entry admits an exact platform + chat id + listed user id.
  Ownership is the exact `(platform, chat_id, thread_id, user_id)`. Other threads,
  other users and hand-started Herdr agents get the same `worker_not_found` as a
  nonexistent id, so existence does not leak.
- **Directories, now and later.** At start, `cwd` is resolved with `realpath` and must
  lie inside a configured project, so symlink escapes are refused. Before every
  prompt, wait, read or status probe, the recorded directory must still resolve to
  itself and still lie inside a *currently* configured project. Removing a project
  or retargeting a project symlink therefore revokes driving and reading existing
  workers (`cwd_not_permitted`), and status reports them without querying them.
  Only `herdr_close` stays available for such a worker. It is authority-reducing: it
  acts only on the exact owned pane after identity checks, returns no pane output,
  and sends no input. Removing the whole origin entry refuses every tool, close
  included.

## Launch integrity

**Asserted at launch, not observed.** A Claude worker is started with exactly
`--permission-mode <default|acceptEdits|plan|auto> --model <exact id> --effort
<level> --name <task>`. Bypass modes, extra arguments, fallback models and
model-supplied values are impossible by construction, and a preset with anything
else disables the gateway. Herdr does not report the running model, effort or
permission mode, so the gateway asserts these through argv and does not verify
them afterwards.

**Observed through Herdr at runtime.** Agent kind label, agent name, pane, workspace,
terminal id, cwd, lifecycle status and `state_change_seq`, and the runtime session id
(`agent_session.value`, which Herdr derives from the agent's integration report). For
Hermes workers also the foreground process-group leader's pid, argv and cwd
(`pane process-info`), plus the worker's own `/status` report (below).

Every argv element is regex-constrained, a realpath, an operator value or a
recorded Herdr id. Prompts are single argv elements (no shell) and may not begin
with `-`, so they cannot be parsed as Herdr flags. A Claude capacity probe must
succeed before layout creation and before every turn.

### Hermes workers: preflight, then native admission

For Hermes, complete actual-runtime proof is required **before the task brief**, not
before layout creation. Herdr's `agent start --kind hermes` runs whatever canonical
`hermes` the pane's shell resolves, and Herdr 0.9.3 cannot select that executable or
report it beforehand. So the gateway checks the operator's *intended* launch policy
before any layout exists, then proves the *actual* runtime after a bounded owned
startup. A bounded, owned, unfocused startup is therefore accepted as the cost of
admission. Claude's capacity-before-layout and permission behavior are unchanged.

**Preflight (before layout, refused with no Herdr mutation).** The preset must define
exactly `launcher`, `home`, `provider`, `model`, `effort` and `approvals: smart`. Launch
arguments, `yolo`, profiles, TUI and fallback providers cannot be expressed, and any
other key disables the gateway. The home must be a normalized default-profile
directory (never `<root>/profiles/<name>`), exist, and be reached without symlinks. The
endpoint must be compatible. The intended launcher, run with a minimal environment as
`--print-runtime-command -- <exact args>` (Hermes's documented machine boundary in
`hermes_cli/_launchers.py`), must print `[python, -I, -c, <bootstrap>, <exact args>]`.
`<bootstrap>` must be byte-for-byte `runtime_command`'s canonical `hermes_cli.main`
bootstrap for one absolute source root. That interpreter, source root and argument list
are the evidence the launched process must match.

**Narrow launch.** The workspace is created `--no-focus` with only `HERMES_HOME=<home>`
and `HERMES_YOLO_MODE=0` added to its environment. No caller pane or other variable is
injected. The agent is started with native `agent start` and only `--cli --provider P
--model M --reasoning E`, never a raw `pane run`.

**Native admission (after startup, before the brief, under the lifecycle lease).**
1. The exact agent name, kind, pane, workspace, terminal id, cwd and Git identity are
   verified. Herdr must report the agent idle.
2. The pane's foreground process-group leader (`pane process-info`, the process whose pid
   is the group id, never a child or the shell) must run the preflight interpreter with
   `-I -c`, exactly the preset arguments, in the worker cwd. Its code must be byte-for-byte
   one of Hermes's two canonical bootstraps for that source root: the printed
   `runtime_command` form, or `_launcher_script("hermes")`, which the managed launcher
   execs. Another entrypoint, appended code or an extra root insertion is refused, and a
   mismatched process is never queried.
3. The screen must hold no earlier status block. The gateway then sends Hermes's
   read-only `/status <token>` once, with a fresh unpredictable 32-hex token, via
   `agent prompt` without `--wait`, so it never passes through the model-task activity
   gate. The CLI dispatches on the first word, so the token changes nothing about the
   command (`process_command`, `status` takes no argument). Hermes renders this locally
   (`cli_session_mixin._show_session_status`) with no model turn and no configuration
   write. `/config` is never sent.
4. Herdr reads have no cursor, only the last 400 lines, so block counts and text cannot
   tell identical reports apart. The CLI echoes the whole submitted line
   (`⚙️  /status <token>`, `cli_tui_runtime_mixin._tui_run_slash_input`) before running
   it. Exactly one echo of this query's token, then exactly one complete block (an exact
   `Hermes CLI Status` title line through `Agent Running:`) after it, must appear within a
   bounded wait. Earlier reports, identical or not, sit before the echo and never count.
   Each line must be a known, unrepeated label. Incidental words in the banner or prompt
   suggestions are not blocks. A missing or repeated echo, more than one block after it,
   a malformed block or none at all refuses. A lost acknowledgement is observed, never
   resent.
5. The block must show the preset home in Hermes's display form (`~/.hermes`), the exact
   `model (provider)`, a matching reasoning effort when shown, and `Approvals: smart`.
   That label is the live approval engine's `_get_approval_mode()` plus a suffix whenever
   `is_approval_bypass_active_for_session` is true (process `--yolo`/`HERMES_YOLO_MODE`,
   session `/yolo`, or `approvals.mode: off`). It must also show `Tokens: 0` and
   `Agent Running: No`. The session-`/yolo` part holds only with the runtime repair below.
6. Agent, pane, terminal, cwd and the same foreground process (pid, argv, cwd) are
   verified again after the query.

Any failure refuses the brief. The exact owned pane (terminal id checked) is closed and
read back absent, or the record is kept as `cleanup_required`. It is never resurrected or
respawned.

**Initial session binding.** A fresh Hermes CLI has no Herdr `agent_session`. The
`herdr-agent-state` integration reports it at the first conversation. The status session
id is bound in the ledger with the admitted process `{pid, argv}`, before the brief, in
the same transaction that refuses a session already bound to any worker. Afterwards
Herdr's session must be absent or equal to the bound one. The gateway never guesses a
session and never resumes another.

**Runtime repair prerequisite.** Unpatched Hermes `4ed093c` computes that suffix from
`getattr(self, "session_key", "")`. The CLI never sets that attribute, and native `/yolo`
keys on `self.session_id`, so unpatched `/status` cannot show a session's YOLO. A pane
toggle would then pass admission and every revalidation unseen. Preflight therefore parses
`hermes_cli/cli_session_mixin.py` under the preset's source root statically, never
importing it. That root comes from the launcher's canonical runtime command, and the
launched process is later bound to it. Unless exactly one `_show_session_status` queries
`getattr(self, 'session_id', '') or ''` and exactly one `_toggle_yolo` toggles
`self.session_id or 'default'`, the preset is refused before any layout
(`runtime_unsupported`). The repair is a one-line, repository-owned patch with a
manifest pinning upstream base, path, preimage and postimage SHA256 and patch digest.
The source is read at preflight. The process imports it moments later at startup, and
it is not re-read afterwards. A same-user change of the source in that window is not
detected.

**Later input.** Every read, wait, status probe, prompt and close re-checks the admitted
pid and argv. Before every follow-up, under the turn lease, the full `/status` proof
runs again and must show the bound session and exactly the recorded, verified mode. An
unresolved mode change (`mode_unresolved`, refused before any query), a YOLO change not
made through `/herdr-yolo`, a `/new` session, a model or profile switch, or a replaced
process refuses the follow-up with ownership kept.

### Explicit per-worker YOLO

Smart approvals are the safe default. Every Hermes worker starts with them and the
frozen process bypass off. YOLO is a capability the user deliberately selects for one
existing worker. Its authorization is the private, end-to-end-encrypted room that an
operator scoped to exact user ids, plus the owning thread and the worker's recorded
ownership. Those are meaningful controls, not a sandbox.

- **Who.** Only a person's typed `/herdr-yolo <worker-id> on|off|status` in the owning
  conversation (above). No tool or schema exposes it. A model cannot invoke slash
  commands, and Hermes briefs or follow-ups starting with `/` are refused, so neither
  the coordinator nor worker output can toggle a mode.
- **When.** Only for a `ready` Hermes worker with no unsettled turn, holding the
  worker's lifecycle lease and its session turn lease. Starts, turns, closes and other
  control requests on that worker get `worker_busy`. Nothing is typed into a running
  task or a dialog. Herdr must report the agent idle before each native query.
- **Evidence.** The mode is observed from one identity-checked `/status`, the admission
  query above, before any change. That status must show the bound session, home,
  `model (provider)`, smart base approvals, no running turn and the same admitted
  process. Only `smart` and `smart (YOLO bypass active)` are recognized. Approvals
  `off`, `manual` or anything else refuses. Admission proved that this pid started
  without the frozen `--yolo`/`HERMES_YOLO_MODE` bypass, which is fixed at import. So
  for the admitted process the suffix can only be that session's own `/yolo`.
- **Change.** `/yolo` is sent at most once per request, only when the observed mode
  differs, and the mode is observed again with the same fencing. The intent is
  persisted as `pending:<mode>` before sending. A lost acknowledgement is observed,
  never resent. An unobservable outcome keeps `pending:<mode>`, ownership and the
  refusal of task input until an observation resolves it. An observed failure is
  recorded as observed and reported. Only an observed mode is ever claimed.
- **Afterwards.** Revalidation accepts exactly the recorded mode, so an authorized,
  verified YOLO keeps later tasks working. Drift either way is refused for tasks and
  reported by `status` without being adopted. The mode is per worker. It never
  changes other workers or startup defaults, and it ends with `off` or close. Status,
  acknowledgements and closed locators show it.

**Task text cannot drive the CLI.** The classic CLI strips each submission and removes
leaked bracketed-paste and terminal-response artifacts (`input_sanitize`,
`cli_terminal_input`). It then runs a leading `!` as a local shell command and a leading
`/` as a native command (`cli_tui_mixin._tui_handle_enter`,
`cli_tui_runtime_mixin._tui_process_one_input`), never as a model turn. `/yolo`, `/new`
and `/model` would change the very policy admission proved. Those replacements are
sequential, so stripping one marker can splice its neighbors into a new one. `[20^[[200~0~/yolo`
becomes `/yolo`. A Hermes brief or follow-up is therefore refused before any Herdr contact
(and before any revalidation `/status`) if it contains:
- a terminal control character other than newline and tab (ESC, CR, DEL, C1, …), which
  could act as keystrokes or end a bracketed paste;
- any text the sanitizers would remove (`^[`, `[200~`, `[201~`, `00~`, `01~`,
  `<n;n;nM`); or
- a leading `/` or `!` after whitespace.

With nothing for the sanitizers to remove, the text the CLI dispatches is exactly the
stripped brief, so the prefix check is complete for Hermes `4ed093c`. Ordinary text passes
unchanged whatever its first character. The gateway's read-only `/status <token>` is the
only slash input it sends. There is no general command API. Claude prompt validation is
unchanged.

## Targeting and identity

Herdr is reached only through `socket_path` with a minimal environment
(`HERDR_SOCKET_PATH`, `HOME`, `PATH=os.defpath`, `LC_ALL`). Inherited
`HERDR_PANE_ID`/`HERDR_ENV` never reach Herdr, and no caller pane is fabricated.
Layout is created with `--no-focus`. Every later operation targets the recorded
agent name and revalidates name, kind, pane, workspace, terminal id, cwd, runtime
session, endpoint and Git root/common-dir/branch before input, reading or cleanup.
Reads are re-verified afterwards and discarded on drift. Recovery of an
unacknowledged workspace accepts only one workspace whose label carries the
worker's random id, holding exactly one pane in the recorded cwd. Focus and
inventory position are never used to pick anything.

## Dialogs

No tool answers approvals or questions. A blocked turn returns a bounded excerpt
(2,000 characters) so the conversation can ask a human, who answers in the visible
pane. The single automated keypress is Claude's folder-trust prompt, and only when
the displayed path resolves exactly to the operator-permitted `cwd` that the request
was authorized for. Any other startup dialog, and `unknown` readiness, is returned
as `worker_not_ready` with the brief unsent.

## State, serialization and crash safety

- **Validated before use.** Every read validates the whole ledger under its flock:
  exact top-level shape, record id = key, the full field set and its types, owner
  fields, task/agent/label correspondence, absolute paths, supported phases, the
  layout fields each phase requires, and turn shape. Any defect refuses every tool
  (`state_unsafe`) before Herdr is contacted, and leaves the bytes untouched. Writes
  are validated too.
- **Private files.** The state directory must be 0700 and the ledger and lock files
  0600, owned by the Hermes user and not symlinks. Open, `lstat` and write failures,
  including symlinked lock files, become `state_unsafe` rather than raised errors.
- **Atomic writes.** A fresh 0600 temp file is fsynced and renamed, then the
  directory is fsynced.
- **Lifecycle lease.** Each worker has a non-blocking lifecycle lease held from
  before its reservation until start returns, and by every prompt, wait and close.
  Close can never complete while layout creation or agent start is in flight
  (`worker_busy`), and a start cannot resurrect a closed worker. Inside that, a
  per-runtime-session turn lease still serializes turns. Lock order is always
  lifecycle → short ledger transaction → turn. Both leases are non-blocking, so
  contention returns an error instead of deadlocking.
- **No resend.** The turn state is persisted as `submitting` before every prompt, so
  a lost acknowledgement is never resent.
- **Reservation checks.** A duplicate open task in the same scope and the global
  worker cap are checked in the same transaction as the reservation.

## Cleanup

Close verifies identity first, records `closing`, closes only the recorded pane, and
reads back `pane_not_found` and `agent_not_found`. When it cannot prove absence it
keeps `cleanup_required` ownership for a retry. A workspace create whose outcome was
never acknowledged is never terminalized because its label is not yet visible. It
stays owned and reports `cleanup_unverified` until a retry finds and closes the
labelled layout, and it is never respawned. Closed records keep the runtime session
id, cwd and branch as locators. Workspaces are never closed directly, so panes a
person adds to a worker's workspace survive.

## Residual risks

- **Terminal output is sensitive.** `herdr_read` returns up to 40,000 characters of
  recent output, and blocked turns include a dialog excerpt. Either can contain
  secrets visible in the pane, and they enter the conversation and its model
  provider. Nothing is logged by this plugin. Prompts are stored only in Herdr's own
  pane history, never in the ledger.
- **Same-user reach.** Any process running as the Hermes user can drive Herdr or edit
  the ledger directly. The permission and validation checks stop accidents and
  malformed state, not a same-user adversary.
- **Unresolved creates.** Herdr 0.9.3 exposes no server boot identity, so nothing can
  prove a lost create will never land. Such a record stays owned, blocks its task slug
  in that scope, and counts toward `max_workers` until its layout appears and is
  closed. If an operator confirms out of band that no such workspace exists, they can
  remove the record by hand. The gateway never infers that.
- **Point-in-time checks.** The capacity probe, project revalidation and Hermes `/status`
  proof are point-in-time. A worker keeps whatever access its own permission mode allows
  between turns. Someone at the visible pane can change a Hermes worker's policy
  mid-turn. The gateway sees that only before the next input it sends.
- **Launch-time assertions** (Claude model, effort, permission mode; Hermes effort when
  `/status` omits it) are not observed later.
- **Explicit YOLO is real authority.** While a worker's YOLO bypass is on, its model
  runs commands Hermes would otherwise ask about, as the same user, and not only inside
  its project directory. Hermes's hardline blocklist still runs first. That is the
  capability the user selects. The gateway proves which worker has it and that nobody
  else turned it on, but it does not limit what such a worker does. Someone at the
  visible pane can also type `/yolo`. The gateway sees that only at its next query
  of that worker, and then refuses task input until the user settles it.
- **Hermes evidence is same-user and textual.** The foreground argv, the `/status` text
  and the Herdr session are reported by processes running as the same user. A same-user
  adversary can forge any of them. Admission proves the intended policy against honest
  software and accidental drift. It is not a hard sandbox. The process check accepts only
  the two canonical bootstraps inspected in Hermes `4ed093c`. A Hermes update that
  changes either template therefore fails closed until this package is updated. So do an
  installed `setproctitle`, a non-English locale, a Hermes relaunch that rewrites argv, and
  a `/status` line or its echo wrapped by the terminal. So does a terminal that renders
  the echo's `⚙️` other than as that glyph, with or without its variation selector,
  followed by whitespace. A Hermes update that changes the repaired
  `/status` or `/yolo` session keying also fails closed, at preflight.
- **Task-text rule relies on whole-buffer submission.** Herdr's `agent prompt` honors the
  pane's bracketed-paste mode, so a multi-line brief arrives as one submission and the CLI
  dispatches on its first character. If bracketed paste were off, Hermes's own
  rapid-input guard is what keeps later lines from being submitted separately. Text
  containing the rare marker sequences above (for example `00~`) is refused even when
  ordinary. A Hermes update that adds a sanitizer needs this rule re-inspected.
- **Admission costs a startup.** A refused Hermes worker has already been started in its
  own unfocused pane before it is closed. No brief or model turn reaches it.

## Evidence and remaining acceptance gates

**Synthetic, not live.** `hermes/test_herdr_gateway_plugin.py` drives the registered
public handlers and the registered `/herdr-yolo` command with real filesystem state, a
fake `herdr` executable (including a native `/yolo` toggle), a fake Hermes launcher, a
fixture source root, and test ContextVars named like Hermes's gateway bindings. On host
Python a stand-in mirrors `agent.delegation_context`. Under Hermes's managed Python the
real module is used for the delegation tests. The command is also dispatched there
through the installed `gateway.session_context` binding on a pool thread, as the gateway
does. `hermes/test_hermes_cli_status.py` reads the installed `cli_session_mixin.py`
statically. It checks the patch's exact preimage (equal to upstream's blob at the base
commit) and postimage. It then compiles only the real `_show_session_status`, with
injected printing, translation, status fields and approval engine. The repaired method
queries the CLI session for smart, session-YOLO on, another session's YOLO and frozen
bypass, while the unrepaired one misses the session toggle. It also compiles the real
`_tui_run_slash_input`, `process_command`, its dispatch table and slash detector from
`cli.py` and `cli_tui_runtime_mixin.py`: `/status <token>` reaches `_show_session_status`
with no argument and no model turn, its whole line is echoed first, and the gateway's
fence parser takes exactly the report after that echo. The plugin tests' fake `herdr`
honors `--lines` and fills a 400-line read with identical reports. None of this is Matrix,
gateway, live-Herdr, live-runtime or model evidence.

**Directly checked, read-only.** Against the running Herdr 0.9.3 server: the `status`,
`agent get`, `pane get`, `workspace list`, `pane list` and `pane process-info` shapes,
and the stderr JSON not-found errors. A `process-info` leader is the entry whose pid is
`foreground_process_group_id`, and child entries may lack `argv`. Against installed
Hermes `f42f579`: inspection of the `PluginContext`, session-context and
delegation-context source. Against installed Hermes `4ed093c`: the installed launcher's
`--print-runtime-command` array, plus inspection of `hermes_cli/_launchers.py`, the
managed launcher script, `hermes_bootstrap` relaunch, top-level `--cli`/`--provider`/
`--model`/`--reasoning` routing to the classic chat, `cli_session_mixin._show_session_status`,
`hermes_cli/status_report.py`, the English `/status` labels, `tools.approval`'s bypass
predicate, and sticky `active_profile` resolution under a pinned `HERMES_HOME`. Hermes
`plugins doctor --ci` (6 tools) and `plugins validate` (capability probe, security scan
"safe", no core override) pass for this version.

**Remaining live acceptance gates (pending):**

- the independent security review;
- applying the reviewed runtime patch to the exact preimage, with a backup, and observing
  live native `/status` before and after a user-authorized `/herdr-yolo` mode change of
  an owned worker;
- a real Matrix `/herdr-yolo` dispatch from the authorized user, its reply, and a
  follow-up task under the enabled mode;
- an authorized canary through the real Matrix gateway, confirming per-turn
  ContextVar binding during actual tool dispatch, including thread ids and the
  dispatch `session_id`;
- the live `workspace create` result shape;
- real `agent prompt --wait` activity, stall and timeout behavior and
  `state_change_seq` progression;
- the current Claude release's folder-trust prompt text;
- live close and absence read-back;
- behavior of the lifecycle lease under the gateway's real concurrency;
- the live Hermes admission path end to end through the gateway, including the
  rendered `/status` text and its `⚙️  /status <token>` echo through
  `agent read --source recent-unwrapped`, the
  foreground leader argv after `--cli --reasoning`, reasoning display, and Herdr's
  first-conversation session report agreeing with the bound session. One bounded
  probe saw a fresh `agent start --kind hermes` reach `idle` with no Herdr session, and
  `/status` reporting smart approvals and zero tokens. That probe was not this code.
