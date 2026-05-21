---
name: sync-hold-transforms
description: Sync main into HOLD-transforms for SDK Plugin Enhancements work (manual trigger)
---

You are syncing `main` into `HOLD-transforms` for the SDK Plugin
Enhancements work. Target branch: HOLD-transforms.

Operate on the local checkout at:
  /Users/bryan/code/sgg/HHS/simpler-grants-protocol

Before starting, confirm:
- `git -C /Users/bryan/code/sgg/HHS/simpler-grants-protocol remote -v` shows the HHS/simpler-grants-protocol origin.
- The working tree is clean (no uncommitted changes). If dirty, stop and report — do not stash, do not modify uncommitted work.

Do:
1) Fetch origin, check out HOLD-transforms, pull.
2) Merge origin/main into HOLD-transforms.
3) If conflicts:
   - Surface the conflicting files and the conflict regions verbatim.
   - Do not auto-resolve.
   - Stop and report.
4) If clean:
   - Run package builds and tests for any package touched since the
     last sync. Report which packages were exercised and whether they
     passed.
5) Push HOLD-transforms to origin.
6) For each open PR targeting HOLD-transforms, post a single comment noting
   the sync date and a one-line summary of what landed from main
   (commit count, headline categories: Dependabot / fix / chore).

Constraints:
- Do not force-push.
- Do not edit changeset files under .changeset/.
- Do not edit source beyond what the merge produces.
- If the merge is empty (nothing new on main), skip steps 4-6 and
  report "no-op: main unchanged since last sync."