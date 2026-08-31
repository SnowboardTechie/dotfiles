---
type: multiagent-pr-model-review
status: advisory
canonical: false
pr_url: <github-pr-url>
repository: <owner/repo>
pr_number: <number>
author: <login>
base_sha: <full-sha>
head_sha: <full-sha>
merge_base_sha: <full-sha>
diff_sha256: <sha256>
expected_pr_head_ref: <ref>
evidence_manifest_sha256: <sha256>
reviewer_family: <claude|gpt>
provider: <provider>
primary_model: <model>
models_used: <comma-separated-observed-models>
agent_name: <herdr-agent-name>
pane_id: <herdr-pane-id>
runtime_session_id: <runtime-session-id>
selected_lanes: <standards,spec,correctness[,risk],ponytail>
risk_reason: <deterministic-selection-reason>
generated_at: <iso-8601>
---

# <Reviewer family> advisory review

Advisory findings are not yet root-confirmed. They are leads for independent
root adjudication, not a verdict.

## Summary and Confidence

<Headline, candidate scope, confidence, and material limitations.>

## Critical

- [<stable-source-id>] `<file:line>` — <failure mode and evidence> — Source:
  <lane(s)>. Suggested correction: <smallest reasonable correction>.

## Major

<Omit when empty.>

## Minor

<Omit when empty.>

## Nit

<Omit when empty.>

## Acceptance-Criteria Observations

- <criterion and observation; do not claim root confirmation>

## Coverage and Verification Performed

- <files, seams, commands, and lane coverage actually inspected>

## Unverified Limitations

- <missing evidence, provenance limit, or untested runtime boundary>
