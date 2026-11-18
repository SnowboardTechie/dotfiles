---
name: pre-review-cleanup
description: Use when Bryan wants to turn the SGG pre-review service's draft for a pull request into the review he posts, or to review a teammate's SGG pull request whose current head has no draft. Re-reviews each finding, rewrites it in his voice, posts through the submit tool on his go, rates the draft and records what changed in the sgg vault's pre-review feedback index.
---

# Pre-review cleanup

Bryan and you turn one of the pre-review service's drafts into the review he posts. The same pass labels the draft,
rates it, records what changed and why, and proposes changes to the service's review skill once a problem recurs.

The pre-review service drafts one review task per pull request head. Its drafts are usually right about the code and
wrong about how much to say. Your job is the review Bryan would have written, and a record of the distance.

Read these before step 2 and follow them; this skill does not restate them:

- `teammate-pr-review` (the finding bar, the human-facing draft shape, withdrawing a challenged finding) and
  `../pr-self-review/references/review-contract.md`.
- `voice-bryan`: `references/core-traits.md` ("Channel: PR review"), `references/anti-patterns.md`,
  `references/off-target.md`, `references/samples.md`, and its "Complete drafts and revision diffs" section.
- The feedback index, `~/code/sgg/vault/reviews/pre-review-feedback.md`: its categories are the only words you use for
  what changed, and its running list is where proposed bot changes go.

Every step that touches the review task runs the deployed submit tool. Written below as `evidence.js`:

```bash
node ~/.local/share/pi-durable/sgg-deployment/dist/workspaces/sgg/src/evidence.js <command> <case> [options]
```

`<case>` is the tool's own name for its argument: the review task ID `owner/name#N@<full 40-character head>`, or
`owner/name#N` for the pull request's current head. Never shorten a head.

## 1. Load one review

From a PR URL or `owner/name#N`:

1. Read the PR's current head (`gh pr view <N> --repo <owner/name> --json headRefOid,state,title,author,body,url`).
2. Run `evidence.js show owner/name#N`. It binds the current head's draft to its review task and lists every finding.
   When no draft exists for the current head, you are on the no-draft path: steps 6 and 7 change, the rest do not.
3. List the older heads that have drafts: the directories under
   `~/code/sgg/vault/reviews/<owner>/<name>/pr-<N>/` other than the current head's. Read each one's findings: they are
   candidates for this review, never carried over unread.
4. Say, before anything else: the head you work on (short SHA linked to the commit), whether it has a draft, and which
   older heads have drafts.

When `show` reports the head moved, or the PR is closed or merged, stop and say so: the tool refuses that review task,
and the newer head's draft (or the no-draft path) is a new run of this skill. Done when Bryan has seen the head, the
draft's state and the older drafts.

## 2. Re-review before rewording

Every finding, from this head's draft and every older draft, gets three questions at the current head, answered from
the code in a Worktrunk worktree of the PR at that head (`teammate-pr-review` step 1):

- **Still true?** Read the anchored lines and the evidence again at this head.
- **Worth raising?** Judge against the surrounding code and the author's evident intent, not only the authority. A
  deliberate pattern across the author's commits (every header comment trimmed the same way, an example kept on
  purpose) is intent: a finding that fights it must show a consequence that matters. Apply the finding bar.
- **A fix that keeps the intent?** Prefer correcting the author's work to deleting it. When the draft proposes a
  deletion, look for the change that keeps what the author meant and makes it right, and check that fix with the
  repository's own tool (for an example: compile it, run `cg check` on it).

Re-check every authority's status now: an ADR, issue or PR named as open may have merged or closed since the draft was
written. Write each as it stands today.

Add what the draft missed: a defect you find at this head that no draft raised is a new inline.

Done when every finding has an answer to all three questions with the evidence you read, and every authority's status
was read today.

## 3. Rewrite in Bryan's voice

- **Body**: the assent or the ask, a pointer to the inlines, and at most one more note. Nothing about what was run,
  regenerated or counted: that stays in the vault note's private audit.
- **Each inline**: an ask ("Could we…", "Small one:"), the defect in one or two sentences, then the suggestion.
- **Suggestion blocks**: the range covers exactly the lines the suggestion changes. A range wider than the change shows
  unchanged lines as replaced and reads as a no-op; narrow it, and set the inline's `start_line` and `line` to match.
- **Links**: every issue, PR, commit and ADR is a link with a few words saying what it is, in the posted text and in
  everything you say to Bryan.

## 4. Verify before showing

Every round, before Bryan sees it:

- Apply every suggestion in the PR worktree at its head, run the repository's own compile and format checks (in the
  protocol repository through `nix develop ~/code/nix-configs#simpler-grants -c <cmd>`, as `~/code/sgg/AGENTS.md`
  says), then revert. A suggestion that fails is fixed before it is shown.
- Every anchor and range is a commentable line of the diff at the head; `preview` checks this in step 6, so a plan
  you are unsure of can be previewed early.
- Every link resolves (`gh api` for issues, PRs and commits; fetch an ADR page).
- No bare `#N` remains: `grep -nE '(^|[^[/0-9A-Za-z])#[0-9]+' <the review text>` finds nothing.

## 5. Show everything, every round

Each round shows the complete review in `teammate-pr-review`'s human-facing shape (the proposed event, the body as a
quote, every inline with its exact-head permalink, side and range, `L7-L23` style, and its full text as a quote), then
a diff against the previous round (`voice-bryan`, "Complete drafts and revision diffs"). The first round's diff is
against the draft.

Then work through Bryan's edits. When he challenges a finding, re-check it from its claim and evidence: keep it and
give the evidence, or withdraw it. Change a conclusion only for a new fact, and name that fact. The authority's wording
is never the reason.

