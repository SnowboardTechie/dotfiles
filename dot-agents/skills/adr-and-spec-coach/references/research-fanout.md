# Research fan-out for open ADR decisions

Use between inventory (Phase 2) and deliberation (Phase 3) when the agenda's
load-bearing items need evidence the author does not already have.

## Splitting the work

- One child per **decision cluster**, typically 3:
  1. Precedent survey (how real systems/standards solve it, primary sources).
  2. The load-bearing semantics question (the one that drives everything else),
     with concrete example payloads per option grounded in the repo.
  3. Wire/edge details (defaults, errors, granularity, HTTP plumbing).
- Do not split by source ("one reads the RFCs, one reads the repo"). Clusters
  keep each child's recommendation coherent.
- Give every child the same **consumer story** so trade-offs are judged from the
  adopter's side, not the implementer's.

## Shared background block (repeat verbatim in every child)

Children know nothing about the conversation. Include:

- The issue/ADR goal and acceptance criteria, quoted from the live issue.
- The ownership split, naming the collaborator's lane so children do not design it.
- Current leans, explicitly marked **not decided**.
- Prior private research notes to read and *extend and verify*, not copy.
- The plan note the child is part of.

## Source pinning

- `git fetch origin <branch>` and record the SHA. Read repo files with
  `git -C <repo> show <sha>:<path>` and list with
  `git -C <repo> ls-tree -r --name-only <sha> <dir>`. The local checkout may be
  on a teammate's branch with their work in it, so children must never
  checkout, switch, stash, or commit.
- Put the SHA in each output's frontmatter (`source-sha`).

## Hard rules for children

- Read-only everywhere except their one output file. No posting, issues, PRs,
  comments, or shared-doc edits.
- No meeting transcripts or retired memory stores.
- External claims come from primary sources fetched now, with URLs. If a page
  can't be fetched, they must say so rather than fill the gap from memory.
- Label consequential claims **Verified / Inferred / Proposed**.
- Follow the target repo's ADR hygiene: ADRs cite decisions, options, and
  requirements, not meetings or named adopters.
- Output: one markdown draft in the vault's drafts folder, with frontmatter.
  Final reply of 300 words or fewer covering findings, recommendation, open
  questions, and the path.

## After the children report

1. Read each output file and spot-check its load-bearing claims against the
   cited source.
2. Commit and push task-owned drafts per the workspace rules.
3. Start Phase 3 with the heaviest decision, one per turn.
