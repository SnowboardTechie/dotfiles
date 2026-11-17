# pstack's models on Pi, with a verifier from another family

Read this when you set up the Pi agent directory pstack runs in, or change which
models its roles use. Everything here was run on 2026-11-16 in the trial agent
directory (`~/.pi/pstack-trial`), with Pi 1.5.2, the pstack port at
`a12b04786023e762f12f5de7bb5fafb8c23f8c36`, pi-claude-code at `d5b5e04` and
Claude Code 2.1.322.

The verifier that did not write the code runs on OpenCode Go, not on Claude and
not on Codex (Bryan's Codex subscription is ending).

## The sheet

pstack reads `pstack-models.md` in the Pi agent directory. These are the lines
that ran:

```text
pi models: opus=claude-code/claude-opus-5-5, fable=claude-code/claude-fable-5-2, sonnet=claude-code/claude-sonnet-5-5, haiku=claude-code/claude-haiku-5-5

interrogate reviewers: opus, opencode-go/kimi-k3.1-pro
arena runners: opus, opencode-go/kimi-k3.1-pro
architect runners: opus, opencode-go/kimi-k3.1-pro
arena cross-judge pool: opencode-go/kimi-k3.1-pro, opencode-go/glm-5.3
swarm workers: opus
default effort: session
session hook: off
```

The other role lines keep `/setup-pstack`'s defaults (`opus`, with `fable` for
the strongest judgment and `sonnet` for features and refactoring). A full
`provider/id` in a role line is passed through unchanged by the port's `agent`
tool. Panels are two wide, one Claude and one OpenCode Go, sized for one
machine. Arena's cross-judge takes only a family other than the orchestrator's, so
its pool lists only OpenCode Go models.

Proven:

- Each mapped Claude model (`opus`, `fable`, `sonnet`, `haiku` above) and
  `opencode-go/kimi-k3.1-pro` and `opencode-go/glm-5.3` ran two tool calls and
  answered in `pi --mode rpc`, the mode the port starts background agents in.
- A headless `pi -p` on Claude started a background agent through the port's `agent`
  tool with `model: "opencode-go/kimi-k3.1-pro"`. It read a file and answered
  correctly; its transcript records `opencode-go` / `kimi-k3.1-pro` on every
  turn.
- `/skill:interrogate` from a headless `pi -p`, on a two-file diff in a scratch
  repository with an off-by-one bug planted, ran both reviewers in their own
  worktrees. Each reported the bug with a failing test as proof, the orchestrator
  reran both proofs, and merged them into one finding.

Not proven: a reviewer from the other family catching a bug Claude missed. On
this diff both found the same one. Kimi was picked over the other OpenCode Go
models without a comparison between them.

## What failed, and why

`sonnet` mapped to `claude-code/claude-sonnet-5` fails as a background agent with:

```text
Incomplete Claude Code upstream response (status 400, capture incomplete,
upstream said: messages.1.output_config: Extra inputs are not permitted)
```

It is not pstack. Plain `pi --mode rpc --model claude-code/claude-sonnet-5`,
with no pstack involved, failed the same way on the request after the first tool
call in three runs of three. The same model passed under `pi -p` in five tool-using runs.
pi-claude-code replays the conversation's opening system messages from the
first response, and those carry an `output_config` field. Claude Code's
`claude-sonnet-5` answers as Sonnet 5.5 (the native response says
`claude-sonnet-5-5`). Asked for `claude-sonnet-5-5` directly, the same replay is
accepted. The likely cause is the mismatch between the requested and the
answering model on the replay; that, and why `-p` survives where RPC doesn't,
were not traced further. It belongs upstream in pi-claude-code.

Fix: map `sonnet=claude-code/claude-sonnet-5-5`. Separately,
`claude-sonnet-5` with `--thinking off` fails with a different 400 ("send
thinking type between_tools instead"); `claude-sonnet-5-5` takes `off`.

## The OpenCode key in a headless run

Pi lists no `opencode-go` models until it has a key. pi-bots jobs export
`OPENCODE_API_KEY` from `~/.secrets/opencode-api-key` into the background agent's
environment. For pstack, put a command in the agent directory's `auth.json`
instead:

```json
{
  "opencode-go": {
    "type": "api_key",
    "key": "!cat \"$HOME/.secrets/opencode-api-key\""
  }
}
```

Keep `auth.json` mode 600. Pi runs the command when the key is first needed and
keeps the output in memory for the process. Background agents are their own `pi` process
reading the same agent directory, so each resolves the key itself; nothing is
passed on a command line or in the environment. Checked:

- A model on `opencode-go`, asked to run `env | grep -i opencode` in its tool
  shell, saw only `PI_PROVIDER=opencode-go`.
- A search of every session and background agent transcript in the trial directory for
  the key's opening characters found none.

Never `export OPENCODE_API_KEY` in the shell that starts a pstack run: the
model's `bash` tool inherits that environment, and the key is then one `env`
away from a transcript.
