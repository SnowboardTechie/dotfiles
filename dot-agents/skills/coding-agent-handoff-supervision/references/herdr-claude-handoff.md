# Herdr-Native Claude Handoffs

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
injected path is absent, non-executable, or incompatible, use Agent View.

This is especially important for the watcher: a tracked background terminal
may start a login shell that exposes an older Herdr client. Invoke the inherited
`HERDR_BIN_PATH` directly; do not let that shell resolve `herdr` again. A
protocol mismatch means the wrong client ran. Retry the same watcher once with
the injected compatible path rather than starting another worker.

Use the injected caller pane ID even when another Herdr tab is globally focused.
Stop rather than substituting the focused pane if the caller cannot be resolved.

## Create the visible worker

A horizontal handoff means a side-by-side split created to the caller's right.
Keep focus on the caller while preparing Claude, and preserve the exact working
directory:

```sh
"$HERDR_BIN_PATH" pane split --pane "$HERDR_PANE_ID" \
  --direction right --ratio 0.5 --cwd "$PWD" --no-focus
```

Read the new pane from `.result.pane.pane_id`; never derive it from sidebar
position, example IDs, or the globally focused pane. Record the pane ID as a
handoff-owned resource.

Choose a useful unique Herdr agent name matching
`[a-z][a-z0-9_-]{0,31}`. Check `"$HERDR_BIN_PATH" agent list` before naming it. The Herdr
agent name is the stable control target; Claude's `--name` is the human display
name.

Start Claude without an initial prompt so Herdr can verify interactive readiness:

```sh
"$HERDR_BIN_PATH" agent start <agent-name> --kind claude --pane <new-pane-id> -- \
  --permission-mode auto --model opus --effort high \
  --name "<short task name>"
```

Preserve an explicitly requested model, effort, or safer permission mode instead
of overwriting it with the example defaults. If startup returns
`agent_not_ready`, inspect `agent get` and `agent read` through the recorded
binary. A trust, approval, or question UI is `blocked`; do not answer it for the
user.

Submit the concept brief without waiting for completion:

```sh
"$HERDR_BIN_PATH" agent prompt <agent-name> "<concept brief>"
"$HERDR_BIN_PATH" agent get <agent-name>
```

Verify the returned agent resolves to the new pane, intended cwd, a real Claude
session identity, and `working`. If the prompt stalls or the agent is blocked,
inspect the UI and report the blocker rather than creating another worker.

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

Send a follow-up to the existing name:

```sh
"$HERDR_BIN_PATH" agent prompt <agent-name> "<follow-up>"
"$HERDR_BIN_PATH" agent get <agent-name>
```

Verify the same pane and Claude session identity return to `working`, then start
a new tracked wait for that turn if completion reporting is still promised.
Do not focus updates by default. Use `agent focus` through the recorded binary
only when Bryan explicitly asks to see the follow-up.

If the agent is `blocked`, read its terminal and ask Bryan before answering a
question or approval. Never submit an automatic prompt suggestion already
visible in Claude's input box.

## Fallback and failure handling

Use the Agent View fallback when:

- `HERDR_ENV` is not `1`;
- caller-pane identity is absent or cannot be resolved;
- Bryan explicitly requests background-only dispatch; or
- Herdr cannot create or start the pane without disturbing unrelated work.

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
never close the caller pane or an existing Claude pane. Stop the tracked watcher
if cleanup happens before it naturally returns.
