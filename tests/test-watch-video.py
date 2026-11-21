"""Tests for dot-agents/skills/watch-video/scripts/get_video.py (offline parts)."""
import importlib.util
import pathlib
import unittest

SCRIPT = pathlib.Path(__file__).resolve().parent.parent / "dot-agents/skills/watch-video/scripts/get_video.py"
spec = importlib.util.spec_from_file_location("get_video", SCRIPT)
gv = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gv)

AUTO_VTT = """WEBVTT
Kind: captions
Language: en

00:00:00.160 --> 00:00:02.310 align:start position:0%
on<00:00:00.480><c> September</c><00:00:01.000><c> 20th</c>

00:00:02.310 --> 00:00:02.320 align:start position:0%
on September 20th

00:00:02.320 --> 00:00:05.000 align:start position:0%
on September 20th
two police officers came

1:02:03.000 --> 1:02:04.000
the end
"""


class VttToLines(unittest.TestCase):
    def test_strips_tags_and_scrolling_repeats(self):
        self.assertEqual(
            gv.vtt_to_lines(AUTO_VTT),
            ["[00:00:00] on September 20th", "[00:00:02] two police officers came", "[01:02:03] the end"],
        )

    def test_whisper_style_cues(self):
        vtt = "WEBVTT\n\n00:36:22.840 --> 00:36:25.440\nbut this was a story\n"
        self.assertEqual(gv.vtt_to_lines(vtt), ["[00:36:22] but this was a story"])

    def test_fmt_ts(self):
        self.assertEqual(gv.fmt_ts(2190), "00:36:30")
        self.assertEqual(gv.fmt_ts(3723.9), "01:02:03")


if __name__ == "__main__":
    unittest.main()
