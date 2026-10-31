# Draft → ready for review

Use this when Bryan asks "is this PR ready to open for review?" or "mark it ready and
tag <reviewer>". It continues `ship` after the draft PR exists.

## Readiness check (read-only; answer before changing anything)

1. `gh pr view N --json isDraft,headRefOid,mergeable,mergeStateStatus,statusCheckRollup,reviewRequests,body,commits,files`.
   Checks must be green **on the current head SHA**, and mergeState should be CLEAN.
2. Clone fresh into scratch and `git fetch origin pull/N/head:pr-N`. Confirm the
   branch contains the current base (`git merge-base --is-ancestor origin/main pr-N`).
3. Check the description against the diff. Every bullet should match a change,
   lock bumps should match `git diff -- <lockfile> | grep -E '^[-+](name|version) ='`,
   and claims like "newest release" should be checked at the source (e.g. PyPI JSON).
4. Look for leftovers the change should have caught. For a rename or version
   bump, `git grep` the head for the old spelling or version, including in
   `.github/` issue templates and docs. Keep wire-format matches, such as camelCase
   in HTTP query strings, and don't count them as leftovers.
5. Make sure the body follows the repo's `pull_request_template.md`.
6. Report a verdict, the evidence behind it, and any optional nits. Name the
   reviewers to request (derive them from recent review activity) and offer to
   make each nit. Don't edit anything yet.

## Applying the go-ahead

- One request ("bump X, mark ready, tag Y") authorizes the edit, commit, push,
  description update, `gh pr ready N` and `gh pr edit N --add-reviewer Y`. Don't
  ask again between those steps.
- Commit with the identity the branch's existing commits use. Push, then confirm
  the remote SHA equals local HEAD.
- Add a bullet to the PR description for each new commit. Write the body to a
  file, change only that section, and save it with `gh pr edit --body-file`.
- **After every push, watch CI on the new head before reporting**
  (`gh pr checks N --watch`). A trivial docs commit can still go red:
  dependency-audit jobs (pip-audit, npm audit) query live advisory databases,
  so CVEs published since the last green run fail an unchanged lock.
- An audit failure that comes from new advisories is in-lane work. Clear it in
  a separate `fix(deps)` commit that updates only the named packages (e.g.
  `poetry update <pkg> <pkg>`). Check that the lock diff changes only those
  versions, then run the repo's CI and audit targets locally before pushing.
  List each package with old → new version and CVE in the description.
- Finish by reading back: not draft, reviewers requested, head SHA, CLEAN, and
  every check SUCCESS. If you added commits beyond what was asked, say so in
  the report.
