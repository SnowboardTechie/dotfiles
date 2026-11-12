# Documentation walkthrough demos

Use this pattern when the demo is a release or sprint update for a mixed audience (product, design, other teams) and nothing needs to run live: protocol releases, SDK releases, docs and tooling updates. The proof is published artifacts and readable documentation, not a command.

## When to choose it over a live terminal demo

- The claim is "this is published and usable," not "this computes the right thing."
- No public service exercises the feature yet (optional routes, unreleased reference implementation), so a live call would need a mock that adds risk without adding credibility.
- The slot is three minutes or less and the audience is not all engineers.

Offer a short live run only as an upgrade when the user has more time, and name the exact runnable example (for instance an SDK's offline-mock example script).

## Gather the sprint record first

For a sprint or release review, build the inventory from live sources before choosing screens:

```bash
# Everything merged in the window, per repo
gh pr list --repo OWNER/REPO --state merged --search "merged:YYYY-MM-DD..YYYY-MM-DD" \
  --limit 100 --json number,title,mergedAt,author \
  --jq '.[] | "\(.mergedAt[0:10]) #\(.number) [\(.author.login)] \(.title)"' | sort

# Releases published in the window
gh api "repos/OWNER/REPO/releases?per_page=15" \
  --jq '.[] | select(.published_at >= "YYYY-MM-DD") | "\(.published_at) \(.tag_name)"'

# Release notes for the headline tags
gh api "repos/OWNER/REPO/releases/tags/TAG" --jq '.html_url, .body'
```

Then:

- Treat registry state (`npm` dist-tags, PyPI `info.version`) as the ground truth for "shipped." A merged change with an open release PR is not released; leave it out of the talk track rather than announcing it as coming soon.
- Read the team's posted sprint report on the deliverable issue, if one exists. The talk track must not contradict it, but it can be a positive subset: omit the report's bug fixes and next-sprint plans (see SKILL.md step 3).
- Check whether downstream consumer apps actually pin the new version before implying adoption.
- Record which work belongs to which teammate. Frame team work as "we"; list teammates' separately presentable items as optional swaps rather than presenting them by default.

## Choosing screens

- Two or three tabs. One anchor per tab, so the presenter switches tabs instead of scrolling live.
- For SDK work, a README or guide section with a short, realistic code example is the strongest visual: a mixed audience can read `client.awards.search(filters=...)` with plain-language narration. Release-notes pages are commit-title lists; keep them as Q&A links.
- Tie the first screen back to the previous demo when this is a follow-on ("last time the protocol gained X; now the SDKs expose it").
- For "other work," pick the screen whose first visible line carries the claim (for example a guide step that says "click Use this template").
- Avoid dense field tables and long JSON examples; they wrap badly and make the audience hunt.

## Rehearsing the screens

The live path is the screens, so rehearse them:

1. Open each URL in the browser at the presentation viewport (1280×800 is a safe default) and capture a screenshot.
2. Inspect the screenshot: the heading and the whole snippet must be visible without scrolling.
3. Derive GitHub README anchors from the DOM instead of guessing. Rendered heading ids are `user-content-<slug>`; the link fragment is `#<slug>`. A heading containing an HTML comment (such as `<!-- omit in toc -->`) produces a slug with a trailing hyphen, so a guessed anchor silently lands at the top of the file.
   ```python
   js('Array.from(document.querySelectorAll("[id^=user-content-]")).map(e=>e.id)')
   ```
4. Tell the presenter to collapse GitHub's file-tree sidebar; it otherwise takes a quarter of the shared screen. Note that their theme and zoom will differ from the rehearsal.
5. Record the commit the README was checked at when linking to `main`.

## Talk-track discipline

- About 220–260 spoken words for a three-minute ceiling with three tabs; run `scripts/talk-track-timing.py` on the runbook and record per-tab counts and the estimate.
- Give per-tab pacing targets and an explicit cut order: cut tooling sentences first, then secondary screens, and keep the headline capability statement.
- Close on a takeaway about what was delivered, not on next-sprint plans.
- Every number must reconcile with a source (PR body, release notes, registry). Prefer the source's own framing; restate a count only when the restatement is exactly equivalent.
- Withhold figures that a team report marks as pending clearance, in both the talk track and Q&A.
- Zero em-dashes in spoken copy (the presenter reads it as written).

## Runbook sections specific to this format

- **Screen plan** with the presenter companion's tailnet URL first, then exact URLs, what is visible at each anchor, and anything not to scroll into. A screen can be a web page or a public live service's docs; check a live service's freshness indicators (for example a `/snapshot` or `asOf` field) against what the talk track claims, and leave out claims the live state contradicts, such as "refreshes daily" when the data is a week old.
- **Multi-item reviews** (several short items in an agreed order): give each item its own tab, pacing target, and talk-track subsection. Label a mention-only item as optional on screen. Keep held-back items out of the track and note them on the companion's Prep tab.
- **Likely questions** covering: breaking changes and upgrade docs, companion plugin releases, downstream adoption, whether a live service exists to try it, uncleared numbers, and deliverable status. Answer about future work without committing to timing or owners. If a public report mentions a fix the talk track omits, add one neutral "only if asked" line, not a set of diagnostic answers.
- **Offline fallback**: transcribed snippets from the live page, labeled as documentation examples, not API output.
- **Scope considered**: what was included and what was left out as optional swaps, so the presenter can change emphasis without new research.
- **Pre-meeting checklist**: open tabs at anchors, screen-share zoom, one timed read-aloud, and end after the takeaway.
- State assumptions the agent could not verify (meeting time, spoken rehearsal) in the evidence section rather than implying them.
