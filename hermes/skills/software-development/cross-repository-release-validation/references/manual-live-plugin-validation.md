# Manual live plugin validation

Use this after repository gates and packaged-consumer tests pass. It is a separate release-evidence layer, not a substitute for either one.

## Preconditions

- Record immutable upstream SDK and downstream plugin SHAs.
- Build/install the same local artifacts used by the packaged-consumer harness.
- Confirm the plugin worktree and harness are clean.
- Use a read-only or search endpoint unless the user explicitly authorizes writes.
- Load credentials from the user's environment. Never print, persist, or request that the user paste secrets into chat.

## Run each consumer independently

For every language/plugin implementation:

1. Run a baseline request without custom behavior.
2. Run each registered option/filter independently.
3. Run the options together to catch composition problems.
4. Exercise one invalid value locally and confirm fail-fast validation prevents a request.
5. Capture output to a temporary log without credentials.

## Validate the runner before trusting it

Treat live examples as test infrastructure, not throwaway documentation.

- Prove the documented credential variable reaches every configuration layer. A client may validate a key in `Config` even when a separate `Auth` object receives the same key; pass it explicitly when the example documents a nonstandard environment variable.
- Add focused tests for import-time configuration, response-shape assumptions, and failure exit status.
- If scenarios catch exceptions so later checks can run, aggregate their outcomes and exit nonzero when any scenario fails. Never leave a runner that prints a success banner after caught errors.
- Verify whether displayed filter/request metadata came from the service or was reconstructed by the client. Client-classified request data proves what was sent, not what the service echoed or applied; label it `filters sent` and use response behavior or raw server metadata for server-side claims.

## Inspect behavior, not just exit status

Check the full log for:

- network, HTTP, validation, and parse errors;
- the service's echoed/applied request metadata, when the client actually preserves it;
- per-row parse-failure counts;
- typed access to representative response fields;
- all expected options in the combined request.

A response with zero matching items can still pass when the service accepted the request and the response parsed cleanly. Treat missing applied metadata, unexpected local validation, or parse failures as investigation items.

## Capture approval evidence

Screenshot evidence must show behavior, not merely that a wrapper script ran.

- Keep the live example output unfiltered when reviewers need to see actual returned records and parsed custom fields.
- Include scenario name, request/filter context, totals, parse-failure count, representative parsed content, and honest final status.
- Use multiple screenshots rather than removing substantive output to fit one viewport.
- Save the full output with `tee`, use `set -o pipefail`, and perform separate error-marker/count checks after the run.
- Keep credentials outside screenshots and inspect captures before posting.

Map evidence to its destination:

- protocol/SDK PR: artifact build/pack/install provenance, wire shape, and independent consumer assertions;
- plugin PR: live API scenarios and actual parsed response content;
- cross-repository release recap: links to both evidence layers, with hosted CI dependency gates described separately.

For multi-PR posting plans, provide a complete package every time—even after a correction—including full links, shared setup, exact commands, screenshot instructions, paste-ready comments, expected revisions, and a final checklist. Delta-only revisions force the user to reconstruct the plan and are not acceptable.

## Cross-language comparison

Compare request shape, accepted option names, response parsing, and error behavior. Do not require identical result counts from a changing live dataset.

## Completion language

Use precise layer status:

- "repository gates green";
- "packaged consumer scenario green";
- "manual live smoke test green";
- or "manual live smoke test pending/blocked by <specific prerequisite>."

Do not say "testing complete" until every planned layer has run or the user accepts a documented blocker.
