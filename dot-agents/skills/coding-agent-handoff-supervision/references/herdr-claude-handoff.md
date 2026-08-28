# Herdr-Native Claude and Hermes Handoffs

## Preconditions and caller identity

Use this path only when the parent process is inside Herdr:

```sh
test "${HERDR_ENV:-}" = 1
test -n "${HERDR_PANE_ID:-}"
test -x "${HERDR_BIN_PATH:-}"
"$HERDR_BIN_PATH" status
"$HERDR_BIN_PATH" pane current --pane "$HERDR_PANE_ID"
"$HERDR_BIN_PATH" pane layout --pane "$HERDR_PANE_ID"
```

The pane-injected Herdr binary is authoritative. If a needed command differs
from this reference, inspect that command's live `--help` before acting. If the
built-in Herdr control skill is not already available in context, run
`"$HERDR_BIN_PATH" --skill` and follow it.

Herdr's injected `HERDR_BIN_PATH` identifies the client paired with the pane
even when shell startup has reordered `PATH`. Use that inherited absolute path
directly in every command so separate tool calls and background processes do
not depend on parent-shell state. Verify `status` reports a running server and
`compatible: yes` before mutating layout. Do not reduce this to an exit-code
check: an incompatible client can print status and exit successfully. If the
injected path is absent, non-executable, or incompatible, stop. Visible work has
no Agent View fallback.

This is especially important for the watcher: a tracked background terminal
may start a login shell that exposes an older Herdr client. Invoke the inherited
`HERDR_BIN_PATH` directly; do not let that shell resolve `herdr` again. A
protocol mismatch means the wrong client ran. Retry the same watcher once with
the injected compatible path rather than starting another worker.

Use the injected caller pane ID even when another Herdr tab is globally focused.
Stop rather than substituting the focused pane if the caller cannot be resolved.

## Create the visible worker

A horizontal handoff means a side-by-side split created to the caller's right.
Keep focus on the caller while preparing the selected worker, and preserve the
exact working directory:

```sh
"$HERDR_BIN_PATH" pane split --pane "$HERDR_PANE_ID" \
  --direction right --ratio 0.5 --cwd "$PWD" --no-focus
```

Read the new pane from `.result.pane.pane_id`; never derive it from sidebar
position, example IDs, or the globally focused pane. Record the pane ID as a
handoff-owned resource.

Choose a useful unique Herdr agent name matching
`[a-z][a-z0-9_-]{0,31}`. Check `"$HERDR_BIN_PATH" agent list` before naming it. The Herdr
agent name is the stable control target.

Start the selected worker without an initial prompt so Herdr can verify
interactive readiness. Claude is the default:

```sh
"$HERDR_BIN_PATH" agent start <agent-name> --kind claude --pane <new-pane-id> -- \
  --permission-mode acceptEdits --model opus --effort high \
  --name "<short task name>"
```

Use Hermes only after an explicit same-run selection:

```sh
"$HERDR_BIN_PATH" agent start <agent-name> --kind hermes --pane <new-pane-id>
```

Preserve explicitly requested agent arguments instead of overwriting them with
the Claude example defaults. Do not pass Claude-only arguments to Hermes. Before
starting Hermes, require `approvals.mode: smart` in the selected profile, require
`HERMES_YOLO_MODE` to be unset, and pass no `--yolo` flag. If approval mode is
`off`, cannot be verified, or startup arguments bypass approval, stop. If startup
returns `agent_not_ready`, inspect `agent get` and `agent read` through the
recorded binary. A trust, approval, or question UI is `blocked`; do not answer it
for the user.

Claude's `acceptEdits` and Hermes's smart mode are approval gates, not hard
confinement. Do not claim the visible worker has sandbox confinement. If the
handoff requires hard filesystem, network, credential, or Git confinement, stop
unless a separately verified runtime provides it.

Submit the short ticket-backed handoff without waiting for completion:

```sh
"$HERDR_BIN_PATH" agent prompt <agent-name> "<concept brief>"
"$HERDR_BIN_PATH" agent get <agent-name>
```

Before the first prompt, build and persist this exact identity record from
`herdr agent get`, `git rev-parse --show-toplevel`, `git rev-parse
--path-format=absolute --git-common-dir`, and `git branch --show-current`:

