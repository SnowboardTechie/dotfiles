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
4. **Adapt** it into Claude Code skill format if the user wants to add it

Claude Code skills live at one of:
- `~/.claude/skills/{skill-name}/SKILL.md` (user-level, available everywhere)
- `{project}/.claude/skills/{skill-name}/SKILL.md` (project-level)
- Bundled inside a plugin's `skills/` directory

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

If the user wants to add the skill, adapt it:

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

### Create the skill:

```bash
mkdir -p ~/.claude/skills/{skill-name}
# Write adapted content to SKILL.md
```

---

## Step 4: Verify Installation

After creating the skill file, confirm it exists using the **Read** tool:

```
Read(file_path="~/.claude/skills/{skill-name}/SKILL.md")
```

If Read returns the content, installation succeeded. The skill becomes available to Claude Code automatically via description-based triggering — no config needed. Start a new session to pick it up.

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

**User:** "Find me a skill for systematic debugging"

**Agent:**

1. Search: `curl -s "https://skills.sh/api/search?q=debugging&limit=10"`
2. Find: `obra/superpowers/systematic-debugging` (9.0K installs)
3. Fetch: `curl -s "https://raw.githubusercontent.com/obra/superpowers/main/skills/systematic-debugging/SKILL.md"`
4. Present content to user
5. If user wants it: create `~/.claude/skills/systematic-debugging/SKILL.md` with adapted content
