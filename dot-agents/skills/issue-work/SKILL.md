---
name: issue-work
description: End-to-end GitHub/Forgejo ticket workflow. Intake, plan approval, isolated implementation, verification, Standards/Spec/conditional Risk review, mandatory final Ponytail quality review, then an explicit ship gate.
---

# Issue Work

End-to-end workflow for taking a GitHub or Forgejo ticket from URL to review-ready implementation. Four phases: **Intake → Plan → Implement → Self-Review**. Intake includes a mandatory plan-source gate before any worktree or implementation work begins.

Execution state lives under the ticket workspace's trunk. Code operations live
under the independently verified implementation trunk. These are the same path
for ordinary issues, but an approved `issue-plan` may explicitly bind a private
ticket/vault workspace to a different public implementation repository. When the
project has a vault, its approved note is the preferred durable planning
authority; the state-root `plan.md` is a derived execution snapshot.

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
{TICKET_TRUNK_ROOT}/.hermes/issue-work/{ticket-owner}-{ticket-repo}-{N}/
```

This survives implementation-worktree teardown and keeps private execution
artifacts in the private workspace. Resume reads `progress.md` frontmatter.
`{IMPLEMENTATION_TRUNK_ROOT}` separately owns the fetched base, worktree, tests,
commits, and PR.

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
| Resolve an approved project-vault plan | load Hermes `vault-pkm`; follow `issue-plan`'s handoff contract | host-native `vault-pkm` plus the same contract |
| Write the approved plan | load Hermes `plan` | `superpowers:writing-plans` or equivalent |
| Execute an approved plan | reuse the existing governing issue and route to a visible Claude worker through `coding-agent-handoff-supervision`; honor explicit same-run Hermes, Qwen, or host-native GPT requests | host-native implementation workflow |
| Implement test-first | load `tdd` | load `tdd` |
| Debug repeated failures | load `diagnosing-bugs` | load `diagnosing-bugs` |
| Independent final review | a verification context independent of the implementation context | equivalent verification/reviewer workflow |
| Push and open the approved draft PR | load Hermes `ship` | host-native `ship` workflow |

If delegation is unavailable, perform the same bounded analysis serially. Missing a framework-specific plugin is never by itself a blocker.

### 0.2 Resume check

After resolving `{TICKET_TRUNK_ROOT}` in Phase 1.2, compute the state-dir path. If
its `progress.md` exists:

1. Read `status:`, `plan_source:`, issue/comment checkpoints, planning-base and
   repository-role metadata, and, for `plan_source: vault`, source-plan
   path/status metadata.
2. If the metadata required for that source is missing, classify the state as
   **legacy**. Do not reuse or enter its worktree. Offer to refresh intake
   through Phase 1; never infer a plan source for legacy state.
3. Report: "Found existing work on {ticket}. Status: {status}. Resume or
   refresh?"
4. On **resume**, always re-fetch the issue/comments, recompute the comment
   checkpoint, fetch the current default branch, and rerun the bounded inspection
   plus Phase 1.5 authority validation before skipping phases:
   - For `intake` or `planned`, do not reuse the worktree until the gate passes.
   - For `implementing`, `reviewed`, or `blocked`, compare current authority with
     the recorded approved snapshot. Immaterial drift is logged and resume may
     continue. Material goal/scope/decision/acceptance drift stops for the user;
     do not silently widen implementation or ship stale work.
   - When `implementation_loop: coding-agent-handoff-supervision`, require the
     complete visible-worker record: `worker_surface`, `worker_agent_name`,
     `worker_pane_id`, `worker_kind`, `worker_runtime_session_id`, and
     `worker_worktree_identity`. Legacy or incomplete visible-worker state must
     stop as blocked; never launch a replacement worker or infer missing fields
     from a currently visible pane.
5. On **refresh**, continue with the full flow and replace prior intake/plan
   state only after the new source passes.

Resume always refreshes authority evidence. It does not regenerate the plan when
evidence is unchanged; material drift routes through the source-specific rules
below.

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

### 1.2 Resolve the ticket workspace clone

See [references/repo-resolution.md](references/repo-resolution.md). Resolve the
clone matching the issue URL's forge host and owner/repository. Bind its canonical
trunk as `{TICKET_TRUNK_ROOT}` using `worktrunk`'s `resolve_trunk_root` pattern.
This clone owns workspace instructions, vault discovery, ticket state, and the
state directory; it is not automatically the code target.

If the ticket clone is missing, ask before cloning. Never substitute a similarly
named implementation checkout.

### 1.3 Create state directory

Create
`{TICKET_TRUNK_ROOT}/.hermes/issue-work/{ticket-owner}-{ticket-repo}-{N}/`.

### 1.4 Fetch ticket context and bind the implementation repository

Use [references/fetch-ticket.md](references/fetch-ticket.md) to fetch the ticket
body, update timestamp, comments with IDs/update timestamps, linked refs, and
inferred open questions. Compute the canonical comment checkpoint. Prefer an
isolated intake child, but run the same recipe inline when delegation is
unavailable. Write `context.md` in the ticket-root state directory.

Load `vault-pkm` and inspect project-vault candidates just far enough to locate a
single matching handoff section. This preliminary read does not approve the plan:
Phase 1.5 still validates status, content, freshness, and linked decisions.

- If a matching candidate says `Planning status: approved` and uses the explicit
  contract, bind its `Implementation forge` and `Implementation repository` for
  the read-only implementation inspection. Phase 1.5 still verifies that approval
  is consumable and current.
- If no candidate exists, default implementation identity to the ticket forge and
  repository for the clear-issue fallback.
- A matching draft cross-repository candidate stops and routes back to
  `issue-plan`; it cannot redirect inspection or be bypassed by issue fallback.
- A legacy `Repository` field may bind implementation only when it exactly equals
  the ticket repository and the implementation origin uses the ticket forge; it
  cannot authorize a cross-repository or cross-forge target.
- Missing, ambiguous, or conflicting cross-repository identity stops intake.

Resolve the matching implementation clone independently and bind its canonical
trunk as `{IMPLEMENTATION_TRUNK_ROOT}`. Verify its origin hostname and
owner/repository exactly. The ticket repository and implementation repository may
differ only through the explicit approved-plan binding; directory proximity,
similar names, or equal bytes are not identity evidence.

Resolve the implementation forge's current default branch, fetch it against
`{IMPLEMENTATION_TRUNK_ROOT}`, and bind its remote ref and full SHA as
`{PLANNING_BASE_REF}` and `{PLANNING_BASE_SHA}`. If resolution or fetch fails,
stop; never validate against a stale local ref.

Perform the bounded read-only inspection against that fetched implementation
base: active instructions, issue-named files/symbols, neighboring patterns, test
locations, and relevant repo-owned specs/ADRs. Use `git diff`, `git show`, and
`git ls-tree` when the local checkout differs. Write `intake-inspection.md` in the
ticket-root state directory. This inspection is not worktree creation.

### 1.5 Plan-source readiness gate

This gate runs after ticket refresh, explicit repository binding, and current
implementation-base inspection, but before dirty-tree checks or worktree reuse.
Read [`issue-plan`'s handoff contract](../issue-plan/references/handoff-contract.md),
then evaluate:

1. **Approved project-vault plan.** Resolve candidates in the contract's order.
   Search for the exact canonical issue URL and validate the complete handoff,
   required content, linked decisions, issue timestamp, comment checkpoint,
   implementation identity, default branch, and fetched-base drift. Record
   `plan_source: vault` only when one approved plan is current. Material drift or
   disagreement stops and routes back to `issue-plan`.
2. **Issue-as-plan fallback.** When no consumable vault plan exists, implementation
   defaults to the ticket repository. Evaluate all five clear-issue criteria and
   record the verdict plus checkpoints and implementation-base SHA in `context.md`.
   Issue prose alone can never redirect execution to another repository.
3. **Blocked.** If neither source passes, list the missing planning inputs,
   recommend `issue-plan {canonical-url}`, and stop before worktree creation,
   code edits, or implementation delegation.

This is a readiness gate, not permission to publish. A current approved vault
plan carries prior approval forward only when Phase 2 does not change its goal,
scope, decisions, or acceptance contract.

### 1.6 Pre-flight checks

Run code checks against `{IMPLEMENTATION_TRUNK_ROOT}`. Ticket-forge authentication
still governs issue reads; implementation-forge authentication governs fetch and
later publication. The default branch was already fetched in Phase 1.4.

Verify each distinct forge role independently (deduplicate when both roles use the
same host):

- GitHub: `gh auth status`, then resolve repository/default branch with `gh`.
- Forgejo/Gitea/Codeberg: select the `tea login` whose URL hostname exactly
  matches that role and perform a bounded authenticated repository read. Never
  accept a configured login for another host or inspect/copy its token.

Then check the implementation working tree:

```bash
# Working tree clean? (modified or staged — ignore untracked)
git -C "{IMPLEMENTATION_TRUNK_ROOT}" status --porcelain | grep -E '^[ MADRC]'
```

If either required forge role cannot authenticate, stop. If the implementation
trunk is dirty (modified/staged, not just untracked), stop and offer stash /
commit / abort. Do not silently stash. Ticket-workspace or vault dirt that
overlaps the approved plan is a freshness/synchronization blocker handled by the plan gate;
unrelated ticket-workspace files do not contaminate the code worktree.

### 1.7 Create worktree

Use the [`worktrunk`](../worktrunk/SKILL.md) skill as the preferred controlled-worktree path.

1. **Compute slug, branch, and base.** "Same repository" means both canonical
   forge hostname and normalized owner/repository match. Only then use the
   established repo convention or `issue-{N}-{kebab-slug}`. Whenever either
   identity component differs, do not expose the private ticket host, repository,
   number, or title in a public branch. Compute `ticket_digest` as the first 16
   lowercase hex characters
   of SHA-256 over the exact canonical ticket URL and use
   `issue-xrepo-{ticket_digest}`. Retain the full URL-to-branch mapping only in
   private ticket-root state. Base ref = `origin/$DEFAULT_BRANCH`.
2. **Check for an existing worktree.** Run `wt list` (or Git's porcelain list).
   Reuse only the exact computed branch when the ticket-root `progress.md` records
   the same canonical ticket URL, implementation forge/repository, and branch.
   Any branch/worktree without matching state is a collision: stop rather than
   adopting it.
3. **Create from the fetched base.** From `{IMPLEMENTATION_TRUNK_ROOT}`, run `wt switch --create {branch} --base origin/$DEFAULT_BRANCH`. If `wt` is unavailable, use the controlled fallback against that same trunk.
4. **Operate in isolation.** Hermes runs subsequent file and terminal operations with the resulting absolute path as `workdir`; hosts with `EnterWorktree` may enter that path. Record it as `{WORKTREE_PATH}`.

Never switch the trunk checkout in place.

### 1.8 Write initial progress.md

```markdown
---
status: intake
ticket: {url-or-shorthand}
worktree: {abs-path}
branch: {branch-name}
base: {default-branch}
planning_base: {default-branch}
ticket_repository: {ticket-owner}/{ticket-repo}
implementation_forge: {implementation-host}
implementation_repository: {implementation-owner}/{implementation-repo}
implementation_trunk: {absolute-implementation-trunk}
plan_source: {vault|issue}
source_plan: {absolute-vault-note-path-or-empty}
issue_checked_through: {forge-updated-timestamp}
comments_checkpoint: sha256:{digest}
planning_base_revision: {full-sha}
started: {iso8601}
---

