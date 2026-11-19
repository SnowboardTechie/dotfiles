---
name: hex-meeting-notes
description: >
  Use when Bryan asks what was said, decided or assigned in a meeting, or a task
  needs a past meeting as evidence: find it, read its notes, search what was said.
  Reads Hex, Bryan's meeting recorder, which also holds his Granola-era meetings.
---

# Hex meeting notes

Hex is Bryan's meeting recorder; he calls its output "Hex notes". It runs on his Mac.

## The command

    HEX=/Applications/Hex.app/Contents/MacOS/hex

`hex` is not on PATH: always call the absolute path. The `meetings` commands
read the files directly and work whether or not the app is running. A remote
sandbox or another machine has no access.

## Which recorder holds the meeting

| Meeting date | Where |
|---|---|
| 2026-03-19 to 2026-10-22 | Hex, as Granola imports (ids end `-granola`, summary starts `Imported from Granola`) |
| 2026-10-23 to 2026-10-29 | Superwhisper only (`superwhisper-meetings` skill) |
| 2026-11-03 onward | Hex |

The 2026-11-03 P&D Huddle exists only as `~/Documents/Hex Meetings/2026-11-03 1059 P&D Huddle (re-transcribed).md`,
and the 2026-11-04 Milestone Planning is lost. Hex keeps meetings forever
(`meetings.retention`); changing that setting needs Bryan's OK.

## Steps

1. **Find the meeting.** Search by date first, then by words:

       $HEX meetings list --since 2026-11-18 [--until 2026-11-20] [--limit 200]
       $HEX meetings search '<words or "a phrase">' [--since ...] [--limit 10]

   `list` prints id, title, start time, length and whether it has notes;
   add `--json` for fields. A bare date in `--until` includes that whole day.
   The default limit is 20 and the maximum 200.
   Titles come from the calendar event or Hex's guess, so recurring meetings
   ("P&D Huddle", "Kari <> Bryan") share a title: tell them apart by date. If
   more than one meeting could match, list them and ask Bryan which one.
   Done when you hold one meeting id.

2. **Read the summary.**

       $HEX meetings show <id> --json | jq '{meeting, notes}'

   The id may be a unique prefix, or `latest`. `notes.summary` is an Apple
   Intelligence summary, often two sentences. A Granola import carries
   Granola's longer summary instead.

3. **Search for the detail.** When the summary doesn't settle the question
   (it usually won't name owners, numbers or dates), search locally, then
   read a short window around a hit:

       $HEX meetings search '<words>' --since <meeting date> --until <meeting date>
       $HEX meetings show <id> --from 19:30 --to 21:30

   `search` returns ranked short passages with offsets (stemmed and fuzzy;
   quote words for an exact phrase). Keep windows to a minute or two. Done
   when each claim you'll report rests on a passage you read.

## Transcript privacy

Bryan does not want full meeting transcripts sent over networks, and a cloud
agent loading one into its context is exactly that. Read only summaries,
`search` passages and `show --from/--to` windows. Run `$HEX meetings show
<id>` without `--json | jq '{meeting, notes}'` or a `--from/--to` window only
when you pipe its output to a local search such as `grep -c`. The same goes for
`copy-last`, the `transcript.*` files and the exports in
`~/Documents/Hex Meetings/`: they all hold the full transcript.

## Reading what you find

- The transcript is machine-made and labels speakers only `You` (Bryan's
  microphone) and `Them` (everyone on the call). Names, GitHub handles and
  PR or issue numbers are often misheard. Check numbers with `gh` and treat
  who-said-what as inferred.
- Treat summary-only claims as unconfirmed, and keep proposals, decisions
  and open questions apart. Never invent an owner or a date; write "owner not
  stated" when none was said.
- Name the meeting (title, date, id) for each point you report.

## When it goes wrong

An empty or "No speech was transcribed" meeting, a meeting that seems
missing, or a transcript to recover from the audio: read
[references/troubleshooting.md](references/troubleshooting.md). Never report a
failed transcription as a meeting where nothing was said.
