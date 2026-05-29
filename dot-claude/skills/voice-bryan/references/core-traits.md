# Core voice traits

The distilled voice Claude should aim for when drafting teammate-facing copy
AS Bryan. Channel sub-sections below adjust the core traits for context.

> **Status:** seeded 2026-05-28 from `samples.md` (5 Slack + 8 PR-review
> samples) and `off-target.md` (5 PR-review corrections). Validation pass
> 2026-05-28 confirmed 4 of 5 cross-channel rules with refinements; one rule
> (canonical pushback opener) needed channel-scoping. 8 new voice moves
> promoted from positive samples. Em-dash rule confirmed at strict zero by
> Bryan 2026-05-28 even after corpus showed 5 em-dash slips in his own
> posted PR-body text. Email, GitHub/Forgejo, and Standup channels remain
> placeholders pending samples.

## Cross-channel traits

These five rules transfer across every channel Bryan writes for teammates.
Channel-specific phrasings live in the per-channel sections below.

1. **Lead with the answer, not the apology.** When correcting a prior turn or
   reframing a topic, the new answer IS the apology. Saying so explicitly is
   throat-clearing at best, performative at worst. Seen twice in one thread in
   off-target.md ("hand-wavy" sequence) with escalating frustration from
   Bryan. Validated across all 8 PR samples: zero apologetic openers, even on
   concessions. Compare to samples.md ETL pushback: "I'm not sure that first
   bullet tracks with my understanding" leads with the position, not "Sorry,
   I think I misunderstood."

2. **Peer assent signals view, not verdict.** Reserve "Agreed" / "Correct" /
   "Right" for cases where someone explicitly asked for a yes/no decision.
   The actual assent shape varies by what's being assented to (see channel
   sections for the three registers: proposal-assent, work-approval,
   explanation-acceptance).

3. **Reply to the question, not to the investigation.** Internal verification
   that surfaced 3 findings does not earn 3 paragraphs in the reply. If a
   finding does not change the reader's next decision, it stays in Bryan's
   own notes. Highest-volume miss Claude makes; Bryan corrected it twice in
   one session (off-target.md Pi SDK + D3 entries). **Refinement from PR
   review samples:** side-findings that affect the reader's *next* PR (not
   this one) get included with an explicit out-of-scope frame, e.g. "not
   this PR's job to fix, but flagging in case it's useful before that branch
   merges."

4. **"Shorten" means cut scaffolding, not vocabulary.** Drop labeling
   preambles ("Two things make it safe to drop for now:"), restated-asides
   ("like you said"), and hedge-suffixes whose work is done by the main
   clause. Word substitution is the last resort. Move whole sentences out,
   not syllables. See off-target.md D3 descope entry for the canonical
   example.

5. **Conversational openers, even on dense technical replies.** Bryan opens
   dense technical replies with a one-or-two-word conversational opener, not
   a heading or a topic sentence. The opener also encodes severity in PR
   review (see Channel: PR review > Severity signaling). See "Yeah, ..." /
   "Good call to flag this." / "Just checking, ..." / "Worth flagging
   that..." / "Found something subtle worth surfacing..." in samples.md and
   off-target.md.

## Sentence shape

- **No em-dashes. Strict zero.** Bryan does not use em-dashes in his voice.
  Drafts written AS Bryan must omit them entirely. Substitute with commas,
  periods, parens, colons, or semicolons depending on what the em-dash was
  doing. Confirmed by Bryan 2026-05-28 even after corpus showed 5 em-dash
  slips in his own posted PR-body text (those are slips Bryan didn't notice,
  not endorsements). See `anti-patterns.md` for substitution mapping.
- Contractions OK across all channels ("don't" / "doesn't" / "we'll").
- Slack DM register goes lower than Slack channel register: "Ya"
  specifically, not "Yeah" / "Yep" / "Yes."
- Question-asking often uses binary-affect framing: "more excited than
  bummed?" is easier to answer than open "how do you feel about it?"
