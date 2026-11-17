# dot-agents

Single source of truth for Bryan's **personal agent skills**, shared across the
five coding agents he runs: **Claude Code**, **Pi**, **OpenCode**, **Hermes**, and **Codex**.

## How it works

`skills/` is a flat pool — one directory per skill, one canonical copy. Each tool
gets a *curated subset* via per-skill symlinks created by
[`../scripts/reconcile-agent-skills.sh`](../scripts/reconcile-agent-skills.sh):

```
~/.agents/skills/<name>         -> dot-agents/skills/<name>  # Codex
~/.claude/skills/<name>          -> dot-agents/skills/<name>
~/.config/opencode/skills/<name> -> dot-agents/skills/<name>
~/.pi/agent/skills/<name>        -> dot-agents/skills/<name>
~/.hermes/skills/personal/<name> -> dot-agents/skills/<name>
```

The reconciler is idempotent and has two modes: `--check` reports the plan
without touching anything; `--apply` links the curated skills, prunes symlinks
that are no longer curated, and **never touches** anything that isn't a symlink
into this pool — so Claude's own skill entries (such as the claude.ai-synced `synced/` directory) and
Omarchy's packaged skill links (`omarchy`, `diagnose-crash`) are left alone.
The legacy `setup-platform-configs.sh` delegates its agent-skill step to this
reconciler, and `scripts/setup-omarchy.sh` invokes it as one payload in the
additive Omarchy setup.

Why a flat pool instead of per-tool subfolders: most skills are wanted by 2+ tools.
Subfolders would force either duplicate copies or a `common/` + cross-folder symlink
layer. A flat pool keeps one copy of each skill and makes "give tool X skill Y" a
one-line change to a curation array.

## Curation

Not every tool gets every skill. Pi gets the common core plus the workflows
made to run from it, a set that grows as Pi becomes the primary harness
(dotfiles-workspace#34); no shared desk skill needs a Hermes session. Pi also
reads Codex's `~/.agents/skills`, so Codex-set skills reach Pi without a
`PI_SKILLS` entry; Pi skips a second link to the same pool file. Hermes gets adapted personal workflows but keeps its
bundled/local `obsidian` and `vault-pkm` implementations, so those names are
intentionally excluded from its pool links. Personal knowledge lives in the
`~/second-brain` Markdown vault (Forgejo Git), written through `vault-pkm` like
any other vault, with `knowledge-capture` routing resting-point captures between
it and project vaults. `apple-notes-pkm` (2026-10-31) and `vault-capture` are
retired and removed; the reconciler prunes their stale links, as it does for the
local `code-review` and the six skills adapted from Matt Pocock's (2026-11-16,
see below). No pool skill takes a name one of his promoted skills holds.

The **single authoritative curation source** is the set of `*_SKILLS` Bash arrays
in [`../scripts/reconcile-agent-skills.sh`](../scripts/reconcile-agent-skills.sh):
`COMMON_SKILLS` (the core shared by Claude, OpenCode, Pi, and Codex) plus per-tool
additions, and Hermes's independent list. A skill existing in the pool does not
mean every tool receives it. This README intentionally does not mirror the
membership lists or counts — read the arrays.

