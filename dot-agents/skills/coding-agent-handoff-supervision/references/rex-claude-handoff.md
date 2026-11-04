# Visible Claude workers in Rex

A CLI session in a Rex pane starts and supervises its worker with the `rex` CLI
directly, and does these checks by hand: identity record, capacity gate, one
turn per session, settlement, close. Everything else in the skill (contract file,
one-line prompt, permissions, parent acceptance, correction bound) is unchanged.
Verified end to end (start, settle, close) on durable-pi-workspace#278's
layout prototype, 2026-11-02.

## Which host you are in

Hermes tools run under the gateway, so the tool shell may have no `REX_*` of
its own. Hermes's `terminal.client_env_passthrough` usually puts the `REX_*`
values in the tool shell already; check `echo $REX_SESSION $REX_BLOCK` first.
Otherwise find this session's CLI process as SKILL.md describes and read it with
`python3 ~/code/dotfiles/dot-agents/lib/terminal_host.py PID`: `REX_BLOCK` and
`REX_SESSION` present means Rex; use this page. Without them there is no caller
pane and no visible-worker route.

The binary is not on PATH: `REX="$REX_BIN_DIR/rex"`. `"$REX" whoami --json`
confirms the session and block still exist.

## Start

**Workers never open in the orchestrator's own tab**: a split beside the
coordinator's block squeezes the chat Bryan reads. They open in the orchestrator's sub-agents tabs, in the same
session, without taking focus:

- **Tabs.** The first is the caller tab's label plus " Sub Agents" (for example
  "Pi Durable Sub Agents"); when it is full the next is "... Sub Agents 2", then
  3. A tab holds at most **four** workers.
- **Layout: 2x2.** The first worker is the tab's own root block. Each later one
  splits the largest pane, right when it is at least as wide as tall, otherwise
  below: 2 side by side, 3 with the left column split, 4 a square grid. A closed
  worker's quadrant is refilled first. Never stack workers with `--split=below`
  on a fixed anchor; that is the column of thin panes this rule replaces.
- **No empty shell.** A new tab is created *with the worker's command*, so its
  root block is the worker. Never `window new` without a command and then
  split: the tab's initial shell is left idle and the grid starts one short.
- **One sub-agents tab set per orchestrator,** so many orchestrators can run at
  once while Bryan talks only to them. Read-only research and briefing agents
  also run as visible workers here, not as hidden background delegations.
- **Never** `split -b "$REX_BLOCK"`. A worker started in the wrong place can be
  moved without stopping it: `"$REX" block move -s "$REX_SESSION" <block> right
  <a block in the sub-agents tab>`.

`scripts/rex_subagent_slot.py` makes the choice from the live layout (tested in
`tests/test_rex_subagent_slot.py`): it prints `{"action":"new","tab_label":…}`
or `{"action":"split","anchor":…,"direction":…}`. Run it right before each
start, never from a cached layout:

```sh
S=<ticket state dir>; W=<worktree>; NAME=<agent name, e.g. sgg-278-layout>
SK=~/code/dotfiles/dot-agents/skills/coding-agent-handoff-supervision
# Who pays follows the worktree (Bryan, 2026-11-03): SGG repos under ~/code/sgg use the
# work seat (the default login); everything else, durable-pi-workspace included, the
# personal subscription in ~/.claude-personal.
case "$W/" in "$HOME/code/sgg/"*) CCD= ;; *) CCD="$HOME/.claude-personal" ;; esac
cap=$(env ${CCD:+CLAUDE_CONFIG_DIR="$CCD"} "$SK/scripts/claude-usage.sh" | grep -oE '[0-9]+%' | head -1 | tr -d %)
[ -n "$cap" ] && [ "$cap" -lt 75 ] || { echo "capacity $cap: stop"; exit 1; }
UUID=$(uuidgen | tr A-Z a-z)
WORKER=(env ${CCD:+CLAUDE_CONFIG_DIR="$CCD"} CLAUDE_CODE_DISABLE_TERMINAL_TITLE=1
  claude --permission-mode auto --model claude-opus-5-5 --effort medium
  --name "$NAME" --session-id "$UUID" "$(cat "$S/<lane>-prompt.md")")
SLOT=$("$REX" window ls -s "$REX_SESSION" --json |
  python3 "$SK/scripts/rex_subagent_slot.py" --caller-block "$REX_BLOCK")
get() { python3 -c 'import json,sys;print(json.loads(sys.argv[1])[sys.argv[2]])' "$SLOT" "$1"; }
if [ "$(get action)" = new ]; then
  "$REX" window new -s "$REX_SESSION" "$(get tab_label)" --focus=false \
    --keep-open -c "$W" --json -- "${WORKER[@]}" > "$S/<lane>-rex-split.json"
  "$REX" block rename -s "$REX_SESSION" \
    "$(python3 -c 'import json,sys;print(json.load(sys.stdin)["block_ids"][0])' < "$S/<lane>-rex-split.json")" "$NAME"
else
  "$REX" split -s "$REX_SESSION" -b "$(get anchor)" --split="$(get direction)" \
    --focus=false --keep-open --label "$NAME" -c "$W" --json -- "${WORKER[@]}" \
    > "$S/<lane>-rex-split.json"
fi
```

`window new` has no `--label` for the block, hence the `block rename`. Start
workers one at a time (each start re-reads the layout); two starts racing on
the same layout can pick the same anchor. Verified in a scratch Rex session,
2026-11-02: four starts gave four equal quadrants, a fifth went to a new
"Sub Agents 2" tab, a closed quadrant was refilled, and closing a tab's last
worker removes the tab.

- The prompt is the positional argument, so the first turn starts with the
  pane; no typing into it.  `--session-id` fixes the runtime session ID up front,
  and the transcript lands at
  `${CCD:-~/.claude}/projects/<worktree path with / and . as ->/<UUID>.jsonl`
  (the login directory chosen above; record it in the identity file, because a
  later `claude --resume` must run under the same `CLAUDE_CONFIG_DIR`). That
  file appears only once Claude writes its first record (about 20 s), so check
  it after `capture` shows the turn running, and don't let a `set -e` script
  abort before the identity record is written.
- **Workers don't notify Bryan** (Bryan, 2026-11-03). Rex raises its "done" and
  "needs attention" alerts from OSC 7501 status reports, and
  `CLAUDE_CODE_DISABLE_TERMINAL_TITLE=1` is what stops Claude Code sending them
  (it also leaves the pane title alone, and the sub-agents tab shows no working
  dots). Keep it in every worker command. Claude sends no other notification in
  Rex: its `auto` channel has no method for `TERM_PROGRAM=rex`. The coordinator
  watches workers through the transcript and handback, never Rex's alerts.
  Checked 2026-11-03 with Claude Code 2.1.318: with the variable, a finished
  turn left `program_status` empty and the Rex app recorded no alert; without
  it, `done` and an alert.
- `--focus=false` keeps Bryan's focus; `--keep-open` keeps the pane readable
  after Claude exits. Record `worker_rex_window` as the sub-agents tab.
- An empty capacity reading is a stop, never a pass. The usage line begins
  with a non-ASCII icon (e.g. `<icon> 72% ↻1:11`), so an anchored `^ *[0-9]+`
  never matches; parse it with `grep -oE '[0-9]+%'` as above, and make any
  capacity waiter fail at once on an empty reading instead of looping.
- `claude-opus-5-5` at `medium` effort is the default (Bryan, 2026-10-23). Set
  the exact full model name only when Bryan explicitly selects a different
  Claude model, and a higher effort only when he asks; never add a fallback
  model.
- If the worker doesn't reach a running turn, `capture` its pane before doing
  anything else, so an approval or login prompt isn't lost behind a generic
  failure. Startup prompts other than folder trust remain blockers. Never
  attribute a startup failure to unrelated active agents.
- A new worktree may show Claude's "Yes, I trust this folder" prompt. Starting
  in the authorized worktree already covers it: confirm the shown path is the
  worktree in `capture`, then `"$REX" send-key -s "$REX_SESSION" -b <block> down enter`.
  Nothing else is answered this way.

