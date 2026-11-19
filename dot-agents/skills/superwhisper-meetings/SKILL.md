---
name: superwhisper-meetings
author: Bryan
description: >
  Use when Bryan asks about a meeting from 2026-10-23 to 2026-10-29, the week
  only Superwhisper recorded: find it, answer questions about it, pull decisions
  and action items. Every other meeting is in Hex (hex-meeting-notes).
---

# Superwhisper Meetings

Superwhisper holds Bryan's meetings from 2026-10-23 to 2026-10-29, plus four
Granola imports from 2026-10-15 to 10-22. Hex holds everything else, Granola-era
meetings included: use the `hex-meeting-notes` skill for those.

## Access

Local CLI on Bryan's Mac (verified 2026-10-23, CLI 0.2.0, app 3.0.2):

    SW=/Users/bryan/.local/bin/superwhisper

`~/.local/bin` is not on the agent's PATH, so always call the absolute path.
The CLI reads `~/Library/Application Support/superwhisper/database/superwhisper.sqlite`.
A remote sandbox or another machine has no access to these meetings.

Read-only commands (use only these for meeting work):

    $SW meetings --json [--limit N] [--since YYYY-MM-DD] [--before YYYY-MM-DD]   # list recent
    $SW meetings search "<query>" --json [--since ...] [--before ...]            # FTS5: words, "phrases", AND/OR/NOT, prefix*
    $SW meetings read <meeting-id> --json                                        # summary + metadata
    $SW meetings read <meeting-id> --json --transcript                           # + raw transcript, timestamped speaker segments
    $SW meetings read --json                                                     # latest meeting
    $SW doctor                                                                   # diagnostics if something looks wrong

Use the meeting IDs (full UUID or unique hex prefix) the CLI returns; never
guess an ID. `meetings` excludes dictations — an empty list means no meeting
recordings exist, not a broken connection (check `$SW doctor` for the record
count). Re-run `--help` on any subcommand if flags seem to have changed.

Do not use `record`, `start`, `stop`, `switch`, `transcribe`, `vocab`,
`snippets`, or `settings` unless Bryan asks; they change app state.
`superwhisper mcp` can expose the same data as a stdio MCP server
(command: the absolute path above, args: `["mcp"]`) if a client needs it.

## Imported Granola meetings

The 138 Granola meetings (2026-03-19 to 2026-10-22) are read through Hex
(`hex-meeting-notes`), which holds all of them. Superwhisper kept only 4
(2026-10-15 to 10-22); recognize them by summary text starting
`_Imported from Granola. Participants: ..._` and speakers `Microphone` /
`System audio`. They have no audio.

Durable Markdown copy (outside iCloud): `~/granola-export/index.md` and
`~/granola-export/meetings/*.md`; raw MCP responses in `~/granola-export/raw/`;
folder ↔ Granola ID map in `~/granola-export/superwhisper-import.json`.
Screenshots attached in Granola were not exported.

How the import works (the CLI has no import command): each recording is
`~/Documents/superwhisper/recordings/<unix-epoch>/meta.json` (+ audio); on
launch the app backfills folders with valid meta.json into its SQLite index.
A meeting needs `"kind": "meeting"`, `title`, `privateNotes`, `llmResult`
(summary), `result`/`rawResult` (transcript), `segments` (start/end/text/
speaker/words), `speakers` [{number,name}], `datetime` (UTC), `duration` ms.
The folder name should be the meeting's epoch. Quit and reopen Superwhisper,
then verify with `meetings --json`. Unsupported format; back up first.

Fallback without the CLI: ask Bryan to open the meeting in Superwhisper,
click Share, and drag the summary note into the chat, or paste the relevant
notes or transcript. Use only the material provided.

## Finding the meeting

- Search by title, date, participant, or topic. Combine `search` with
  `--since`/`--before` for date ranges.
- If several meetings plausibly match, list them (title, date, ID prefix) and
  ask which one; don't pick silently.
- Never dump full transcripts into context; read the summary first.

## Transcript privacy

Bryan does not want full meeting transcripts sent over networks. He runs
Superwhisper's summary model locally for this reason; do not suggest cloud
models to improve summaries. A cloud agent reading `--transcript` output into
its context is the same exposure, so:

- Work from the summary and `privateNotes` (Bryan's own notes) by default.
- Never print or load a full transcript into context. When a specific
  detail is needed, write the `--transcript` JSON to a scratch file, search it
  locally (counts, keyword hits), print only short targeted excerpts, then
  delete the file.
- Local summaries are weaker than Granola's (observed 2026-10-27: invented
  decisions, action items all assigned to one person, diarization collapsing
  speakers). Label summary-derived decisions and owners as unconfirmed unless
  Bryan's notes or a targeted excerpt support them.

## Reading and answering

- Read the relevant meeting before answering. Start with the summary and
  `privateNotes`; use a targeted local transcript search (see Transcript
  privacy) only when you need an exact quote, speaker attribution, timing, or
  a detail the summary lacks.
- Speaker names come from calendar attendees, not voice recognition; Bryan
  can appear as `Speaker N`. Verify attribution before assigning an owner.
- Ground every answer in the meeting content. Name the meeting title and date;
  include speaker names or timestamps when available.
- Distinguish decisions, proposals, and unresolved questions.
- Never invent quotes, owners, or deadlines. If an owner or due date wasn't
  stated, say so ("owner not stated").
- For uploaded or pasted notes, use only that material.

## What to help with

- Summaries, decisions, action items (owner + due date only when stated).
- Follow-up drafts — draft only; never send unless Bryan explicitly asks
  (then follow outbound-communication-safety and voice-bryan).
- Comparisons across meetings: read each, cite which meeting each point came
  from.
- Capture into notes only when Bryan asks or the knowledge-capture routing
  applies; SGG/day-job meetings follow the existing Granola/SGG conventions.
