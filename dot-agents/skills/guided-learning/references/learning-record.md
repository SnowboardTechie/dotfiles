# Learning record format

Records live in `<workspace>/learning-records`, numbered sequentially:
`0001-<dash-case-slug>` (a note title in Apple Notes; a `.md` file in a vault).
List the subfolder (`apple-notes-pkm list --folder …`) or directory for the
highest number and increment. Create it with the first approved record, not
before.

They are the learning equivalent of ADRs: they capture non-obvious lessons, key
insights, and stated prior knowledge that steer future sessions. Adapted from
Matt Pocock's `teach/LEARNING-RECORD-FORMAT.md`; see
[`dot-agents/upstreams/mattpocock-skills.json`](../../../upstreams/mattpocock-skills.json).

## Template

```markdown
{One to three sentences: what was learned, and why it changes what to teach next.}

**Evidence:** {how it was demonstrated — the question answered, the real work it
was applied to, the prior knowledge cited.}

Created: YYYY-MM-DD
Status: active
Tags: area/ai-agents, type/learning-record
```

The record's title (`0001-<slug>`) is the note's first line, written by the
helper. In a vault workspace the same fields go in YAML frontmatter per that
vault's `AGENTS.md`. The body may be a single paragraph. The value is recording
*that* this is now known and *why* it changes the next session — not filling
out sections.

`Status:` is `active`, or `superseded` once a later record replaces it (in
Notes, `append` the supersession line; do not rewrite).

## Evidence is required

Upstream treats an evidence line as optional. Here it is mandatory: the whole
point of the distinction between exposure and demonstrated understanding is that
a record without evidence is indistinguishable from a coverage log. If you
cannot name the evidence, there is no record to write yet.

## When to write one

1. Bryan demonstrated genuine understanding of something non-trivial — evidence
   he can *use* the concept, not that it was explained to him. This sets a new
   floor.
2. Bryan disclosed prior knowledge ("I already know X"). Record it, and the
   depth claimed, so future sessions do not re-teach it.
3. A misconception was corrected. Highest-value: these predict where related
   topics will stumble.
4. The mission shifted in response to learning. Cross-link `INDEX.md` and update
   it there too.

## What does not qualify

- Material merely covered. Coverage is not learning — wait for evidence.
- A session activity log. Records are decision-grade insights, not a journal.
- Anything a one-line definition in `INDEX.md` already captures.
- A recalled agent memory about a past session. Memory is not evidence.

## Supersession

When a later record contradicts an earlier one, mark the earlier record
`Status: superseded` (append in Notes; edit frontmatter in a vault), add a line
naming the replacement, and say what changed. Never delete. How an understanding evolved is itself signal —
it shows which ideas were sticky and which had to be unlearned.
