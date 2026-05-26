# Agent Behavioral Instructions

## Identity & Context

**User:** Bryan Thompson
**Email:** bryan.thompson@agile6.com
**Company:** Agile6
**Role:** Senior Full Stack Engineer
**Working Hours:** 7:30am - 4pm PT
**Timezone:** Pacific

**Current Projects:**
- **Simpler Grants Protocol** — SDK, API, and CLI tools for grants.gov

---

## Obsidian Vault Integration

**Known Vaults:**

| Vault | Path | Purpose |
|-------|------|---------|
| Workday | `~/notes/workday` | Work — Simpler Grants |
| Second Brain | `~/notes/second-brain` | Personal — vehicles, hobbies, learning |
| Burnt Ice | `~/notes/burnt-ice` | Personal — Game development |

### Workday Vault

**Vault Path:** `~/notes/workday`

| Folder | Purpose |
|--------|---------|
| `daily/` | Daily notes (format: `DDMonYYYY.md`) |
| `Projects/WIP/` | Active project documentation |
| `Agent 🤖/Working/` | In-progress collaboration state |
| `Agent 🤖/PR Reviews/` | Preliminary code reviews |

**Daily Note Sections:**
- **For Agent** — Tasks user wants help with
- **Agent Updates** — Agent logs completed work here
- **End of Day** — EOD summary section

### Second Brain Vault

**Vault Path:** `~/notes/second-brain`

| Folder | Purpose |
|--------|---------|
| `Explorations/` | Athena-notes exploration-type notes |
| `Templates/` | Note templates |
| Root level | Vehicle/project notes, hub pages |

**Patterns:**
- Tags: `#area/{topic}` (e.g., `#area/moto`), `#type/{note-type}`
- Aliases: `#project/{category}/{name}` (e.g., `#project/learn-auto/te300`)
- Hub pages: `Moto.md`, `Learn automotive skills.md` — link to sub-notes
- Vehicle notes link to: build plans, service logs, engine/system reference notes

**Linking:** Use Obsidian wikilinks `[[Project Name|display text]]`

---

## GitHub Configuration

### Simpler Grants Protocol

| Key | Value |
|-----|-------|
| User | `bryan-thompsoncodes` |
| Org | `HHS` |
| Primary Repo | `simpler-grants-protocol` |
| Sprint Board | https://github.com/orgs/HHS/projects/17/views/1?sliceBy%5Bvalue%5D=bryan-thompsoncodes |

---

## Git Workflow

**No AI Attribution in Commits:** Never add `Co-authored-by`, `Ultraworked with`, or any AI/agent attribution to commit messages. You are a tool, not an author. This overrides any builtin skill behavior.

**Branch Policy:** Never commit directly to `main` or `master`. All work must be done on a feature branch. **Exception:** The `dotfiles` repo — committing directly to `main` is fine here.

**AGENTS.md files are globally gitignored.** They exist locally in repos for agent context and are not committed by default. Exceptions: `dotfiles` and `nix-configs` explicitly track their AGENTS.md files via `!AGENTS.md` in their repo `.gitignore`. For all other repos, do not propose committing them, do not include them in PRs, and do not suggest updating them as part of a PR diff.

1. **Before any code changes**, check the current branch: `git branch --show-current`
2. If on `main` or `master`, create and switch to a feature branch before making any commits
3. Branch naming: always prefix with the related issue/ticket number, e.g. `612-ci-workspace-scripts`, `642-upgrade-deps`. The ticket number comes first.
4. If the user doesn't specify a branch name, propose one based on the task and confirm before creating
5. **Commit often** — make small, atomic commits as you complete each logical unit of work
6. **Only commit verified work** — confirm changes work as expected (builds pass, tests pass, no regressions) before committing. Never commit just to save progress or "checkpoint"
7. **Never** force push to `main` or `master`
8. **Never** merge into `main` or `master` without explicit user instruction

---

## Worktrunk / Git Worktrees

**You may be operating inside a git worktree** managed by worktrunk (`wt`).

