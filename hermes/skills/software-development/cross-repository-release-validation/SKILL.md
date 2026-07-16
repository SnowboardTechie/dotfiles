---
name: cross-repository-release-validation
description: Validate a multi-repository release train when downstream consumers depend on an unpublished upstream SDK or package. Use for local artifact testing, expected CI dependency gates, package-shape verification, and release-readiness evidence.
version: 1.3.0
platforms: [linux, macos]
metadata:
  hermes:
    tags: [release, integration-testing, multi-repo, dependencies, ci]
---

# Cross-Repository Release Validation

## Trigger

Use this skill when a downstream repository or PR needs an upstream SDK/package revision that has not reached its registry yet. Typical signs:

- downstream CI installs the published dependency and reports missing symbols;
- several repositories must be retested at the same upstream SHA;
- unit tests pass inside the SDK but consumer behavior or package exports remain uncertain;
- release order matters: upstream merge/publish before downstream dependency-floor bumps.

## Core Principle

**Validate the exact release candidate as a packaged dependency from the consumer's point of view.**

A source-tree test proves internal behavior. A wheel/tarball test proves the publish shape, resolver behavior, exports, generated signatures, and downstream compilation together.

## Workflow

### 1. Freeze the release graph

Record before testing:

- upstream repository, branch, and full SHA;
- each downstream repository, branch, and full SHA;
- registry version currently installed by hosted CI;
- required merge/publish order;
- which failures are expected before publication.

Do not describe a branch name alone as provenance: moving branches are insufficient evidence.

### 2. Start clean

For every repository:

- inspect branch/worktree status;
- preserve unrelated changes;
- use an isolated worktree for experimental installs or patches;
- identify repo-local instructions and canonical check commands.

Do not change lockfiles or manifests casually. If a local artifact install must rewrite them, snapshot or restore them and verify the tree is clean afterward.

### 3. Build real upstream artifacts

Build the artifact exactly as publication would:

- Python: wheel through the declared build backend;
- JavaScript/TypeScript: packed tarball through the package manager;
- generated-code SDKs: run generation/build before packing.

Capture the upstream SHA and artifact filename in the test output. Clear stale artifact directories first so glob selection cannot pick an older package.

### 4. Install without resolver substitution

Install the exact local artifact in each consumer. The critical failure mode is a resolver silently replacing the local package with the registry version.

- install the upstream artifact first;
- when appropriate, install the consumer with dependency resolution disabled (`--no-deps`) or use a direct artifact override;
- verify installed package bytes/metadata or exported symbols before running tests;
- record the resolved package version and source.

Never claim “tested against branch X” solely because the source checkout exists nearby.

### 5. Use the correct RED

If the defect is static—type checker diagnostics, generated constructor signatures, package exports—the focused checker is the executable RED. Do not invent a runtime regression test that already passes before the change.

For a static-only repair:

1. capture the exact checker diagnostics/count;
2. make the minimum source change;
3. rerun the checker for GREEN;
4. run the full test suite for runtime regressions;
5. add a runtime test only if it protects independently required behavior and actually fails before the change.

### 6. Verify at four distinct levels

Run every layer included in the release plan:

1. **Repository gates:** format, lint, type checking, build, tests, audit.
2. **Focused runtime proof:** exercise the changed values and serialized/wire form.
3. **Packaged consumer scenario:** install real SDK and consumer artifacts in a separate harness and execute a downstream use case.
4. **Manual live smoke test:** when planned, call the real service through each consumer/plugin and inspect the applied filters, parsed response, and per-row errors.

The packaged scenario is mandatory for public SDK surfaces, generated signatures, exports, transforms, and plugin contracts. It proves package shape and local wire construction; it does **not** prove that the live endpoint accepts the request. Never summarize testing as complete while a planned live/manual layer is still pending. Report the layers separately.

Manual example programs may catch per-scenario exceptions and still exit zero or print a final completion line. Inspect every scenario, search captured output for error markers, and verify the service echoed or applied the requested inputs. A zero-result search can still pass if the service accepted the request and the response parsed correctly.

