---
name: find-skills
description: Search skills.sh for community agent skills. Use when the user wants to find, browse, or add skills from the open skills ecosystem. Fetches skill content from GitHub for manual review and adaptation into Claude Code skill format.
---

# Find Skills

Search the [skills.sh](https://skills.sh) open skills ecosystem and fetch skill content for manual review and adaptation into Claude Code skills.

## When to Use This Skill

- User says "find a skill for X" or "is there a skill for X"
- User asks about extending agent capabilities for a specific domain
- User wants to browse community skills for inspiration
- User mentions skills.sh or wants to search for agent skills

## Important Context

**We do NOT use `npx skills add`.** That CLI has opinions about directory layout that may not match how you organize Claude Code skills.

Instead, we:

1. **Search** skills.sh via their API
2. **Fetch** the raw `SKILL.md` from GitHub
3. **Present** the content for the user to review
4. **Adapt** it into the canonical pool if the user wants to keep it

**Adopted skills are authored in the canonical pool, never written straight into
a runtime directory.** `~/.claude/skills/`, `~/.config/opencode/skills/`, and
`~/.hermes/skills/personal/` are *outputs*: they hold per-skill symlinks that
`scripts/reconcile-agent-skills.sh` creates from `dot-agents/skills/`. A file
written directly into one of them is unmanaged — untracked, absent on every
other machine, invisible to the curation arrays, and liable to be pruned or to
shadow a pooled skill of the same name.

So an adoption lands in three places, all of them in the repository:

| What | Where |
|---|---|
| The adapted skill | `dot-agents/skills/{name}/SKILL.md` |
| Its upstream provenance | `dot-agents/upstreams/{source}.json` |
| Which runtimes get it | the `*_SKILLS` arrays in `scripts/reconcile-agent-skills.sh` |

---

## Step 1: Search for Skills

Use the skills.sh search API:

```bash
curl -s "https://skills.sh/api/search?q={query}&limit=10" | jq '.skills[] | {name, id, installs, source}'
```

**Response shape:**

```json
{
  "query": "react",
  "searchType": "fuzzy",
  "skills": [
    {
      "id": "vercel-labs/agent-skills/vercel-react-best-practices",
      "skillId": "vercel-react-best-practices",
      "name": "vercel-react-best-practices",
      "installs": 120153,
      "source": "vercel-labs/agent-skills"
    }
  ],
  "count": 5,
  "duration_ms": 14
}
```

Present results as a table:

```
| # | Skill | Source | Installs |
|---|-------|--------|----------|
| 1 | vercel-react-best-practices | vercel-labs/agent-skills | 120.1K |
| 2 | ... | ... | ... |
```

Include a link for each: `https://skills.sh/{id}`

---

## Step 2: Fetch Skill Content

Once the user picks a skill, fetch the raw SKILL.md from GitHub.

**Skills live in GitHub repos** under a `skills/` directory:

```
{owner}/{repo}/skills/{skill-name}/SKILL.md
```

Fetch with GitHub CLI:

```bash
gh api repos/{owner}/{repo}/contents/skills/{skill-name}/SKILL.md --jq '.content' | base64 -d
```

Or with curl (raw content):

```bash
curl -s "https://raw.githubusercontent.com/{owner}/{repo}/main/skills/{skill-name}/SKILL.md"
```

**If the skill has additional files** (scripts, references), list them:

```bash
gh api repos/{owner}/{repo}/contents/skills/{skill-name} --jq '.[].name'
```

Present the full SKILL.md content to the user for review.

---

## Step 3: Adapt to Claude Code Format

If the user wants to add the skill, **delegate the authoring to `superpowers:writing-skills`** (the `Skill` tool) rather than hand-trimming the file. That skill owns the skill-authoring discipline — what belongs in a good `SKILL.md`, how to structure it, and how to confirm it actually works. Hand it the fetched content plus the skills.sh→Claude-Code input cleanups below; it produces the final skill.

The cleanups below are *this* skill's domain knowledge (how skills.sh format differs from Claude Code), so supply them as inputs to `writing-skills`:

### Skills.sh format (input):

```markdown
---
name: skill-name
description: What this skill does
license: MIT
metadata:
  author: someone
  version: "1.0"
compatibility: Optional requirements
allowed-tools: Bash(git:*) Read
---

# Skill Title

Instructions...
```

### Claude Code format (output):

```markdown
---
name: skill-name
description: What this skill does
---

# Skill Title

Instructions adapted for your workflow...
```

**Key adaptations:**

1. Keep only `name` and `description` in frontmatter (Claude Code skills use just these two fields)
2. Remove any `npx skills` commands or install references
3. Remove cursor-specific paths (`.cursor/rules/`, etc.) if present
4. Adjust file paths to match your conventions
5. Keep the actual procedural knowledge — that's the valuable part

### Create the skill in the canonical pool

```bash
mkdir -p dot-agents/skills/{skill-name}
# Write the adapted content to dot-agents/skills/{skill-name}/SKILL.md
```

### Record its provenance

An adapted copy without a pin is a silent fork. Add an entry to
`dot-agents/upstreams/{source}.json` — or create that ledger if the source is
new — carrying the upstream repository and **exact commit**, the license and
where it is retained, the upstream paths this adaptation came from, the local
paths, what was changed locally and why, which upstream rules were accepted or
rejected, and the upstream files worth watching. See
[`dot-agents/README.md`](../../README.md) → *Upstream adaptations*.

### Curate the runtimes

Add the name to the `*_SKILLS` array(s) in
`scripts/reconcile-agent-skills.sh` for the runtimes that should receive it.
Curating nothing means nothing loads it. Pi is deliberately lean — do not add to
it without a reason.

---

## Step 4: Verify through the reconciler

Existence in the pool is not availability. Distribution is what makes a skill
load, and the reconciler owns it:

```bash
./scripts/reconcile-agent-skills.sh --check     # review the planned links
./scripts/reconcile-agent-skills.sh --apply     # after the plan looks right
```

`--check` must show `would create link: {skill-name}` for each intended runtime.
If it says `WARNING: skill '{skill-name}' not in pool`, the file is in the wrong
place. If it says nothing about the skill at all, it is not curated.

Then confirm the link resolves back into the pool, and start a fresh session so
the runtime rescans:

```bash
readlink ~/.claude/skills/{skill-name}      # -> …/dot-agents/skills/{skill-name}
```

A skill is done when the link resolves into the pool **and** the trigger
actually fires in a fresh session — not when the file exists.

---

## Search Tips

| Category     | Good Queries                                       |
| ------------ | -------------------------------------------------- |
| Web Dev      | `react`, `nextjs`, `typescript`, `css`, `tailwind` |
| Testing      | `testing`, `jest`, `playwright`, `e2e`, `cypress`  |
| DevOps       | `deploy`, `docker`, `kubernetes`, `ci-cd`          |
| Docs         | `docs`, `readme`, `changelog`, `api-docs`          |
| Code Quality | `review`, `lint`, `refactor`, `best-practices`     |
| Design       | `ui`, `ux`, `design-system`, `accessibility`       |
| Productivity | `workflow`, `automation`, `git`                    |

**Popular skill sources:**

- `vercel-labs/agent-skills` - React, Next.js, web development
- `openai/agent-skills` - General purpose (PDF, DOCX, design, testing)
- `obra/superpowers` - Agent workflow patterns (brainstorming, debugging, TDD)
- `expo/skills` - React Native / Expo

**Browse the full leaderboard:** https://skills.sh/

---

## When No Skills Are Found

If the search returns no results:

1. Try alternative keywords (e.g., "deploy" vs "deployment" vs "ci-cd")
2. Try broader terms (e.g., "testing" instead of "cypress e2e testing")
3. If nothing relevant exists, let the user know and offer to help directly
4. Suggest they could create their own skill from scratch

---

## Example Workflow

**User:** "Find me a skill for reviewing accessibility"

**Agent:**

1. Search: `curl -s "https://skills.sh/api/search?q=accessibility&limit=10"`
2. Find: `someorg/some-pack/a11y-review` (9.0K installs)
3. Fetch: `curl -s "https://raw.githubusercontent.com/someorg/some-pack/main/skills/a11y-review/SKILL.md"`
4. Present content to user
5. If user wants it: adapt it into `dot-agents/skills/a11y-review/`, record its upstream
   provenance under `dot-agents/upstreams/`, and curate it in the reconciler arrays —
   never write an unmanaged copy straight into `~/.claude/skills/`