Keep a running list, for step 8, of every change from the draft and its category from the index.

## 6. Post only on Bryan's go

Write the plan to a scratch file outside both repositories. With a draft:

```json
{
  "event": "APPROVE",
  "summary": "the body Bryan approved",
  "findings": [
    { "id": "F1", "disposition": "kept", "reason": "one line", "body": "Bryan's wording",
      "anchor": { "path": "lib/a.tsp", "start_line": 7, "line": 23, "side": "RIGHT" } },
    { "id": "F2", "disposition": "dropped", "reason": "one line" }
  ],
  "missed": [
    { "description": "what the draft missed", "body": "the inline text", "severity": "Minor", "dimension": "Spec",
      "anchor": { "path": "lib/b.tsp", "start_line": 3, "line": 5, "side": "RIGHT" } }
  ]
}
```

- Every draft finding gets a resolution with a reason: `kept` (posted; `body` when the wording changed, which it
  usually has), `dropped` (true, not worth posting), `settled` (true, answered by context the draft lacked) or `wrong`.
  The plan's field is named `disposition`: that is the tool's word.
- A kept finding's `anchor` replaces the draft's anchor; give it only when the line or range changed. `start_line`
  only for a range.
- Each new inline is a `missed` row with an anchor and a body. A finding from an older head's draft that you post is a
  `missed` row too: the current draft didn't have it.
- With no draft for the head: `"findings": []`, every inline a `missed` row, and `event` and `summary` given explicitly:
  there is no draft for them to default to.

With a draft, `<case>` below is the review task ID. With no draft, it is `owner/name#N` (the current head, never a
review task ID) followed by `--no-draft`; the tool refuses `--no-draft` while the head has a draft.

Run `evidence.js preview <case> --plan <file>` and show its output in full, unedited. Its `--confirm` hash binds this
exact proposal. On Bryan's go for that preview:

```bash
evidence.js post <case> --plan <file> --confirm <hash> --basis approved-proposal
```

Any change to the plan is a new preview shown in full before posting. Report what `post` prints: the review link, any
warning, each destination published or pending. For a refusal, a partial post or a pending destination, follow the
submit skill's rules (`~/code/durable-pi-workspace/workspaces/sgg/plugin/skills/submit/SKILL.md`, step 4, "A pull
request whose current head has no draft" and "Refusals are the rules"); the only way to post is `evidence.js post`.

An interrupted post is finished with `evidence.js resume`, which never posts: it records a review that landed and
publishes what is pending (`evidence.js status` shows what is recorded). With a draft: `resume <review task ID>`. With
no draft: `resume owner/name#N --no-draft`, or `resume owner/name#N@<head> --no-draft` once the pull request has moved
past the head that was posted (`status` takes the same forms).

## 7. Rate the draft

In the same message as the final review, propose a rating for the draft you worked from with one line of reasoning,
from the meanings in `RATINGS` (`workspaces/sgg/src/ratings.ts`): 👍 `successful` (Bryan likes the results overall),
➖ `not_needed` (he didn't need this review; not a quality rating) or 👎 `unsatisfactory` (he had to change it
drastically). His go covers the post and the rating.

After the post: `evidence.js rate <review task ID> <rating>`; `clear` in place of the rating removes one set by mistake.
Report what it prints; the notification's reaction follows from the service's mirror within a minute. When the deployed build has no `rate` command, say so and leave the rating
for Bryan to set on the pre-review page (`https://bryans-mac-studio.tail5ba690.ts.net:8790/#/list/all`). With no draft
there is nothing to rate: say so.

## 8. Record the feedback

In the sgg vault (`~/code/sgg/vault/`, following `vault-pkm` and `vault/AGENTS.md`):

1. Write the review's note, `vault/reviews/<date>-pr-<N>-<slug>.md`, in the shape of
   `vault/reviews/2026-11-17-pr-1401-version-headers.md`: the posted event, body and inlines with their links, the
   private audit, provenance from the drafts, anything withdrawn, then a "What changed from the draft" section with one
   line per change: its category from the index, what changed, why, and whether the draft or this session caused it.
2. Add the review's row to the index's Reviews table and link the note from `vault/reviews/INDEX.md`.
3. Commit only those files and push, as `~/code/sgg/AGENTS.md` says (approval to post the review is approval to record
   it). The submit tool pushes to the same repository: pull with `--ff-only` first.

## 9. Propose bot changes

For each change caused by the draft, add to the index's running list: the category, the rule in the service's review
skill (`~/code/durable-pi-workspace/workspaces/sgg/plugin/skills/code-review/SKILL.md`, or `dependency-review/SKILL.md`)
that would have prevented it, and this review beside the others behind it. A line already there for the same rule gets
this review added and its count raised. Changes this session caused feed this skill, not the service.

When a line reaches three reviews and has no issue yet, draft one issue for `bryan/durable-pi-workspace`: the evidence
(each review's note and the change in it) and the proposed edit as a diff to the service's skill. Show Bryan the full
text. On his go, file it with the `needs-triage` label only, following
`~/code/durable-pi-workspace/docs/agents/issue-tracker.md` (`tea issues create`, then read the labels back). That
label leaves it for Bryan to triage; `ready-for-agent` would start an unattended build. Put the issue's link on the
line and push the index.

The service's skills change only through that issue. You propose; Bryan decides.

## Done when

The review is posted (or Bryan stopped it), the draft is rated or the reason it isn't is said, the note and the index
row are pushed, every proposed bot change is on the running list, and every line at three reviews has an issue or
Bryan's decision not to file one.
