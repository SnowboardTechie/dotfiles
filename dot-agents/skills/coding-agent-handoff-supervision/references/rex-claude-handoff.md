# Visible Pi background agents in Rex

A Pi or Hermes CLI session in a Rex pane starts and supervises its Pi background agent with the `rex` CLI
directly, and does these checks by hand: identity record, capacity limit, one
turn per session, settlement, close. Everything else in the skill (assignment file,
one-line prompt, permissions, orchestrator acceptance, correction bound) is unchanged.
Verified end to end (start, settle, close) on durable-pi-workspace#278's
layout prototype, 2026-11-02.

## Which harness you are in

Pi's tool shell carries `REX_SESSION`, `REX_BLOCK` and `REX_BIN_DIR` directly:
`echo $REX_SESSION $REX_BLOCK` answers it, and empty means no caller pane. The
rest of this section applies only to Hermes.

Hermes tools run under the gateway, so the tool shell may have no `REX_*` of
its own. Hermes's `terminal.client_env_passthrough` usually puts the `REX_*`
values in the tool shell already; check `echo $REX_SESSION $REX_BLOCK` first.
Otherwise find this session's CLI process as SKILL.md describes and read it with
`python3 ~/code/dotfiles/dot-agents/lib/terminal_host.py PID`: `REX_BLOCK` and
`REX_SESSION` present means Rex; use this page. Without them there is no caller
pane and no visible background-agent route.

The binary is not on PATH: `REX="$REX_BIN_DIR/rex"`. `"$REX" whoami --json`
confirms the session and pane still exist.

## Start

**Background agents never open in the orchestrator's own tab**: a split beside the
orchestrator's pane squeezes the chat Bryan reads. They open in the orchestrator's "Background Agents" tabs, in the same
session, without taking focus:

- **Tabs.** The first is the caller tab's label plus " Background Agents" (for example
  "Pi Durable Background Agents"); when it is full the next is "... Background Agents 2", then
  3. A tab holds at most **four** background agents.
- **Layout: 2x2.** The first background agent is the tab's own root pane. Each later one
  splits the largest pane, right when it is at least as wide as tall, otherwise
  below: 2 side by side, 3 with the left column split, 4 a square grid. A closed
  background agent's quadrant is refilled first. Never stack background agents with `--split=below`
  on a fixed anchor; that is the column of thin panes this rule replaces.
- **No empty shell.** A new tab is created *with the background agent's command*, so its
  root pane is the background agent. Never `window new` without a command and then
  split: the tab's initial shell is left idle and the grid starts one short.
- **One "Background Agents" tab set per orchestrator,** so many orchestrators can run at
  once while Bryan talks only to them. Read-only research and briefing agents
  also run as visible background agents here, not as hidden background delegations.
- **Never** `split -b "$REX_BLOCK"`. A background agent started in the wrong place can be
  moved without stopping it: `"$REX" block move -s "$REX_SESSION" <block> right
  <a block in the "Background Agents" tab>`.

`scripts/rex_background_agent_pane.py` makes the choice from the live layout (tested in
`tests/test_rex_background_agent_pane.py`): it prints `{"action":"new","tab_label":…}`
or `{"action":"split","anchor":…,"direction":…}`. Run it right before each
start, never from a cached layout:

```sh
S=<issue state directory>; W=<worktree>; NAME=<agent name, e.g. sgg-278-layout>
SK=~/code/dotfiles/dot-agents/skills/coding-agent-handoff-supervision
# Who pays follows the worktree (Bryan, 2026-11-03): SGG repos under ~/code/sgg use the
# work subscription (the default login); everything else, durable-pi-workspace included, the
# personal subscription in ~/.claude-personal.
case "$W/" in "$HOME/code/sgg/"*) CCD= ;; *) CCD="$HOME/.claude-personal" ;; esac
usage=$(env ${CCD:+CLAUDE_CONFIG_DIR="$CCD"} "$SK/scripts/claude-usage.sh")
cap=$(printf %s "$usage" | grep -oE '[0-9]+%' | head -1 | tr -d %)
# The usage threshold is 75% of a 5-hour usage window and 90% of a weekly one (Bryan, 2026-11-14).
case "$usage" in *weekly*) threshold=90 ;; *) threshold=75 ;; esac
[ -n "$cap" ] && [ "$cap" -lt "$threshold" ] || { echo "capacity $cap (usage threshold $threshold): stop"; exit 1; }
UUID=$(uuidgen | tr A-Z a-z)
if [ -n "$CCD" ]; then SUBSCRIPTION=(env PI_CLAUDE_CODE_CONFIG_DIR="$CCD"); else SUBSCRIPTION=(env -u PI_CLAUDE_CODE_CONFIG_DIR); fi
AGENT=("${SUBSCRIPTION[@]}" PI_PROGRAM_STATUS=0 pi --name "$NAME" --session-id "$UUID"
  --model claude-code/claude-opus-5-5 --thinking medium "@$S/<workstream>-prompt.md")
PANE=$("$REX" window ls -s "$REX_SESSION" --json |
  python3 "$SK/scripts/rex_background_agent_pane.py" --caller-block "$REX_BLOCK")
get() { python3 -c 'import json,sys;print(json.loads(sys.argv[1])[sys.argv[2]])' "$PANE" "$1"; }
if [ "$(get action)" = new ]; then
  "$REX" window new -s "$REX_SESSION" "$(get tab_label)" --focus=false \
    --keep-open -c "$W" --json -- "${AGENT[@]}" > "$S/<workstream>-rex-split.json"
  "$REX" block rename -s "$REX_SESSION" \
    "$(python3 -c 'import json,sys;print(json.load(sys.stdin)["block_ids"][0])' < "$S/<workstream>-rex-split.json")" "$NAME"
else
  "$REX" split -s "$REX_SESSION" -b "$(get anchor)" --split="$(get direction)" \
    --focus=false --keep-open --label "$NAME" -c "$W" --json -- "${AGENT[@]}" \
    > "$S/<workstream>-rex-split.json"
fi
```

