# Visible Claude workers in Rex

`scripts/herdr_worker.py` drives Herdr only. When this CLI session runs in a Rex
pane, start and supervise the worker with the `rex` CLI directly, and do by hand
the checks the helper would do: identity record, capacity gate, one turn per
session, settlement, close. Everything else in the skill (contract file,
one-line prompt, permissions, parent acceptance, correction bound) is unchanged.
Verified end to end (start, settle, close) on durable-pi-workspace#278's
layout prototype, 2026-11-02.

## Which host you are in

Hermes tools run under the gateway, so the tool shell has no `HERDR_*` or
`REX_*` of its own. Find this session's CLI process as SKILL.md describes and
read it with `python3 ~/code/dotfiles/dot-agents/lib/terminal_host.py PID`:

- `HERDR_PANE_ID` present: Herdr; use the helper.
- only `REX_BLOCK` and `REX_SESSION`: Rex; use this page. Hermes's
  `terminal.client_env_passthrough` usually puts the `REX_*` values in the tool
  shell already; check `echo $REX_SESSION $REX_BLOCK` first.
- the gateway's `herdr_*` tools refuse a CLI conversation
  (`origin_not_authorized`); they are for Matrix, not a fallback here.

The binary is not on PATH: `REX="$REX_BIN_DIR/rex"`. `"$REX" whoami --json`
confirms the session and block still exist.

## Start

**Workers never open in the orchestrator's own tab** (the same rule as Herdr's,
`herdr-claude-handoff.md`): a split beside the coordinator's block squeezes the
chat Bryan reads. They open in the orchestrator's sub-agents tab, labelled with
the caller tab's label plus " Sub Agents" (for example "Pi Durable Sub Agents"),
in the same session, without taking focus:

- **No such tab yet:** `"$REX" window new -s "$REX_SESSION" "<label> Sub Agents"
  --focus=false --keep-open -c "$W" --json -- claude …`. Its root block is the
  worker; no empty shell is left beside it. Read the caller tab's label from
  `"$REX" window ls -s "$REX_SESSION" --json` (the window holding `$REX_BLOCK`).
- **The tab exists:** `"$REX" split -s "$REX_SESSION" -b <a worker block in that
  tab> --split=below --focus=false …`.
- **Never** `split -b "$REX_BLOCK"`. A worker started there by mistake can be
  moved without stopping it: `"$REX" block move -s "$REX_SESSION" <block> below
  <a block in the sub-agents tab>`.

The command and checks are the same either way:

```sh
S=<ticket state dir>; W=<worktree>; NAME=<agent name, e.g. sgg-278-layout>
cap=$(~/.config/herdr/claude-usage.sh | grep -oE '[0-9]+%' | head -1 | tr -d %)
[ -n "$cap" ] && [ "$cap" -lt 75 ] || { echo "capacity $cap: stop"; exit 1; }
UUID=$(uuidgen | tr A-Z a-z)
"$REX" split -s "$REX_SESSION" -b "$SUBAGENT_BLOCK" --split=below --focus=false \
  --keep-open --label "$NAME" -c "$W" --json -- \
  claude --permission-mode auto --model claude-opus-5-5 --effort medium \
  --name "$NAME" --session-id "$UUID" "$(cat "$S/<lane>-prompt.md")" \
  > "$S/<lane>-rex-split.json"
```

- The prompt is the positional argument, so the first turn starts with the
  pane; no typing into it.  `--session-id` fixes the runtime session ID up front,
  and the transcript lands at
  `~/.claude/projects/<worktree path with / and . as ->/<UUID>.jsonl`. That
  file appears only once Claude writes its first record (about 20 s), so check
  it after `capture` shows the turn running, and don't let a `set -e` script
  abort before the identity record is written.
- `--focus=false` keeps Bryan's focus; `--keep-open` keeps the pane readable
  after Claude exits. Record `worker_rex_window` as the sub-agents tab.
- An empty capacity reading is a stop, never a pass.
- A new worktree may show Claude's "Yes, I trust this folder" prompt. Starting
  in the authorized worktree already covers it: confirm the shown path is the
  worktree in `capture`, then `"$REX" send-key -s "$REX_SESSION" -b <block> down enter`.
  Nothing else is answered this way.

Then write `<lane>-worker-identity.json` yourself: `worker_surface: "rex"`,
`worker_agent_name`, `worker_pane_id` (the new block ID from
`.block_ids[0]`), `worker_rex_session`, `worker_rex_window`, `worker_kind`,
model, effort, `worker_runtime_session_id` (the UUID, after checking the
`.jsonl` exists), `worker_worktree_identity` (branch, git common dir, root),
`capacity_start_percent`, `closed: false`.

## Watch and settle

- Read the pane: `"$REX" capture -s "$REX_SESSION" -b <block> --trim | tail -40`.
- **Settled** means both: the last `assistant` record in the transcript has
  `message.stop_reason == "end_turn"` with no `user` record after it, and the
  contract's handback file ends with its `Divergence:` line. A turn that ends
  with a background shell still running can show `end_turn` before the
  handback exists, so the handback is the deciding signal.

  ```sh
  tail -40 "$T" | python3 -c '
  import json,sys
  last=None
  for l in sys.stdin:
      d=json.loads(l)
      if d.get("type") in ("assistant","user"): last=d
  m=(last or {}).get("message") or {}
  print(last and last["type"], m.get("stop_reason"))'
  ```
  `assistant end_turn` means settled; `assistant tool_use` or `user` means working.
- Wait with a bounded background loop that polls the handback and transcript
  (for example every 60 s, under a cap sized to the task). Make it also exit
  when the transcript has shown `end_turn` for about ten minutes with no
  handback: that is a worker waiting on a question or one that stopped early,
  and the coordinator must read the pane. Run it with
  `terminal(background=true, notify=true)` so settlement wakes the coordinator.
  Never resend a prompt to regain a completion signal.
- **Text in the input line after a turn is often not Bryan's.** Claude Code
  greys in a predicted next prompt (prompt suggestion). Plain `capture` can't
  tell it from typed text; `capture --format=html` shows it inside
  `opacity: 0.5`. Never read it as Bryan's answer, and never submit it.
- A worker blocked on a permission or question shows it in `capture`. Answer
  only what the governing plan already settles, through `rex send` and
  `rex send-key`; anything new goes to Bryan.

## A second turn (correction)

One turn at a time per session: only after settlement, rerun the capacity
check, then type into the same block and submit:

```sh
"$REX" send -s "$REX_SESSION" -b <block> "$(cat "$S/<lane>-correction-1-prompt.md")"
"$REX" send-key -s "$REX_SESSION" -b <block> enter
```

Confirm in `capture` (and a new `user` record in the transcript) that it was
accepted before you report it delivered.

## Close

When no concrete next turn remains, exit Claude and close only the recorded
block, then confirm it is gone:

```sh
"$REX" send -s "$REX_SESSION" -b <block> "/exit"
"$REX" send-key -s "$REX_SESSION" -b <block> enter   # pane prints the resume command
"$REX" block close -s "$REX_SESSION" <block>
"$REX" block ls -s "$REX_SESSION" --json | grep -c <block>    # expect 0
```

Mark the identity file `closed: true` with the end capacity. The transcript
stays at its path; `claude --resume <UUID>` in the worktree reopens it later.

## What this does not give you

No turn lease or journal: two coordinators could both type into the block, so
one coordinator owns each worker and nothing else sends to it. No automatic
identity revalidation: before every `send`, `"$REX" block inspect <block>`
must still show the recorded label and window.
