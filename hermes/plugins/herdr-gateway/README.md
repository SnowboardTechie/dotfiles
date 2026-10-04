# herdr-gateway

A native Hermes plugin that lets an authorized conversation (for example a Matrix
room) run **visible, task-specific coding workers** under a local
[Herdr](https://herdr.dev) server and supervise them through completion inside
the originating request.

The conversation keeps authority, context and final synthesis. Each worker gets a
bounded brief and belongs to the exact room, thread and user that started it.
The gateway is **disabled until configured** and fails closed on missing,
ambiguous, stale or unsupported context.

## Tools

| Tool | Purpose |
|---|---|
| `herdr_start` | Validate, reserve ownership, create one unfocused workspace in a permitted directory, start the preset agent, submit the brief |
| `herdr_prompt` | Follow-up turn to an owned, idle worker (refused while a turn is unsettled) |
| `herdr_wait` | Bounded synchronous wait for the current turn; never sends anything |
| `herdr_read` | Bounded recent output of an owned worker, identity-checked before and after |
| `herdr_status` | This conversation's own workers with live, identity-checked status |
| `herdr_close` | Close only the recorded pane, prove absence, keep session locators; idempotent |

Turn states are literal: `submitted` (delivered, no activity observed), `working`,
`blocked` (approval or question for a human), `settled`, `timed_out` (still running
and still owned) and `unknown` (acknowledgement lost). A follow-up is refused until
the previous turn settles, so a timeout or lost acknowledgement never causes a
duplicate prompt.

The bundled skill `herdr-gateway:workflow` holds the supervision guidance the
model should follow.

## Request routing in Matrix

### Right-sized runtime selection (v0.5.2)

Simple questions stay with the coordinator unless the person asks for a worker.
Requested lightweight questions and read-only inspection use a configured Hermes
preset; substantial implementation uses a configured Claude preset. Explicit
runtime selection overrides these defaults. Keep the brief and verification
proportional: a simple question is not permission to commission an exhaustive
audit. Bryan's pilot uses `hermes-sol` as the omitted-preset default, with
`claude-opus` selected for substantial implementation. Neither preset's effort,
model nor approval mode changes. This is routing guidance, not a latency guarantee
or additional authorization.

Hermes lists no plugin skill in the system prompt's `<available_skills>`, and an existing
conversation keeps its persisted prompt. So a Matrix room could follow the CLI handoff skill,
find no injected `HERDR_ENV`/`HERDR_PANE_ID`, refuse visible workers, and keep repeating that
refusal or substitute a background `delegate_task` review. The plugin therefore registers
`llm_request` middleware (`routing.py`). It runs on every provider request, existing
conversations included, and appends one delimited `<herdr-gateway-routing>` note to the
request's instructions when, and only when, the request comes from a non-delegated, trusted
Matrix origin that the current settings admit. The note:

- selects the native `herdr_*` tools and skill `herdr-gateway:workflow` for an explicit
  worker request, through whichever entrypoint the request actually offers (see below);
- says a missing caller pane is normal in Matrix, forbids substituting `delegate_task`, a
  background task or the CLI helper, and tells the model to disregard earlier refusals made
  for that reason;
- lets a bounded read-only request start from that origin's permitted project directories and
  the configured presets (names, kinds, default), without asking for internals or a new ticket.
  The default preset stays the default, and another preset is used only when expressly
  selected;
- names one of three native entrypoints, decided from the request's own function schemas.
  It never adds tool schemas.

| Entrypoint | When | Note says |
|---|---|---|
| direct | all six `herdr_*` function schemas are declared | use `herdr_start`, then `herdr_wait`/`herdr_read`/`herdr_status`/`herdr_prompt`/`herdr_close` |
| deferred | not all six, but both bridge functions are declared: `tool_describe` (taking `names`) and `tool_call` (taking `calls`) | `tool_describe(names=[all six herdr_* names])`, then `tool_call(calls=[{"name": "herdr_start", "arguments": {...}}])`, and supervise through `tool_call` |
| unavailable | neither | the herdr tools are not available in this request (the existing blocker) |

Hermes's progressive tool disclosure (`tools/tool_search.py`) defers every plugin tool. It
replaces them in the model-visible array with `tool_search`, `tool_describe` and `tool_call`
(Codex wires `tool_search` as `hermes_tool_search`). The configured toolsets can select
`herdr` while a request still declares no direct `herdr_*` schema. Describing a tool doesn't
make it first-class: it stays callable only through `tool_call`, whose dispatch runs the
normal policy, hooks and approvals. The bridge is a discovery route, not proof that the
herdr tools are enabled. If `tool_describe` or `tool_call` reports one absent, disabled or
refused, the note says to report exactly that, with no background substitute. Only declared
`type: function` entries count. A name inside a description, a non-function entry, a partial
bridge, `tool_search` alone, or cached assistant and tool text is never treated as
availability. A partial direct surface plus the full bridge is deferred, and all six direct
schemas win. In the deferred case, the gateway's real launch is the outer `tool_call` whose
nested `herdr_start` returns an owned worker. Acceptance correlates that nested name and its
pane and session, not a first-class `herdr_start` row.

The note alone did not stop a live v0.5.0 request from choosing `delegate_task`. So for the
same admitted origin the middleware also chooses the transport, per request. When that
request's most recent user message (a Responses `input_text` message, or Chat Completions
string or `text` parts) leads with an explicit worker request, it omits only the
`delegate_task` function schema from that outgoing request. A named `delegate_task`
`tool_choice` becomes `auto`. Recognized forms are a short, documented pattern rather than a
classifier: an optional greeting, an optional "can/could/would you" or "please", or "I want /
need / I'd like", then have, get, ask, start, launch, spawn, use, send, open, spin up or fire
up, then a worker, coding agent or pane. Case, whitespace and curly apostrophes don't matter.
Only the first 400 characters are inspected:

