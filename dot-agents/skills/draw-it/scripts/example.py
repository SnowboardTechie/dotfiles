#!/usr/bin/env python3
"""A starting point for a draw-it picture. Copy it to scratch and change the content.

    uv run -q --with pillow python example.py OUT.png

The sizes are the ones Bryan called readable in a half-width Rex pane: a canvas
1100 pixels wide with 44 / 32 / 26 point text. Keep the width and the sizes;
grow the height to fit the content.
"""

import sys

from PIL import Image, ImageDraw, ImageFont

WIDTH = 1100
MARGIN = 40
BG = (13, 17, 23)
TEXT = (230, 237, 243)
MUTED = (160, 170, 180)
ACCENT = (210, 153, 34)
BLUE, PURPLE, GREEN, RED = (31, 111, 235), (137, 87, 229), (35, 134, 54), (218, 54, 51)

FONTS = (
    "/System/Library/Fonts/Menlo.ttc",
    "/usr/share/fonts/TTF/DejaVuSansMono.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
    "/run/current-system/sw/share/X11/fonts/DejaVuSansMono.ttf",
)


def font(size: int) -> ImageFont.FreeTypeFont:
    for path in FONTS:
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            continue
    return ImageFont.load_default(size)


TITLE, LABEL, NOTE = font(44), font(32), font(26)


def box(draw, top: int, title: str, note: str, color) -> int:
    """A full-width labelled box. Returns its bottom edge."""
    bottom = top + 150
    fill = tuple(int(v * 0.35) for v in color)
    draw.rounded_rectangle((MARGIN, top, WIDTH - MARGIN, bottom), 14, fill=fill, outline=color, width=3)
    draw.text((MARGIN + 30, top + 24), title, font=LABEL, fill=TEXT)
    draw.text((MARGIN + 30, top + 86), note, font=NOTE, fill=MUTED)
    return bottom


def arrow(draw, top: int, label: str) -> int:
    """A labelled down arrow from the middle of a box. Returns where the next box starts."""
    x, tip = WIDTH // 2, top + 80
    draw.line((x, top, x, tip - 20), fill=ACCENT, width=4)
    draw.polygon([(x - 16, tip - 25), (x + 16, tip - 25), (x, tip)], fill=ACCENT)
    draw.text((x + 35, top + 22), label, font=NOTE, fill=ACCENT)
    return tip


def main(out: str) -> None:
    height = 860
    image = Image.new("RGB", (WIDTH, height), BG)
    draw = ImageDraw.Draw(image)
    draw.text((MARGIN, 24), "How the SGG pieces relate", font=TITLE, fill=TEXT)
    y = box(draw, 110, "simpler-grants-protocol", "defines the open spec (TypeSpec, SDKs)", BLUE)
    y = arrow(draw, y, "extends")
    y = box(draw, y, "py-cg- / ts-cg-grants-gov", "plugins: CG SDK + grants.gov fields", PURPLE)
    y = arrow(draw, y, "consumed by")
    box(draw, y, "simpler-grants-gov", "the app that consumes them", GREEN)
    draw.text((MARGIN, height - 60), "Upstream wins: fix the downstream layer.", font=NOTE, fill=MUTED)
    image.save(out)


if __name__ == "__main__":
    main(sys.argv[1])