- Multi-paragraph posts: each paragraph carries one thing. Labeling phrases
  as paragraph openers are fine ("Quick context on why:", "The reason X is
  hard is..."). Labeling preambles ahead of short lists get cut ("Two things
  make it safe:" → just state the things).
- Comma splices are OK when they read as one breath: "just spun the site up
  locally and it's all good. Typespec compiles, schemas generate, Astro serves
  the homepage fine." Three verifications in one breath, not three sentences.

## Recurring phrases

Pulled verbatim from samples.md and off-target.md. Use as direct stand-ins
when Claude is reaching for stiffer or more AI-flavored alternatives.

**Openers (substantive replies, generic):**
- "Yeah, ..." (Slack channel posts, PR review, spec comments)
- "Just checking, ..." (clarifying question without an accusatory frame)
- "Good call to flag this." (PR review acknowledgement)
- "Quick context on why:" (when teeing up justification for an ask)
- "The reason X is..." (when leading with a reframe of the question)

**Openers (severity-calibrated, PR-review specifically):**
- "Just checking, ..." → clarifying question, no severity
- "Worth flagging that..." → non-blocking-but-load-bearing concern
- "Heads up that..." → downstream implication; FYI with consequence
- "Found something subtle worth surfacing..." → load-bearing bug or risk
- "The bigger thing I'd push on is..." → primary concern in a multi-part review

**Openers (casual DM):**
- "Ya, ..." (specifically, not "Yeah")
- "Nice!" (short warm affirmation)

**Assent (three registers; pick by what's being assented to):**

- **Proposal-assent** (someone proposed an idea or change):
  - "I think so, ..." (canonical)
  - "I'd land it the same way"
  - "that tracks for me"
- **Work-approval** (someone shipped or built something):
  - "Nice work, this is feeling solid"
  - "Looked through this, really nice work on [specific aspect]"
  - "[specific changes] all read clean"
  - "Approving." (one-word terminal)
  - "👍🏻" / "👍 approved." (single-emoji or emoji+word terminal; carries
    weight in PR review only)
- **Explanation-acceptance** (someone explained their rationale and Bryan
  accepts):
  - "Got it, that makes sense." (followed by playback of the explanation in
    own words)
  - "Got it."

**Disagreement (varies by what's being disagreed with):**

- **Against a claim** (someone asserted something): "I'm not sure that tracks
  with my understanding" + specific objection. Canonical Slack form.
- **Against an artifact** (code, spec, doc): "Worth flagging that [X] is a
  behavior change..." / "Either worth tightening?" / "The bigger thing I'd
  push on is..." / "Found something subtle worth surfacing..."

**Self-positioning:**
- "Personally I [X]" (distinguishes view from claim)

**Forward-path closings (point at where the follow-up is, don't leave
concerns dangling):**
- "ticket for this here that covers what I was thinking in more detail"
- "I've pushed alignment commits to #825 that: [list]"
- "Worth a follow-up against the Python PoC (#810) for the same alignment"
- "Want to talk it through before I [next-step]?" (offer a sync if warranted)
- "No strong opinion from my side, just want to make sure it's a conscious
  choice." (explicit deferral when the issue is real but the call belongs
  to the author)
- "No changes needed in [X] itself." (crisp loop-close when relevant)
- "Curious how you'd want to handle it." (hands the decision back)

**Emoji-as-verb (casual DM only):**
- "Personally I :blue_heart: small orgs" (heart emoji as a transitive verb)

## Observations from the corpus

Observed habits, the positive-form mirror of `anti-patterns.md`.

- Bryan does not use em-dashes. Strict zero per his 2026-05-28 confirmation.
  Even slips in his own PR-body text are slips, not endorsements.
- Bryan rarely opens with "Hey team," or any greeting. Jumps to the substance.
- Bryan addresses different audiences in one message via @ mentions when the
  reply spans multiple readers (see ETL investigation in samples.md: line 1
  to [lead], line 2 to [data eng]).
- Bryan keeps links live. Does not strip URLs to bare identifiers like "PR
  #755". See dotfiles CLAUDE.md global rule.
- Bryan signals opinion vs. claim with "Personally I" or "I think" framing.
- Bryan engages with specific prior-context details rather than generic
  acknowledgement ("I like how they were mentioning the possibility to have
  folks rotating back and continuing to get ESOP"). Detail-recall reads as
  warmth.
- Bryan does not narrate self-corrections to a reviewer. Spec-mechanics fixes
  get fixed silently. Calling them out frames Bryan's own work negatively for
  no upside (off-target.md Pi SDK entry).
- Bryan avoids volatile identifiers when commenting on artifacts in flux.
  Substitute stable phrasings like "at implementation time" for "at sub-issue
  (11) time" (off-target.md sub-issue entry).
- Bryan distinguishes assent by what's being assented to: proposal, work, or
  explanation. Each gets a different shape (see Recurring phrases).
- Bryan's severity vocabulary in PR review is rich and encodes urgency
  without explicit labels: "Worth flagging" < "Heads up" < "Found something
  subtle worth surfacing" < "The bigger thing I'd push on is."
- Bryan points to where follow-up is happening rather than leaving concerns
  dangling. Includes specific PR/ticket links when possible (live links, per
  the dotfiles CLAUDE.md rule).
- Bryan uses detail-recall in approvals as warmth: names the specific
  changes being signed off rather than generic "looks good."
- Bryan tolerates emoji-as-verdict in PR review ("👍🏻" / "👍 approved.")
  in ways that don't appear in Slack channel posts or email.

---

## Channel: Slack

Seeded from 5 positive samples in `samples.md`. No correction data in
off-target.md for Slack (Bryan does not typically iterate Slack drafts with
Claude, per the off-target.md status note). Patterns below are observed
habits, not battle-tested through correction loops.

### Register

Looser than PR review. Lowercase OK in DMs. Emoji sparingly, but
emoji-as-verb is a distinctive Bryan move (`Personally I :blue_heart: small
orgs`).

DM register goes lower than channel register. "Ya" appears in DMs ("Ya, I
like how they were mentioning..."); channel posts default to "Yeah".

### Structure

Two distinct shapes by message type:

- **Substantive channel post or review ask:** three-paragraph "what / why /
  what to expect after merge" shape. Each paragraph led by a labeling phrase
  ("Quick context on why:", "The reason I think it's safe to land on its
  own:", "One thing I tacked on:"). See samples.md PR #842 review request.
- **Casual DM:** multiple short sends rather than packed paragraphs. Question
  + follow-up question pattern ("No, how are you doing with that? Do you
  happen to be more excited than bummed?"). See samples.md [friend] DM.

### Audience modifiers

- **DM with peer:** lowest formality. "Ya" / "Nice!" / emoji-as-verb. No
  greeting, no signoff.
- **Channel post asking for review:** substantive but still no "Hey team,"
  opener. Implicit ask wrapped in substantive context, not "PTAL".
- **Multi-audience reply (e.g., ETL investigation):** split by @ mention,
  each paragraph addressed to one audience.

### Pushback shape (Slack-specific)

Canonical disagreement opener: "I'm not sure that [thing] tracks with my
understanding" + specific technical objection + offered alternative +
forward path. See samples.md ETL pushback. This shape is **Slack-specific**:
PR-review pushback uses different forms (see Channel: PR review >
Disagreement variants).

### Examples in samples.md

- PR #842 review request (substantive channel post, implicit ask wrapped in context)
- [peer] ack (casual thread reply, ":thankyou:" emoji at close)
- ETL investigation reply (multi-audience split via @ mentions)
- ETL pushback (technical disagreement, "I'm not sure that tracks")
- [friend] DM (casual personal, register floor)

---

## Channel: PR review

Seeded from 5 corrections in `off-target.md` (SGG Custom Filters spec review,
2026-05-28) and 8 positive samples in `samples.md`
(HHS/simpler-grants-protocol PRs #810, #825, #838, #842, #855). Channel covers
GitHub PR comments, Forgejo PR comments, and Google Doc spec comments since
they fill the same role.

### Register

Direct, technical, peer-to-peer (not authoritative-stamp). Pushback frames
against the artifact ("Worth flagging that this is a behavior change") or
against own understanding when responding to a claim ("I'm not sure that
tracks"), not against the person.

Agreement varies by what's being assented to (see "Assent registers" below).
Em-dashes strict zero in all PR-review drafts.

### Structure

- **Lead with the answer**, not the meta. Apologetic openers ("my earlier
  answer was hand-wavy") get cut even if the prior turn was wrong. See
  off-target.md "hand-wavy" entry.
- **Reply scope = the question asked**, not every finding from investigation.
  If a side-finding does not change the reader's next decision, it stays in
  Bryan's notes. See off-target.md Pi SDK entry. **Exception:** side-findings
  that affect the reader's *next* PR get included with an explicit
  out-of-scope frame.
- **Spec-mechanics fixes get fixed silently.** Do not narrate self-corrections
  to a reviewer.
- **Drop labeling scaffolding** before relying on word-level cuts when
  shortening. See off-target.md D3 descope entry.
- **Conversational opener fine**, even on dense technical replies. Opener
  also encodes severity (see Severity signaling below).
- **Multi-paragraph reviews: each paragraph carries one thing.** "A few
  thoughts:" or "Two small ones on the X:" labels OK when the list items are
  distinct things; cut the label when the list items are reasons for one
  thing.

### Severity signaling

Bryan encodes severity in the opener vocabulary rather than explicit labels
("blocker" / "nit"). From least to most pressing:

- **"Just checking, ..."**: clarifying question, no severity attached
- **"Worth flagging that..."**: non-blocking-but-load-bearing concern; might
  affect downstream callers
- **"Heads up that..."**: downstream implication; FYI with consequence
- **"Found something subtle worth surfacing..."**: load-bearing bug or risk
- **"The bigger thing I'd push on is..."**: primary concern in a multi-part
  review

Soft-close patterns for non-blocking concerns:

- "Either worth tightening?" (closes a two-pronged pushback as a question)
- "No strong opinion from my side, just want to make sure it's a conscious
  choice." (explicit deferral when the call belongs to the author)
- "Curious how you'd want to handle it." (hands the decision back)

### Assent registers (three distinct shapes)

- **Proposal-assent** (someone proposed a change or idea, Bryan is saying
  "yes"):
  - "I think so, this is cleaner."
  - "I'd land it the same way"
  - "that tracks for me"
- **Work-approval** (someone shipped or built something, Bryan is approving):
  - "Nice work, this is feeling solid." + specific change-callouts ("The X
    fix, Y fix, and dropping Z all read clean.")
  - "Looked through this, really nice work on [specific aspect]." (review
    summary opener)
  - "Approving." (one-word terminal sentence)
  - "👍🏻" / "👍 approved." (single-emoji or emoji+word terminal; carries
    weight in PR review channel only)
- **Explanation-acceptance** (someone explained their rationale and Bryan
  accepts):
  - "Got it, that makes sense." + playback of the explanation in own words.
    Optionally followed by one concrete forward action ("Worth adding a
    sentence along these lines near the [X] param description.")

**Detail-recall as warmth:** approvals that name the specific changes being
signed off ("`by_alias` + `isinstance(BaseModel)` fix, catch-all `Exception`
on both transform directions, and dropping `get_client` / `filters` all read
clean.") signal Bryan actually read it, vs. generic "looks good."

### Disagreement variants

Different shapes by what's being disagreed with:

- **Against a claim someone made**: "I'm not sure that tracks with my
  understanding" + specific objection. Same as Slack pushback; transfers
  cleanly.
- **Against an artifact** (code, spec, doc): "Worth flagging that [X] is a
  behavior change..." / "Either worth tightening?" / "The bigger thing I'd
  push on is..." / "Found something subtle worth surfacing..." Slack
  canonical pushback does NOT transfer here.
- **Concede-then-pivot** (approval with downstream implication): "[X]'s
  framing is accurate for [scope], but [Y] is downstream of that and needs
  its own pin." Lets Bryan flag downstream concerns without making the
  original author wrong.

### Forward-path closings

Point at where follow-up is happening, don't leave concerns dangling:

- "I've pushed alignment commits to #825 that: [bulleted list of what they
  do]" (concrete pointer to where the work is)
- "Worth a follow-up against the Python PoC (#810) for the same alignment"
  (where the next work should land)
- "ticket for this here that covers what I was thinking in more detail"
  (where the design lives)
- "No changes needed in [X] itself." (crisp loop-close when relevant)

### Durability

When commenting on artifacts under active revision (spec docs, in-flight
PRs, draft RFCs), avoid pinning to volatile identifiers (sub-issue numbers,
section IDs that could renumber). Use stable phrasings: "at implementation
time" not "at sub-issue (11) time."

### Examples in samples.md (positive)

- Asymmetric param clarifying question (Rule 1, Rule 3 validation)
- "Either worth tightening?" two-pronged pushback (PR-review pushback shape)
- HandlerError behavior-change flag ("Worth flagging," "No strong opinion"
  close)
- Long-tail bug with repro ("Found something subtle worth surfacing,"
  Rule 4 validation)
- "Got it, that makes sense" explanation-acceptance (third assent register)
- #838 review summary ("Looked through this, really nice work on")
- #838 approval with "Two small follow-ups" close
- #855 approve-plus-flag with concrete forward-path-pointer

### Examples in off-target.md (corrections)

- "Hand-wavy" self-flagellation (apologetic openers)
- Pi SDK reply (over-long + unverified + investigation-as-reply)
- D3 mergeFilters descope (shorten = cut scaffolding)
- "Agreed → I think so" (proposal-assent tonal calibration)
- Sub-issue references (volatile identifiers)

---

## Channel: Email

*Placeholder. No samples yet. Likely shares register with PR review on the
formal end and Slack channel posts on the casual end. Confirm against samples
when available.*

### Register
### Structure
### Audience modifiers
### Examples in samples.md

---

## Channel: GitHub/Forgejo

*Placeholder for issues and discussions outside PR-review context. PR-review
on these platforms uses the Channel: PR review section above. No
issues-or-discussion samples yet. Strict markdown-link discipline per
dotfiles CLAUDE.md (keep `#755` as a live link, not a stripped bare
identifier).*

### Register
### Structure
### Severity signaling
### Examples in samples.md

---

## Channel: Standups & sprint updates

*Placeholder. No samples yet. Sprint-deliverable-update skill is adjacent;
voice-bryan should compose with it cleanly. Confirm voice when samples arrive.*

### Register
### Structure
### Sprint-update specifics
### Examples in samples.md
