---
name: issue-work
description: End-to-end GitHub/Forgejo ticket workflow. Use when the user shares a ticket URL (github.com/owner/repo/issues/N or /pull/N), a shorthand like owner/repo#123, asks to "start on ticket", "pick up this issue", "work on this ticket", or pastes issue text asking for implementation. Fetches ticket with all comments and linked work, creates a worktree, spawns parallel exploration agents, proposes an implementation plan for approval, implements, runs tests, then runs parallel self-review (correctness/security/simplicity) before returning for human review.
---

# Issue Work

End-to-end workflow for taking a GitHub or Forgejo ticket from URL to review-ready implementation. Four phases: **Intake → Plan → Implement → Self-Review**, with a human approval checkpoint between Plan and Implement.

Standalone — does not require any specific note system. Resolve the local clone first, then write durable state under `{TRUNK_ROOT}/.hermes/issue-work/` (not the notes vault). This workspace-local path is safe for Hermes profiles and remains usable by Claude, OpenCode, and Pi.

**Ticket ownership rule:** when the request names one or more tracked issues and also names a narrower implementation workflow, keep `issue-work` as the umbrella unless the user explicitly limits the task to an implementation/review-only handoff. Load the narrower workflow in Phase 3 rather than replacing ticket intake, durable state, self-review, and the ship gate. A publication prohibition remains in force until Phase 4 obtains item-level approval; it is not a reason to skip the umbrella.

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
{TRUNK_ROOT}/.hermes/issue-work/{owner}-{repo}-{N}/
```

This survives worktree teardown. Resume is supported by reading `progress.md` frontmatter `status:` field.

---

## Phase 0 — Pre-flight

### 0.1 Runtime capability mapping

Use the host's native operations; do not require one agent framework or plugin:

| Operation | Hermes | Other compatible hosts |
|---|---|---|
| Clarify a decision | interactive clarification (`clarify`) | conversational prompt / `AskUserQuestion` |
| Track implementation tasks | task list (`todo`) | native todo/task-list tool |
| Delegate isolated research/review | `delegate_task` | `Task`, `Agent`, or equivalent |
| Create/enter worktree | `wt switch --create` then run tools with that worktree as `workdir` | `EnterWorktree` or controlled `git worktree` fallback |
| Write the approved plan | load Hermes `plan` | `superpowers:writing-plans` or equivalent |
| Execute a Codex-authored plan with Claude | load Hermes `codex-claude-implementation-loop` when the parent is Codex-backed | host-native implementation workflow |
| Implement test-first | load Hermes `test-driven-development` | host TDD/execution workflow |
| Debug repeated failures | load Hermes `systematic-debugging` | equivalent root-cause workflow |
| Independent final review | load Hermes `requesting-code-review` | equivalent verification/reviewer workflow |
| Push and open the approved draft PR | load Hermes `ship` | host-native `ship` workflow |

If delegation is unavailable, perform the same bounded analysis serially. Missing a framework-specific plugin is never by itself a blocker.

### 0.2 Resume check

After resolving `{TRUNK_ROOT}` in Phase 1.2, compute the state-dir path. If `{TRUNK_ROOT}/.hermes/issue-work/{owner}-{repo}-{N}/progress.md` exists:

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

### 1.2 Resolve local clone

See [references/repo-resolution.md](references/repo-resolution.md) for details. Short version:

```bash
# Look for a clone matching owner/repo under ~/code/ (1 and 2 levels deep)
Glob(pattern="$HOME/code/*/.git")
Glob(pattern="$HOME/code/*/*/.git")
# For each match, check remote URL matches owner/repo
```

If no local clone: ask before running `gh repo clone {owner}/{repo} ~/code/{repo}`.

Bind the resolved clone path as `{TRUNK_ROOT}` — later phases reference it. If the resolved path is itself a worktree, resolve to the trunk via `git -C {path} rev-parse --path-format=absolute --git-common-dir` and strip the trailing `/.git` (same pattern used for worktree-aware resolution; see [`agent-workspace/SKILL.md`](../agent-workspace/SKILL.md) → *Worktree-Aware Resolution*).

### 1.3 Create state directory

Create `{TRUNK_ROOT}/.hermes/issue-work/{owner}-{repo}-{N}/` with the host file tools or `mkdir -p`.

### 1.4 Fetch ticket context

Use [references/fetch-ticket.md](references/fetch-ticket.md) to fetch the ticket body, comments, linked refs, and inferred open questions. Prefer an isolated intake child (`delegate_task` on Hermes; `Task`/`Agent` elsewhere), but run the same recipe inline when delegation is unavailable. Write `context.md` in the state directory and read it after completion.

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

Use the [`worktrunk`](../worktrunk/SKILL.md) skill as the preferred controlled-worktree path.

1. **Compute slug, branch, and base.** `kebab-slug` = ticket title, lowercased, non-alphanumerics → `-`, collapsed, trimmed. Branch = `issue-{N}-{kebab-slug}` — or match the repo's convention if recent local branches show a different prefix. Base ref = `origin/$DEFAULT_BRANCH`.
2. **Check for an existing worktree.** Run `wt list` (or `git worktree list --porcelain` when `wt` is unavailable) and reuse the matching branch; never nest worktrees.
3. **Create from the fetched base.** From `{TRUNK_ROOT}`, run `wt switch --create {branch} --base origin/$DEFAULT_BRANCH`. If `wt` is unavailable, use the controlled fallback `git -C "{TRUNK_ROOT}" worktree add -b {branch} "{TRUNK_ROOT}.{N}-{kebab-slug}" origin/$DEFAULT_BRANCH`.
4. **Operate in isolation.** Hermes runs subsequent file and terminal operations with the resulting absolute path as `workdir`; hosts with `EnterWorktree` may enter that path. Record it as `{WORKTREE_PATH}`.

Never switch the trunk checkout in place.

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

- Context file: {TRUNK_ROOT}/.hermes/issue-work/{owner}-{repo}-{N}/context.md
- Worktree: {abs-path}
- Base branch: {default-branch}
```