## Intake complete

- Context file: {TICKET_STATE_DIR}/context.md
- Worktree: {abs-path}
- Implementation repository: {implementation-host}/{implementation-owner}/{implementation-repo}
- Base branch/revision: {default-branch} at {full-sha}
- Plan source: {approved vault note | clear issue}
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
> Write your findings to `{TICKET_STATE_DIR}/explore-{area-slug}.md` where `{area-slug}` is a short kebab-case tag. One file per agent — never share a file between Explore agents.

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

- **Inputs:** `context.md`, the `explore-*.md` outputs from 2.1, any inline research from 2.2, and the validated vault note when `plan_source: vault`.
- **Plan-path override:** `{TICKET_STATE_DIR}/plan.md`. This keeps private planning state in the ticket workspace and out of the implementation worktree.

For a vault source, first compare exploration findings with its goal, scope,
accepted decisions, and acceptance contract. Any material mismatch is an
unconditional stop that routes back to `issue-plan`; do not synthesize a
superseding derived plan. Otherwise compile it into executor-ready tasks and
checkboxes rather than mutating the vault note. Record `plan_source: vault`,
`source_plan`, `source_plan_status: approved`, `source_plan_validated:
{iso8601}`, issue/comment checkpoints, and planning-base metadata in frontmatter.
For an issue source, synthesize the detailed execution plan from the issue's
planning authority and repository exploration, recording the same checkpoints
with `plan_source: issue`.

