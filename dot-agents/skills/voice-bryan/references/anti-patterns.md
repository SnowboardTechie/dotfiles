# Anti-patterns: phrases and shapes to avoid

Phrases, openings, closings, and structural moves that read as off-voice for
Bryan when drafting AS Bryan. Reaching for any of these means rewrite before
showing the draft.

> **Status:** seeded 2026-05-28. The top section ("Bryan-specific, confirmed
> from corpus") is grounded in real Bryan corrections from `samples.md` and
> `off-target.md`. The lower section ("Generic AI-flavored defaults") is
> seeded from common AI patterns but unconfirmed against Bryan's corpus.
> Treat the lower section as suspicion-worthy until validated; the top section
> is canon.

## Bryan-specific (confirmed from corpus)

These rules come directly from Bryan corrections observed in the corpus.
Highest-priority avoidance list.

### Em-dashes (U+2014)

**Zero is the target, not moderation.** Bryan does not use em-dashes in his
voice. Drafts written AS Bryan must omit them entirely. Substitute based on
what the em-dash was doing:

- Clarifying aside → parens or comma. Example: "Bryan (the user) prefers..."
- Joining clauses → semicolon, period, or comma + conjunction
- Emphasis or pause → colon or period
- Range or interruption → period

Confirmed by Bryan directly on 2026-05-28 ("I do not like the use of
emdashes"). **Reconfirmed at strict zero** on 2026-05-28 after the validation
pass found 5 em-dash slips in Bryan's own posted PR-body / review-summary
text (samples.md PR review entries). Bryan chose to treat those as slips he
didn't notice, not endorsements. The rule stands: zero em-dashes in any
draft AS Bryan, regardless of whether Bryan-typed text in the corpus
contains them.

Cross-validated: zero em-dashes appear in any verbatim Bryan-authored Slack
message across the samples.md corpus (5 Slack samples). The 5 em-dashes that
appear in posted PR-body / review-summary text are slips. The em-dashes in
off-target.md Claude drafts (the things Bryan corrected away from) are the
canonical AI-default pattern.

**Scope note:** This rule applies to drafts written AS Bryan. Claude's own
responses to Bryan in conversation are unconstrained (see memory file
`feedback_em_dashes.md`).

### Apologetic openers on correction replies

Forbidden patterns:

- "My earlier answer was [bad-thing]" (hand-wavy, sloppy, unclear, etc.)
- "I should have caught this earlier"
- "Sorry, let me re-read"
- "I missed that"
- "My earlier answer skipped past your actual question"

Lead with the new framing directly. The quality of the new answer is the
apology. See off-target.md "hand-wavy" entry: Bryan corrected the apologetic
opener twice in one thread, escalating from "do we need to call it 'hand-wavy'?
feels like you're beating me up for trying" to "wow, still beating me up with
line 1."

### "Agreed" / "Correct" / "Right" as peer assent (use the right register)

Reserve definitive-stamp words for cases where someone explicitly asked for
a yes/no decision. The actual assent shape depends on what's being assented
to (validated against samples.md PR-review entries, 2026-05-28):

- **Proposal-assent** (someone proposed a change or idea): use "I think so,
  ..." / "I'd land it the same way" / "that tracks for me." Canonical
  correction in off-target.md "Agreed → I think so" entry.
- **Work-approval** (someone shipped or built something): use "Nice work,
  this is feeling solid" + specific change-callouts, OR "Approving." as a
  one-word terminal, OR "👍🏻" / "👍 approved." (single-emoji terminals
  carry weight in PR review only).
- **Explanation-acceptance** (someone explained their rationale and you
  accept it): use "Got it, that makes sense." + playback of the explanation
  in your own words.

Reaching for "Agreed" / "Correct" / "Right" in any of these three contexts
is the anti-pattern. See `core-traits.md` "Channel: PR review > Assent
registers" for the canonical examples.

### Packing every investigation finding into the reply

If a finding does not change the reader's next decision, it stays in Bryan's
own notes. Reply to the question that was asked, not to the investigation
that surfaced 3 things. Bryan corrected this twice in one session. Highest
volume miss Claude makes.

### Narrating self-corrections to a reviewer

Forbidden patterns:

- "I'll fix that in the same pass"
- "I noticed I had X wrong, I'll update"
- "The spec overstates Y, I'll correct"

Spec-mechanics fixes get fixed silently. Calling them out in a reviewer reply
frames Bryan's own work negatively for no upside. Apply quietly; mention only
if the reviewer would otherwise be confused.

### Substituting smaller words instead of cutting scaffolding

When Bryan says "shorten the reply," the move is:

1. Cut labeling preambles ("Two things make it safe to drop for now:")
2. Cut restated-asides ("like you said", "as you mentioned")
3. Cut hedge-suffixes whose work is done by the main clause
4. Only then consider word substitution

See off-target.md D3 descope entry. "Shorten" is structural, not lexical.

### Volatile identifiers in artifact comments

When commenting on artifacts under active revision (spec docs, in-flight PRs,
draft RFCs), avoid pinning to identifiers that could shift:

- Sub-issue numbers in a spec being renumbered
- Section IDs in a doc under restructure
- Line numbers in a draft under edit

Use stable phrasings: "at implementation time" not "at sub-issue (11) time",
"in the catalog section" not "in section 4.2.3."

### Gratitude on re-review / second-favor asks (don't strip it)

When asking teammates to spend time *again* on something they already
reviewed (re-review requests, second-favor asks), Bryan uses gracious,
imposition-acknowledging politeness, including phrasings the generic list
below flags as forbidden:

- "Thank you in advance for taking another pass when time allows." (posted
  verbatim, 2026-06-26)

The generic "Thanks in advance" closing anti-pattern (below) applies to
*cold / first-time* asks, not re-review asks: there the reviewer already did
you a favor once, so the close thanks them for both the past look and the
next. Two calibration rules confirmed in the same session:

- **"when time allows" is fine; "no rush" is not.** "when time allows"
  acknowledges the reviewer's time; "no rush" downplays the work's
  importance. Bryan rejected "no rush" and posted "when time allows" in the
  same draft. Same surface, opposite urgency signal. Don't reach for "no
  rush" / "whenever you've got a spare cycle" to sound gracious.
- **Gratitude can lead AND close** on a second-favor ask: thank for the
  first looks up front, thank for the next pass at the end. Not a praise
  sandwich; two real thank-yous for two real favors.

See samples.md "2026-06-26: Re-review request for a batch of PRs."

---

## Generic AI-flavored defaults (unconfirmed against Bryan corpus)

Common AI-output anti-patterns. Treat with suspicion until validated against
real corrections. Some of these may be wrong for Bryan specifically; some may
need promotion to the canonical section above once seen in corrections.

### Openings to avoid

- "Great question!" / "Excellent point!" (sycophantic, unearned warmth)
- "I appreciate you bringing this up" (performative)
- "Just wanted to..." / "Just a quick note..." (minimizing, hedging)
- "I hope this finds you well" (formal email template flavor)
- "Hey team," without substance immediately after (filler greeting)
- "To follow up on..." (meta-narration; just follow up)

### Closings to avoid

- "Hope this helps!" (over-eager)
- "Please let me know if you have any questions" (generic default footer)
- "Happy to discuss further" (filler when no specific discussion is offered)
- "Thanks in advance" (presumes the ask, often reads as pushy). Exception:
  re-review / second-favor asks, where Bryan does use it; see "Gratitude on
  re-review / second-favor asks" above.
- "Looking forward to your response" (pressure-cuffed politeness)

### Structural anti-patterns

- Excessive bullet lists where 2 sentences would do
- Numbered steps for non-sequential things
- Leading with context the recipient already has (they sent the message)
- Closing every message with a CTA when none is needed
- Restating what they said back to them (fine for ambiguous threads; default
  to action, not summary)
- Three-paragraph framing for a one-sentence answer

### Word-level

- "Leverage" (as verb), "synergy", "circle back", "touch base", "reach out":
  corporate flavor
- "Utilize": use "use"
- "Simply" / "just" as minimizers that underplay the actual work
- "Definitely" / "absolutely" as enthusiastic agreement filler
- "Going forward": usually deletable
- "At this time": say "now" or delete

### Tonal anti-patterns

- Over-explaining your reasoning when no one asked (Bryan trusts recipients
  to ask if they need more)
- Hedging blockers as nits (if it's blocking, say so; don't soften it)
- Praise sandwiches (if you have a concern, say the concern; the
  praise+concern+praise wrapper reads as evasive)
- Performative humility ("I might be wrong but..." preceding a correct
  technical observation)

## When in doubt

- Cut the first sentence. If the message still works, the first sentence was
  filler.
- Cut adjectives and adverbs. Most of them are filler too.
- If you're tempted to write "I think" or "I believe" before a factual
  statement, delete it.
- If you wrote "can" / "could" / "may" before a behavior you've verified,
  delete the hedge: "an invalid Date throws past safeParse", not "can throw".
- Run the draft through the Bryan-specific list above before considering it
  done. If any rule is broken, rewrite before showing.

---

> Refine the lower section against `off-target.md` as real corrections
> accumulate. Generic anti-patterns should be *promoted* to the Bryan-specific
> section once confirmed, or *removed* if Bryan-specific evidence contradicts
> them.
