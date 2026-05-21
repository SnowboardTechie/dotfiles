---
name: watch-pr-reviews
description: watches the included PRs for any reviews and notifies the user
---

Check my open PRs across these repos for reviewer comments I have not yet addressed:
- https://github.com/HHS/simpler-grants-protocol/pulls/SnowboardTechie
- https://github.com/HHS/simpler-grants-gov/pulls/SnowboardTechie
- https://github.com/common-grants/py-cg-grants-gov/pulls/SnowboardTechie
- https://github.com/common-grants/ts-cg-grants-gov/pulls/SnowboardTechie

My GitHub username is SnowboardTechie. Do not report my own comments as unaddressed.

For each open PR:
1. Fetch all inline review comments via `gh api repos/{owner}/{repo}/pulls/{number}/comments`.
2. Group comments into threads by `in_reply_to_id` (comments with no `in_reply_to_id` start a thread; replies share that root id).
3. For each thread started by another reviewer (not SnowboardTechie):
   a. Check whether I have replied in that thread.
   b. If I have replied, verify the reply was substantive (not just "done" with no follow-through) by checking whether a commit was pushed AFTER my reply that plausibly addresses the concern — use `gh pr view {number} --repo {owner}/{repo} --json commits` and compare commit timestamps and messages against the reviewer's ask.
   c. Only flag a thread as unaddressed if: (i) I have no reply, OR (ii) I replied with intent to fix but no subsequent commit backs it up.
4. Before reporting any thread as unaddressed, confirm via the branch's current file content (`gh api repos/{owner}/{repo}/contents/{path}?ref={branch}`) that the concern hasn't already been resolved in the code — a reviewer ask that is satisfied in the current file is not unaddressed even if the thread has no explicit reply.

For each unaddressed thread, include: repo, PR number and title, reviewer name, a short quote of their comment, and why you concluded it is unaddressed.