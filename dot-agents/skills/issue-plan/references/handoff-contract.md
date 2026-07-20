# Issue-plan handoff contract

This is the shared boundary between `issue-plan` and `issue-work`. The vault note
is the durable planning authority; `.hermes/issue-work/.../plan.md` is a derived
execution snapshot.

## Required section

Every canonical issue plan contains this body section exactly once:

```markdown
## Issue plan handoff

- Issue: https://github.com/owner/repo/issues/123
- Planning status: draft
- Issue checked through: 2026-07-20T17:30:00Z
- Comments checkpoint: sha256:0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef
- Repository: owner/repo
- Repository base: main
- Repository revision: 0123456789abcdef0123456789abcdef01234567
```

Forgejo uses its canonical issue URL in the same `Issue` field. `Planning status`
is exactly `draft` or `approved`. The issue timestamp is the forge's
`updatedAt`/`updated_at` value from the planning fetch. `Comments checkpoint` is
the canonical SHA-256 digest defined in `issue-work`'s ticket-fetch reference.
`Repository base` is the fetched default branch and `Repository revision` is the
full remote-base commit SHA inspected during planning, never an arbitrary local
`HEAD`.

Vault-local frontmatter remains owned by `vault-pkm`; do not add conflicting
frontmatter keys merely for this contract. The body section is deliberately
portable across vault schemas and searchable by hosts that lack an Obsidian
index.

## Required plan content

The same note must make these statements unambiguous, using vault-native headings
and links:

- Goal and externally observable outcome.
- Scope and non-goals.
- Accepted implementation/design decisions.
- Implementation approach and ordered tasks.
- Exact likely files/components grounded in repository inspection.
- Test and validation strategy.
- Risks, migration/rollout needs when applicable, and non-blocking open questions.

An approved plan has no unresolved load-bearing product or architecture decision.
Supporting explorations, ADRs, specs, and DX targets may be separate linked notes;
the handoff note remains the canonical implementation plan.

## `issue-work` discovery

After resolving the repository, `issue-work` checks these project-vault candidates
in order:

1. A vault path explicitly named by project instructions.
2. `{TRUNK_ROOT}/vault` when it is a directory or symlink.
3. `~/code/notes/{repo}` when it exists and clearly belongs to the repository.

It loads `vault-pkm`, reads vault-local instructions and the entry point, then
searches for the exact canonical issue URL. A candidate is consumable only when:

- It contains exactly one handoff section.
- `Issue` exactly matches the current canonical URL.
- `Planning status` is `approved`.
- `Repository` matches the resolved origin owner/repo.
- `Repository base` matches the current default branch.
- All required plan content exists.
- No linked decision/spec is still draft or unresolved.

If multiple approved candidates disagree, `issue-work` stops instead of choosing
one silently.

## Freshness validation

Before importing a plan, `issue-work` fetches the current issue and every comment
ID/update timestamp/body, then compares both the issue timestamp and canonical
comment checkpoint. It resolves and fetches the current default branch before
comparing its remote-base SHA with `Repository revision`; when the revision has
moved, it inspects relevant changed paths before deciding whether drift is
material.

Drift is **material** when it changes any of:

- Goal, scope, non-goals, or acceptance criteria.
- A load-bearing decision or API/DX shape.
- Relevant implementation patterns or exact target paths.
- Migration, rollout, compatibility, or test requirements.

Timestamp or commit movement by itself is not material. If drift is immaterial,
`issue-work` records the validation in execution state and imports the plan. If
drift is material, it stops and asks the user to reopen `issue-plan`; it never
silently edits an approved vault plan during implementation intake.

## Derived execution snapshot

A validated plan is copied or compiled into:

```text
{TRUNK_ROOT}/.hermes/issue-work/{owner}-{repo}-{N}/plan.md
```

The derived plan records:

```yaml
plan_source: vault
source_plan: /absolute/path/to/vault/note.md
source_plan_status: approved
source_plan_validated: <iso8601>
issue_checked_through: <forge-updated-timestamp>
comments_checkpoint: sha256:<digest>
planning_base: <default-branch>
planning_base_revision: <full-sha>
```

The executor mutates checkboxes only in the derived snapshot. It does not turn
implementation progress into churn in the durable vault note. Repository-owned
planning closeout and later `vault-capture` remain separate workflows.

## Clear-issue fallback

When no consumable vault plan exists, `issue-work` may use the current issue and
comments as planning authority only if **all** of these pass:

1. **Outcome:** the problem and externally observable result are clear.
2. **Boundary:** scope is bounded; non-goals are explicit or safely implied by a
   narrow change.
3. **Acceptance:** success is testable from stated criteria, a reproduction plus
   expected behavior, or an equally concrete verification contract.
4. **Direction:** constraints and established repository patterns provide enough
   implementation direction to produce an exact execution plan without choosing
   product behavior or architecture on the user's behalf.
5. **Decisions:** no unresolved load-bearing question remains in the body,
   comments, linked issue, or inspected implementation surface.

A concise bug can pass when it has a reproducible failure, expected behavior, a
bounded surface, and a clear regression-test path. Length, labels, assignment,
or milestone membership do not make an issue plan-ready.

If any criterion fails, `issue-work` lists the missing planning inputs, recommends
`issue-plan {url}`, and stops before dirty-tree checks, worktree creation, code
edits, or implementation delegation. Ticket reads, default-branch fetch, and the
bounded read-only inspection are intake prerequisites for making this verdict,
not permission to begin implementation.