`window new` has no `--label` for the pane, hence the `block rename`. Start
background agents one at a time (each start re-reads the layout); two starts racing on
the same layout can pick the same anchor. Verified in a scratch Rex session,
2026-11-02: four starts gave four equal quadrants, a fifth went to a new
"Background Agents 2" tab, a closed quadrant was refilled, and closing a tab's last
background agent removes the tab.

- **Pi is the background agent for everything** (Bryan, 2026-11-10): implementers,
  reviewers, read-only research, from a Pi or a Hermes orchestrator. Claude or Hermes
  runs only when Bryan explicitly selects it for that run (see "Other harnesses for
  background agents" below).
- `@$S/<workstream>-prompt.md` makes the prompt file the first turn, so the turn
  starts with the pane; no typing into it. `--session-id` fixes the Pi
  session ID up front (Pi warns that no session with that ID exists yet and
  creates it). The transcript lands at
  `~/.pi/agent/sessions/--<worktree path with / as ->--/<time>_<UUID>.jsonl`;
  find it with `ls ~/.pi/agent/sessions/*/*_"$UUID".jsonl` once `capture` shows
  the turn running, and don't let a `set -e` script abort before the identity
  record is written. `pi --session "$UUID"` in the worktree, with the same subscription,
  reopens it later.
- **Pi has no approval gate.** It runs every tool call, so a background agent's limits
  are the assignment's prohibitions only. That fits work in Bryan's own
  repositories. When a task needs an approval gate or hard confinement, Pi
  can't give it: stop and ask Bryan, who may select a Claude background agent for it.
- **Background agents don't notify Bryan** (Bryan, 2026-11-03, 2026-11-10). Rex raises its
  "done" and "needs attention" alerts from OSC 7501 status reports, Pi's only
  Rex signal. `PI_PROGRAM_STATUS=0` turns them off (and the "Background Agents" tab shows
  no working dots). Keep it in every background agent command. The orchestrator watches
  background agents through the transcript and completion report, never Rex's alerts. Checked
  2026-11-10: a finished Pi turn with the variable left `program_status` empty.
- **Silence the background agent, not the tab.** Rex's per-tab mute exists only in the
  Mac app (right-click a tab); there is no CLI or API for it, and writing its
  `Workspace.mutedTabs` preference while the app runs has no effect (checked
  2026-11-10).
- `--focus=false` keeps Bryan's focus; `--keep-open` keeps the pane readable
  after Pi exits. Record `background_agent_rex_window` as the "Background Agents" tab.
- The background agent spends the Claude subscription its `PI_CLAUDE_CODE_CONFIG_DIR` names, so
  the capacity check reads that subscription. An empty capacity reading is a stop, never a pass. The usage line reports
  the 5-hour usage window when the subscription has one (e.g. `<icon> 72% ↻1:11`) and the
  weekly one when it doesn't (e.g. `<icon> 25% weekly ↻6d 3h`). Either way
  the first `NN%` is the utilization. The line begins with a non-ASCII icon,
  so an anchored `^ *[0-9]+` never matches; parse it with `grep -oE '[0-9]+%'`
  as above, and make any wait for capacity fail at once on an empty reading
  instead of looping.
- `claude-code/claude-opus-5-5` at `medium` thinking is the default (Bryan,
  2026-10-23). Set another model only when Bryan explicitly selects it, and a
  higher thinking level only when he asks; never add a fallback model.
- If the background agent doesn't reach a running turn, `capture` its pane before doing
  anything else, so a login or trust prompt isn't lost behind a generic
  failure. Startup prompts remain blockers unless the plan settles them. Never
  attribute a startup failure to unrelated active agents.

Then write `<workstream>-background-agent-identity.json` yourself: `background_agent_surface: "rex"`,
`background_agent_name`, `background_agent_pane_id` (the new pane's ID from
`.block_ids[0]`), `background_agent_rex_session`, `background_agent_rex_window`, `background_agent_kind:
"pi"`, model, thinking level, subscription, `background_agent_session_id` (the UUID, after
checking the `.jsonl` exists), `background_agent_transcript` (its path),
`background_agent_worktree_identity` (branch, git common dir, root),
`capacity_start_percent`, `closed: false`. Use a fresh path: never overwrite an
existing identity record, including a closed one.

### Other harnesses for background agents (explicit selection only)

**A Claude background agent** keeps the same placement, capacity limit and identity record, with
this command; its transcript lands at
`${CCD:-~/.claude}/projects/<worktree path with / and . as ->/<UUID>.jsonl`
(about 20 s after start), and `rex_wait.sh` reads it too:

```sh
AGENT=(env ${CCD:+CLAUDE_CONFIG_DIR="$CCD"} CLAUDE_CODE_DISABLE_TERMINAL_TITLE=1
  claude --permission-mode auto --model claude-opus-5-5 --effort medium
  --name "$NAME" --session-id "$UUID" "$(cat "$S/<workstream>-prompt.md")")
```

`CLAUDE_CODE_DISABLE_TERMINAL_TITLE=1` is Claude's silence switch (checked
2026-11-03 with Claude Code 2.1.318). A new worktree may show Claude's "Yes, I
trust this folder" prompt: starting in the authorized worktree covers it, so
confirm the shown path in `capture`, then
`"$REX" send-key -s "$REX_SESSION" -b <block> down enter`. Nothing else is
answered this way. Close it with `/exit`; `claude --resume <UUID>` under the
same `CLAUDE_CONFIG_DIR` reopens it. Claude's prompt suggestions grey a
predicted next prompt into the input line (`capture --format=html` shows it at
`opacity: 0.5`); never read it as Bryan's answer or submit it.

