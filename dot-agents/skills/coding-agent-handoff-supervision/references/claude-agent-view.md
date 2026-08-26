# Claude Agent View Fallback

## When to use it

Use this path when the parent is outside Herdr, Herdr cannot safely resolve or
split the caller pane, or Bryan explicitly requests background-only work. Do not
start this fallback after a Herdr worker was successfully created.

## Dispatch a background worker

Use a positional prompt so Claude creates an attachable background session:

```sh
claude --bg --permission-mode auto --model opus --effort high \
  --name "Short task name" "<concept brief>"
```

Do not combine `--bg` with `-p`. Preserve an explicitly requested model, effort,
or safer permission mode. Verify immediately:

```sh
claude agents --json --all
```

Check the returned session ID, intended repository `cwd`, display name, and
`working` state. Do not treat a command returning successfully as proof that the
right worker exists.

## Monitoring contract

Claude's background supervisor and parent-runtime notifications are separate.
If the parent must report completion, start a tracked watcher supported by the
current runtime or inspect at explicit named gates:

```sh
claude agents --json --all
claude logs <id>
```

A worker in `done` or `blocked` has finished its current turn. Inspect its actual
branch before accepting the result.

## Continue the original session

Do not use `claude --resume <id> --bg "follow-up"` when preserving the original
Agent View row matters; it creates another row. Attach the original session in a
monitorable terminal and send the correction there:

```sh
tmux new-session -d -s claude-followup -x 160 -y 50
tmux send-keys -t claude-followup \
  'cd <worker-cwd> && claude attach <id>' Enter
```

After the prompt appears, paste the follow-up through a tmux buffer rather than
key-by-key input, then verify the original ID is `working` again. Do not submit
text already sitting in the prompt box unless the user explicitly sent it;
Claude may have generated it as an automatic suggestion.

## Cleanup

After parent acceptance and publication:

```sh
claude stop <id>
claude rm <id>
```

Verify the worker row and worktree are gone before deleting a merged remote
branch. Kill only helper tmux sessions created by the parent.