- a request that mentions `background` there (a background worker, background-only, a
  background review) keeps `delegate_task`, unless it negates background or says `visible`;
- ordinary conversation, research, quoted README text, assistant history, tool output and
  framework messages that start with `[` (async-delegation and process completions,
  `[Replying to …]` quotes) never select. So a worker request sent as a Matrix reply keeps
  the note-only behavior;
- every tool-loop request carrying that same user message gets the same choice, including
  after `herdr_start`;
- a visible request gets no `delegate_task` on any entrypoint. With the bridge it gets the
  deferred route; with neither the six tools nor the bridge, the note reports the blocker.

Everything else stays as it was: all other schemas (unknown and non-function entries
byte-identical), other `tool_choice` values, history, model and cache keys. Hermes's tool
registry, cached tool grants, persisted prompt, permissions and config are never changed.

It is instructions and transport selection, not authorization. Every `herdr_*` call is still
authorized by the handlers, and refusals remain blockers. Supported request shapes are Codex
Responses (`instructions`) and Chat Completions (a leading system or developer message).
Other shapes, such as native Anthropic `system`, are left unchanged. A model can still
ignore an instruction or decline to call a tool. The first routed request after activation or
a settings change misses the provider's cached prompt prefix once, and so does an explicit
worker request whose narrower tool list differs from the previous request's (see
`SECURITY.md`).

## Native command: `/herdr-yolo`

| Command | Purpose |
|---|---|
| `/herdr-yolo <worker-id> status` | Observe one owned Hermes worker's approval mode from its own `/status` |
| `/herdr-yolo <worker-id> on` | Turn on that worker's session YOLO bypass, verified |
| `/herdr-yolo <worker-id> off` | Turn it off again (smart approvals), verified |

Hermes workers always start with smart approvals and no bypass. YOLO is a capability
a person selects for one worker. It is never a default, and it never carries over to
other workers or later starts. A person types the command in the conversation that
owns the worker. Hermes dispatches plugin commands before any agent turn and binds
the message's source exactly as it does for a tool call. The same origin, user,
thread, project and ownership checks apply. It is not a tool, so the model cannot
call it, and task text that starts with `/` is refused anyway (below).

