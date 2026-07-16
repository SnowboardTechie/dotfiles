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

## Distinguish deterministic fixtures from live-service evidence

A packaged-consumer harness and a live example answer different questions. Keep their commands, captions, screenshots, and claims separate:

- A deterministic fixture proves package installation, imports/exports, request construction, and cross-language parity against controlled data. Its output is intentionally scripted and must never be presented as a live API response.
- A live example proves endpoint acceptance and response parsing. Its evidence must contain actual returned records or substantive server response data—not only scenario headings, totals, or a final `PASS` line.
- If a protocol PR needs both layers, describe fixture results in text or attach clearly labeled package evidence, then link or attach separate live-plugin evidence. Do not repurpose fixture screenshots as API proof.
- Make the executed script path visible in the command or caption so reviewers can tell a fixture runner from a live client.

## Trace metadata provenance independently in every client

Do not copy labels such as `filters sent`, `server echo`, or `applied filters` between language implementations merely because their output shapes look similar. Trace each client separately:

1. Construct the consumer input and inspect classification output.
2. Inspect the serialized HTTP request boundary.
3. Determine whether the service parses, normalizes, or coerces the value.
4. Determine whether response metadata is passed through from the server or reconstructed locally from the request.
5. Label output according to that provenance.

Cross-language screenshots can legitimately differ even when requests are equivalent. For example, one client may show its original boolean request while another passes through a server-normalized numeric representation. Before calling this a parity failure, reproduce the exact deployed dependency version and compare it with the release candidate. A compact deterministic probe of model construction plus serialization is often enough to isolate coercion:

```text
input value/type -> parsed model value/type -> serialized representation
```

Use the service lockfile/manifest to choose the exact deployed package version; do not test only the newest source checkout. If the release candidate already preserves the value, classify the discrepancy as an explicit downstream dependency-upgrade follow-up rather than patching the consumer symptom.

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

## Audit posted PR evidence from the source

When the user says evidence has been posted, switch from planning to read-only verification. Inspect the live PR comments and the image attachments themselves; do not infer success from the draft text or local files.

For every destination, verify:

- the intended comment exists on the correct PR;
- every attachment URL loads;
- displayed SHAs match the current tested heads;
- the screenshot shows the claimed runner and evidence layer;
- all planned scenarios and the final status are visible;
- actual returned content is present when claiming live behavior;
- no credentials or unrelated private data are exposed;
- duplicate, stale, misleading, or wrong-destination comments are called out;
- current CI state is reported separately from the screenshot evidence.

A comment body saying “all scenarios passed” is not verification. Read the pixels. If the screenshot shows a surprising representation, trace its provenance before calling it a consumer bug or dismissing it as cosmetic.

## Cross-language comparison

Compare request shape, accepted option names, response parsing, and error behavior. Do not require identical result counts from a changing live dataset.

## Completion language

Use precise layer status:

- "repository gates green";
- "packaged consumer scenario green";
- "manual live smoke test green";
- or "manual live smoke test pending/blocked by <specific prerequisite>."

Do not say "testing complete" until every planned layer has run or the user accepts a documented blocker.
