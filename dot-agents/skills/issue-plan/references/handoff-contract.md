# Issue-plan handoff contract

This is the shared boundary between `issue-plan` and `issue-work`. The vault note
is the durable planning authority; `.hermes/issue-work/.../plan.md` is a derived
execution snapshot.

## Repository roles

A project workspace may keep its issue tracker and private vault separate from
the public implementation repository. The contract therefore distinguishes:

- **Ticket repository** — owns the canonical issue, comments, private project
  workspace, vault discovery, and repo-scoped execution state.
- **Implementation repository** — owns the code, fetched planning base, feature
  worktree, commits, tests, and eventual PR.

The ticket repository and implementation repository may differ only when an
approved vault plan records the complete explicit binding below. An issue-as-plan
fallback always implements in the ticket repository because it has no separate
approved binding authority.

## Required section

Every newly written canonical issue plan contains this body section exactly once:

```markdown
## Issue plan handoff

- Issue: https://github.com/owner/private-workspace/issues/123
- Planning status: draft
- Issue checked through: 2026-07-20T17:30:00Z
- Comments checkpoint: sha256:0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef
- Ticket repository: owner/private-workspace
- Implementation forge: github.com
- Implementation repository: owner/public-project
- Implementation base: main
- Implementation revision: 0123456789abcdef0123456789abcdef01234567
```

Forgejo uses its canonical issue URL in the same `Issue` field. `Planning status`
is exactly `draft` or `approved`. The issue timestamp is the forge's
`updatedAt`/`updated_at` value. `Comments checkpoint` is the canonical SHA-256
digest defined in `issue-work`'s ticket-fetch reference.

`Ticket repository` must equal the owner/repository parsed from `Issue`.
`Implementation forge` is the lowercase hostname of the implementation clone's
canonical forge. `Implementation repository` is its exact owner/repository.
`Implementation base` is the fetched default branch and `Implementation revision`
is the full remote-base SHA inspected during planning, never an arbitrary local
`HEAD`. Same-repository plans repeat the same owner/repository in both repository
roles so the authority remains explicit.

### Legacy same-repository form

Plans written before this contract may still contain `Repository`, `Repository
base`, and `Repository revision`. They are consumable only when `Repository`
exactly matches the issue repository, the implementation origin owner/repository,
and the implementation origin hostname equals the issue forge hostname.
Legacy fields can never authorize a cross-repository handoff. Reopened plans are
upgraded to the explicit form above.

Vault-local frontmatter remains owned by `vault-pkm`; do not add conflicting
frontmatter merely for this contract.

## Required plan content

The same note must make these statements unambiguous, using vault-native headings
and links:

- Goal and externally observable outcome.
- Scope and non-goals.
- Accepted implementation/design decisions.
- Implementation approach and ordered tasks.
- Exact likely files/components grounded in implementation-repository inspection.
- Test and validation strategy.
- Risks, migration/rollout needs when applicable, and non-blocking open questions.

An approved plan has no unresolved load-bearing product or architecture decision.
Supporting explorations, ADRs, specs, and DX targets may be separate linked notes;
the handoff note remains the canonical implementation plan.

## `issue-plan` grounding

`issue-plan` first resolves the ticket repository and project vault. If the user
or existing project authority identifies a different implementation repository,
it must then:

1. Resolve that implementation clone independently without moving, cloning, or
   choosing a lookalike checkout silently.
2. Verify its origin hostname and owner/repository against the intended binding.
3. Resolve and fetch its actual default branch.
4. Inspect code, tests, instructions, specs, and patterns against that fetched
   remote revision.
5. Record the explicit fields above before approval.

The ticket clone remains the workspace/vault authority. The implementation clone
is the code authority. A dirty checkout is never used as planning provenance.

## `issue-work` discovery and binding

`issue-work` resolves the ticket trunk first and stores state under:

```text
{TICKET_TRUNK_ROOT}/.hermes/issue-work/{ticket-owner}-{ticket-repo}-{N}/
```

It checks project-vault candidates in order:

1. A vault path explicitly named by ticket-workspace instructions.
2. `{TICKET_TRUNK_ROOT}/vault` when it is a directory or symlink.
3. For same-repository work only, an implementation-instruction path,
   `{IMPLEMENTATION_TRUNK_ROOT}/vault`, or
   `~/code/notes/{implementation-repo}` when it clearly belongs to the project.

Cross-repository canonical plans must be ticket-discoverable through candidate 1
or 2. This avoids a cold-start cycle where the plan is required to discover the
implementation repository but is stored behind that still-unknown repository.

A candidate is consumable only when:

- It contains exactly one handoff section.
- `Issue` exactly matches the current canonical URL.
- `Planning status` is `approved`.
- `Ticket repository` matches the issue owner/repository.
- `Implementation forge` and `Implementation repository` match the resolved
  implementation clone's origin.
- `Implementation base` matches its current default branch.
- All required plan content exists.
- No linked decision/spec is still draft or unresolved.

If multiple approved candidates disagree, `issue-work` stops instead of choosing
one silently. It never treats similar names, equal bytes, directory proximity, or
a workspace-relative path as repository identity evidence.

## Freshness validation

Before importing a plan, `issue-work` fetches the current issue and every comment
ID/update timestamp/body, then compares both the issue timestamp and canonical
comment checkpoint. It resolves and fetches the implementation repository's
current default branch before comparing its remote-base SHA with
`Implementation revision`; when the revision has moved, it inspects relevant
changed paths before deciding whether drift is material.

Drift is **material** when it changes any of:

- Goal, scope, non-goals, or acceptance criteria.
- A load-bearing decision or API/DX shape.
- Relevant implementation patterns or exact target paths.
- Migration, rollout, compatibility, or test requirements.
- Ticket/implementation repository identity or forge ownership.

Timestamp or commit movement by itself is not material. If drift is immaterial,
`issue-work` records the validation in execution state and imports the plan. If
drift is material, it stops and asks the user to reopen `issue-plan`; it never
silently edits an approved vault plan during implementation intake.

## Derived execution snapshot

A validated plan is copied or compiled into the ticket-root state directory. The
derived plan records:

```yaml
plan_source: vault
source_plan: /absolute/path/to/vault/note.md
source_plan_status: approved
source_plan_validated: <iso8601>
issue_checked_through: <forge-updated-timestamp>
comments_checkpoint: sha256:<digest>
ticket_repository: <owner/repo>
implementation_forge: <hostname>
implementation_repository: <owner/repo>
planning_base: <implementation-default-branch>
planning_base_revision: <full-implementation-sha>
implementation_trunk: /absolute/path/to/implementation-trunk
```

The executor mutates checkboxes only in the derived snapshot. The implementation
worktree, tests, commits, and PR operate only in the implementation repository.
Repository-owned planning closeout and later `vault-capture` remain separate.

## Clear-issue fallback

When no consumable vault plan exists, `issue-work` may use the current issue and
comments as planning authority only if all five criteria pass. The implementation
repository defaults to the ticket repository; issue prose alone cannot redirect
execution to another repository.

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

If any criterion fails, `issue-work` lists the missing planning inputs, recommends
`issue-plan {url}`, and stops before dirty-tree checks, worktree creation, code
edits, or implementation delegation.