See `references/manual-live-plugin-validation.md` for the live-test checklist.

### 7. Interpret hosted CI precisely

Hosted CI may remain red until the upstream package publishes. Inspect failed logs rather than labeling the whole PR “expected red.” Confirm:

- failures are limited to absent symbols/version-gated APIs from the registry package;
- diagnostics fixed by the patch are gone;
- formatting/lint or unrelated tests did not regress;
- CI is using the published version you expect.

Report the exact residual error class and count. An expected dependency gate is not a passing check, and it must not hide unrelated failures.

### 8. Preserve release boundaries

Local validation authorizes neither merge nor publication. Stop at the approved boundary and distinguish:

- code pushed;
- local verification green;
- hosted CI dependency-gated;
- review pending;
- merge ready;
- publish ready.

Do not dispatch release workflows or merge upstream/downstream PRs without explicit authorization for those actions.

### 9. Communicate status without replaying the whole release plan

For a teammate recap, assume the thread already carries the background. Use one short paragraph:

- what changed or was pushed;
- the smallest useful proof (checker state and test count);
- the immediate next verification step;
- the expected CI dependency gate, if it is still visible.

Do not restate settled rationale, enumerate the entire release sequence, or call the release ready while manual testing remains pending. Keep detailed SHAs, artifact provenance, and diagnostic counts in the engineering record unless the recipient needs them.

### 10. Prepare complete PR evidence packages

When the user is collecting screenshots and comments across several PRs, every revised response must remain self-contained. Do not answer a correction with only a replacement command or changed paragraph. Regenerate the complete usable package with:

- every full PR/ticket URL;
- shared setup and immutable provenance checks;
- exact copy-pasteable commands for each destination;
- what each screenshot must visibly prove;
- paste-ready comment text for every PR;
- expected outcomes and a final evidence-to-PR checklist.

Match evidence to the claim. Protocol/SDK PRs need packaged-artifact and independent-consumer evidence. Plugin PRs need unfiltered live-service output with actual parsed response content. Do not strip reviewer-relevant API content through `grep` merely to fit one screenshot; prefer multiple readable screenshots and retain the full log. Keep automated checks, packaged-consumer validation, and manual live validation explicitly separate.

A deterministic playground/fixture runner is not live-service evidence, even when it prints realistic request JSON and a success banner. Make the runner path and evidence layer visible, and never caption fixture output as an API response. Likewise, do not assume similarly shaped metadata has the same provenance across languages: one client may reconstruct request metadata while another passes through a server-normalized response. Trace classification, serialized request, server parsing, and response assembly before naming or comparing those fields.

After the user posts evidence, stop regenerating plans and perform a read-only source audit: inspect the actual PR comments, load every attachment, read the screenshots, verify immutable revisions and scenario coverage, check for exposed secrets, and identify duplicates or misleading claims. Comment prose alone is not proof.

See `references/manual-live-plugin-validation.md` for runner-hardening, fixture-vs-live distinctions, metadata-provenance tracing, screenshot/comment guidance, and post-publication evidence auditing.

### 11. Final hygiene and evidence

Before reporting completion:

- verify pushed SHA equals the intended branch head;
- verify every worktree and harness is clean;
- remove temporary worktrees/artifacts when safe;
- rerun the canonical check/test command after the final edit or commit;
- report exact test counts, checker counts, artifact provenance, CI residuals, and untouched release boundaries.

## Pitfalls

- Testing against a locally edited source tree instead of the packed artifact.
- Allowing a package resolver to fetch the published dependency over the local build.
- Calling CI “expected red” without reading the failed job.
- Adding a behavioral test that passes before a static-only fix and pretending it is RED.
- Leaving package manifests dirty after temporary tarball installation.
- Treating a successful local run as approval to merge or publish.
- Reporting branch names without immutable SHAs.

## Reference

See `references/unreleased-dependency-gates.md` for a concrete Python/TypeScript validation recipe and evidence checklist.
