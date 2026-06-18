---
name: sprint-deliverable-update
description: >
  Draft or post a sprint update comment on a deliverable issue. Use when asked to
  "write the sprint update for [deliverable]", "post the update on #7309", or
  "draft the deliverable comment for this sprint."
---

# Sprint Deliverable Update

Write a sprint update comment on an individual deliverable issue (e.g., #7309, #7311,
#6195). This is the per-deliverable update that the team posts at the end of each sprint.

The project-level rollup that combines all these comments into a board status update
is a separate skill: `sprint-status-update`.

## Key Rules

1. **Always tag Julius.** Open every comment with `@juchang111`. Every time, no exceptions.
2. **ACs and metrics are different things.** Use the bolded name from the deliverable as
   the sub-heading (e.g., "### Custom Fields Catalog", "### SGG Adoption"). Never use
   numbered labels like "Criteria 1", "Criteria 2".
3. **"Criteria completed" is an H2.** Needs visual separation from the sprint update above.
4. **Read the previous sprint's comment first.** Fetch the last sprint update comment
   on this deliverable to understand what was planned, what rolled over, and whether
   any ACs/metrics were intentionally held back.

## Template

```markdown
## Sprint X.Y updates

@juchang111 here's our end-of-sprint report for [deliverable name]. Let us know if you
have any questions!

**Status:** [emoji]

### Sprint goal

- [goal 1]
- [goal 2]

### Accomplishments

- [what got done, with links to PRs/artifacts where helpful]

### Rollover

- [anything that didn't get done, or "None"]

### Risks

- [or "None"]

### Next sprint (Sprint X.Y+1)

- [planned work]
```

## Criteria Completed

Most sprints, no ACs or metrics are completed. That's normal. If nothing was completed,
the comment ends after "Next sprint" and there is no criteria completed section at all.

Only include this section when ACs or metrics were actually completed that sprint. It
goes at the bottom of the comment, separated as its own H2.

```markdown
## Criteria completed

@juchang111 Here are additional details and evidence for the ACs and metrics that we
marked as completed this sprint. Let us know if you have any questions about these items.

### [Bolded AC name from deliverable]

> - [x] **[AC name]:** The full AC text quoted from the deliverable.

Evidence paragraph with links to artifacts, screenshots, etc.

### [Bolded metric name from deliverable]

> - [x] **[Metric name] (metric):** The full metric text quoted from the deliverable.

Evidence paragraph with links, data, screenshots.
```

### Finding Completed Criteria

1. Fetch the deliverable issue body and find all `- [x]` checkboxes (both ACs and metrics)
2. Compare against the previous sprint's update to see which are newly checked off
3. Include all newly completed items with evidence
4. Also check off the checkbox on the deliverable issue body if it isn't already

```bash
gh issue view {NUMBER} --repo HHS/simpler-grants-gov --json body --jq '.body'
```

## When Drafting From Scratch

If the engineer hasn't posted an update and you're drafting one, look for closed tasks
(sub-issues) during the sprint period.

First, get the issue's node ID:

```bash
gh issue view {NUMBER} --repo HHS/simpler-grants-gov --json id --jq '.id'
```

Then fetch all sub-issues with their state in a single GraphQL query:

```bash
gh api graphql -f query='
  query($id: ID!) {
    node(id: $id) {
      ... on Issue {
        subIssues(first: 50) {
          nodes {
            number
            title
            state
            closedAt
            repository { nameWithOwner }
          }
        }
      }
    }
  }
' -f id="ISSUE_NODE_ID"
```

Filter results for issues closed during the sprint period (closedAt > SPRINT_START_DATE).

Sub-issues may be in either `HHS/simpler-grants-gov` or `HHS/simpler-grants-protocol`.

**Always get user approval before posting.**
