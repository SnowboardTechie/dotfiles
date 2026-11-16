# Forgejo tracker doc

`issue-tracker-forgejo.md` is the tracker doc Matt Pocock's skills read for a workspace whose issues live on Forgejo,
written in the shape of his GitHub template (`skills/engineering/setup-matt-pocock-skills/issue-tracker-github.md`).
A workspace copies it to `docs/agents/issue-tracker.md`, replaces `<owner>/<repo>` and `<host>`, and points to it
from the `## Agent skills` block in its `AGENTS.md`. Its **Wayfinding operations** route his `wayfinder` to the
`forgejo-map` command (`dot-agents/bin/forgejo-map`, linked onto PATH by `scripts/reconcile-agent-commands.sh`).
