---
name: next-session
description: Use when Bryan asks to launch the next session you suggested. Starts it in a Rex split beside this one, with the prompt as its first turn, so he can close this session and continue there without copy-paste.
---

# Next session

Many sessions end by suggesting what Bryan should say to the next agent. A
Wayfinder ticket, for example, names the next decision on the map. This skill
does that handoff for him: it splits this session's Rex pane to the right
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
- Only from a Hermes CLI session inside Rex. If the helper can't find this
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

- `--name` is a short name (`[a-z][a-z0-9_-]{0,31}`), e.g. `wf-182`. It labels
  the new pane.
- The working directory defaults to this pane's. Pass `--cwd` only when the next
  session belongs elsewhere.
- `--skills a,b` preloads skills when the prompt names one to use.
- Focus stays in this pane so Bryan can read the final report. Pass `--focus`
  only if he asks.

The helper finds the host from the pane's own environment (`dot-agents/lib/terminal_host.py`):
Rex when `REX_BLOCK` and `REX_SESSION` are set. Outside Rex it refuses; give
Bryan the prompt instead.

**Under the gateway, the helper finds the pane itself.** When the tool's commands
run under the Hermes gateway (`$PPID` is `hermes ... gateway run`, with no TTY),
their environment has no `REX_*` variables, even though this
session's chat runs in a pane. The helper then takes this session's TTY from
Hermes's own record, finds the one Hermes process on it, and adopts that
process's `REX_*` values, read exactly from the kernel. `host_env_from`
in its output names the TTY and pid. Don't export variables by hand first.

If it still refuses, its `lookup` field says why (no TTY record, several Hermes
processes on the TTY, or a process outside Rex); give Bryan the prompt
then. Never scrape `ps eww` to fill the variables in: it joins variables with
spaces, and Rex's `REX_BIN_DIR` contains spaces ("Application Support",
"Rex Server.app"), so a hand-parsed value silently breaks the launch. To inspect
a process's host variables, run `python3 dot-agents/lib/terminal_host.py <pid>`
from the dotfiles repo.

The caller is `REX_BLOCK`, which must still exist on the server; it is never
found from UI focus. The new pane is a shell with the `hermes chat` command
typed in, labelled with `--name`. Launch counts as done once a Hermes process is
that pane's foreground. That proves Hermes started, not that the first turn
finished.

If the split succeeds but the start fails, it leaves the new pane open and prints
the command to run there by hand. Don't retry into a second pane.

## Finish

Report the new pane, its name and the prompt it started with, then end the
turn. Never close this pane or the new one: closing this session is Bryan's
step. A launched session isn't evidence that its work happened. It only shows
the first turn was submitted. Don't ask Bryan to check that the new session
picked up its prompt: the start has proven reliable.