**A Hermes background agent** uses the same placement with
`hermes chat --query-file "$S/<workstream>-prompt.md"` as the background agent command, as
`next-session` starts Hermes in Rex. It has no transcript `rex_wait.sh` reads,
so settle it on the completion report file plus `capture`. Wait for a `Divergence:` line in the completion report's
last section, with `rex_wait.sh`'s test, as a background job with `notify=true` (from
a Pi orchestrator, run this loop in the foreground with a `bash` timeout; `watch_background_agent`
needs a transcript):
`until test -f "$H" && awk '/^[ \t]*(```|~~~)/{fence=!fence; next} !fence && /^#{1,6}[ \t]/{found=0; next} !fence && /^(\*\*)?Divergence:/{found=1} END{exit !found}' "$H"; do sleep 60; done`
(add a cap). Independently check its smart approvals and no yolo mode first. A
Hermes background agent still notifies Bryan: OSC 7501, the bell and an OSC 9 desktop
notification at turn end and on prompts. No per-process switch exists; Bryan
accepted that for rare Hermes background agents (2026-11-03).

## Watch and settle

- Read the pane: `"$REX" capture -s "$REX_SESSION" -b <block> --trim | tail -40`.
- **Settled** means both: the transcript's last message is an assistant one
  that stopped without a tool call (`stopReason` `stop`; `error` and `aborted`
  also end the turn), and the last section of the assignment's completion report file
  has its `Divergence:` line. A turn that ends with a background shell still running
  can end before the completion report exists, so the completion report is the deciding signal.

  ```sh
  tail -40 "$T" | python3 -c '
  import json,sys
  last=None
  for l in sys.stdin:
      d=json.loads(l)
      if d.get("type")=="message": last=d["message"]
  print(last and last.get("role"), last and last.get("stopReason"))'
  ```
  `assistant stop` means the turn ended; `assistant toolUse`, `toolResult` or
  `user` means working.
- Wait with `scripts/rex_wait.sh <transcript> <completion report> <cap seconds>
  [marker]`, armed so settlement wakes the orchestrator: from Pi, the
  `watch_background_agent` tool (it runs this script in the background and wakes the
  session with its exit code and output); from Hermes,
  `terminal(background=true, notify=true)`. Arm it after every start and every
  typed turn, before ending your own turn. It polls every 60 s and also exits (code 2) when
  the turn has stayed ended about ten minutes with no completion report: a background agent waiting on a
  question or one that stopped early, so read the pane. It exits 3 when the
  last message is an unanswered user prompt or tool result and the transcript
  has been silent about eight minutes: the turn halted without ending and the
  pane sits idle
  at its prompt. A model safety-filter stop ("…safeguards stopped the response")
  looks like this. A wait keyed only on the turn ending sits until its cap while
  Bryan wonders why nothing moves. Read the pane, then send the same session one
  short continuation (not a correction pass). If exploit-style wording in the
  assignment tripped the filter, restate the work as defensive checks and tests.
  Never resend a prompt merely to regain a completion signal.
