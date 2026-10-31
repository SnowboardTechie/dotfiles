---
name: next-session
description: Use when Bryan asks to launch the next session you suggested. Starts it in a Herdr or Rex split beside this one, with the prompt as its first turn, so he can close this session and continue there without copy-paste.
---

# Next session

Many sessions end by suggesting what Bryan should say to the next agent. A
Wayfinder ticket, for example, names the next decision on the map. This skill
does that handoff for him: it splits this session's Herdr or Rex pane to the right
(a vertical divider), starts a fresh Hermes session in the new pane, and seeds
it with the suggested prompt as its first turn. Bryan then closes this session
and carries on in the new one.

It hands over the **conversation**, not a worker. The new session is Bryan's to
drive; nothing here supervises it, reads its pane or waits on it. For a
supervised coding worker use `coding-agent-handoff-supervision`; for untracked
implementation slices use `session-handoff`.

## When

- Only when Bryan asks for it ("launch it", "start the next one", "split and
  start it"). Suggesting the prompt is the default ending; launching is his call,
  because the new session starts working (and, on a map, claims a ticket) at once.
- Only from a Hermes CLI session inside Herdr or Rex. If the helper can't find this
  session's pane, give him the prompt to paste and say why. That is a normal
  outcome, not a failure to work around.

## The prompt

Use the prompt you suggested, unchanged in meaning. It is a pointer, not a copy:
name the map, ticket, plan or note by title and link, plus anything that doesn't
autoload. Don't restate what the record already says.

Write it to a file in session scratch (`$TMPDIR`), never into a repository or the
vault. The file is read once, verbatim, at startup: nothing in it is
shell-interpreted.

Give the file a name unique to this launch (e.g. `next-session-<name>.md`), and
read it back before launching. Never launch in the same batch as the write.
Scratch is shared across sessions, so a fixed name can hold an earlier session's
prompt, and a refused or failed write then launches that stale prompt.

## Launch

```sh
S=~/.hermes/skills/personal/next-session/scripts/launch_next_session.py
python3 "$S" launch --prompt-file "$TMPDIR/next-session-<name>.md" --name <name> --dry-run
python3 "$S" launch --prompt-file "$TMPDIR/next-session-<name>.md" --name <name>
```

- `--name` is a short name (`[a-z][a-z0-9_-]{0,31}`), e.g. `wf-182`. In Herdr
  it is the agent name and must be unique among live agents; in Rex it labels
  the new pane.
- The working directory defaults to this pane's. Pass `--cwd` only when the next
  session belongs elsewhere.
- `--skills a,b` preloads skills when the prompt names one to use.
- Focus stays in this pane so Bryan can read the final report. Pass `--focus`
  only if he asks.

The helper picks the host from the pane's own environment (`dot-agents/lib/terminal_host.py`):
Herdr when `HERDR_ENV`/`HERDR_PANE_ID` are set, else Rex when `REX_BLOCK` and
`REX_SESSION` are. Herdr wins because it can run inside a Rex pane. Outside both
it refuses; give Bryan the prompt instead.

**A refusal from the terminal tool doesn't show where the session runs.** When the tool's
commands run under the Hermes gateway (`$PPID` is `hermes ... gateway run`, with
no TTY), its environment has no `REX_*` or `HERDR_*` variables, even though this
session's chat runs in a pane. Before saying the session isn't in a pane, find
this session's `hermes chat` process: `ps eww` on each Hermes process with a
TTY, matching `PWD` to this session's working directory. Read its `REX_SESSION`,
`REX_BLOCK`, `REX_SERVER` and `REX_BIN_DIR` (or its `HERDR_*` variables), export
them, and dry-run again. If more than one process matches, ask Bryan which pane.
Sessions created after `terminal.client_env_passthrough` lists the `REX_*` names
get them directly; `HERDR_*` and older sessions still need this lookup.

- **Herdr:** it refuses unless exactly one Hermes pane runs on this session's
  TTY. It finds that pane from Hermes's own TTY record and Herdr's process info,
  never from UI focus.
- **Rex:** the caller is `REX_BLOCK`, which must still exist on the server. The
  new pane is a shell with the `hermes chat` command typed in, labelled with
  `--name`. Launch counts as done once a Hermes process is that pane's
  foreground. That proves Hermes started, not that the first turn finished.

If the split succeeds but the start fails, it leaves the new pane open and prints
the command to run there by hand. Don't retry into a second pane.

## Finish

Report the new pane, its agent name and the prompt it started with, then end the
turn. Never close this pane or the new one: closing this session is Bryan's
step. A launched session isn't evidence that its work happened. It only shows
the first turn was submitted. Don't ask Bryan to check that the new session
picked up its prompt: an `idle` status right after launch is normal, and the
start has proven reliable.