---

## Phase 2 — Plan

### 2.1 Spawn parallel exploration

Decide how many exploration children to dispatch: **always** at least one; **add a second** if the ticket clearly spans two distinct areas. Use `delegate_task` on Hermes or `Task`/`Agent` elsewhere. Dispatch independent children together, with distinct output paths and no shared writes. If delegation is unavailable, perform the scopes serially.

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
> Write your findings to `{TRUNK_ROOT}/.hermes/issue-work/{owner}-{repo}-{N}/explore-{area-slug}.md` where `{area-slug}` is a short kebab-case tag for your assigned scope (e.g., `frontend`, `api`, `migration`). One file per agent — never share a file between Explore agents, since parallel appends can interleave and corrupt the output.

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

Use the host's read-only web search/fetch tools (Hermes browser/web tooling; Claude/OpenCode/Pi equivalents) to look up official docs. Capture findings directly in `plan.md` under a **Research** section. Do not create a separate agent or file.

### 2.3 Synthesize plan.md

> **Consumer- or plugin-author-facing surface? (soft pointer, judgment call.)** If this ticket introduces or reshapes a consumer/plugin-author-facing surface in the SGG / CommonGrants repos (a new endpoint, protocol/`.tsp` change, or SDK/extension surface), consider running the `dx-target` skill *before* delegating to plan authoring — it works backwards from the developer experience (2-3 candidate usage shapes → a chosen target) and hands the chosen target to `writing-plans` as the acceptance oracle, so the plan is "make this snippet real" rather than an inward-facing task list. Skip for endpoint bug-fixes, dep bumps, docs, and internal-only changes.

After exploration returns, load Hermes's installed `plan` skill or the host's equivalent plan-authoring workflow. Do not clone that skill's instructions here. Give it:

- **Inputs:** `context.md`, the `explore-*.md` outputs from 2.1, and any inline research from 2.2.
- **Plan-path override:** `{TRUNK_ROOT}/.hermes/issue-work/{owner}-{repo}-{N}/plan.md`. Hermes `plan` normally writes under workspace `.hermes/plans/`; use this ticket-specific path so resume state stays together and never appears in the feature worktree's `git status`.

The result is a bite-sized, checkbox-task plan (exact file paths, code, expected command output, commit boundaries) — the shape Phase 3's executor consumes. Make sure its frontmatter carries `status: planned` and `ticket: {url}` so Phase 0.2 resume and the 2.4 approval gate keep working against it.

### 2.4 Approval checkpoint

This is a hard stop. **Do not proceed to Phase 3 without explicit user approval.**

Present the full `plan.md` contents inline to the user with a clear prompt:

> **Plan ready for review** — `{TRUNK_ROOT}/.hermes/issue-work/{owner}-{repo}-{N}/plan.md`
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

`plan.md` (at the state-root path) is the source of truth. Mirror its checkboxes into the host task list (Hermes: `todo`). Then select exactly one execution path.

#### Hermes with a Codex-backed parent

When `codex-claude-implementation-loop` is installed, load it and use it as the implementation engine:

1. Record the worktree's baseline status and run the worker's subscription-auth check.
2. Invoke `claude_worker.py implement` with `plan.md`, `{WORKTREE_PATH}`, and `--model opus`. Never authorize a model downgrade on the run's behalf; if Opus remains unavailable after the wrapper's same-model retry, stop and report the blocker.
3. Save the normalized worker envelope as `{state-dir}/claude-implementation.json`. Record its `session_id` in `progress.md` frontmatter as `claude_session_id:` so Phase 4 can resume the same Claude context.
4. Codex reviews the actual repository diff and independently reruns every targeted and broader check required by the plan. Claude's structured result is evidence, not the verdict.
5. For blocking findings, write `{state-dir}/codex-review-{pass}.md` and resume the same Opus session with `claude_worker.py revise`. Repeat the complete Codex gate after each revision; cap the correction loop at two revision passes.
6. Mark plan/task checkboxes complete only after Codex accepts the final repository state. Preserve the implementation and revision envelopes in the state directory.

Claude must not commit, push, reset, clean, publish, or alter history. After the complete Codex gate passes, the parent may create local commits at the approved plan's logical boundaries, staging only reviewed paths and preserving the repository's message and hook rules. Plan approval authorizes those local implementation commits; it does not authorize a push, PR, comment, or other publication.

#### Other hosts or a non-Codex Hermes parent

Execute task-by-task with the host-native workflow. Load `test-driven-development` for behavior changes and `systematic-debugging` for failures. Pass through:

- **plan_path:** `{TRUNK_ROOT}/.hermes/issue-work/{owner}-{repo}-{N}/plan.md`
- **worktree path:** the absolute path from `progress.md`
- **commit rules:** atomic (one logical unit per commit); message style matches `git log --oneline -20` in **this repo** (not global defaults); **never** add `Co-authored-by: Claude` or any AI signature; **never** use `--no-verify`.
- **failure policy:** hand off the 3.5 escalation rule below — on a task whose tests fail, attempt a direct fix first; on a **second** consecutive failure of the same task, escalate per 3.5; hard cap at 3 attempts, then stop and report. The Codex–Claude path instead uses its two-revision bound above.

Keep `plan.md` checkboxes and the host task list synchronized, so a resumed run (`status: implementing`) picks up at the first unchecked task automatically.

### 3.3 Test / lint / typecheck reference

Run each task's own verification commands. When a task doesn't name one, fall back to detection by manifest:

| Manifest | Command |
|---|---|
| `package.json` with `test` script | `npm test` / `yarn test` / `pnpm test` (match lockfile) |
| `pyproject.toml` | `pytest` |
| `Cargo.toml` | `cargo test` |
| `go.mod` | `go test ./...` |
| `nx.json` / `turbo.json` | `nx affected -t test` or `turbo test` |

Lint + typecheck when configured: TypeScript `tsc --noEmit`; Python `ruff check` / `mypy`; Go `go vet ./...`; Rust `cargo clippy`.

