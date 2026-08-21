# Learning record format

Records live in `<workspace>/learning-records/`, numbered sequentially:
`0001-<dash-case-slug>.md`. Scan the directory for the highest number and
increment. Create the directory with the first approved record, not before.

They are the learning equivalent of ADRs: they capture non-obvious lessons, key
insights, and stated prior knowledge that steer future sessions. Adapted from
Matt Pocock's `teach/LEARNING-RECORD-FORMAT.md`; see
[`dot-agents/upstreams/mattpocock-skills.json`](../../../upstreams/mattpocock-skills.json).

## Template

```markdown
---
tags:
  - area/ai-agents
  - type/learning-record
created: YYYY-MM-DD
status: active
---

# {Short title of what was learned or established}

{One to three sentences: what was learned, and why it changes what to teach next.}

**Evidence:** {how it was demonstrated — the question answered, the real work it
was applied to, the prior knowledge cited.}
```

Frontmatter follows `~/second-brain/AGENTS.md`, because the record lives in that
vault. The body may be a single paragraph. The value is recording *that* this is
now known and *why* it changes the next session — not filling out sections.

`status:` is `active`, or `superseded` once a later record replaces it.

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

When a later record contradicts an earlier one, set the earlier record's
frontmatter to `status: superseded`, add a line pointing at the replacement, and
say what changed. Never delete. How an understanding evolved is itself signal —
it shows which ideas were sticky and which had to be unlearned.