The result is a bite-sized, checkbox-task plan (exact file paths, code, evidence-shaped expected results, commit boundaries) — the shape Phase 3's executor consumes. Do not invent exact test counts or command output that was not run. Make sure frontmatter carries `status: planned` and `ticket: {url}` so Phase 0.2 resume and the 2.4 approval gate keep working against it.

### 2.4 Approval checkpoint

This is normally a hard stop. **Do not proceed to Phase 3 without explicit user approval or inherited approval from a current vault plan.**

When `plan_source: vault`, compare the derived plan against the approved source.
If synthesis only adds executor detail without changing the approved goal, scope,
decisions, or acceptance contract, record `approval: inherited` and the source
path in `plan.md`; present a concise validation/import summary and continue. Any
material change is an unconditional stop that routes back to `issue-plan`. It
cannot be approved only in the derived execution snapshot.

When `plan_source: issue`, present the full approval checkpoint:

Present the full `plan.md` contents inline to the user with a clear prompt:

> **Plan ready for review** — `{TICKET_STATE_DIR}/plan.md`
>
> {paste plan.md contents}
>
> Reply `approve` to begin implementation, or describe changes you'd like.

Then wait for the user's next message. Do not implement anything until you see an approval.

On an issue-sourced amendment, overwrite `plan.md` with the revised version, keep
`status: planned` in frontmatter, and re-present. Iterate until approved. For a
vault source, executor-only clarification may update the derived snapshot;
anything that changes goal, scope, decision, or acceptance routes back to
`issue-plan` without inline approval.