- Only an idle, settled, admitted Hermes worker is eligible. A running turn, a
  blocked dialog or an unfinished start is refused (`turn_unsettled`,
  `worker_not_ready`), and nothing is typed into the pane. A person can still act in
  the visible pane. Claude workers have no mode (`unsupported_kind`).
- Every request first observes the mode through the identity-checked `/status`
  query used for admission: bound session, home, `model (provider)`, smart base
  approvals, no running turn, same admitted process. `on` and `off` send Hermes's
  native `/yolo` at most once, and only when the observed mode differs. Then they
  observe again under the same process and session fencing. Only an observed mode is
  reported or recorded. Repeating a request is idempotent. A lost acknowledgement is
  observed, never resent. If the toggle demonstrably did not land, that is reported
  (`mode_unverified`) and nothing more is sent.
- The intent is persisted as `pending:<mode>` before `/yolo` is sent. If the outcome
  cannot be observed (crash, restart, unreadable status), the worker keeps
  `pending:<mode>` and its ownership. Task input is refused (`mode_unresolved`) until
  `/herdr-yolo <worker-id> status` observes the mode, or `on`/`off` observes and
  settles it.
- Follow-ups re-prove the recorded mode. With YOLO authorized and verified, later
  tasks run under it. A mode the gateway did not set and verify (for example `/yolo`
  typed into the pane) refuses task input (`hermes_unverified`). `status` reports it
  as drift without adopting it. A person settles it with `on` or `off`.
- `herdr_status`, every acknowledgement and closed-worker locators show `mode`
  (`smart`, `yolo` or `pending:<mode>`). YOLO stays on until `off` or `herdr_close`.

## Runtime prerequisite: `/status` must see a session's YOLO

Hermes `4ed093c`'s classic `/status` (`cli_session_mixin._show_session_status`) asks
the approval engine about `getattr(self, "session_key", "")`. The CLI never sets that
attribute, while native `/yolo` toggles `self.session_id`. Unpatched `/status`
therefore never shows a session's YOLO bypass. Neither admission, follow-up
revalidation nor `/herdr-yolo` could then see a toggle. Preflight therefore reads the
preset's Hermes source statically, without importing it, from the source root the
launched process is later bound to. A Hermes preset is refused before any layout
(`runtime_unsupported`) unless `_show_session_status` queries
`getattr(self, 'session_id', '') or ''` and `_toggle_yolo` toggles
`self.session_id or 'default'`.

This repository carries the one-line repair as
`hermes/runtime-patches/cli-status-session.patch`. Its manifest
`cli-status-session.json` pins the upstream repository, base commit `4ed093c`, path,
preimage and postimage SHA256 and patch digest. The operator applies it to exactly
that preimage, with a backup, then restarts Hermes so new workers load it.
`hermes/test_hermes_cli_status.py` holds the synthetic regression for the real
extracted method. A Hermes update that changes this source fails closed until it is
re-inspected.

## Configuration

All settings live under `plugins.entries.herdr-gateway.settings` in the Hermes
profile's `config.yaml`. Room IDs, user IDs, paths and model policy are local
operator choices. Nothing personal ships in this package. **The values below are
illustrative placeholders.**

```yaml
plugins:
  entries:
    herdr-gateway:
      settings:
        herdr_bin: /usr/local/bin/herdr               # absolute path; required
        socket_path: /home/example/.config/herdr/herdr.sock   # explicit endpoint; required
        origins:                                      # empty = disabled
          - platform: matrix
            chat_id: "!exampleRoomId:example.org"
            user_ids: ["@operator:example.org"]
            projects: ["/home/example/src/example-repo"]   # cwd must be inside one of these
        presets:
          claude-default:
            kind: claude
            model: example-exact-model-id             # exact; no fallback model is ever passed
            effort: high                              # low|medium|high|xhigh|max
            permission_mode: auto                     # default|acceptEdits|plan|auto only
          hermes-default:
            kind: hermes
            launcher: /home/example/.local/bin/hermes # absolute; asked for its runtime command
            home: /home/example/.hermes               # default-profile Hermes home, no symlinks
            provider: example-provider                # exact; no fallback provider
            model: example-exact-model-id
            effort: high                              # minimal|low|medium|high|xhigh|max|ultra
            approvals: smart                          # the only accepted value
        default_preset: claude-default
        claude_capacity_command: /home/example/bin/claude-capacity   # run with --check-capacity
        max_workers: 4
        max_wait_seconds: 1800
```