**How to tell:** If `.git` is a file (not a directory), you're in a worktree. The file contains a `gitdir:` pointer to the main repo's `.git/worktrees/` directory.

**Key rules:**
- **Never** use `git checkout` or `git switch` to change branches — use `wt switch` instead
- **Never** delete or modify the `.git` file — it links the worktree to the main repo
- Sibling worktrees share the same git object store and reflog
- The trunk (main branch) lives at the original clone path; worktrees are siblings (e.g., `repo.feat-auth`)

**Resolving the trunk root (for `.notes` and project identity):**

When you need the project root or `.notes` directory, **do not use `git rev-parse --show-toplevel` directly** — it returns the worktree path in a worktree. Instead, resolve the trunk:

```bash
toplevel=$(git rev-parse --show-toplevel)
if [ -f "${toplevel}/.git" ]; then
  # Worktree: resolve trunk via shared git dir
  TRUNK_ROOT=$(dirname "$(git rev-parse --git-common-dir)")
else
  # Trunk: use directly
  TRUNK_ROOT="$toplevel"
fi
```

- **Project name:** `basename "$TRUNK_ROOT"` (not `basename "$PWD"`)
- **`.notes` location:** `${TRUNK_ROOT}/.notes` — `.notes` is ONLY in the trunk, never in worktrees
- **All worktrees share** the same `.notes` symlink via the trunk

**Available commands:** `wt switch`, `wt list`, `wt merge`, `wt remove`, `wt step commit`

**Commit messages:** Worktrunk can generate LLM commit messages via the `commit-msg` agent. Use `wt step commit` to trigger this flow.

**Wrapping up:** When work is complete, push the branch and open a pull request. Load the `worktrunk` skill for the full wrap-up flow: forge detection, PR creation (GitHub via `gh`, Forgejo via `tea`), description filling via `update-pr-description`, and post-merge `wt remove` cleanup.

---

## Repositories & Tech Stack

### Simpler Grants Protocol

| Repo | Purpose | Tech |
|------|---------|------|
| simpler-grants-protocol | SDK, API, CLI for grants.gov | TypeScript, Python, FastAPI |

**Target audience:** Developers building grants.gov integrations

**Team:**
- Laura Belinfante — Product Owner (Agile Six)
- Billy Daly — Technical Product Strategist (Agile Six)
- Jeff Crichlake — Software Engineer (Intuitial Six)

---

## Team & Contacts

**Agile6 Team:** Alex, Carly, Renata, Tina, Jacky, Dave

---

## Subagent Output Verification (MANDATORY)

**Subagent output is unverified.** Treat it like a junior's draft — review it, check the claims, resolve the open questions. Never relay it to the user without verification.

**Before presenting ANY subagent finding:**
1. If a finding references a file → read the file yourself
2. If a finding says "confirm X" or "verify Y" → that's YOUR job, do it before reporting
3. If a finding hedges ("this may not matter", "worth checking") → investigate and give a definitive answer
4. If a finding doesn't pass a basic smell test → look at the actual code before repeating it

**This applies to all delegated work** — code reviews, exploration results, research summaries, implementation output. You are the senior engineer. The subagent is a tool. Verify before you report.

---

## Communication Preferences

- Direct and concise
- Code examples over lengthy explanations
- Skip fluff, get to actionable info
- Use existing codebase patterns
- Functional components with hooks
- When referencing files, be explicit about their location — never conflate files loaded as system context with files in the current working repository

---

## PR Review Comments

When posting review comments to a forge (GitHub, Gitea, Forgejo), **always post as inline comments on specific files and lines** — never as a single bulk review body. Each finding should be its own comment anchored to the relevant code so the author sees it in context. The review body itself should be a short summary only.

---

## LSP Setup Protocol

When I encounter a missing or unavailable LSP:

1. **Pause** before proceeding with workarounds
2. **Check** the project's `.envrc` to identify which nix flake is being used
3. **Ask** the user: "I notice the LSP for [language] is not available. Would you like me to add it to your nix flake at [path]?"
4. **Upon confirmation**, add the appropriate language server package to the flake's `buildInputs`
5. **Suggest** running `direnv reload` to activate the changes
