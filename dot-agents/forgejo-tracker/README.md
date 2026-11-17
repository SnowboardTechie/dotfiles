# Forgejo templates for Matt Pocock's skills

The three files his setup skill (`setup-matt-pocock-skills`) writes under `docs/agents/`, for a workspace whose issues
live on Forgejo. A workspace copies each one there, replaces `<owner>/<repo>`, `<owner>`, `<repo>` and `<host>`, and
points to all three from the `## Agent skills` block in its `AGENTS.md`:

- `issue-tracker-forgejo.md` → `docs/agents/issue-tracker.md`: `tea` and `tea api` for issues, labels, comments,
  native blocking between ordinary issues and the PR triage surface, in the shape of his GitHub template
  (`skills/engineering/setup-matt-pocock-skills/issue-tracker-github.md`). Its **Wayfinding operations** route his
  `wayfinder` to the `forgejo-map` command (`dot-agents/bin/forgejo-map`, linked onto PATH by
  `scripts/reconcile-agent-commands.sh`).
- `triage-labels.md` → `docs/agents/triage-labels.md`: his five triage roles, plus the two category labels `triage`
  uses, and how to create them on Forgejo. `loop-issue` builds whatever carries the literal `ready-for-agent` label,
  so mapping that role to `ready-for-agent` makes publishing approval to build; map it to another label anywhere
  that isn't wanted.
- `domain.md` → `docs/agents/domain.md`: his single-context default, `GLOSSARY.md` and `docs/adr/` at the workspace
  root.

Every command in them was run against a private scratch tracker on 2026-11-16 by headless Pi sessions following his
`wayfinder`, `to-spec`, `to-tickets` and `triage` as written.
