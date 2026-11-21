#!/usr/bin/env python3
"""Get a video's transcript (and optionally frames) into a directory.

Usage: get_video.py URL OUT_DIR [--frames N] [--force-whisper]

Order: the video's own captions through yt-dlp; when those fail (YouTube
answers 429 on the caption endpoint, or there are none), the audio through
yt-dlp transcribed locally with Whisper. --frames N also saves N evenly
spaced stills for looking at the picture.

Writes into OUT_DIR: meta.json (title, channel, duration, chapters,
description), transcript.txt (timestamped lines), source.txt (which path
produced the transcript), and frames/*.jpg with --frames.
Exits non-zero, with the reason on stderr, when no transcript was produced.
"""
import argparse
import json
import os
import platform
import re
import shutil
import subprocess
import sys
from pathlib import Path

# yt-dlp needs a JavaScript runtime for YouTube; node is on PATH here, deno
# (its default) is not; ejs:github fetches its challenge solver. curl_cffi
# lets it impersonate a browser.
YTDLP = ["uvx", "--with", "curl_cffi", "yt-dlp", "--js-runtimes", "node",
         "--remote-components", "ejs:github", "--no-playlist"]
WHISPER_MLX = ["uvx", "--python", "3.12", "--from", "mlx-whisper", "mlx_whisper"]
WHISPER_MLX_MODEL = "mlx-community/whisper-large-v3-turbo"
WHISPER_GENERIC = ["uvx", "--from", "openai-whisper", "whisper"]


def run(cmd, cwd, timeout):
    p = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout)
    return p.returncode, (p.stdout or "") + (p.stderr or "")


def fmt_ts(seconds):
    s = int(seconds)
    return f"{s // 3600:02d}:{s % 3600 // 60:02d}:{s % 60:02d}"


def vtt_to_lines(text):
    """Flatten a WebVTT file into '[hh:mm:ss] text' lines.

    YouTube's automatic captions repeat each phrase as it scrolls; keep a
    line only when it is new.
    """
    out, seen, stamp = [], set(), "00:00:00"
    for raw in text.splitlines():
        line = raw.strip()
        m = re.match(r"(\d+:)?(\d\d):(\d\d)\.\d+\s+-->", line)
        if m:
            h = int((m.group(1) or "0:")[:-1])
            stamp = f"{h:02d}:{m.group(2)}:{m.group(3)}"
            continue
        if not line or line == "WEBVTT" or line.startswith(("Kind:", "Language:", "NOTE")) or line.isdigit():
            continue
        line = re.sub(r"<[^>]+>", "", line).strip()
        if line and line not in seen:
            seen.add(line)
            out.append(f"[{stamp}] {line}")
    return out


def get_meta(url, out):
    p = subprocess.run(YTDLP + ["--skip-download", "--dump-single-json", url], cwd=out,
                       capture_output=True, text=True, timeout=180)
    try:
        info = json.loads(p.stdout)
    except ValueError:
        return None, p.stderr
    meta = {k: info.get(k) for k in ("id", "title", "channel", "upload_date", "duration", "description", "webpage_url")}
    meta["chapters"] = [
        {"start": fmt_ts(c.get("start_time", 0)), "title": c.get("title")} for c in (info.get("chapters") or [])
    ]
    (out / "meta.json").write_text(json.dumps(meta, indent=2))
    return meta, ""


def try_captions(url, out):
    for f in out.glob("cap*.vtt"):
        f.unlink()
    code, log = run(
        YTDLP + ["--skip-download", "--write-subs", "--write-auto-subs", "--sub-langs", "en,en-orig,en-US,en-GB",
                 "--sub-format", "vtt", "-o", "cap.%(ext)s", url],
        out, 240)
    files = sorted(out.glob("cap*.vtt"), key=lambda p: ("orig" in p.name, p.name))
    for f in files:
        lines = vtt_to_lines(f.read_text(errors="replace"))
        if len(lines) > 5:
            return lines, f"captions ({f.name})"
    return None, log[-1500:]


def try_whisper(url, out):
    for f in out.glob("audio.*"):
        f.unlink()
    code, log = run(YTDLP + ["-f", "bestaudio[ext=m4a]/bestaudio", "-o", "audio.%(ext)s", url], out, 900)
    audio = next(iter(sorted(out.glob("audio.*"))), None)
    if audio is None:
        return None, "audio download failed:\n" + log[-1500:]
    mac_arm = platform.system() == "Darwin" and platform.machine() == "arm64"
    if mac_arm:
        cmd = WHISPER_MLX + [audio.name, "--model", WHISPER_MLX_MODEL, "--output-format", "vtt", "--output-dir", "."]
    else:
        cmd = WHISPER_GENERIC + [audio.name, "--model", "turbo", "--output_format", "vtt", "--output_dir", "."]
    code, log = run(cmd, out, 3600)
    vtt = out / (audio.stem + ".vtt")
    if not vtt.exists():
        return None, "whisper failed:\n" + log[-1500:]
    lines = vtt_to_lines(vtt.read_text(errors="replace"))
    return (lines, "whisper " + ("mlx " + WHISPER_MLX_MODEL if mac_arm else "openai-whisper turbo")) if lines else (None, "whisper produced no text")


def get_frames(url, out, n, duration):
    frames = out / "frames"
    frames.mkdir(exist_ok=True)
    code, log = run(YTDLP + ["-f", "worstvideo[height>=360]/best[height>=360]/best", "-o", "video.%(ext)s", url], out, 900)
    video = next(iter(sorted(out.glob("video.*"))), None)
    if video is None or not shutil.which("ffmpeg"):
        return "frames skipped: " + ("no ffmpeg" if video else "video download failed")
    duration = duration or 600
    for i in range(n):
        t = duration * (i + 0.5) / n
        run(["ffmpeg", "-loglevel", "error", "-y", "-ss", str(t), "-i", video.name, "-frames:v", "1",
             "-vf", "scale=960:-2", f"frames/{fmt_ts(t).replace(':', '-')}.jpg"], out, 120)
    return f"frames: {len(list(frames.glob('*.jpg')))} saved in {frames}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("url")
    ap.add_argument("out_dir")
    ap.add_argument("--frames", type=int, default=0)
    ap.add_argument("--force-whisper", action="store_true")
    a = ap.parse_args()
    if not shutil.which("uvx"):
        sys.exit("uvx is not on PATH; install uv")
    out = Path(a.out_dir).expanduser().resolve()
    out.mkdir(parents=True, exist_ok=True)

    meta, why = get_meta(a.url, out)
    if meta:
        print(f"title: {meta['title']}  channel: {meta['channel']}  duration: {fmt_ts(meta['duration'] or 0)}")
    else:
        print("metadata failed (continuing):", why[-500:], file=sys.stderr)

    lines, source = (None, "skipped") if a.force_whisper else try_captions(a.url, out)
    if lines is None:
        print("captions unavailable, transcribing the audio:", source.strip().splitlines()[-1:] or "", file=sys.stderr)
        lines, source = try_whisper(a.url, out)
    if lines is None:
        sys.exit("NO TRANSCRIPT. " + source)

    (out / "transcript.txt").write_text("\n".join(lines) + "\n")
    (out / "source.txt").write_text(source + "\n")
    words = sum(len(l.split()) - 1 for l in lines)
    print(f"transcript: {out / 'transcript.txt'}  ({len(lines)} lines, ~{words} words, via {source})")

    if a.frames:
        print(get_frames(a.url, out, a.frames, meta and meta.get("duration")))


if __name__ == "__main__":
    main()
