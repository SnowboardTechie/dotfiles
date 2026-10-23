---
name: superwhisper-meetings
author: Bryan
description: >
  Use when Bryan asks about a meeting recorded in Superwhisper: find a meeting,
  answer questions about it, pull decisions and action items, compare meetings,
  or draft follow-ups. Reads meetings read-only through the local superwhisper
  CLI on Bryan's Mac; falls back to notes or transcripts Bryan pastes or shares.
---

# Superwhisper Meetings

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

138 Granola meetings (through 2026-10-22, Agile6 account) were imported on
2026-10-23 as Superwhisper meeting folders. Recognize them by summary text
starting `_Imported from Granola. Participants: ..._` and speaker names
`Microphone` / `System audio` / `System audio (<name>)`. They have no audio.
`Microphone` is the recorder's mic (usually Bryan, not guaranteed); plain
`System audio` can be several people. Speakers are Granola's labels, not
voice-separated by Superwhisper. Summaries are Granola's AI summaries.

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
- Avoid dumping full transcripts into context; read the summary first.

## Reading and answering

- Read the relevant meeting before answering. Start with the summary; fetch
  `--transcript` when you need exact quotes, speaker attribution, timing, or
  details the summary lacks.
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
