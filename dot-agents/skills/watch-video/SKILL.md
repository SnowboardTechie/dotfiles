---
name: watch-video
description: Use whenever Bryan gives a video link (YouTube, Vimeo, any page yt-dlp reads) or asks you to watch a video or read its transcript. Gets the real transcript and frames before anything else is said about the video.
---

# Watch a video

When Bryan hands you a video, he is asking you to watch it. Reading the whole transcript is the minimum; articles, search snippets, descriptions and comments about the video are not the video. The work about the video starts only after you have read its transcript.

## Steps

1. **Get the transcript.** Run, with a timeout of at least 15 minutes:

   ```sh
   python3 <this skill's directory>/scripts/get_video.py "<url>" "$(mktemp -d)/video" --frames 8
   ```

   It writes `meta.json` (title, channel, length, chapters, description), `transcript.txt` (timestamped) and `frames/*.jpg`. It tries the video's own captions first; YouTube often answers those with HTTP 429 here, and then it downloads the audio and transcribes it locally with Whisper (about a minute for a 35-minute video on the Mac). Done when the script prints a `transcript:` line with a word count that fits the length (roughly 130–170 words a minute of speech).

2. **Read all of `transcript.txt`.** Every line, paged with `read` if long. Done when you have read the last line.

3. **Look at the frames** when the picture matters: slides, documents, code, demos, on-screen text, or when Bryan said "watch". Read each frame image. For a specific moment, rerun with more frames or grab one with ffmpeg from `video.*` at that timestamp.

4. **Then do what Bryan asked**, citing the video by timestamp (`[00:27:22]`) for what it says or shows.

## When the script fails

It exits non-zero and prints why. Read the reason and fix it: try the other path (`--force-whisper` skips captions), update yt-dlp (`uvx --refresh ...`), or fetch a different format. Pi's `fetch_content` YouTube mode needs a Gemini key or a Chrome Google login that this machine lacks; it is not the route.

If every route fails, stop and tell Bryan, before any other work: the video was not watched, what you tried, and the exact error. Then ask him how he wants to proceed. Hand him no summary built from coverage of the video, and fold no secondhand version into a larger report.

## Reporting

Say how you got the transcript (`source.txt`: captions or Whisper) in one line. A Whisper transcript can mishear names and numbers; check those against the frames or the description before relying on them.
