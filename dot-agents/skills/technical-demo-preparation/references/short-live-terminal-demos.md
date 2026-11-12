# Short live terminal demos

Use this pattern for a technical update with a hard three-minute ceiling. The goal is a credible proof in roughly 90 to 120 seconds, leaving the remaining time for screen-share friction, a pause, or one question.

## Recommended shape

| Beat | Target | Purpose |
|---|---:|---|
| Opening | 15 to 25 sec | State the question and what changed |
| One live command | 20 to 45 sec | Produce the observable result |
| One result inspection | 20 to 40 sec | Make the output concrete |
| Close | 20 to 30 sec | State what the result proves and its status |
| Buffer | 45 to 90 sec | Absorb friction or one question |

If the prepared material already consumes the full slot, it is too long. Cut a command or context paragraph.

## One-command, one-result rule

A short terminal demo should normally have this shape:

```bash
<single build, request, or scenario command>
```

Then inspect one compact result:

```bash
<query> <output-file-or-response>
```

The first command proves the system works. The second lets the audience see what the output means. A third command needs a specific justification.

## Selecting the result

Avoid `first` or array index zero if ordering can change. Select by a stable semantic property such as a title prefix, ID, slug, or scenario name, then project only the fields used in narration.

A useful projection usually contains:

- human-readable name or title;
- related object or join target;
- recipient or actor;
- one value that makes the result tangible;
- status;
- source or traceable identifier.

Keep it to roughly six fields. Do not show a full schema-sized object unless the schema itself is the point.

## Narrating data funnels

Pipeline demos often produce several counts. Present them in causal order:

1. total source records;
2. records with a usable join key;
3. distinct keys;
4. matched parent records;
5. emitted child records;
6. validation failures.

Explain non-obvious expansion or contraction. For example, several child records may come from one matched parent, so emitted records can exceed matched keys. Unmatched input is not automatically a failure; name known source-data coverage limits honestly.

## Proving an offline claim

If the demo claims to run without network access or credentials:

1. unset the credential;
2. point every optional service and schema URL at an unreachable local address;
3. run the exact build;
4. inspect the result and validation output;
5. run any pinned reference comparison.

For the live presentation, use the clean default command after this proof. Do not clutter the screen with the diagnostic environment variables.

## Timing the narration

Count only spoken lines, not headings or commands. Estimate at 120 to 140 words per minute. A concise three-minute demo often has 170 to 230 prepared words, because the rest of the time belongs to command output and human pauses.

Timing is an engineering check, not a script-reading mandate. The presenter should be able to paraphrase while preserving the three claims:

- what problem was tested;
- what the live result shows;
- what is now merged, reusable, or unblocked.

## Fallback package

Capture during a successful rehearsal:

- condensed command output with the decisive counts and validation result;
- the exact compact result shown live;
- the source candidate identity and rehearsal date;
- one sentence explaining whether the data is live, cached, or snapshot-based.

Keep the fallback in the same runbook, immediately after the live sequence. It should be usable by screen sharing the note without editing.

## Likely questions

Prepare short answers for:

- What is the join key or contract boundary?
- Why do the counts change between stages?
- Why did some inputs not match?
- Is the data live or a snapshot?
- What makes the result reproducible?
- What does this prove, and what does it not prove?

Answers should distinguish a reference implementation from a production service and verified behavior from future scope.

## Screen hygiene

- Use one enlarged terminal.
- Pre-position the runbook beside it.
- Keep credentials, noisy shell initialization, unrelated tabs, and distracting Git state off screen.
- Run the sequence once immediately before the meeting.
- If the checkout's tracking branch creates irrelevant status noise, verify the exact candidate separately and omit `git status` from the live path.
