---
name: voice-bryan
author: Bryan
description: >
  Use when drafting messages other humans will read: Slack, PR comments, PR
  reviews, email replies, GitHub/Forgejo issue replies, standup notes, sprint
  deliverable updates, retros, or any teammate-facing copy. Invoke BEFORE
  writing the message, not after. Skip for commit messages, PR descriptions of
  your own work, code comments, internal planning notes, and vault notes.
---

# Voice: Bryan

How Bryan writes to teammates and collaborators. The corpus, not any agent or
runtime, is the source of truth. Drafts should be concise, direct, and ready to
send, with zero em-dashes. PR review has the richest positive and correction
coverage; Slack is also well represented. Email, GitHub/Forgejo issues, and
standups remain placeholders pending samples in those channels.

## When this applies

- Slack messages, replies, threads, announcements
- PR comments and code-review feedback (Bryan's own PRs or others')
- Email replies (`gws-gmail-reply`, `gws-gmail-send`, drafts in Gmail)
- GitHub/Forgejo issue and PR-discussion replies
- Standup notes, sprint deliverable updates, retro write-ups
- Any text where the audience is a teammate, collaborator, or external partner

## When NOT to use

- Commit messages: different audience (future-self / git archaeologist)
- PR descriptions of Bryan's own work: repo template, factual not voiced
- Code comments: terse technical register
- Internal planning, scratchpads, vault notes: for Bryan's own consumption
- AI-to-AI prompts, skill content, agent instructions: different register

## Process

1. **Load `references/core-traits.md`.** Cross-channel voice + per-channel
   sub-sections (Slack / PR review / Email / GitHub-Forgejo / Standups). Always
   load; channel rules and core traits live in the same file.
2. **Skim `references/anti-patterns.md`.** Cheaper to avoid forbidden phrases
   up front than to rewrite a draft Bryan already saw.
3. **Draft the message.**
4. **Self-check against anti-patterns** before presenting. Cut context that
   does not change the reader's next decision, and confirm there are zero
   em-dashes. Rewrite as needed.
5. **Pattern-match against `references/samples.md`** if channel or register
   feels ambiguous. The corpus is the source of truth; `core-traits.md` is the
   distilled summary.

## When uncertain

Present 2 drafts at different registers and ask Bryan to pick. Capture the
choice into `references/samples.md` (with date + channel) so next draft is
closer to target.

## Reference material

| File | Purpose | Load |
|---|---|---|
| `references/core-traits.md` | Cross-channel voice + per-channel sub-sections | Every time |
| `references/samples.md` | Corpus of real Bryan messages, organized by channel | When uncertain or to seed `core-traits.md` |
| `references/off-target.md` | Historical drafts Bryan rewrote, with diagnoses | When stuck on a recurring miss |
| `references/anti-patterns.md` | Phrases, openings, closings, structural moves to avoid | Every time |

## For non-Skill agents

Plain markdown. Agents without a Skill runtime read `SKILL.md` plus all four
files in `references/`. Mechanism differs; content is the same.