(If the harness happens to be in Plan Mode when this skill runs, `ExitPlanMode` is the harness-native approval gate and you can use it in place of the inline prompt above. Do not try to enter Plan Mode from inside the skill — that's not a thing.)

---

## Phase 3 — Implement

After user approval:

### 3.1 Update status

```bash
# Set progress.md frontmatter status: implementing
```

### 3.2 Execute the plan

`plan.md` (at the state-root path) is the source of truth. Mirror its checkboxes into the host task list (Hermes: `todo`). Then select exactly one execution path. This routing applies only inside `issue-work`; it does not prevent GPT from implementing ad hoc work outside this skill.

#### Hermes with a Codex-backed parent

The canonical ticket passed to `issue-work` is the existing governing issue for
the implementation handoff. Reuse it; never create a second implementation
ticket. If a caller reaches handoff preparation without a governing issue, stop
and follow `coding-agent-handoff-supervision`'s `issue-create` gate before any
worker is launched.

Select the implementation engine after plan approval, in this order:

1. **Explicit same-run override.** Honor an explicit Hermes, Qwen, Claude, or
   host-native GPT request. Qwen is available only through an explicit same-run
   request; plan approval alone never selects it.
2. **Default visible worker.** Otherwise select Claude through
   `coding-agent-handoff-supervision`, independent of forge or repository.

Resolve this decision with the skill's deterministic router, using `--override
auto` unless Bryan explicitly selected `--override hermes`, `qwen`, `claude`, or
`gpt`:

```bash
python3 <issue-work-skill-dir>/scripts/select_issue_worker.py \
  --workdir "{WORKTREE_PATH}" \
  --ticket-host "{ticket-host}" \
  --ticket-repo "{ticket-owner}/{ticket-repo}" \
  --implementation-host "{implementation-host}" \
  --implementation-repo "{implementation-owner}/{implementation-repo}" \
  --override auto
```

Load the exact skill named by `implementation_loop`; a `null` loop means the
explicit host-native GPT path. Preserve the router JSON in the state directory
as `implementation-routing.json`.

The ticket repository and implementation repository may differ only through the
validated handoff. The approved implementation hostname and owner/repository must
match the worktree origin before routing. A similarly named checkout, lookalike
forge, or unrelated repository cannot satisfy this identity gate. Missing
prerequisites stop the run.

For the visible Claude or Hermes path:

1. Require Herdr for visible Claude or Hermes. Verify `HERDR_ENV=1`, the exact
   caller pane, and a compatible injected `HERDR_BIN_PATH`; stop if any are
   unavailable. Agent View and background wrappers cannot represent the
   persisted correction identity and are not fallbacks for this route.
2. Record the worktree's baseline status, then follow
   `coding-agent-handoff-supervision`. Use Herdr kind `claude` for automatic or
   explicit Claude routing and kind `hermes` only for an explicit Hermes
   selection. Preserve the caller's focus and attach a finite watcher.
3. Send a short handoff containing only the ticket URL, verified implementation
   repository and worktree, authority boundaries, and delivery permissions. The
   worker must inspect the ticket and repository instructions itself. Do not
   duplicate `plan.md`, the complete ticket body, or the parent's exploration in
   the prompt.
4. Use one authority rule: the default visible handoff forbids staging, local
   commit creation, push, PR or issue mutation, and every other publication
   action; the worker may edit and test only in the named worktree. Each broader
   action requires its own explicit same-run user approval. Publication approval
   still passes through Phase 4's ship/public-action gate; worker permission
   never bypasses that gate or follows from implementation approval.
   Destructive and history-rewriting Git operations are absolute and not
   approval-eligible: the worker must never run `git reset`, `git clean`, a
   checkout-discard operation, `rebase`, `commit --amend`, any other history
   rewrite, or `force-push`; delete or overwrite any local ref or branch,
   including branch deletion and `git update-ref -d` update-ref deletion, is
   likewise forbidden.
5. Start Claude with `acceptEdits`; start Hermes only with normal smart approvals
   and no yolo. Stop if approval state is disabled or unverifiable. This route is
   approval-gated, not sandbox-confined; if hard confinement is required but
   unavailable, stop.
6. Record `implementation_loop: coding-agent-handoff-supervision` and persist all
   six distinct fields in `progress.md`: `worker_surface: herdr`,
   `worker_agent_name`, `worker_pane_id`, `worker_kind`,
   `worker_runtime_session_id`, and `worker_worktree_identity` (canonical
   worktree root, Git common directory, and branch). Preserve the worker's final
   report in `{state-dir}/visible-worker-implementation.md`.

For the explicit Qwen path, run `qwen_worker.py check`, then its `implement`
command with `plan.md` and `{WORKTREE_PATH}`. Pin the exact local provider and
model, permit no cloud fallback, save the normalized envelope as
`{state-dir}/qwen-implementation.json`, and record
`implementation_loop: codex-qwen-implementation-loop` plus its session ID.

For every delegated path:

1. Codex reviews the actual repository diff and independently reruns every
   targeted and broader check required by the plan. Worker reports and JSON are
   evidence, not the verdict.
2. For blocking findings, write `{state-dir}/codex-review-{pass}.md` and continue
   the same worker. For Claude or Hermes, before and after every correction
   prompt compare all six persisted identity fields with `herdr agent get` and
   freshly recomputed Git worktree identity. Any incomplete legacy state,
   missing agent, or mismatch stops; never launch a duplicate. For Qwen, use its
   original session ID with `revise`. Repeat the complete Codex gate after each
   revision; cap the correction loop at two revision passes.
3. Mark plan/task checkboxes complete only after Codex accepts the final
   repository state. Preserve every implementation and revision artifact in the
   state directory.

After the complete Codex gate passes, the parent may create local commits at the
approved plan's logical boundaries, staging only reviewed paths and preserving
the repository's message and hook rules. Those parent-owned commits do not alter
the worker authority recorded above. Plan approval authorizes the parent's local
implementation commits; push, PR, comment, or other publication still requires
the ship/public-action gate.

When Bryan explicitly selects GPT implementation, execute task-by-task with the host-native workflow below while retaining the same plan, test, failure, and independent-review gates.

#### Other hosts or a non-Codex Hermes parent

Execute task-by-task with the host-native workflow. Load `tdd` for behavior changes; the approved `plan.md` is where the test seam was pre-agreed, which is what lets this run unattended. Escalate repeated failures per 3.5. Pass through:

- **plan_path:** `{TICKET_STATE_DIR}/plan.md`
- **worktree path:** the absolute path from `progress.md`
- **commit rules:** atomic (one logical unit per commit); message style matches `git log --oneline -20` in **this repo** (not global defaults); **never** add `Co-authored-by: Claude` or any AI signature; **never** use `--no-verify`.
- **failure policy:** hand off the 3.5 escalation rule below — on a task whose tests fail, attempt a direct fix first; on a **second** consecutive failure of the same task, escalate per 3.5; hard cap at 3 attempts, then stop and report. Delegated Claude, Hermes, and Qwen paths instead use their two-revision bound above.

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

On the host-native path, first failure of a task's tests: attempt a direct fix → commit → rerun. **Second consecutive failure of the same task:** load `diagnosing-bugs` rather than guessing again — it builds a tight failing loop and tests ranked hypotheses instead of applying another patch. **Hard cap at 3 attempts total.** On the 4th failure, stop and report the failing output to the user.

On either delegated path, Codex first determines whether the failure is a plan defect, implementation defect, pre-existing failure, or external blocker. Send implementation defects back through the same retained worker session under the two-revision bound. A plan defect, ambiguity, destructive conflict, unavailable selected worker, or exhausted revision budget stops for the user instead of switching workers or guessing.

### 3.6 Progress log

After each test run, append to `progress.md`:

```markdown
## {iso8601} — commit {sha7}

{one-line commit subject}

Tests: {pass/fail summary}
Lint/typecheck: {summary}
```

For either delegated path, also record the implementation/revision artifact path, worker-reported checks, Codex-rerun checks, and Codex gate verdict. Never collapse worker claims and Codex's fresh results into one line.

Do not advance `status` when tests go green — Phase 4 bumps it to `reviewed` after self-review completes. Leave it at `implementing` until then.

### 3.7 Repository planning closeout

Re-read the worktree's active project instructions. If they identify tracked
specs, plans, status notes, decision records, or other living planning
artifacts, reconcile them before self-review. Record completed milestones,
verified findings, changed assumptions, closed or newly opened questions, and
the next tracked work where applicable. These updates belong in the same
feature branch and PR as the implementation.

If no tracked planning artifact needs a change, record the inspected files and
the reason in `progress.md` under `## Planning closeout`. Do not proceed to
final verification until the required updates are in the diff or the no-update
rationale is recorded. External vault capture remains governed by
`vault-capture`; this gate covers repository-owned planning artifacts required
by project instructions.

### 3.8 Verify before handing off

Before Phase 4 spawns review, prove the suite is green rather than trust the implementation context. If Phase 3 used either delegated implementation loop, its final Codex review/retest gate satisfies this step; cite that fresh gate output rather than spawning a duplicate generic reviewer, and rerun only checks invalidated by the parent's post-gate local commit operation. Otherwise use a verification context independent of the one that wrote the code, rerun the project's test / lint / typecheck commands, and preserve actual output.

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

Before issue-work may invoke ship, it must launch a fresh visible Claude reviewer
through Herdr in a new Herdr agent, pane, and runtime session. This reviewer is
separate from every implementation worker and is the only context allowed to
run Phase 4's final review. Herdr or fresh Claude unavailability stops the run;
there is no Agent View, wrapper, native-parent, serial, or ad-hoc fallback.
Earlier parent reviews and ad-hoc reviews cannot satisfy this gate.

First freeze the exact final candidate after all implementation commits and with
an empty worktree. Record `base_sha`, `head_sha`, `merge_base_sha`, and
`diff_sha256` using the same canonical binary-diff fingerprint required by
`pr-self-review`, plus `expected_head_branch`. Any later candidate change makes
all review artifacts stale. Require the implementation worker to be settled and
prevent concurrent edits while the reviewer examines this candidate.

Then use `coding-agent-handoff-supervision` to start a new `--kind claude`
reviewer in the implementation worktree. Persist and pass:

- `reviewer_surface: herdr`;
- `reviewer_agent_name`;
- `reviewer_pane_id`;
- `reviewer_kind: claude`;
- `reviewer_runtime_session_id`;
- `reviewer_worktree_identity`.

The reviewer must be distinct from the implementation worker: require a new
agent name, pane ID, and runtime session ID, and compare them against
`worker_agent_name`, `worker_pane_id`, and `worker_runtime_session_id` when that
visible implementation identity exists. Equal, missing, reused, legacy, or
unverifiable identity blocks review. The shared worktree identity must match the
frozen candidate exactly.

Prompt the fresh reviewer with the ticket URL, implementation repository and
worktree, plan path, state directory, frozen candidate identity, review-only
authority, and the original implementation-worker identity used only for
correction routing. The fresh visible Claude reviewer must load
[`pr-self-review`](../pr-self-review/SKILL.md) in `pre-pr` mode and run Standards,
Spec, conditional Risk, mandatory Ponytail, the acceptance-criteria sweep, and
the Ship Readiness verdict. Start a finite watcher and fail closed on blocked,
missing, replaced, or settled-without-artifacts review state.

Before delegation, run
`scripts/validate_cross_repo_context.py` with the recorded ticket trunk/state,
canonical ticket URL/identity, implementation worktree, and implementation
identity. Save its successful JSON as `{TICKET_STATE_DIR}/context-validation.json`.
Failure blocks review; prose comparison is not a substitute for this executable
identity/state gate.

```bash
python3 <issue-work-skill-dir>/scripts/validate_cross_repo_context.py \
  --ticket-trunk "{TICKET_TRUNK_ROOT}" \
  --state-dir "{TICKET_STATE_DIR}" \
  --worktree "{WORKTREE_PATH}" \
  --ticket-url "{canonical-ticket-url}" \
  --ticket-host "{ticket-host}" \
  --ticket-repo "{ticket-owner}/{ticket-repo}" \
  --implementation-host "{implementation-host}" \
  --implementation-repo "{implementation-owner}/{implementation-repo}" \
  > "{TICKET_STATE_DIR}/context-validation.json"
```

- `mode`: `pre-pr`
- `state_dir`: `{TICKET_STATE_DIR}`
- `ticket_trunk_root`: `{TICKET_TRUNK_ROOT}` — authorizes confinement of the
  private caller state independently from the implementation worktree's Git root
- `context_validation_path`: `{TICKET_STATE_DIR}/context-validation.json`
- `ticket_url`: `{canonical-ticket-url}`
- `ticket_host`: `{ticket-host}`
- `ticket_repo`: `{ticket-owner}/{ticket-repo}`
- `implementation_host`: `{implementation-host}`
- `implementation_repo`: `{implementation-owner}/{implementation-repo}`
- `worktree_path`: the absolute path from `progress.md`
- `head_branch`: the value from `progress.md` `branch:`; pr-self-review uses it for branch-drift checks because no PR-derived `headRefName` exists yet
- `base_branch`: the value from `progress.md` `base:`
- `plan_path`: `{TICKET_STATE_DIR}/plan.md`
- `reviewer_surface`, `reviewer_agent_name`, `reviewer_pane_id`,
  `reviewer_kind`, `reviewer_runtime_session_id`, and
  `reviewer_worktree_identity`: the fresh Claude reviewer's persisted Herdr
  identity.
- `exact_candidate`: full `base_sha`, `head_sha`, `merge_base_sha`,
  `diff_sha256`, and `expected_head_branch` frozen immediately before reviewer
  launch.
- `source_issue`: pass `{ticket-owner}/{ticket-repo}#{N}` only when the verified
  `context-validation.json` says `source_issue_mode: github_shorthand`. Omit it
  for Forgejo/Codeberg/Gitea and every cross-repository or cross-forge handoff;
  the current `pr-self-review` shorthand resolver is GitHub-only, so `plan_path`
  remains intent authority on those routes. Never let a hostless identifier
  resolve against the wrong forge. Private ticket identity must not flow into
  public artifacts.
- `implementation_loop`: the exact selected value,
  `coding-agent-handoff-supervision` or `codex-qwen-implementation-loop`.
- For `coding-agent-handoff-supervision`, pass every persisted value distinctly:
  `worker_surface`, `worker_agent_name`, `worker_pane_id`, `worker_kind`,
  `worker_runtime_session_id`, and `worker_worktree_identity`. Omit
  `worker_session_id`; it is reserved for wrapper sessions.
- For `codex-qwen-implementation-loop`, pass `worker_session_id` and omit all
  visible-worker identity fields. Native paths omit both contracts.

The fresh reviewer writes `review-standards.md`, `review-spec.md`,
`review-risk.md` when selected, mandatory `review-ponytail.md`,
`intent-checklist.json`, and `summary.md` into the state dir. Every artifact must
record the exact final candidate's `base_sha`, `head_sha`, `merge_base_sha`, and
`diff_sha256`; the summary must record current lane selection, acceptance-
criteria results, and Ship Readiness.

Accepted corrections preserve the implementation identity contract. A
candidate-changing fix goes to the original implementation worker, never the
fresh reviewer. After the parent accepts and commits the fix, the same fresh
reviewer must re-run the complete exact-candidate gate—Standards, Spec,
conditional Risk, mandatory Ponytail, acceptance-criteria sweep, and Ship
Readiness—before ship. Any candidate-changing fix invalidates every prior review
artifact; partial, affected-lane-only, or earlier-review reuse is forbidden.

After the fresh reviewer returns, revalidate both its complete Herdr identity and
the current candidate fingerprint. Require all selected primary artifacts,
mandatory `review-ponytail.md`, `intent-checklist.json`, and `summary.md` to match
that fingerprint. A missing or stale artifact, incomplete sweep, reviewer drift,
candidate drift, open blocking verdict, or any Ship Readiness value other than
ready blocks the run. Only then set `progress.md` `status: reviewed` and continue.

### 4.3 Present to user and ask for ship approval

Present the review outcome inline in this order:

1. **Headline** — the one-line summary from `summary.md`.
2. **Critical + Major findings** — full bullets, not just counts. If none, say so explicitly ("No critical or major findings").
3. **Minor / Nit counts** — single line, e.g. "Minor: 3, Nit: 1. Full detail in review-*.md."
4. **Lane selection** — which primary lanes ran, and why Risk did or did not.
5. **Ponytail selection/status** — mandatory and selected, plus clean/findings/blocker status from `summary.md`.
6. **Paths** — `summary.md`, each written primary `review-{lane}.md`, and required `review-ponytail.md`, as clickable Markdown links when the surface supports them.
7. **Ship prompt.** End the message with a direct question — do not stop silently:

   > Ready to push the branch and open the draft PR? Reply `ship it` to proceed, or flag anything you want changed first.

   On `ship it` (or equivalent approval like "yes", "go", "push"), first
   recompute the candidate fingerprint and re-read the fresh reviewer's current
   `summary.md` Ship Readiness verdict. Any mismatch stops. Only then **load the
   [`ship` skill](../ship/SKILL.md)** — do not run `git push` / `gh pr create`
   directly. `ship` preserves draft-PR defaults, forge-specific creation,
   PR-template fidelity, and labels.

   For same-repository work, `/ship` may use `{TICKET_STATE_DIR}/summary.md`.
   For private cross-repository work, first derive
   `{TICKET_STATE_DIR}/publication-summary.md` containing only public-safe
   implementation outcome, changed surfaces, and verified checks. Programmatically
   verify it contains none of the private ticket URL, host, owner/repository,
   title, vault paths, or ticket-state paths; then tell `/ship` to use that file.
   The branch, commit messages, PR title/body, and labels must not disclose the
   private ticket identity without explicit publication approval.

   On anything ambiguous: ask again, do not ship. Do not treat silence as approval.

**Do not auto-ship before this exchange.** The review summary on its own isn't consent — the user needs one more explicit step after reading it.

---

## Edge Cases

| Case | Behavior |
|---|---|
| Worktree already exists for this ticket | Reuse only the exact namespaced branch when `progress.md` matches the canonical ticket and implementation identity; otherwise stop on collision |
| Trunk dirty (modified/staged) | Stop. List files. Offer stash / commit / abort |
| Ticket is a PR (review work, not new work) | Fetch the PR head, create/reuse a controlled `wt` worktree without switching trunk, swap Phase 3 for "review against plan"; Phase 4 reviewers still run |
| Tests fail (2nd time on a task) | Load `diagnosing-bugs`; hard cap 3 attempts, then stop and surface output |
| Critical review findings | Present prominently; recommend fix-before-ship; never auto-ship |
| User amends an issue-sourced plan | Overwrite `plan.md`; reset status `planned`; re-present inline and await approval again (see Phase 2.4) |
| User materially amends a vault-sourced plan | Stop and route to `issue-plan`; never supersede the canonical vault authority in derived state |
| Approved vault plan is current | Import/compile it, record freshness validation, and inherit approval when no material planning contract changed |
| Vault plan has material drift | Stop before worktree creation and route back to `issue-plan`; do not patch the vault note during intake |
| No approved vault plan, but issue passes all five criteria | Record `plan_source: issue`, continue to exploration/synthesis, and use the normal Phase 2.4 approval gate |
| Neither vault plan nor issue passes | List missing criteria, recommend `issue-plan {url}`, and stop before dirty-tree checks/worktree/implementation |
| Legacy resume state lacks plan-source/checkpoint metadata | Do not reuse its worktree; refresh intake and validate authority first |
| Repo not cloned locally | Ask before `gh repo clone` to `~/code/{repo}` |
| Forgejo ticket | Intake uses the REST API in `references/fetch-ticket.md`; everything else is identical |
| Pasted raw text (no URL) | Skip fetch; ask user for repo; `context.md` has only Body |
| User says "refresh" on a resumed ticket | Overwrite prior state files; restart from Phase 1 |

---

## Things This Skill Does NOT Do

- Ship without explicit approval — Phase 4.3's ship gate is mandatory; silence is not consent. On `ship it` the skill hands off to `/ship`, which handles the push + PR creation.
- Modify files outside the worktree and the state dir. Approved project-vault plans are read-only inputs; vault changes route through `issue-plan` or `vault-capture`.
- Add AI signatures to commits or PRs
- Skip hooks (`--no-verify`) or bypass signing
- Create or silently amend external vault notes. It may read an approved
  `issue-plan` note and derive state under the ticket workspace's `.hermes/issue-work/`.
  Repository-owned planning artifacts required by project instructions are
  implementation files and follow the Phase 3.7 closeout gate.

---

## References

Detailed recipes that load on demand:

- [references/fetch-ticket.md](references/fetch-ticket.md) — exact gh/tea CLI commands, pagination, rate limits, Forgejo API auth
- [references/repo-resolution.md](references/repo-resolution.md) — local clone discovery, remote URL matching, clone-if-missing prompt
- [`issue-plan` handoff contract](../issue-plan/references/handoff-contract.md) — vault-plan discovery, freshness, import metadata, and clear-issue fallback rubric

## Related Delegation Roles

- Intake child — Phase 1 fetch + digest; use `delegate_task`, `Task`, or `Agent` when available.
- Review-dimension reviewer — Phase 4 reviewer with a `lane` argument (`standards` | `spec` | `risk` | `ponytail`); primary lanes run in a host-appropriate batch and Ponytail runs last.

## Related Skills

- `pr-self-review` — Phase 4 delegates here for the lane-selected autonomous review-and-fix loop.
- `tdd` — Phase 3 implementation discipline; the plan pre-agrees the seam.
- `diagnosing-bugs` — Phase 3.5 second-failure escalation.
- `code-review` — owns the Standards, Spec, Risk, and mandatory Ponytail definitions `pr-self-review` dispatches.
- `ship` — Phase 4.3 hands off here on `ship it` for push + PR creation + template fill + label application.
- `issue-plan` — prepares and approves the preferred durable vault-backed plan before implementation.
- `vault-pkm` — resolves and reads project-vault plans without bypassing local vault rules.
- `worktrunk` — Phase 1.7 controlled worktree setup.
- `plan` — Phase 2.3 Hermes plan authoring (path-overridden to the state root).
- `coding-agent-handoff-supervision` — default ticket-backed visible Claude
  handoff and the explicit visible Hermes route.
- `codex-qwen-implementation-loop` — explicit same-run local Qwen route.

### Optional Delegation

Soft references — the skill works without them, but if the host environment has them installed they can be invoked on demand during a run:

- `engineering:testing-strategy` — optional, when Phase 2 exploration surfaces a test-architecture gap deep enough to warrant its own plan