Codex receives the portable coding, issue delivery, review, knowledge, and
planning workflows. Its user links use `~/.agents/skills`, the supported local
[Codex discovery path](https://developers.openai.com/codex/skills); Codex follows
symlinked skill folders. Existing `~/.codex/skills` contents (including bundled
`.system` skills) stay untouched. These local links do not install skills into
native/cloud catalogs or prove that a running desktop task has refreshed them.

The Rex-supervised `coding-agent-handoff-supervision` and `multiagent-pr-review`
run from a Pi or Hermes root and are excluded from Codex. Specialist `dx-target`, `dx-preview`, `gamedev`,
`weekly-planning`, `sprint-deliverable-update`,
`sync-hold-branch`, and `find-skills` remain outside its initial curation.
Capability-dependent operations still require the tools and authorization
specified by each skill; installing a skill does not grant those capabilities.

## Adding or re-curating a skill

1. Create `skills/<name>/SKILL.md` (plus optional `references/`, `templates/`).
2. Add `<name>` to the relevant `*_SKILLS` array(s) in
   `scripts/reconcile-agent-skills.sh` — or to `COMMON_SKILLS` to give it to
   Claude, OpenCode, Pi, and Codex at once.
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
upstream files worth watching. Each adapted `SKILL.md` carries a one-line
pointer to the ledger rather than repeating its own adaptation history.

Matt Pocock's skills ([`upstreams/mattpocock-skills.json`](upstreams/mattpocock-skills.json))
are not adapted: every harness loads them as written from one checkout.
[`../scripts/reconcile-mattpocock-skills.sh`](../scripts/reconcile-mattpocock-skills.sh)
keeps it at the ledger's `commit` in `~/.local/share/mattpocock-skills`, lists
its promoted `skills/engineering` and `skills/productivity` directories in Pi's
settings, and links each promoted skill into `~/.claude/skills` and
`~/.config/opencode/skills` under its own name. Those links are not pool links:
this pool's reconciler never touches them, and his script owns only links into
the checkout. In Pi his copy of a name wins once no copy of that name is in
`~/.agents/skills` or `~/.pi/agent/skills` (started from `~`, a copy there
wins), so the reconciler warns about one.

On 2026-11-16 the pool's adapted copies retired in favour of his: `grilling`,
`wayfinder`, `tdd`, `diagnosing-bugs`, `codebase-architecture` (his
`codebase-design` and `improve-codebase-architecture`) and `guided-learning`
(his `teach`), after the local `code-review`. What stays local sits on top of
or under his skills: `pr-self-review`'s review contract
(`pr-self-review/references/review-contract.md`), `teammate-pr-review` (his
`code-review` plus Risk, Ponytail and Bryan's drafting rules), and the Forgejo
adapter under [`forgejo-tracker/`](forgejo-tracker/), which his `wayfinder`
reaches through a workspace's tracker doc and the `forgejo-map` command.

The pi-bots job `mattpocock-skill-watch` advances Matt Pocock's pin by itself
(Bryan, 2026-11-16). Each week, when upstream is ahead, it moves `commit`,
`version` and `verifiedOn` in the ledger, runs the reconciler, checks that Pi
loads every promoted skill from the checkout, commits the ledger alone to
`main` and announces the advance in Matrix with the rollback. A failed load
puts the old pin back. Every other source's pin is still a reviewed change.

Every other source is adapted, and its pin is a reviewed change:
[pstack-claude](upstreams/pstack-claude.json) (`black-box-verification`) and
[Ponytail](upstreams/ponytail.json), the plugin the review contract's Ponytail
pass (also called the simplicity review) is named after and adapted from. The
pi-bots scheduled job `adapted-skill-watch` reads every record whose
`updatePolicy.autoApply` is false, each of which must name it as `monitor`.
Weekly, for each source whose watched files changed since the pin, Steve posts
in `studio-alerts` how many commits behind the pin is and which watched files
changed; it posts nothing otherwise, and never edits a record. A refresh then
reads each change, records it under `refreshes` as accepted or rejected with a
reason, adopts what is accepted with the smallest edit, and advances `commit`,
`version` and `verifiedOn`.

## Notes

- Hermes's `personal/` entries are ordinary symlinks into this repository. A
  foreground skill edit can therefore modify the canonical pool; review diffs
  before committing. Hermes's autonomous curator does not own these files.
- Some skills carry **local-only, gitignored** content (e.g. `voice-bryan`'s
  verbatim corpus under `references/`). It lives in the pool dir on each machine but
  is never committed; a fresh clone starts without it.
- This pool replaced two former per-tool copies (`dot-claude/skills/`,
  `dot-config/opencode/skills/`) that drifted out of sync.
