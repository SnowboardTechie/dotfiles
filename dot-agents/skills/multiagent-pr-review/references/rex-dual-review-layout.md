# Dual Visible Reviewer Layout

Extend, do not duplicate, the established
[Rex Claude handoff](../../coding-agent-handoff-supervision/references/rex-claude-handoff.md).
That reference owns caller identity, focus preservation, "Background Agents" tab
placement, startup inspection, settlement, and ownership-safe cleanup. This
reference defines only the two-reviewer delta.

## Preflight

Require all of the following before starting either reviewer:

```sh
test -n "${REX_SESSION:-}"
test -n "${REX_BLOCK:-}"
REX="$(command -v rex || echo "$REX_BIN_DIR/rex")"
"$REX" whoami --json
```

`whoami` must name the same session and pane; an exit code alone is not proof.
Use the caller's injected pane throughout. There is no background
substitution, Agent View substitution, model fallback, or focused-pane guess
when this preflight fails.

Before startup, verify Claude authentication and the Opus 5.5/medium-effort route.
Fix the GPT route as the skill's Phase 0 says: the Hermes root's active GPT
model, provider, base URL, and high-reasoning setting, with no fallback chain or
conflicting `delegation.*` override; or, from a Pi root, the named
`openai-codex` model at high thinking, proven by a one-turn probe. Never rewrite
global configuration to make the route pass.

## Place both reviewers in the "Background Agents" tab

Both reviewers open in the instigating session's "Background Agents" tab, never beside
the instigating pane, without taking focus. Start them one at a time, running
`scripts/rex_background_agent_slot.py` right before each start as the Rex handoff
reference shows: Claude first, then GPT. Each start re-reads the live layout,
so the two never race for one anchor. Confirm both new pane IDs, their tab,
labels, and working directories (`"$REX" block inspect <block>`) before either
reviewer's turn proceeds. On any mismatch, stop and close only the verified
reviewer panes.

## Start exact reviewer routes

Choose two unique pane labels. Claude starts with the Rex reference's background-agent
command (`--permission-mode auto --model claude-opus-5-5 --effort medium`, a
fixed `--session-id`) in `$CLAUDE_WORKTREE`. GPT starts in `$GPT_WORKTREE` as a
background agent of the root's own kind: a Hermes background agent, as that reference's Hermes
paragraph describes, or a Pi background agent, as its Pi paragraph describes but with
`--model <GPT route> --thinking high` and no Claude subscription variable. A Pi GPT
background agent spends the Codex subscription, so the Claude capacity gate does not apply
to it. Each background agent's
first turn is the review prompt, so write both prompt files and verify both
worktrees before the first start.

The dedicated `multiagent-pr-lane-reviewer` agent must be available to the
Claude orchestrator. A Hermes GPT background agent must use smart approvals, no `--yolo`,
the root's active GPT model/provider/base URL, high reasoning, and delegation
inherited or exactly pinned to that same GPT route. A Pi GPT background agent has no
built-in background agent of its own, so each lane leaf is its own headless process in its
worktree, limited to read-only tools:

```sh
pi -p --mode json --no-session --model "$GPT_ROUTE" --thinking high \
  --tools read,grep,find,ls "@$STATE/<lane>-prompt.md" > "$STATE/<lane>.jsonl"
```

The primary lanes run in parallel as background jobs the background agent waits on, and
`ponytail` runs after them. The background agent takes each leaf's findings from its last
`message_end` and records the provider and model those events report; a leaf
that reports any other route invalidates the report. A Pi background agent has no
approval gate; the contract's prohibitions and the clean-worktree check are its
only limits. No fallback is allowed for either orchestrator or any leaf.

Persist two distinct identity records as each start returns. Each record
includes:

- `surface: rex`, pane label (agent name), pane ID, Rex session and
  tab, kind, and harness session ID;
- canonical worktree root, absolute Git common directory, and branch;
- launch model, provider, base URL where applicable, and reasoning/effort;
- dedicated reviewer state root.

Compare both records to `block inspect`, Git, and the intended worktrees. The
prompt deliberately requires bundle files. That is a narrow review-bundle
requirement, not generic transcript recovery.

## Supervise without focus

Arm one bounded completion supervisor per reviewer—two distinct supervisors and
root-owned process handles. Reviewer-orchestrators can legitimately end a turn
while their asynchronous lane leaves are still running. Treat a settled turn
without that family's final `report.sidecar.json` as an intermediate stage:
reverify the same recorded identity and keep waiting inside the same
supervisor. Completion requires both the final sidecar and a settled matching
reviewer. A reviewer blocked on an approval or question stops its supervisor so
the root can inspect and ask Bryan rather than answering automatically.

These supervisors are internal synchronization, not user notifications. When
the root intends to finish the review in the same turn, start them silently
(`notify=false` / omit terminal completion notification) and await their process
handles explicitly. Do not create a new notification-enabled background process
for each intermediate wait: those completions can arrive after the final
review and hide the verdict with stale status messages. The same rule applies to
builds, tests, and probes: run them in the foreground when practical, otherwise
use one silent owned process and explicitly wait for it.

Before presentation, prove both supervisor handles and every task-owned
verification process have exited or been closed. If any notification-enabled
process was accidentally created, do not present yet; drain it before the final
review. Permit only read-only root investigation while either reviewer runs.
Never focus either pane automatically.

Keep reviewer outputs isolated: neither reviewer receives the other's state
root, report, transcript, or eventual root disposition. Do not substitute a
background agent or another model when one fails. Continue the same recorded
reviewer for at most one bounded same-model retry.

Handle each reviewer independently. As soon as its report is admitted—or that
route becomes terminally incomplete after its one allowed retry—that reviewer
has no permitted next turn. Stop its supervisor, reverify ownership, close its
recorded pane with the Rex reference's close steps, and verify that pane ID is
absent while the other reviewer may continue. Require both panes absent before
root adjudication or incomplete-result presentation continues. Do not wait for
the peer reviewer, vault capture, final presentation, or a separate cleanup
approval, and do not leave completed panes visible as status markers. Close only
the recorded reviewer panes, never the instigating pane.
