# Hermes Desktop project-scope navigation case study

Use this as a concrete example of separating workspace authority from GUI navigation intent when assessing an upstream Desktop change.

## Question assessed

Should clicking a Project overview row's `+` create a session in that project's directory while leaving the sidebar on the Projects overview, rather than drilling into the project?

## Confirmed implementation path (2026-07-16)

Current `main` routes the action as follows:

1. `apps/desktop/src/app/chat/sidebar/projects/overview-row.tsx` calls the shared new-session callback with `project.path`.
2. `apps/desktop/src/app/session/workspace-session-target.ts` treats any non-empty path as an `explicitTarget`.
3. After resolving the target, it calls `followActiveSessionCwd(resolved)`.
4. `apps/desktop/src/store/projects.ts` maps the cwd to a project and calls `enterProject(projectId)`, changing the persisted sidebar scope.

The important architectural distinction is:

- **Session workspace authority:** the clicked project path must remain the cwd used by `session.create`.
- **Sidebar navigation intent:** overview-project `+`, project trunk `+`, and explicit worktree selection need not all change scope the same way.

Do not infer navigation intent merely from `path` being non-empty. A project root selected from the overview and an explicit worktree lane both carry paths but represent different UI actions.

## Existing-work landscape at assessment time

No exact open issue or PR requested scope-preserving Project overview `+` behavior. Relevant adjacent work:

- [#49037](https://github.com/NousResearch/hermes-agent/pull/49037) — merged first-class Projects implementation.
- [#63081](https://github.com/NousResearch/hermes-agent/pull/63081) — merged explicit-workspace target preservation; introduced/extracted `workspace-session-target.ts`. Its design comments distinguish scope-preserving project-trunk behavior from explicit worktree drill-in, but the Project overview passes a non-empty root path and therefore follows the worktree branch.
- [#53004](https://github.com/NousResearch/hermes-agent/issues/53004) — open broader Projects-workflow criticism.
- [#58653](https://github.com/NousResearch/hermes-agent/issues/58653) — open report that Desktop project/sidebar behavior is confusing.
- [#58069](https://github.com/NousResearch/hermes-agent/pull/58069) — open PR preserving a separate Sessions roster alongside Projects.
- [#63976](https://github.com/NousResearch/hermes-agent/pull/63976) — open project-scope reset on profile switching; same state area, different defect.
- [#63262](https://github.com/NousResearch/hermes-agent/pull/63262) — open Windows path-membership correction in `followActiveSessionCwd`; same function, different behavior.

## Search technique that found the provenance

Title/body searches alone did not reveal an exact match. The useful sequence was:

1. Search open and closed issues/PRs with several vocabulary families: project scope, project overview, new session/chat, sidebar, auto-enter, drill-in, and the relevant symbol name.
2. Trace current `main` to the function that performs the scope transition.
3. Query recent commits for each affected path.
4. Map the introducing commit back to its PR using GitHub's commit-associated-pulls endpoint (`GET /repos/{owner}/{repo}/commits/{sha}/pulls`).
5. Read the introducing PR's body, comments, and patch—not just its title—to recover intended distinctions and identify a call-site semantic mismatch.

This pattern is broadly useful when no issue names the behavior users observe.

## Smallest contribution shape

A focused change should carry navigation intent separately from the workspace path, for example with a `followProjectScope`/`enterProject` option or a typed action object:

- Project overview row `+`: explicit project cwd, preserve overview scope.
- Explicit worktree/repo lane action: explicit cwd, follow/enter project when needed to reveal the lane.
- Agent-driven same-session cwd relocation: retain current auto-follow behavior.

Add regression coverage around `workspace-session-target.ts` and the Project overview call site. Open an issue first if maintainers may regard drill-in as intentional UX; frame it as separating session placement from presentation state, not weakening project-owned working directories.