```yaml
worker_surface: herdr
worker_agent_name: <agent-name>
worker_pane_id: <new-pane-id>
worker_kind: <claude|hermes>
worker_runtime_session_id: <.result.agent.agent_session.value>
worker_worktree_identity: {"root":"<canonical-root>","git_common_dir":"<canonical-common-dir>","branch":"<branch>"}
```

Verify the returned agent resolves to every persisted value and `working`. The
agent name, pane ID, kind, underlying runtime session ID, surface, and worktree
identity are distinct. Read the agent name from `.result.agent.name`, pane from
`.result.agent.pane_id`, kind from `.result.agent.agent`, and runtime session ID
from `.result.agent.agent_session.value`; require `.result.agent.cwd` to resolve
to the worktree root. Missing or ambiguous fields stop before prompting.

## Watch without changing focus

Visibility and supervision are separate. Once `working` is verified, start a
tracked background watcher in the parent runtime:

```sh
"$HERDR_BIN_PATH" agent wait <agent-name> --timeout 7200000
```

For Hermes, launch that command as a tracked background terminal process with
completion notification enabled and give the outer process a timeout slightly
longer than Herdr's two-hour bound. Preserve its process handle. Use a shorter
bound when the task has a known shorter horizon, but never omit the timeout.
The default wait settles on `idle`, `done`, or `blocked`; do not add `--until`
unless the workflow needs one exact state.

If the wait times out, inspect the same agent. Re-arm one bounded watcher if it
is still `working`; inspect terminal state if it is `unknown` or absent. A
timeout is not permission to start a duplicate worker.

Do not run `agent focus` after creation, prompting, watcher startup, or worker
updates. The pane is available in the caller's layout, but Bryan's active
window, workspace, tab, and pane must remain unchanged. If Bryan explicitly
asks to see this worker, focus the recorded agent at that time:

```sh
"$HERDR_BIN_PATH" agent focus <agent-name>
```

Focusing may change the worker's eventual settled label from `done` to `idle`
because Herdr marks viewed work as seen. Both are completion signals for the
turn, not acceptance signals for the implementation.

When the watcher returns, inspect before acting:

```sh
"$HERDR_BIN_PATH" agent get <agent-name>
"$HERDR_BIN_PATH" agent read <agent-name> --source recent-unwrapped --lines 120
```

If terminal alternate-screen history has discarded the complete response, ask
the same worker to write its report to a temporary Markdown file and reply with
the path. Do not request file output preemptively.

## Continue the same session

Before and after every correction prompt, run `agent get` and recompute the Git
worktree identity. Compare all six fields exactly: `worker_surface`,
`worker_agent_name`, `worker_pane_id`, `worker_kind`,
`worker_runtime_session_id`, and `worker_worktree_identity`. A missing legacy
field, lookup failure, mismatch, or absent agent stops; never launch a duplicate.
Only then send a follow-up to the existing name:

```sh
"$HERDR_BIN_PATH" agent prompt <agent-name> "<follow-up>"
"$HERDR_BIN_PATH" agent get <agent-name>
```

Verify all six fields still match and the original agent returns to `working`,
then start a new tracked wait for that turn if completion reporting is still promised.
Do not focus updates by default. Use `agent focus` through the recorded binary
only when Bryan explicitly asks to see the follow-up.

If the agent is `blocked`, read its terminal and ask Bryan before answering a
question or approval. Never submit an automatic prompt suggestion already
visible in Claude's input box.

## Failure handling

If Herdr is unavailable, caller-pane identity cannot be resolved, or Herdr cannot
create or start the pane without disturbing unrelated work, stop. Agent View and
background wrappers are separate explicit-only surfaces and cannot resume this
visible-worker contract.

If a split succeeds but startup or prompting fails, close only that empty or
failed handoff-owned pane after verifying its ID. Do not silently start both a
Herdr worker and a background worker.

## Cleanup

After parent acceptance, publication readback, and confirmation that Bryan no
longer needs the terminal:

```sh
"$HERDR_BIN_PATH" pane get <new-pane-id>
"$HERDR_BIN_PATH" pane close <new-pane-id>
```

Verify the pane is absent afterward. Close only the recorded handoff-owned pane;
never close the caller pane or an existing Claude or Hermes pane. Stop the
tracked watcher if cleanup happens before it naturally returns.
