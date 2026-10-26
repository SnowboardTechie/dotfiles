---
name: next-session
description: Use when Bryan asks to launch the next session you suggested. Starts it in a Herdr split beside this one, with the prompt as its first turn, so he can close this session and continue there without copy-paste.
---

# Next session

Many sessions end by suggesting what Bryan should say to the next agent. A
Wayfinder ticket, for example, names the next decision on the map. This skill
does that handoff for him: it splits this session's Herdr pane to the right
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
- Only from a Hermes CLI session inside Herdr. If the helper can't find this
  session's pane, give him the prompt to paste and say why. That is a normal
  outcome, not a failure to work around.

## The prompt

Use the prompt you suggested, unchanged in meaning. It is a pointer, not a copy:
name the map, ticket, plan or note by title and link, plus anything that doesn't
autoload. Don't restate what the record already says.

Write it to a file in session scratch (`$TMPDIR`), never into a repository or the
vault. The file is read once, verbatim, at startup: nothing in it is
shell-interpreted.

## Launch

```sh
S=~/.hermes/skills/personal/next-session/scripts/launch_next_session.py
python3 "$S" launch --prompt-file "$TMPDIR/next-session-prompt.md" --name <name> --dry-run
python3 "$S" launch --prompt-file "$TMPDIR/next-session-prompt.md" --name <name>
```

- `--name` is a short Herdr agent name (`[a-z][a-z0-9_-]{0,31}`) unique among
  live agents, e.g. `wf-182`.
- The working directory defaults to this pane's. Pass `--cwd` only when the next
  session belongs elsewhere.
- `--skills a,b` preloads skills when the prompt names one to use.
- Focus stays in this pane so Bryan can read the final report. Pass `--focus`
  only if he asks.

The helper refuses unless exactly one Hermes pane runs on this session's TTY.
It finds that pane from Hermes's own TTY record and Herdr's process info, never
from UI focus. If the split succeeds but the start fails, it leaves the new pane
open and prints the command to run there by hand. Don't retry into a second pane.

## Finish

Report the new pane, its agent name and the prompt it started with, then end the
turn. Never close this pane or the new one: closing this session is Bryan's
step. A launched session isn't evidence that its work happened. It only shows
the first turn was submitted. Don't ask Bryan to check that the new session
picked up its prompt: an `idle` status right after launch is normal, and the
start has proven reliable.
