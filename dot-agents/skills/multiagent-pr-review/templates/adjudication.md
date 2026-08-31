---
type: multiagent-pr-review-adjudication
status: <COMPLETE|INCOMPLETE|STALE|UNSTABLE>
canonical: true
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
claude_report: <vault-relative-link-to-claude.md>
claude_report_sha256: <sha256>
gpt_report: <vault-relative-link-to-gpt.md>
gpt_report_sha256: <sha256>
generated_at: <iso-8601>
---

# Canonical PR review adjudication

## Final Verdict

<Only COMPLETE with two admitted current reports may state a verdict. Never say
ready or clean for INCOMPLETE, STALE, or unadmitted evidence.>

## Candidate and Advisory Notes

- Claude advisory: [claude.md](claude.md)
- GPT advisory: [gpt.md](gpt.md)
- Candidate/manifest identity: <four fields plus manifest digest>

## CI and Root Verification

- CI/check snapshot: <name, status, observed-at>
- Root verification commands: <exact commands and results>

## Confirmed Findings

Order Critical, Major, Minor, then Nit. For each: root finding ID, all source
IDs/models/lanes, real `file:line`, violated invariant, root evidence, failure
mode, and smallest reasonable correction.

## Rejected Leads

For each source ID, record the concrete source trace or discriminating probe that
rejected it. Model disagreement alone is not rejection evidence.

## Unresolved Leads and Coverage Gaps

List uncertainty and missing proof without phrasing it as a confirmed defect.

## Acceptance-Criteria Sweep

For every authoritative criterion, record satisfied, failed, or unresolved with
criterion-level source and implementation evidence.

## Changed-File and Omission Sweep

Account for every changed path and behavior that should exist but leaves no diff
line. Record the nearest integration seam for omissions.

## Candidate Currency

- Remote PR head readback: <sha and observed-at>
- Final local candidate recheck: <identity>
- Drift handling: <none|STALE and user choice pending>
