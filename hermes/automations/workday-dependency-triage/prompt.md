Prepare Bryan's weekday SGG dependency-triage report and deliver only the final consolidated report to the configured Matrix room.

Scope: scan all three dependency queues Bryan maintains, every run:
- /Users/bryan/code/sgg/HHS/simpler-grants-protocol (HHS/simpler-grants-protocol)
- /Users/bryan/code/sgg/common-grants/py-cg-grants-gov (common-grants/py-cg-grants-gov)
- /Users/bryan/code/sgg/common-grants/ts-cg-grants-gov (common-grants/ts-cg-grants-gov)
Explicitly exclude HHS/simpler-grants-gov. Do not ask for clarification; this three-repository scope is intentional.

Follow the dependency-triage skill to gather current open dependency PRs, CI/check state, overlaps/supersession, special-handling lanes, fix status, and release attribution (whether a merge actually ships a version bump). Fan out read-only PR analysis in batches of at most three via delegate_task, directing catalog PRs to catalog-review and all other reviewable PRs to dependency-review Steps 0–4. Cover every reviewable PR; do not silently truncate.

This unattended automation is report-only and read-only. Do not check out PR branches, modify working trees, run local builds, comment, approve, close, merge, label, push, or otherwise mutate repositories or GitHub. If a candidate needs local verification, place it under Review manually and say what verification remains. Because cron delivers only the final response, do not emit the dependency-triage skill's dispatch/progress message; return one final consolidated report.

Use the skill's concise Markdown report structure, but group entries by repository within each bucket when useful. Every PR reference must be a clickable Markdown link. Include Merge now, Review manually, Hold, Special handling, and Notes; omit empty buckets. State explicitly when no open dependency PRs exist in a repository and when any GitHub/CI lookup failed. Ground every recommendation in current forge metadata and the read-only review verdict. Do not invent results.
