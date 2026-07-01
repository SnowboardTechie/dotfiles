---
name: issue-work
description: End-to-end GitHub/Forgejo ticket workflow. Use when the user shares a ticket URL (github.com/owner/repo/issues/N or /pull/N), a shorthand like owner/repo#123, asks to "start on ticket", "pick up this issue", "work on this ticket", or pastes issue text asking for implementation. Fetches ticket with all comments and linked work, creates a worktree, spawns parallel exploration agents, proposes an implementation plan for approval, implements, runs tests, then runs parallel self-review (correctness/security/simplicity) before returning for human review.
---

# Issue Work

End-to-end workflow for taking a GitHub or Forgejo ticket from URL to review-ready implementation. Four phases: **Intake → Plan → Implement → Self-Review**, with a human approval checkpoint between Plan and Implement.

Standalone — does not require any specific note system; writes state under `~/.claude/issue-work/` (not the notes vault).

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

## Phase 0 — Pre-flight

### 0.1 Required skills check

This skill hard-depends on the `superpowers` plugin. Before doing anything — before computing paths, fetching the ticket, or creating any state — confirm every skill below appears in your available-skills list for this session:

- `superpowers:using-git-worktrees`
- `superpowers:dispatching-parallel-agents`
- `superpowers:writing-plans`
- `superpowers:executing-plans`
- `superpowers:systematic-debugging`
- `superpowers:verification-before-completion`

If any are missing, stop immediately and tell the user:

> `issue-work` requires the `superpowers` plugin, but these skills aren't available: {missing list}. Install or enable superpowers, then re-invoke.

There is no inline fallback — the phases below assume these skills are present.

### 0.2 Resume check

Compute the state-dir path from the input. If `~/.claude/issue-work/{owner}-{repo}-{N}/progress.md` exists:

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

Bind the resolved clone path as `{TRUNK_ROOT}` — the placeholder Phase 1.5 and Phase 1.6 reference. If the resolved path is itself a worktree, resolve to the trunk via `git -C {path} rev-parse --path-format=absolute --git-common-dir` and strip the trailing `/.git` (same pattern used for worktree-aware resolution; see [`agent-workspace/SKILL.md`](../agent-workspace/SKILL.md) → *Worktree-Aware Resolution*).

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

Delegate worktree setup to `superpowers:using-git-worktrees` via the `Skill` tool. That skill owns isolation detection (its Step 0 covers the resume case — if we're already in this ticket's worktree it skips creation), native-tool preference (it uses the harness `EnterWorktree`), and the manual `git worktree add` fallback. Don't re-implement the `EnterWorktree` `name`-vs-`path` base-branch footgun here; the skill handles base selection.

First compute the names the skill needs, then invoke it passing them as declared preferences (it honors a declared directory and branch without re-asking, and skips the consent prompt when a preference is already declared):

1. **Compute slug, path, branch, base.** `kebab-slug` = ticket title, lowercased, non-alphanumerics → `-`, collapsed, trimmed. Worktree directory name = `{repo}.{N}-{kebab-slug}` (cap at 60 chars). Worktree path = `{TRUNK_ROOT}/.claude/worktrees/{repo}.{N}-{kebab-slug}`. Branch = `issue-{N}-{kebab-slug}` — or match the repo's convention if `git -C "{TRUNK_ROOT}" for-each-ref --format='%(refname:short)' --count=20 refs/heads/` shows a different prefix (e.g., `bryan/issue-…`). Base ref = `origin/$DEFAULT_BRANCH`.

2. **Invoke `superpowers:using-git-worktrees`** with: worktree-directory preference `{TRUNK_ROOT}/.claude/worktrees/`, the computed branch name, and base ref `origin/$DEFAULT_BRANCH`. Let it create the worktree and enter it.

The resume case needs no special handling here — `using-git-worktrees` Step 0 detects existing isolation and skips creation on its own.

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

Decide how many `Explore` agents to dispatch: **always** at least one; **add a second** if the ticket clearly spans two distinct areas (e.g., frontend + backend, API + client SDK).

Dispatch them via `superpowers:dispatching-parallel-agents` (the `Skill` tool) — it owns the "single message, multiple Task calls, no shared state" discipline, so we don't restate it here. Hand it the agent prompt(s) below plus each agent's distinct output path.

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

> **Consumer- or plugin-author-facing surface? (soft pointer, judgment call.)** If this ticket introduces or reshapes a consumer/plugin-author-facing surface in the SGG / CommonGrants repos (a new endpoint, protocol/`.tsp` change, or SDK/extension surface), consider running the `dx-target` skill *before* delegating to plan authoring — it works backwards from the developer experience (2-3 candidate usage shapes → a chosen target) and hands the chosen target to `writing-plans` as the acceptance oracle, so the plan is "make this snippet real" rather than an inward-facing task list. Skip for endpoint bug-fixes, dep bumps, docs, and internal-only changes.

After exploration returns, delegate plan authoring to `superpowers:writing-plans` (the `Skill` tool). Give it:

