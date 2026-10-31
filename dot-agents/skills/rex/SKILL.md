---
name: rex
description: Use when in a Rex terminal (REX_BLOCK set) or driving Rex. The rex CLI manages Rex sessions, tabs, panes, commands, terminal output, and connected Rex apps.
---

# Rex

Rex's own `rex skill setup` installs this skill only for Claude Code, Codex,
OpenCode, and Pi. This copy gives the same pointer to agents Rex does not
support (Hermes). Like Rex's version, it holds no guide of its own: the guide
comes from the installed Rex CLI, so it always matches that version.

## Find the rex binary

The Rex app does not put `rex` on PATH. Inside a Rex terminal it exports the
directory as `REX_BIN_DIR`. The zsh config appends it to PATH, but Hermes's
terminal tool runs under the gateway and does not see that PATH; it gets the
`REX_*` variables through `terminal.client_env_passthrough` in
`~/.hermes/config.yaml`. Resolve the binary like this:

```bash
REX="$(command -v rex || echo "$REX_BIN_DIR/rex")"
```

Outside a Rex terminal, the CLI is still at
`/Applications/Rex Beta.app/Contents/Helpers/Rex Server.rex/Contents/MacOS/rex`.

## Use it

Run `"$REX" __internal skill` and follow the guide it prints.

If that command fails, the installed Rex version predates the guide. Start with
`"$REX" whoami --json`, then use `"$REX" --help` and `"$REX" COMMAND --help`.

Your own location in Rex is in the environment: `REX_SESSION` and `REX_BLOCK`
name this terminal's session and block, and `REX_SERVER` the server socket.