- **Watch a read-only reviewer the same way.** Its "completion report" is the summary
  file its assignment names; pass that path to `rex_wait.sh`, so exit 3 covers a
  halted review too.
- **Where `Divergence:` goes.** `rex_wait.sh` settles when the completion report's last
  section (everything after its last Markdown heading outside a code fence, or the whole
  file when it has none) has a line starting `Divergence:` or `**Divergence:**`. A list
  of differences under it, with or without a blank line, is fine, and so is a wrapped
  line. A `Divergence:` line above a later heading doesn't count: that is how a
  correction's new section stays unsettled until its own line is written. Until
  2026-11-24 the line had to be the report's last paragraph, and reports that put a
  bulleted list after `Divergence:` sat unsettled until the ten-minute fallback (exit 2).
  When a wait still exits 2 on a finished report, read the completion report by hand
  rather than resending.
- **A correction turn needs the marker** (its new section's heading, such as
  `"Correction 1"`): the wait needs the new section to exist before the old turn's
  `Divergence:` line stops counting, so without the marker it can settle on the old
  turn before the background agent has appended anything.
- Background shells load the interactive profile: use `test -f`, never `ls`,
  to check a path there, because an alias can swap `ls` for a tool that rejects
  the argument and kills the wait before it starts.
- **A background agent that backgrounds its own long check may not resume.** A background agent can
  start a long run (a full mutant search, a test suite) as a background shell,
  end its turn and promise to finish "once it reports". Put "run long checks in
  the foreground" in every assignment. When it happens anyway (`rex_wait.sh` exits
  2), send the same session one short continuation prompt to finish from the
  run's output. That is not a correction pass.
- A background agent blocked on a permission or question shows it in `capture`. Answer
  only what the governing plan already settles, through `rex send` and
  `rex send-key`; anything new goes to Bryan.
- **"Read outside the working directories."** (Claude background agents only.) The
  issue's state directory sits outside the worktree, so Claude asks before
  reading the completion report it must append to. Choose the narrowest yes, "Yes, but
  ask again next time" (`down down down enter`, after `capture` shows the path
  is the state directory). Never "keep allowing any reads". Pi doesn't ask.

## A second turn (correction)

One turn at a time per session: only after settlement, rerun the capacity
check, then type into the same pane and submit. Clear the input line first
(`"$REX" send-key -s "$REX_SESSION" -b <block> ctrl+u`): leftover text would
join the prompt. Afterwards, read the newest `user` message in the transcript
and check it is exactly your prompt.

Send a one-line pointer to the correction file, never the file's text. A long
multi-line `rex send` arrives truncated: on 2026-11-06 a 1.9 KB correction
reached a background agent as only its last ~500 characters, and the background agent (rightly) asked
for a resend instead of acting.

```sh
"$REX" send -s "$REX_SESSION" -b <block> "Read $S/<workstream>-correction-1-prompt.md in full and carry out Correction 1 exactly as written there."
"$REX" send-key -s "$REX_SESSION" -b <block> enter
```

Confirm a new `user` record in the transcript that it was accepted before you
report it delivered; `capture` can still show an empty prompt for several
seconds after a good submit. Then arm the watch with the marker (`watch_background_agent` from Pi), before ending your turn.

## Close

When no concrete next turn remains, quit Pi and close only the recorded
pane, then confirm it is gone:

```sh
"$REX" send -s "$REX_SESSION" -b <block> "/quit"
"$REX" send-key -s "$REX_SESSION" -b <block> enter
"$REX" block close -s "$REX_SESSION" <block>
"$REX" block ls -s "$REX_SESSION" --json | grep -c <block>    # expect 0
```

Mark the identity record `closed: true` with the end capacity. The transcript
stays at its path; `pi --session <UUID>` in the worktree, with the background agent's
subscription, reopens it later. (A Claude background agent exits with `/exit` instead.)

## What this does not give you

No turn lease or journal: two orchestrators could both type into the pane, so
one orchestrator owns each background agent and nothing else sends to it. No automatic
identity revalidation: before every `send`, `"$REX" block inspect <block>`
must still show the recorded label and tab.

## Failure rules

- Never edit an identity record to make a mismatch pass.
- Never switch providers when capacity or identity fails.
- Never target a globally focused pane when the caller's `REX_BLOCK` is
  unavailable.
- Preserve partial repository bytes before closing a capacity-blocked background agent.
- Ask Bryan before answering a blocked approval or question that the governing
  plan doesn't already settle.