### 3.5 On failure

On the host-native path, first failure of a task's tests: attempt a direct fix → commit → rerun. **Second consecutive failure of the same task:** escalate to `systematic-debugging` (the `Skill` tool) rather than guessing again — it drives a root-cause pass instead of another patch. **Hard cap at 3 attempts total.** On the 4th failure, stop and report the failing output to the user.

On the Codex–Claude path, Codex first determines whether the failure is a plan defect, implementation defect, pre-existing failure, or external blocker. Send implementation defects back through the same Opus session under the two-revision bound. A plan defect, ambiguity, destructive conflict, or exhausted revision budget stops for the user instead of switching models or guessing.

### 3.6 Progress log

After each test run, append to `progress.md`:

```markdown
## {iso8601} — commit {sha7}

{one-line commit subject}

Tests: {pass/fail summary}
Lint/typecheck: {summary}
```

For the Codex–Claude path, also record the implementation/revision artifact path, Claude-reported checks, Codex-rerun checks, and Codex gate verdict. Never collapse Claude's claims and Codex's fresh results into one line.

Do not advance `status` when tests go green — Phase 4 bumps it to `reviewed` after self-review completes. Leave it at `implementing` until then.

### 3.7 Verify before handing off

Before Phase 4 spawns review, prove the suite is green rather than trust the implementation context. If Phase 3 used `codex-claude-implementation-loop`, its final Codex review/retest gate satisfies this step; cite that fresh gate output rather than spawning a duplicate generic reviewer, and rerun only checks invalidated by the parent's post-gate local commit operation. Otherwise load `requesting-code-review` on Hermes (or the host's independent verification workflow), rerun the project's test / lint / typecheck commands, and preserve actual output.

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

Phase 4 hands off to the [`pr-self-review`](../pr-self-review/SKILL.md) skill in its `pre-pr` mode — all four review lenses, plus a pre-review context fetch and a per-finding triage loop (`accept` / `push-back` / `issue` / `skip`). Hermes runs the four lenses in batches of at most three children; other hosts may run all four concurrently. The worktree, branch, and state dir already exist; pass them in:

- `mode`: `pre-pr`
- `state_dir`: `{TRUNK_ROOT}/.hermes/issue-work/{owner}-{repo}-{N}/`
- `worktree_path`: the absolute path from `progress.md`
- `base_branch`: the value from `progress.md` `base:`
- `plan_path`: `{TRUNK_ROOT}/.hermes/issue-work/{owner}-{repo}-{N}/plan.md`
- `source_issue`: `{owner}/{repo}#{N}` — the ticket this work is for; lets pr-self-review fire its source-issue exception (findings tagged with this issue surface for triage instead of pre-skipping) without waiting for a PR body to exist yet.
- `claude_session_id`: the value recorded in `progress.md`, when Phase 3 used the Codex–Claude loop; otherwise omit it.
- `implementation_loop`: `codex-claude-implementation-loop` when `claude_session_id` is present; otherwise omit it.

Load the skill through the host's skill mechanism. It writes `review-{lens}.md` files and a final `summary.md` into the state dir, matching the shape Phase 4.3 reads below.

Set `progress.md` `status: reviewed` after the skill returns.

### 4.3 Present to user and ask for ship approval

Present the review outcome inline in this order:

1. **Headline** — the one-line summary from `summary.md`.
2. **Critical + Major findings** — full bullets, not just counts. If none, say so explicitly ("No critical or major findings").
3. **Minor / Nit counts** — single line, e.g. "Minor: 3, Nit: 1. Full detail in review-*.md."
4. **Paths** — `summary.md` + individual `review-{lens}.md` files, as clickable Markdown links when the surface supports them.
5. **Ship prompt.** End the message with a direct question — do not stop silently:

   > Ready to push the branch and open the draft PR? Reply `ship it` to proceed, or flag anything you want changed first.

   On `ship it` (or equivalent approval like "yes", "go", "push"): **load the [`ship` skill](../ship/SKILL.md)** — do not run `git push` / `gh pr create` directly. `ship` preserves draft-PR defaults, forge-specific creation, PR-template fidelity, and labels.

   When invoking `/ship`, tell it the authoritative source for what the PR is about lives at `{TRUNK_ROOT}/.hermes/issue-work/{owner}-{repo}-{N}/summary.md` — `/ship` reads that file when filling the PR template's Summary and Test-plan sections so the PR body reflects the review findings, not a generic diff-walk.

   On anything ambiguous: ask again, do not ship. Do not treat silence as approval.

