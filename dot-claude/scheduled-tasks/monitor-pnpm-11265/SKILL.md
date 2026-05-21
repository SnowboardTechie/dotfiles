---
name: monitor-pnpm-11265
description: Daily monitor of pnpm/pnpm#11265 — when fixed, triggers work on HHS/simpler-grants-protocol#731
---

Monitor the upstream pnpm issue that blocks HHS/simpler-grants-protocol#731.

1. Check pnpm/pnpm#11265 for updates:
   `gh issue view 11265 --repo pnpm/pnpm --json state,updatedAt,comments --jq '{state, updatedAt, commentCount: (.comments | length), recentComments: [.comments[-3:][] | {author: .author.login, date: .createdAt, snippet: (.body[:300])}]}'`

2. Check the pnpm releases for a stable v11 fix:
   `gh release list --repo pnpm/pnpm --limit 10 --json tagName,publishedAt,isPrerelease --jq '[.[] | select(.tagName | startswith("v11")) | {tag: .tagName, publishedAt, isPrerelease}]'`

3. Flag **ACTION NEEDED** only if a **stable** (non-prerelease) pnpm v11 release exists that contains the audit fix (pnpm/pnpm#11268). RC and alpha releases do NOT trigger action — wait for a stable release.

   Note: As of 2026-04-16, the fix shipped in v11.0.0-rc.1 (prerelease). Waiting for stable v11.

Report:
- Current state of pnpm/pnpm#11265 (open/closed)
- Number of comments (to track activity)
- Summary of any new comments since yesterday
- Latest pnpm v11 release tag and whether it is a prerelease
- **ACTION NEEDED** banner ONLY if a stable (non-prerelease) pnpm v11 is available — this means it's time to work on HHS/simpler-grants-protocol#731 (remove the audit-deps.js workaround per the acceptance criteria in that issue)