- **Inputs:** `context.md`, the `explore-*.md` outputs from 2.1, and any inline research from 2.2.
- **Plan-path override:** `~/.claude/issue-work/{owner}-{repo}-{N}/plan.md`. `writing-plans` defaults to `docs/superpowers/plans/…` inside the worktree; override it to the state root so the plan survives worktree teardown (resume reads it there) and never shows up in the worktree's `git status`.

The result is a bite-sized, checkbox-task plan (exact file paths, code, expected command output, commit boundaries) — the shape Phase 3's executor consumes. Make sure its frontmatter carries `status: planned` and `ticket: {url}` so Phase 0.2 resume and the 2.4 approval gate keep working against it.

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

### 3.2 Execute the plan

`plan.md` (at the state-root path) is the source of truth. Invoke `superpowers:executing-plans` (the `Skill` tool) to walk it task-by-task. Pass it:

- **plan_path:** `~/.claude/issue-work/{owner}-{repo}-{N}/plan.md`
- **worktree path:** the absolute path from `progress.md`
- **commit rules:** atomic (one logical unit per commit); message style matches `git log --oneline -20` in **this repo** (not global defaults); **never** add `Co-authored-by: Claude` or any AI signature; **never** use `--no-verify`.
- **failure policy:** hand off the 3.5 escalation rule below — on a task whose tests fail, attempt a direct fix first; on a **second** consecutive failure of the same task, escalate per 3.5; hard cap at 3 attempts, then stop and report.

`executing-plans` reads checkbox state, so a resumed run (`status: implementing`) picks up at the first unchecked task automatically — this is the task-level half of the resume protocol.

### 3.3 Test / lint / typecheck reference

`executing-plans` runs each task's own verification commands. When a task doesn't name one, fall back to detection by manifest and hand the detected command to the executor:

| Manifest | Command |
|---|---|
| `package.json` with `test` script | `npm test` / `yarn test` / `pnpm test` (match lockfile) |
| `pyproject.toml` | `pytest` |
| `Cargo.toml` | `cargo test` |
| `go.mod` | `go test ./...` |
| `nx.json` / `turbo.json` | `nx affected -t test` or `turbo test` |

Lint + typecheck when configured: TypeScript `tsc --noEmit`; Python `ruff check` / `mypy`; Go `go vet ./...`; Rust `cargo clippy`.

### 3.5 On failure

First failure of a task's tests: attempt a direct fix → commit → rerun. **Second consecutive failure of the same task:** escalate to `superpowers:systematic-debugging` (the `Skill` tool) rather than guessing again — it drives a root-cause pass instead of another patch. **Hard cap at 3 attempts total.** On the 4th failure, stop and report the failing output to the user.

### 3.6 Progress log

After each test run, append to `progress.md`:

```markdown
## {iso8601} — commit {sha7}

{one-line commit subject}

Tests: {pass/fail summary}
Lint/typecheck: {summary}
```

Do not advance `status` when tests go green — Phase 4 bumps it to `reviewed` after self-review completes. Leave it at `implementing` until then.

### 3.7 Verify before handing off

Before Phase 4 spawns review, invoke `superpowers:verification-before-completion` (the `Skill` tool) to *prove* the suite is green rather than trust that implementation said so. It re-runs the project's test / lint / typecheck commands and surfaces the actual output.

Append the result to `progress.md` under a `## Verification` heading:

```markdown
## Verification

- {iso8601}
- Command(s): {what ran}
- Result: {pass/fail summary + key output lines}
```

If verification fails, do **not** advance to Phase 4. Return to Phase 3's failure loop (3.5) with the new output. Phase 4 starts only once verification is green.

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
| Worktree already exists for this ticket | Handled by `using-git-worktrees` Step 0 (isolation detection skips creation); resume from `progress.md` status |
| Trunk dirty (modified/staged) | Stop. List files. Offer stash / commit / abort |
| Ticket is a PR (review work, not new work) | Skip worktree creation; `gh pr checkout {N}` in trunk or fetch branch; swap Phase 3 for "review against plan"; Phase 4 reviewers still run |
| Tests fail (2nd time on a task) | Escalate to `superpowers:systematic-debugging`; hard cap 3 attempts, then stop and surface output |
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
- `superpowers:using-git-worktrees` — Phase 1.6 worktree setup.
- `superpowers:dispatching-parallel-agents` — Phase 2.1 Explore fan-out.
- `superpowers:writing-plans` — Phase 2.3 plan authoring (path-overridden to the state root).
- `superpowers:executing-plans` — Phase 3 task-by-task execution.
- `superpowers:systematic-debugging` — Phase 3.5 second-failure escalation.
- `superpowers:verification-before-completion` — Phase 3.7 pre-handoff proof.

### Optional Delegation

Soft references — the skill works without them, but if the host environment has them installed they can be invoked on demand during a run:

- `engineering:debug` — optional alternative to `superpowers:systematic-debugging` at Phase 3.5, if that environment-specific debugger is installed and preferred
- `engineering:testing-strategy` — optional, when Phase 2 exploration surfaces a test-architecture gap deep enough to warrant its own plan