- Any malformed setting disables the whole gateway (`config_invalid`). Settings are
  re-read on every call, so removing an origin revokes it immediately. Removing a
  project, or retargeting a project symlink, revokes prompting, waiting, reading and
  status probes for existing workers in it (`cwd_not_permitted`). Only `herdr_close`
  stays available for them.
- Delegated subagents (Hermes `delegate_task` children and their spawned
  descendants) are refused using Hermes's `agent.delegation_context` boundary. A
  runtime without that module is refused (`runtime_unsupported`).
- Origin comes only from the Hermes gateway's per-turn binding (platform, chat,
  thread, user, session key). Model-supplied origin fields are rejected. Process
  environment variables never substitute for a missing binding. Scheduled (cron)
  runs are refused.
- `claude_capacity_command` is required for Claude presets. Exit 0 means capacity
  is available. It runs before layout creation and before every turn, with no
  fallback when it fails.
- Hermes presets support only the classic CLI and the default profile. Herdr starts
  its own canonical `hermes` from the pane's shell, so a Hermes worker is admitted in
  two stages, and no model task establishes either:
  1. **Preflight, before any layout.** The preset is strictly validated: exact
     provider/model, a supported effort, `approvals: smart`, absolute launcher, and a
     default-profile home that exists without symlinks. No launch arguments, profiles,
     TUI or fallback providers can be configured. The endpoint must be compatible. The
     intended launcher must answer `--print-runtime-command -- <exact args>` with
     `[python, -I, -c, <bootstrap>, <exact args>]`, where `<bootstrap>` is exactly Hermes's
     canonical `hermes_cli.main` runtime bootstrap for one absolute source root
     (`launcher_unverified` or `home_unverified` otherwise).
  2. **Native admission, after startup and before the brief.** The workspace is created
     with exactly `HERMES_HOME=<home>` and `HERMES_YOLO_MODE=0` added, and the agent is
     started natively with `--cli --provider P --model M --reasoning E`. Under the worker's
     lifecycle lease the gateway checks the exact agent, pane, terminal and cwd. It also
     checks the foreground process-group leader: same interpreter, `-I -c` with exactly one
     of Hermes's two canonical bootstraps for that source root (the printed runtime form or
     the managed launcher's script, both inspected in Hermes `4ed093c`), exactly those
     arguments, worker cwd. Another entrypoint, extra code or an extra root fails. Then it sends Hermes's
     read-only `/status <token>` once, outside the task activity gate, with a fresh
     unpredictable token. Hermes dispatches on the first word and echoes the whole line
     (`⚙️  /status <token>`) before its report. Herdr reads have no cursor, so the gateway
     requires a screen that held no status block, then exactly one echo of that token and
     exactly one complete status block after it; earlier identical reports never count. That block must show the preset's
     home, `model (provider)` and effort, `Approvals: smart` with no YOLO-bypass suffix,
     zero tokens and no running turn. The same process must be in place afterwards. Any
     doubt refuses (`start_failed`, cause `hermes_unverified` or `identity_mismatch`), and
     the brief is not sent. The exact owned pane is then closed and proved absent, or kept
     as `cleanup_required`. A lost acknowledgement is observed, never resent.
