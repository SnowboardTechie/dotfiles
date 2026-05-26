---
name: issue-work
description: End-to-end GitHub/Forgejo ticket workflow. Use when the user shares a ticket URL (github.com/owner/repo/issues/N or /pull/N), a shorthand like owner/repo#123, asks to "start on ticket", "pick up this issue", "work on this ticket", or pastes issue text asking for implementation. Fetches ticket with all comments and linked work, creates a worktree, spawns parallel exploration agents, proposes an implementation plan for approval, implements, runs tests, then runs parallel self-review (correctness/security/simplicity) before returning for human review.
---

# Issue Work

End-to-end workflow for taking a GitHub or Forgejo ticket from URL to review-ready implementation. Four phases: **Intake → Plan → Implement → Self-Review**, with a human approval checkpoint between Plan and Implement.

Standalone — does not require any specific note system. Ships in the cairn-notes plugin, but writes state under `~/.claude/issue-work/` (not the notes vault).

---

## Inputs Accepted

- GitHub issue URL: `https://github.com/{owner}/{repo}/issues/{N}`
- GitHub PR URL: `https://github.com/{owner}/{repo}/pull/{N}`
- Forgejo URL: `https://{host}/{owner}/{repo}/(issues|pulls)/{N}`
- Shorthand: `{owner}/{repo}#{N}` (GitHub)
- Raw pasted ticket text (asks for repo)

## State Root

All per-ticket state lives at:

```
~/.claude/issue-work/{owner}-{repo}-{N}/
```

This survives worktree teardown. Resume is supported by reading `progress.md` frontmatter `status:` field.

---

## Phase 0 — Resume Check

Before anything else, compute the state-dir path from the input. If `~/.claude/issue-work/{owner}-{repo}-{N}/progress.md` exists:

1. Read its frontmatter `status:` field.
2. Report to the user: "Found existing work on {ticket}. Status: {status}. Resume or refresh?"
3. On **resume**, skip to the phase after the last completed status.
4. On **refresh**, continue with the full flow (will overwrite prior files).

Do not re-fetch or re-plan unless the user says refresh.

---

## Phase 1 — Intake

### 1.1 Detect source

Match the input against these patterns **in order** (stop at the first match):

```bash
# 1. GitHub URL — check this FIRST (note the /issues/ path overlaps with Forgejo)
^https?://github\.com/([^/]+)/([^/]+)/(issues|pull)/([0-9]+)

# 2. Shorthand — always GitHub
^([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+)#([0-9]+)$

# 3. Forgejo URL — only reached if neither of the above matched
^https?://([^/]+)/([^/]+)/([^/]+)/(issues|pulls)/([0-9]+)
```

**Ordering matters.** GitHub issue URLs also satisfy the Forgejo pattern (both use `/issues/`), so GitHub must be checked first. Only PRs differ by path (`/pull/` vs `/pulls/`).

If none match and the input is ticket-like prose, treat as pasted text and **ask which repo** before proceeding.

### 1.2 Create state directory

```bash
mkdir -p "$HOME/.claude/issue-work/{owner}-{repo}-{N}"
```

### 1.3 Spawn `ticket-intake` sub-agent

Invoke the `ticket-intake` agent with the ticket reference and the state-dir path. It writes `context.md` with ticket body, comments, linked refs, inferred open questions.

Do **not** inline the fetch logic here — the agent owns that. Read `context.md` after it returns.

### 1.4 Resolve local clone

See [references/repo-resolution.md](references/repo-resolution.md) for details. Short version:

```bash
# Look for a clone matching owner/repo under ~/code/ (1 and 2 levels deep)
Glob(pattern="$HOME/code/*/.git")
Glob(pattern="$HOME/code/*/*/.git")
# For each match, check remote URL matches owner/repo
```

If no local clone: ask before running `gh repo clone {owner}/{repo} ~/code/{repo}`.

Bind the resolved clone path as `{TRUNK_ROOT}` — the placeholder Phase 1.5 and Phase 1.6 reference. If the resolved path is itself a worktree, resolve to the trunk via `git -C {path} rev-parse --path-format=absolute --git-common-dir` and strip the trailing `/.git` (same pattern the `archivist` agent uses; see [`agent-workspace/SKILL.md`](../agent-workspace/SKILL.md) → *Worktree-Aware Resolution*).

### 1.5 Pre-flight checks

Run all of these against the trunk (not a worktree).

