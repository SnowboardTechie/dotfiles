# Dual Visible Reviewer Layout

Extend, do not duplicate, the established
[Herdr Claude handoff](../../coding-agent-handoff-supervision/references/herdr-claude-handoff.md).
That reference owns preflight, caller identity, focus preservation, startup
inspection, watcher handling, continuation, and ownership-safe cleanup. This
reference defines only the two-reviewer delta.

## Preflight

Require all of the following before splitting:

```sh
test "${HERDR_ENV:-}" = 1
test -n "${HERDR_PANE_ID:-}"
test -x "${HERDR_BIN_PATH:-}"
"$HERDR_BIN_PATH" status
"$HERDR_BIN_PATH" pane current --pane "$HERDR_PANE_ID"
"$HERDR_BIN_PATH" pane layout --pane "$HERDR_PANE_ID"
```

Read the status payload and require `compatible: yes`; an exit code alone is not
proof. Use the injected executable and exact caller pane throughout. There is no
background substitution, Agent View substitution, model fallback, or focused-
pane guess when this preflight fails.

Before startup, verify Claude authentication and the Opus/high-effort route.
Capture the instigating Hermes session's active GPT model, provider, base URL,
and high-reasoning setting. Reject any fallback chain or conflicting
`delegation.model`, `delegation.provider`, or `delegation.base_url` override;
never rewrite global configuration to make the route pass.

## Create right-then-down geometry

First split the instigating pane to the right without focus transfer:

```sh
claude_split=$("$HERDR_BIN_PATH" pane split --pane "$HERDR_PANE_ID" \
  --direction right --ratio 0.5 --cwd "$CLAUDE_WORKTREE" --no-focus)
claude_pane_id=<parse-.result.pane.pane_id-from-claude_split>
```

Then target that returned Claude pane, not the caller or globally focused pane,
and split it down:

```sh
gpt_split=$("$HERDR_BIN_PATH" pane split --pane "$claude_pane_id" \
  --direction down --ratio 0.5 --cwd "$GPT_WORKTREE" --no-focus)
gpt_pane_id=<parse-.result.pane.pane_id-from-gpt_split>
```

The resulting assignment is Claude in the upper-right/top pane and GPT in the
lower-right/bottom pane. Query the final layout from `HERDR_PANE_ID`; confirm both
parsed pane IDs, their parent/position, and both working directories before
starting either agent. On any mismatch, stop and close only verified empty panes.

## Start exact reviewer routes

Choose two unique agent names. Start both without an initial prompt:

```sh
"$HERDR_BIN_PATH" agent start "$CLAUDE_AGENT_NAME" \
  --kind claude --pane "$claude_pane_id" -- \
  --permission-mode acceptEdits --model opus --effort high \
  --name "PR review: Claude"

"$HERDR_BIN_PATH" agent start "$GPT_AGENT_NAME" \
  --kind hermes --pane "$gpt_pane_id"
```

The dedicated `multiagent-pr-lane-reviewer` agent must be available to the
Claude orchestrator. Hermes must use smart approvals, no `--yolo`, the root's
active GPT model/provider/base URL, high reasoning, and delegation inherited or
exactly pinned to that same GPT route. No fallback is allowed for either parent
or any leaf.

Persist two distinct identity records before prompting. Each record includes:

- `surface: herdr`, agent name, pane ID, kind, and runtime session ID;
- canonical worktree root, absolute Git common directory, and branch;
- launch model, provider, base URL where applicable, and reasoning/effort;
- dedicated reviewer state root.

Compare both records to `agent get`, Git, and the intended worktrees. Prompt
only after both records are complete and both agents are ready. The initial
prompt deliberately requires bundle files. That is a narrow review-bundle
requirement, not generic alternate-screen transcript recovery, and is the
intentional exception to the handoff reference's file-only-if-needed fallback.

## Supervise without focus

Arm one bounded watcher per agent—two distinct watchers and process handles—by
calling the injected binary's `agent wait`. Permit only read-only root
investigation while either runs. Never focus either pane automatically. If an
agent is blocked, inspect and ask Bryan rather than answering an approval or
question automatically.

Keep reviewer outputs isolated: neither reviewer receives the other's state
root, report, transcript, or eventual root disposition. Do not substitute a
background worker or another model when one fails. Continue the same recorded
agent for at most one bounded same-model retry.

Leave both panes visible after presenting the review. Pane cleanup requires
explicit user-approved cleanup after ownership is reverified; close only the two
recorded reviewer panes and never the instigating pane.