**Do not auto-ship before this exchange.** The review summary on its own isn't consent — the user needs one more explicit step after reading it.

---

## Edge Cases

| Case | Behavior |
|---|---|
| Worktree already exists for this ticket | Reuse it after `wt list` / `git worktree list`; resume from `progress.md` status |
| Trunk dirty (modified/staged) | Stop. List files. Offer stash / commit / abort |
| Ticket is a PR (review work, not new work) | Fetch the PR head, create/reuse a controlled `wt` worktree without switching trunk, swap Phase 3 for "review against plan"; Phase 4 reviewers still run |
| Tests fail (2nd time on a task) | Escalate to `systematic-debugging`; hard cap 3 attempts, then stop and surface output |
| Critical review findings | Present prominently; recommend fix-before-ship; never auto-ship |
| User amends plan after approval | Overwrite `plan.md`; reset status `planned`; re-present inline and await approval again (see Phase 2.4) |
| Repo not cloned locally | Ask before `gh repo clone` to `~/code/{repo}` |
| Forgejo ticket | Intake uses the REST API in `references/fetch-ticket.md`; everything else is identical |
| Pasted raw text (no URL) | Skip fetch; ask user for repo; `context.md` has only Body |
| User says "refresh" on a resumed ticket | Overwrite prior state files; restart from Phase 1 |

---

## Things This Skill Does NOT Do

- Ship without explicit approval — Phase 4.3's ship gate is mandatory; silence is not consent. On `ship it` the skill hands off to `/ship`, which handles the push + PR creation.
- Modify files outside the worktree and the state dir
- Add AI signatures to commits or PRs
- Skip hooks (`--no-verify`) or bypass signing
- Write notes into `.notes/` or any note system — state goes to `{TRUNK_ROOT}/.hermes/issue-work/` only

---

## References

Detailed recipes that load on demand:

- [references/fetch-ticket.md](references/fetch-ticket.md) — exact gh/tea CLI commands, pagination, rate limits, Forgejo API auth
- [references/repo-resolution.md](references/repo-resolution.md) — local clone discovery, remote URL matching, clone-if-missing prompt

## Related Delegation Roles

- Intake child — Phase 1 fetch + digest; use `delegate_task`, `Task`, or `Agent` when available.
- Diff reviewer — Phase 4 reviewer with a `lens` argument; invoked through `pr-self-review` in host-appropriate batches.

## Related Skills

- `pr-self-review` — Phase 4 delegates here for the four-lens review + triage loop.
- `ship` — Phase 4.3 hands off here on `ship it` for push + PR creation + template fill + label application.
- `worktrunk` — Phase 1.6 controlled worktree setup.
- `plan` — Phase 2.3 Hermes plan authoring (path-overridden to the state root).
- `test-driven-development` — Phase 3 implementation discipline.
- `systematic-debugging` — Phase 3.5 second-failure escalation.
- `requesting-code-review` — Phase 3.7 independent verification.
- `codex-claude-implementation-loop` — preferred Phase 3 implementation/revision engine for a Codex-backed Hermes parent.

### Optional Delegation

Soft references — the skill works without them, but if the host environment has them installed they can be invoked on demand during a run:

- `engineering:debug` — optional alternative to `systematic-debugging` at Phase 3.5, if that environment-specific debugger is installed and preferred
- `engineering:testing-strategy` — optional, when Phase 2 exploration surfaces a test-architecture gap deep enough to warrant its own plan