**First, detect the default branch** (don't assume `main`):

```bash
DEFAULT_BRANCH=$(gh repo view {owner}/{repo} --json defaultBranchRef --jq .defaultBranchRef.name)
# Forgejo equivalent — use the API from references/fetch-ticket.md
```

**Then run the rest of the pre-flight:**

```bash
# GitHub auth — stop if not logged in
gh auth status || { echo "Run: gh auth login"; exit 1; }

# Forgejo auth (only if forgejo ticket) — stop if no token in env
if [[ "$forge" == "forgejo" && -z "${FORGEJO_TOKEN:-${GITEA_TOKEN:-}}" ]]; then
  echo "Set FORGEJO_TOKEN (or GITEA_TOKEN) in your shell env" >&2
  exit 1
fi

# Fetch the actual default branch
git -C "{TRUNK_ROOT}" fetch origin "$DEFAULT_BRANCH"

# Working tree clean? (modified or staged — ignore untracked)
git -C "{TRUNK_ROOT}" status --porcelain | grep -E '^[ MADRC]'
```

If either auth check fails, stop and surface the error to the user — do not proceed to worktree creation. If the trunk is dirty (modified/staged, not just untracked), stop and offer: stash / commit / abort. Do not silently stash.

### 1.6 Create worktree

`EnterWorktree` only accepts `name` or `path` — there is no `base_branch` parameter, and `name`-form always branches off the session's current HEAD. From inside another worktree (the common case), that's the wrong base. Create the worktree with `git worktree add` against the trunk first, then enter it by path.

Three-step pattern:

1. **Compute the worktree slug and path.** `kebab-slug` = ticket title, lowercased, non-alphanumerics → `-`, collapsed, trimmed. The full worktree directory name is `{repo}.{N}-{kebab-slug}` (cap at 60 chars). The branch name is `issue-{N}-{kebab-slug}` — or match the repo's branch convention if recent branches in `git -C "{TRUNK_ROOT}" for-each-ref --format='%(refname:short)' --count=20 refs/heads/` suggest a different prefix (e.g., `bryan/issue-…`).

2. **Create the branch + worktree against the trunk.** Pin the base to the remote ref so a stale local default doesn't become the parent commit:

   ```
   Bash(command="git -C \"{TRUNK_ROOT}\" worktree add -b issue-{N}-{kebab-slug} \"{TRUNK_ROOT}/.claude/worktrees/{repo}.{N}-{kebab-slug}\" \"origin/$DEFAULT_BRANCH\"")
   ```

3. **Enter the new worktree by path** (path-form, not name-form):

   ```
   EnterWorktree(path="{TRUNK_ROOT}/.claude/worktrees/{repo}.{N}-{kebab-slug}")
   ```

**Resume case** (worktree directory already exists at the target path — e.g., `Phase 0 — Resume Check` flagged this ticket as resumed): skip step 2 entirely and call `EnterWorktree(path: ...)` directly. Do not run `git worktree add` against an existing path; it will error and the desired branch is already in place.

### 1.7 Write initial progress.md

```markdown
---
status: intake
ticket: {url-or-shorthand}
worktree: {abs-path}
branch: {branch-name}
base: {default-branch}
started: {iso8601}
---

## Intake complete

- Context file: ~/.claude/issue-work/{owner}-{repo}-{N}/context.md
- Worktree: {abs-path}
- Base branch: {default-branch}
```

---

## Phase 2 — Plan

### 2.1 Spawn parallel exploration

**Always** spawn one `Explore` agent. **Conditionally** spawn a second `Explore` if the ticket clearly spans two distinct areas (e.g., frontend + backend, API + client SDK).

Send a **single message with multiple Task tool calls** — do not spawn sequentially.

Prompt template for each Explore agent:

> Map the codebase area relevant to ticket #{N}: "{title}".
>
> **Scope** (one of): {primary area | secondary area}
>
> Starting points (from ticket body/comments): {files, functions, modules mentioned}
>
> Produce a concise map:
> - Affected modules and files (with paths)
> - Existing patterns/abstractions worth reusing
> - Test locations and conventions in this area
> - Any gotchas or non-obvious coupling
>
> Write your findings to `~/.claude/issue-work/{owner}-{repo}-{N}/explore-{area-slug}.md` where `{area-slug}` is a short kebab-case tag for your assigned scope (e.g., `frontend`, `api`, `migration`). One file per agent — never share a file between Explore agents, since parallel appends can interleave and corrupt the output.

### 2.2 External research (conditional, inline)

If the ticket references libraries or APIs **not** present in the repo's manifests, do research inline.

First, discover which manifests exist in the repo:

```bash
# List manifests that actually exist at the repo root
for f in package.json go.mod Cargo.toml requirements.txt pyproject.toml Gemfile pom.xml build.gradle; do
  [[ -e "$f" ]] && echo "$f"
done
```

Then for each manifest found, grep its declared dependencies and compare against library names mentioned in the ticket. A library named in the ticket but absent from every manifest is a candidate for external research.

Use `WebSearch` + `WebFetch` to look up official docs. Capture findings directly in `plan.md` under a **Research** section. Do not create a separate agent or file.

### 2.3 Synthesize plan.md

After exploration returns, write `plan.md`:

```markdown
---
status: planned
ticket: {url}
updated: {iso8601}
---

## Problem

{2–3 sentences from context.md + explore-*.md}

## Approach

{high-level strategy}

## Affected Files

- `path/to/file.ts` — {what changes}
- `path/to/other.ts` — {what changes}

## Test Strategy

{what tests to add, what suites to run, any new fixtures}

## Research

{external docs/references, only if relevant}

## Open Questions

- {items to flag for the user before implementation}

## Non-goals

- {explicit scope boundaries}
```

### 2.4 Approval checkpoint

This is a hard stop. **Do not proceed to Phase 3 without explicit user approval.**

Present the full `plan.md` contents inline to the user with a clear prompt:

> **Plan ready for review** — `~/.claude/issue-work/{owner}-{repo}-{N}/plan.md`
>
> {paste plan.md contents}
>
> Reply `approve` to begin implementation, or describe changes you'd like.

Then wait for the user's next message. Do not implement anything until you see an approval.

On amendment: overwrite `plan.md` with the revised version, keep `status: planned` in frontmatter, and re-present. Iterate until approved.

(If the harness happens to be in Plan Mode when this skill runs, `ExitPlanMode` is the harness-native approval gate and you can use it in place of the inline prompt above. Do not try to enter Plan Mode from inside the skill — that's not a thing.)

---

## Phase 3 — Implement

After user approval:

### 3.1 Update status

```bash
# Set progress.md frontmatter status: implementing
```

### 3.2 Re-read plan.md

`plan.md` is the source of truth. If anything in the conversation contradicts it, defer to the plan — or stop and ask before diverging.

### 3.3 Commits

- Atomic: one logical unit per commit
- Message style: match `git log --oneline -20` conventions in **this repo** (not global defaults)
- **Never** add `Co-authored-by: Claude` or any AI signature trailer
- **Never** use `--no-verify` to skip hooks

### 3.4 Test suite detection

Run tests after implementation. Detect by manifest:

| Manifest | Command |
|---|---|
| `package.json` with `test` script | `npm test` or `yarn test` or `pnpm test` (match lockfile) |
| `pyproject.toml` | `pytest` |
| `Cargo.toml` | `cargo test` |
| `go.mod` | `go test ./...` |
| `nx.json` / `turbo.json` | `nx affected -t test` or `turbo test` |

Also run lint + typecheck when configured:

- TypeScript: `tsc --noEmit` or repo script
- Python: `ruff check` / `mypy`
- Go: `go vet ./...`
- Rust: `cargo clippy`

### 3.5 On failure

Loop: diagnose → fix → commit → rerun. **Hard cap at 3 attempts.** On the 4th failure, stop and report the failing output to the user.

### 3.6 Progress log

After each test run, append to `progress.md`:

```markdown
## {iso8601} — commit {sha7}

{one-line commit subject}

Tests: {pass/fail summary}
Lint/typecheck: {summary}
```

Do not advance `status` when tests go green — Phase 4 bumps it to `reviewed` after self-review completes. Leave it at `implementing` until then.

---

## Phase 4 — Self-Review

### 4.1 Delegate to `/pr-self-review`

Phase 4 hands off to the [`pr-self-review`](../pr-self-review/SKILL.md) skill in its `pre-pr` mode — same three parallel `diff-reviewer` agents, plus a pre-review context fetch (related open issues in this repo + related `.notes/` decisions/explorations) and a per-finding triage loop (`accept` / `push-back` / `issue` / `skip`) so easy nits get cleared in-pass instead of piling up in a list. The worktree, branch, and state dir already exist; pass them in:

- `mode`: `pre-pr`
- `state_dir`: `~/.claude/issue-work/{owner}-{repo}-{N}/`
- `worktree_path`: the absolute path from `progress.md`
- `base_branch`: the value from `progress.md` `base:`
- `plan_path`: `~/.claude/issue-work/{owner}-{repo}-{N}/plan.md`
- `source_issue`: `{owner}/{repo}#{N}` — the ticket this work is for; lets pr-self-review fire its source-issue exception (findings tagged with this issue surface for triage instead of pre-skipping) without waiting for a PR body to exist.

Invoke it via the `Skill` tool (not by running commands). The skill writes `review-{lens}.md` files and a final `summary.md` into the state dir, matching the shape Phase 4.3 reads below. When it returns, `summary.md` is ready.

Set `progress.md` `status: reviewed` after the skill returns.

### 4.3 Present to user and ask for ship approval

Present the review outcome inline in this order:

1. **Headline** — the one-line summary from `summary.md`.
2. **Critical + Major findings** — full bullets, not just counts. If none, say so explicitly ("No critical or major findings").
3. **Minor / Nit counts** — single line, e.g. "Minor: 3, Nit: 1. Full detail in review-*.md."
4. **Paths** — `summary.md` + individual `review-{lens}.md` files, as clickable Markdown links when the surface supports them.
5. **Ship prompt.** End the message with a direct question — do not stop silently:

   > Ready to push the branch and open the draft PR? Reply `ship it` to proceed, or flag anything you want changed first.

   On `ship it` (or equivalent approval like "yes", "go", "push"): **invoke the [`ship` skill](../ship/SKILL.md)** — do not run `git push` / `gh pr create` directly. `/ship` already handles the push, forge-specific PR creation (GitHub via `gh`, Forgejo via REST API), PR-template detection (`.github/PULL_REQUEST_TEMPLATE.md`), and label application via `gh label list` + domain heuristics. Rolling our own here would duplicate that logic and skip the template / labels.

   When invoking `/ship`, tell it the authoritative source for what the PR is about lives at `~/.claude/issue-work/{owner}-{repo}-{N}/summary.md` — `/ship` reads that file when filling the PR template's Summary and Test-plan sections so the PR body reflects the review findings, not a generic diff-walk.

   On anything ambiguous: ask again, do not ship. Do not treat silence as approval.

**Do not auto-ship before this exchange.** The review summary on its own isn't consent — the user needs one more explicit step after reading it.

---

## Edge Cases

| Case | Behavior |
|---|---|
| Worktree already exists for this ticket | Skip the `git worktree add` step in Phase 1.6; call `EnterWorktree(path: ...)` directly; resume from `progress.md` status |
| Trunk dirty (modified/staged) | Stop. List files. Offer stash / commit / abort |
| Ticket is a PR (review work, not new work) | Skip worktree creation; `gh pr checkout {N}` in trunk or fetch branch; swap Phase 3 for "review against plan"; Phase 4 reviewers still run |
| Tests fail 3× | Stop; surface last failure output; ask user |
| Critical review findings | Present prominently; recommend fix-before-ship; never auto-ship |
| User amends plan after approval | Overwrite `plan.md`; reset status `planned`; re-present inline and await approval again (see Phase 2.4) |
| Repo not cloned locally | Ask before `gh repo clone` to `~/code/{repo}` |
| Forgejo ticket | `ticket-intake` uses REST API; everything else identical |
| Pasted raw text (no URL) | Skip fetch; ask user for repo; `context.md` has only Body |
| User says "refresh" on a resumed ticket | Overwrite prior state files; restart from Phase 1 |

---

## Things This Skill Does NOT Do

- Ship without explicit approval — Phase 4.3's ship gate is mandatory; silence is not consent. On `ship it` the skill hands off to `/ship`, which handles the push + PR creation.
- Modify files outside the worktree and the state dir
- Add AI signatures to commits or PRs
- Skip hooks (`--no-verify`) or bypass signing
- Write notes into `.notes/` or any note system — state goes to `~/.claude/issue-work/` only

---

## References

Detailed recipes that load on demand:

- [references/fetch-ticket.md](references/fetch-ticket.md) — exact gh/tea CLI commands, pagination, rate limits, Forgejo API auth
- [references/repo-resolution.md](references/repo-resolution.md) — local clone discovery, remote URL matching, clone-if-missing prompt

## Related Agents

- `ticket-intake` — Phase 1 fetch + digest (model: haiku)
- `diff-reviewer` — Phase 4 parallel reviewer with `lens` argument; carries its own lens prompts inline (model: sonnet). Invoked via `/pr-self-review`.

## Related Skills

- `pr-self-review` — Phase 4 delegates here for the three-lens review + triage loop.
- `ship` — Phase 4.3 hands off here on `ship it` for push + PR creation + template fill + label application.

### Optional Delegation

Soft references — the skill works without them, but if the host environment has them installed they can be invoked on demand during a run:

- `engineering:debug` — optional, when test failures in Phase 3 prove stubborn and you want a structured debug pass
- `engineering:testing-strategy` — optional, when Phase 2 exploration surfaces a test-architecture gap deep enough to warrant its own plan
