# Hex troubleshooting

`HEX=/Applications/Hex.app/Contents/MacOS/hex`. Commands other than
`meetings` (`settings`, `logs`, `status`) talk to the running app; exit code 3
means Hex isn't running. Changing any Hex setting needs Bryan's OK.

## Where Hex keeps things

- Each meeting: `~/Library/Application Support/hex/meetings/<id>/` with
  `manifest.json`, `system.wav` (the call), `microphone.wav` (Bryan),
  `transcript.md`, `transcript.ndjson` and `transcript.rolling.ndjson`.
- Readable export: `~/Documents/Hex Meetings/YYYY-MM-DD HHMM <title>.md`
  (`manifest.export_path`).
- Settings: `~/Library/Application Support/hex/settings.json`, or
  `$HEX settings get <key>` / `$HEX settings list`. Log: `$HEX logs`.
- `~/granola-export/` is the source backup of the 138 Granola imports
  (`_scripts/to_hex.py` rebuilt them byte-identically on 2026-11-06).

## A meeting seems missing

1. Check the date in the table in `SKILL.md`: 2026-10-23 to 2026-10-29 is
   Superwhisper only.
2. `$HEX meetings list --since <day> --until <day>`; recordings started late or
   by hand can carry a title Hex guessed rather than the calendar's.
3. `$HEX settings get meetings.retention` should be `forever`. Expired meetings
   go to the macOS Trash with the log line `moved an expired meeting to the
   Trash`; agents can't read `~/.Trash` (macOS privacy), so ask Bryan to Put
   Back, or rebuild a Granola import from `~/granola-export`.
4. Report it as "not found in Hex" with what you checked, never as "not
   recorded".

## An empty transcript

"No speech was transcribed", with `notes_error` = `the transcript has no
speech to summarize`, means transcription returned nothing, not that nobody
spoke.

- Confirm the audio has sound: `ffmpeg -hide_banner -nostats -i system.wav -af
  volumedetect -f null -` (a mean around -23 dB is speech).
- `transcript.rolling.ndjson` `covered_ms` shows how much audio Hex processed.
  Full coverage, an empty `transcript.ndjson`, null errors and zero
  `echo_suppressed_utterances` together mean the model ran and returned no text.
- Find the model that was active from the log's `variant="<model>"` line around
  the meeting time (the module shows as `hex::parakeet` for every model).
- History: the 2026-11-03 huddle came back empty on Cohere Transcribe; Bryan
  went back to Parakeet on 2026-11-04 and it has transcribed since. Raise the
  model only if a transcript fails again.

## Recover a transcript from the audio (checked working)

Work in a scratch directory, never inside the Hex folder.

1. Convert each track: `ffmpeg -i <track>.wav -ac 1 -ar 16000 -c:a pcm_s16le
   <track>.16k.wav`.
2. `whisper-cli -m ~/.hermes/profiles/sgg/workspace/whisper-models/ggml-large-v3-turbo-q5_0.bin
   -f <track>.16k.wav -l en -t 8 -oj -otxt -of <track> -np` (Homebrew
   `whisper-cpp`; about 30 s per track for 15 minutes).
3. Merge the JSON segments by `offsets.from`, shifting system segments by
   `(system.first_arrival_us - microphone.first_arrival_us)/1000` ms. Drop
   empty, "Thank you." and "you" lines and consecutive duplicates. Label lines
   `Bryan` (mic) or `Call` (system).
4. Write `~/Documents/Hex Meetings/<export name> (re-transcribed).md`: a header
   (source, model, a note that it is a machine transcript and names are
   inferred), notes by topic, "Action items for Bryan", then the transcript.
   Check the file doesn't exist first; never overwrite Hex's own files.

Registering a recovered transcript back into Hex is done only when Bryan asks
(done once, for `1793732373217-31090`, which has since expired): back up the
meeting's manifest and transcript files; write `transcript.ndjson` as lines of
`{source: system|microphone, start_ms, end_ms, text}` offset by each track's
`first_arrival_us`/1000, and `transcript.md` as `**MM:SS You|Them**  text`;
set `manifest.notes = {title, summary, generated_at_ms, elapsed_ms: 0,
excerpt_chars: 0, transcript_chars}` and `notes_error = null`. Write each file
atomically with mode 0600, then check with `$HEX meetings search`.