- **Session binding.** Herdr reports no session for a fresh Hermes CLI. Hermes's
  integration reports it at the first conversation. The status session id is bound in
  the ledger together with the admitted process (pid and argv). A session already bound
  to any worker is refused. Every later check accepts Herdr's session only if it is absent
  or equal to the bound one. Every later read, wait, status probe and close re-checks the
  admitted process. Before every follow-up, the same `/status` proof runs again, now
  requiring the bound session and exactly the recorded mode. A YOLO change not made
  through `/herdr-yolo`, a `/new` session, or a model or profile switch refuses the
  follow-up (`hermes_unverified`) and keeps ownership.
- **Task text is never a native command.** Hermes's classic CLI strips a submission and
  removes leaked paste or terminal artifacts, which can splice the surrounding text. It then
  runs a leading `/` (slash command, such as `/yolo` or `/new`) or `!` (shell) locally
  instead of as a model turn. A Hermes brief or follow-up is refused (`invalid_argument`),
  before any Herdr contact or status query, if it contains a terminal control character
  (anything but newline and tab) or paste/report marker text (`^[`, `[200~`, `[201~`,
  `00~`, `01~`, `<n;n;nM`). It is also refused if, after whitespace, it starts with `/` or
  `!`. Any other text passes unchanged, whatever its first character, so `42: …`, quoted,
  bracketed and code-prefixed briefs work. The only slash input the gateway sends is its
  own read-only `/status <token>` and, for a person's `/herdr-yolo on|off`, one native `/yolo`.
  Claude prompts are unchanged.
- A worker reporting `unknown` readiness or a startup dialog is a `worker_not_ready`
  blocker, with the brief unsent and no raw pane command used as a bypass. Only
  Claude's exact-cwd folder-trust prompt is ever answered.
- One worker's whole lifecycle (reservation, layout, agent start, turns, close) is
  serialized. A concurrent call gets `worker_busy` instead of racing. A workspace
  create whose acknowledgement was lost stays owned (`cleanup_unverified`) until a
  later `herdr_close` finds its labelled layout. It is never terminalized because
  the layout is not yet visible, and never respawned.

State lives in the plugin's profile-scoped data directory (`ctx.state.data_dir`) as
`workers/ledger.json` plus small lock files. The directory must be mode 0700 and the
files mode 0600, owned by the Hermes user and not symlinks. The ledger is
schema-validated on every read. A corrupt, malformed, foreign or permissive ledger
is refused (`state_unsafe`) before Herdr is contacted, and never reset.

## Herdr protocol used

Only `herdr` subprocesses against `socket_path`, with a minimal environment (no
inherited `HERDR_PANE_ID`/`HERDR_ENV` caller identity): `status`,
`workspace create --no-focus --cwd [--env HERMES_HOME=… --env HERMES_YOLO_MODE=0]`,
`workspace list` (label-exact recovery only), `pane get|list|close|process-info`,
`agent get|start|prompt --wait|wait|read|send-keys`, and `agent prompt <worker> '/status <token>'`
or `/yolo` without `--wait` for Hermes admission, revalidation and `/herdr-yolo`. `send-keys` is used for exactly
one thing: Claude's ordinary folder-trust prompt when the displayed path is exactly the
permitted `cwd`. Targets are always a recorded agent name or pane id, never focus or
inventory position. Hermes's launcher is run only as `--print-runtime-command`. Its
configuration, environment and authentication stores are never read, and `/config` is
never sent.

## Provenance and divergence

