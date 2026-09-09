# Herdr Helper Operations

`scripts/herdr_worker.py` is the executable owner of visible-worker mechanics.
Use its `--help` output as the current command reference; do not copy raw Herdr
JSON parsing or focus-sensitive pane commands into another skill.

## Preconditions

- `HERDR_ENV=1`
- non-empty `HERDR_PANE_ID`
- executable injected `HERDR_BIN_PATH`
- named Git branch and existing worktree
- for Claude, executable `~/.config/herdr/claude-usage.sh`
- for Hermes, independently verified smart approvals and no yolo mode

The helper requires both `endpoint_compatible: yes` and
`private_protocol_compatible: yes` from the injected Herdr client. A different
client found through `PATH` is not a fallback.

## Start

```sh
python3 scripts/herdr_worker.py start \
  --worktree "$WORKTREE" \
  --identity-file "$STATE_DIR/worker-identity.json" \
  --name "$AGENT_NAME" \
  --kind claude \
  --title "$TITLE"
```

The command exclusively reserves a new identity path under a per-identity owner
lock before any pane side effect, performs the live capacity check before pane
creation, creates a
right-hand `--no-focus` split from the injected caller pane, starts Claude with
auto permissions and Opus/high effort, verifies the runtime session and Git
worktree, then atomically writes the six-field identity file with mode 0600.

Any pre-existing identity path, including a closed record, is refused before a
pane is created. Use a different state path for a separately authorized worker;
never overwrite the ownership record of an existing or failed start.

If split succeeds but startup or identity validation fails, it closes that new
pane before returning failure. A failed agent start first captures bounded
terminal output, so an approval or login prompt is not lost behind a generic
`agent_not_ready` error. For an authorized, inspected worktree, the helper
automatically accepts Claude's ordinary folder-trust prompt after matching the
exact displayed path and startup pane/cwd. It waits for a newer ready state;
no extra user confirmation is needed. Other startup prompts remain blockers.
Never attribute startup failure to unrelated active agents or broaden that
folder-trust authorization into unrelated permissions.

## Prompt and wait

```sh
python3 scripts/herdr_worker.py prompt \
  --identity-file "$STATE_DIR/worker-identity.json" \
  --prompt-file "$STATE_DIR/worker-prompt.md" \
  --timeout-ms 7200000
```

Run this command through a tracked background terminal process with completion
notification. It holds an OS file lock for the entire Claude turn, keyed by
the recorded worker runtime session ID. This serializes input to one session,
not all Claude work on the machine or subscription. Independent sessions may
run concurrently in separate worktrees. The lock is process-owned and releases
automatically on exit; `--lease-path` supplies a filename base whose final name
is always session-scoped.

Before input is sent, the command rejects:

- exhausted or unverifiable Claude capacity;
- an overlapping turn targeting this same worker runtime session;
- a closed or malformed identity record;
- any changed name, pane, kind, runtime session, root, Git common directory, or
  branch; and
- a worker already in `working` state.

It calls Herdr `agent prompt --wait`, verifies the same identity after the turn,
and returns compact JSON containing settled status plus start/end capacity. A
failed end probe records `provider_capacity_end_verified: false`; it does not
erase a successfully completed turn.

Use `--text` instead of `--prompt-file` only for a genuinely short literal.

## Inspect

```sh
python3 scripts/herdr_worker.py inspect \
  --identity-file "$STATE_DIR/worker-identity.json"
```

This is read-only and validates the worker and Git identity before reporting its
current status. It does not acquire the provider-turn lease.

## Read and answer a blocked worker

```sh
python3 scripts/herdr_worker.py read \
  --identity-file "$STATE_DIR/worker-identity.json" \
  --lines 120

python3 scripts/herdr_worker.py answer-blocked \
  --identity-file "$STATE_DIR/worker-identity.json" \
  --text "$BRYAN_APPROVED_ANSWER" \
  --timeout-ms 7200000
```

Use `answer-blocked --keys down enter` instead for an approved interactive key
choice. `read` validates identity before and after bounded terminal output.
`answer-blocked` refuses a worker that is not recorded as `blocked`, acquires the
same runtime-session lease as `prompt`, reruns capacity, captures the
current `state_change_seq`, submits only the caller-approved text or keys, and
holds the lease until a newer idle/done/blocked state is observed. Herdr `agent
wait` without explicit lifecycle sequencing would match the old blocked state
immediately and is not sufficient. Herdr `agent prompt` cannot resume a blocked
agent; do not use it for answers.

## Recover an interrupted start

```sh
python3 scripts/herdr_worker.py recover-start \
  --identity-file "$STATE_DIR/worker-identity.json"
```

Every reservation stores intended worktree, name, kind, caller pane, and the
worker pane as soon as it exists. Before splitting it also journals the complete
pane inventory and caller tab/workspace identity. If interruption lands after
the split side effect but before its return, recovery admits only the single new
pane in that tab/workspace whose cwd matches the recorded worktree; zero is safe
absence and multiple candidates fail closed. `recover-start` acquires the same
start lock. It completes a six-field active identity only when the exact
recorded agent, pane, kind, session, and Git worktree are live; otherwise it
closes the exact recorded orphan pane, proves both agent and pane absent, and
terminalizes the record. Transport, protocol, malformed-response, or identity
uncertainty leaves the recoverable record intact for a later retry.

## Close

```sh
python3 scripts/herdr_worker.py close \
  --identity-file "$STATE_DIR/worker-identity.json"
```

The command validates the live identity, atomically records
`closing: true`/`cleanup_required: true` under the identity lock, closes only the
recorded pane, verifies both pane and agent are absent from structured
`agent_not_found` and `pane_not_found` responses, and marks the identity closed.
Every other Herdr error preserves the closing record and fails; rerunning
`close` resumes from that journal without requiring the now-absent agent. A
closed identity is non-resumable. Re-running `close` is idempotent.

## Failure Rules

- Never edit an identity file to make a mismatch pass.
- Never delete or bypass the turn lease. Wait for the owning process to settle or
  terminate it through its tracked process handle.
- Never switch providers when capacity or identity fails.
- Never use a globally focused pane when the injected caller pane is unavailable.
- Preserve partial repository bytes before closing a capacity-blocked worker.
- Ask Bryan before answering a blocked approval or question.

## Validation

```sh
python3 -m unittest \
  dot-agents/skills/coding-agent-handoff-supervision/tests/test_herdr_worker.py
python3 dot-agents/skills/coding-agent-handoff-supervision/scripts/herdr_worker.py --help
```

The tests use a fake Herdr client and isolated Git repository; they never create
a live pane or spend provider capacity.