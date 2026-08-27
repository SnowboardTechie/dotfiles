# dot-agents

Single source of truth for Bryan's **personal agent skills**, shared across the
four coding agents he runs: **Claude Code**, **Pi**, **OpenCode**, and **Hermes**.

## How it works

`skills/` is a flat pool — one directory per skill, one canonical copy. Each tool
gets a *curated subset* via per-skill symlinks created by
[`../scripts/reconcile-agent-skills.sh`](../scripts/reconcile-agent-skills.sh):

```
~/.claude/skills/<name>          -> dot-agents/skills/<name>
~/.config/opencode/skills/<name> -> dot-agents/skills/<name>
~/.pi/agent/skills/<name>        -> dot-agents/skills/<name>
~/.hermes/skills/personal/<name> -> dot-agents/skills/<name>
```

The reconciler is idempotent and has two modes: `--check` reports the plan
without touching anything; `--apply` links the curated skills, prunes symlinks
that are no longer curated, and **never touches** anything that isn't a symlink
into this pool — so Claude's plugin skills (`gsd-*`, `superpowers`, etc.) and
Omarchy's packaged skill links (`omarchy`, `diagnose-crash`) are left alone.
The legacy `setup-platform-configs.sh` delegates its agent-skill step to this
reconciler, and `scripts/setup-omarchy.sh` invokes it as one payload in the
additive Omarchy setup.

Why a flat pool instead of per-tool subfolders: most skills are wanted by 2+ tools.
Subfolders would force either duplicate copies or a `common/` + cross-folder symlink
layer. A flat pool keeps one copy of each skill and makes "give tool X skill Y" a
one-line change to a curation array.

## Curation

Not every tool gets every skill. Pi is kept lean (the common core only). Hermes
gets adapted personal workflows but keeps its bundled/local `obsidian` and
`vault-pkm` implementations, so those names are intentionally excluded from its
pool links.

The **single authoritative curation source** is the set of `*_SKILLS` Bash arrays
in [`../scripts/reconcile-agent-skills.sh`](../scripts/reconcile-agent-skills.sh):
`COMMON_SKILLS` (the core shared by Claude, OpenCode, and Pi) plus per-tool
additions, and Hermes's independent list. A skill existing in the pool does not
mean every tool receives it. This README intentionally does not mirror the
membership lists or counts — read the arrays.

## Adding or re-curating a skill

1. Create `skills/<name>/SKILL.md` (plus optional `references/`, `templates/`).
2. Add `<name>` to the relevant `*_SKILLS` array(s) in
   `scripts/reconcile-agent-skills.sh` — or to `COMMON_SKILLS` to give it to
   Claude, OpenCode, and Pi at once.
3. Run `./scripts/reconcile-agent-skills.sh --check`, review the plan, then
   re-run with `--apply` to (re)build the symlinks.

To pull a skill from a tool, drop it from that tool's array and re-run `--apply`
— the prune step removes the now-stale symlink.

## Writing a skill that actually gets loaded

A skill body is a **context pointer**: it earns its place by being loaded at the
right moment, not by containing everything.

**When disclosure fails — when the agent had the reference and did not open it,
or opened the wrong one — sharpen the pointer's trigger wording first.** Say when
to reach for it in the words someone would actually use at that moment, and name
what it decides. Inlining the referenced body is the *last* resort: it grows the
always-loaded surface every future session pays for, and it usually treats a
discoverability problem as a content problem. Inline only after a sharper
trigger has been tried and still missed.

Corollary: a reference nothing points at clearly is not a reference, it is dead
weight. Delete it or give it a real trigger.

## Upstream adaptations

Skills adapted from an external source keep a pinned provenance record under
[`upstreams/`](upstreams/): the upstream repository and commit, the license, one
entry per adaptation mapping upstream paths to canonical local paths, what was
changed and why, which upstream rules were accepted or rejected, and the list of
upstream files worth watching. Updates are **detected**, never auto-applied;
advancing a pin is a human decision.

Each adapted `SKILL.md` carries a one-line pointer to the ledger rather than
repeating its own adaptation history.

## Notes

- Hermes's `personal/` entries are ordinary symlinks into this repository. A
  foreground skill edit can therefore modify the canonical pool; review diffs
  before committing. Hermes's autonomous curator does not own these files.
- Some skills carry **local-only, gitignored** content (e.g. `voice-bryan`'s
  verbatim corpus under `references/`). It lives in the pool dir on each machine but
  is never committed; a fresh clone starts without it.
- This pool replaced two former per-tool copies (`dot-claude/skills/`,
  `dot-config/opencode/skills/`) that drifted out of sync.