Adapted from [steven-terrana/hermes-herdr-plugin](https://github.com/steven-terrana/hermes-herdr-plugin)
at commit `c33aa2eb2e27087134eb03c9b807eea44e61b9a5` (version 0.1.0), MIT, Copyright (c) 2026
Steven Terrana. The upstream notice is retained verbatim in `LICENSE`. This
adaptation keeps the upstream architecture (`herdr_client.py`, `ledger.py`,
`schemas.py`, `tools.py`, `register(ctx)` registering a `herdr` toolset) and
diverges as follows.

| Upstream behavior | Here |
|---|---|
| `default_agent_args: --dangerously-skip-permissions` for Claude | No launch arguments from config or model; presets map to an allow-list of permission-respecting modes |
| Settings read via `ctx.get_setting`, which Hermes `f42f579` does not provide, so every setting silently fell back to its default; empty values also restored defaults | `ctx.get_config`, strictly validated each call; empty means disabled |
| TCP→socket `socat` auto-bridge, `pkill`, default socket under `/tmp` | Removed; one explicit local endpoint, verified compatible and matching |
| `herdr_status` exposed every live agent ("untracked agents"); read/relay/focus resolved any agent name or pane id | Only workers owned by the exact room/thread/user; untracked agents and panes are unreachable |
| Reused a workspace found by cwd/label; tab per task | One new unfocused workspace per worker, labelled with its private worker id |
| Ledger reset to empty on corrupt JSON; in-place truncate-and-write | Refuse corrupt/unsafe state; atomic 0600 temp+fsync+rename under flock |
| Prompt submission reported as `working` | Truthful turn states from Herdr's activity gate and `state_change_seq` |
| `herdr_relay keys` answered arbitrary dialogs | No dialog-answering tool; blocked turns are surfaced for a human |
| `herdr_focus` staged the TUI | Removed (worker panes are created unfocused) |
| Any model-supplied `kind` (Hermes included) launched with no runtime check | Only operator presets. Hermes workers pass preflight, then native `/status` admission before any brief, with the session and process bound and re-proven before later input |
| No approval-mode control | Smart by default. A person's native `/herdr-yolo` command changes one owned Hermes worker's session YOLO, verified from its own `/status`. No model tool can do it |
| No close | `herdr_close`: identity-verified, owned-only, absence read back, idempotent |
| No request routing | `llm_request` middleware adds a bounded native-routing note to an admitted Matrix origin's provider requests and omits `delegate_task` from an explicit visible-worker request |

Upstream was not contacted and has not reviewed this adaptation.

## Development

```bash
python3 -m unittest hermes.test_herdr_gateway_plugin hermes.test_hermes_cli_status   # host Python
# The supervised gateway's managed generation (not a sibling venv):
~/.hermes/hermes-agent/.hermes/bin/hermes --run-module unittest discover -s hermes -p test_herdr_gateway_plugin.py
hermes plugins doctor --ci hermes/plugins/herdr-gateway
hermes plugins validate hermes/plugins/herdr-gateway
```

The tests drive the registered public handlers with real filesystem state, a fake
`herdr` executable, a fake Hermes launcher, and gateway-named ContextVars standing in
for Hermes's turn binding. Under Hermes's managed Python they use the real `agent.delegation_context`
and also run `/herdr-yolo` through the installed `gateway.session_context` binding. On host
Python they use a stand-in with the same API. The routing tests send synthetic Codex Responses
and Chat Completions requests through the registered middleware. Under managed Python that is
the real `hermes_cli.middleware` request chain and dispatcher, with only plugin discovery
replaced. There, one test also builds both requests with the installed transports (Codex
`build_kwargs` plus preflight, and Chat Completions `build_kwargs`) and the real
`delegate_task` schema. Another registers the six handlers in an isolated `ToolRegistry`,
runs the real progressive assembly and both transports, and routes the result. It then
drives the bridge's own `dispatch_tool_describe`, `resolve_underlying_call`,
`scoped_deferrable_names` and `validate_deferred_call_args`, and re-dispatches into the
plugin's origin gate. `model_tools` is never imported, because importing it runs live plugin
discovery. The fake `herdr` honors `--lines` and echoes
slash commands as the CLI does. `hermes/test_hermes_cli_status.py` compiles only the real
`_show_session_status`, read statically, and checks the runtime patch's exact preimage and
postimage. It also compiles the real idle submit path (`_tui_run_slash_input`,
`process_command` and its table) to pin that `/status <token>` runs native status and is
echoed before its report. All of this is synthetic, not live dispatch, Herdr, model or Matrix
evidence (see `SECURITY.md`).
