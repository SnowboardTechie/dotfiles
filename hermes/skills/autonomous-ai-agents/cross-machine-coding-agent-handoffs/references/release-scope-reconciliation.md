# Reconciling release scope after implementation

Use this reference when maintainer feedback changes *where* a fix should land after an implementation agent has already produced an upstream or library branch.

## Distinguish four states

- **Technically verified:** the branch's code and tests are sound.
- **Accepted for this delivery:** maintainers want this artifact in the current release train.
- **Parked:** technically useful work is preserved by branch/SHA but intentionally has no PR in the current train.
- **Superseded approach:** a narrower delivery route replaces the prior plan; historical notes should point to the new route.

Do not collapse these into “done” or “rejected.” A clean branch can be parked, and a small consumer change can be the accepted release fix.

## Consumer-workaround probe

When a maintainer asks to fix the current consumer rather than change the upstream SDK:

1. Fetch the consumer branch and exact upstream base/dependency revision.
2. Create disposable worktrees; do not experiment on the user's active branch.
3. Install/build the exact local dependency artifact the release will use. Confirm the installed bytes/version come from that artifact rather than a stale registry or wheel.
4. Record the baseline static failures.
5. Apply only the proposed consumer-side adaptation in the disposable tree.
6. Run formatter/linter/type checker and the full consumer test suite.
7. Exercise runtime values and serialized wire output explicitly. Static success alone does not prove aliased constructor values are consumed rather than silently dropped.
8. Restore/remove disposable worktrees; do not imply the real branch changed.

## Alias-specific example

A Pydantic model may expose camelCase aliases in its generated constructor signature while storing snake_case Python attributes. If a consumer currently uses a snake_case keyword that pyright rejects and Pydantic ignores, using the SDK's declared alias keyword can be the correct release-local adaptation:

- verify the alias keyword type-checks;
- assert the Python attribute retains the supplied value;
- assert `model_dump(by_alias=True)` emits the expected wire key;
- test every occurrence, including adjacent alias failures surfaced by the same static-check migration.

This does not settle the long-term SDK ergonomics. Keep broader `populate_by_name` or alias-generator work in a separately reviewed follow-up.

## Reporting and notes

State clearly:

- what was tested only in a disposable worktree;
- what has actually been committed or pushed;
- which broader branch is parked and at what SHA;
- the maintainer's accepted release route;
- the next release step.

Reconcile the status page, active plan, and technical topic note. Preserve the earlier review as historical evidence, then add an explicit superseding delivery note so another agent does not resurrect the old sequence.