Then write `<lane>-worker-identity.json` yourself: `worker_surface: "rex"`,
`worker_agent_name`, `worker_pane_id` (the new block ID from
`.block_ids[0]`), `worker_rex_session`, `worker_rex_window`, `worker_kind`,
model, effort, `worker_runtime_session_id` (the UUID, after checking the
`.jsonl` exists), `worker_worktree_identity` (branch, git common dir, root),
`capacity_start_percent`, `closed: false`. Use a fresh path: never overwrite an
existing identity file, including a closed one.

**A Hermes worker** (read-only work, or Bryan's explicit selection) uses the same
placement with `hermes chat --query-file "$S/<lane>-prompt.md"` as the worker
command, as `next-session` starts Hermes in Rex. It has no Claude transcript, so
the transcript checks and `rex_wait.sh` below don't apply: settle it on the
handback file plus `capture`. Independently check its smart approvals and no
yolo mode first. A Hermes worker still notifies Bryan: it sends OSC 7501 while
`TERM_PROGRAM=rex`, and the bell plus an OSC 9 desktop notification at turn end
and on prompts (`display.bell_on_complete` and `bell_on_prompt`, which are on).
Rex turns OSC 9 into a macOS notification. No per-process switch for the bell
exists yet. Bryan accepted that (2026-11-03): Hermes workers are rare, so no
Hermes patch unless he says the notifications have become a nuisance.

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
- Wait with `scripts/rex_wait.sh <transcript> <handback> <cap seconds>
  [marker]`, run with `terminal(background=true, notify=true)` so settlement
  wakes the coordinator. It polls every 60 s and also exits (code 2) when
  `end_turn` has held about ten minutes with no handback: a worker waiting on a
  question or one that stopped early, so read the pane. Never resend a prompt to
  regain a completion signal.
- **Keep `Divergence:` one paragraph, last.** `rex_wait.sh` settles only when
  the handback's last paragraph begins with `Divergence:`. Wrapped lines, or a
  list directly under it, still pass. A blank line before that list, or
  anything written after the line, makes the last paragraph start with
  something else. The wait then exits 2 "no handback" though the report is
  complete. Say "one line, last, no blank line after it" in every contract's
  and correction's handback list. When it happens anyway, read the handback by
  hand rather than resending.
- **A correction turn needs the marker** (its new section's heading, such as
  `"Correction 1"`): the handback already ends with the first turn's
  `Divergence:` line, so without it the wait settles on the old turn.
- Background shells load the interactive profile: use `test -f`, never `ls`,
  to check a path there, because an alias can swap `ls` for a tool that rejects
  the argument and kills the waiter before it starts.
- **A worker that backgrounds its own long check may not resume.** Claude can
  start a long run (a full mutant search, a test suite) as a background shell,
  end its turn and promise to finish "once it reports". Put "run long checks in
  the foreground" in every contract. When it happens anyway (`rex_wait.sh` exits
  2), send the same session one short continuation prompt to finish from the
  run's output. That is not a correction pass.
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

Confirm a new `user` record in the transcript that it was accepted before you
report it delivered; `capture` can still show an empty prompt for several
seconds after a good submit. Then start `rex_wait.sh` with the marker.

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
stays at its path; `claude --resume <UUID>` in the worktree, under the same `CLAUDE_CONFIG_DIR`
as the worker (`claude-personal --resume <UUID>` outside ~/code/sgg), reopens it later.

## What this does not give you

No turn lease or journal: two coordinators could both type into the block, so
one coordinator owns each worker and nothing else sends to it. No automatic
identity revalidation: before every `send`, `"$REX" block inspect <block>`
must still show the recorded label and window.

## Failure rules

- Never edit an identity file to make a mismatch pass.
- Never switch providers when capacity or identity fails.
- Never target a globally focused pane when the caller's `REX_BLOCK` is
  unavailable.
- Preserve partial repository bytes before closing a capacity-blocked worker.
- Ask Bryan before answering a blocked approval or question that the governing
  plan doesn't already settle.
