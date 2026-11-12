---
name: draw-it
description: Use when Bryan asks you to draw, sketch, or show what you mean ("draw that", "show me a picture", "I can't picture this"), or when an explanation of a layout, flow, state change, or before/after comparison has failed in prose. Renders a picture into a Rex pane beside the conversation. Rex only.
---

# Draw it

When words aren't landing, draw the thing. You render a PNG and `show.py` puts
it in a Rex pane to the right of the conversation, using the kitty graphics
protocol that Rex's terminal already supports. Nothing is installed and no
server runs.

## When

- Bryan asks for a picture, or says an explanation isn't clear.
- You are about to describe geometry, a pipeline, a state machine, a
  before/after, or several options that differ in shape. Draw those instead of
  describing them a second time.
- Not for anything a short table or a code block already shows well.
- Only inside Rex. Outside it `show.py` refuses and prints the image path; give
  Bryan that path instead.

## Draw

Write a short Pillow script in session scratch (`$TMPDIR`), never in a
repository, and run it with uv so nothing needs installing:

```sh
uv run -q --with pillow python "$TMPDIR/draw-<name>.py" "$TMPDIR/draw-<name>.png"
```

Start from `scripts/example.py` next to this file: it has the canvas, palette,
font lookup, and `box` / `arrow` helpers. Copy what you need; it is an example,
not a library.

Sizes Bryan confirmed as readable in a half-width pane (2026-11-12). Keep them:

| Thing | Value |
|---|---|
| Canvas width | 1100 px; grow the height to fit |
| Title | 44 pt |
| Labels | 32 pt |
| Notes, captions | 26 pt, never smaller |
| Margin | 40 px; let boxes run the full width |

The picture is scaled to the pane, so a wider canvas makes the text smaller, not
the picture bigger. If the content doesn't fit at these sizes, cut content or
draw a second picture.

What makes a drawing explain something:

- Draw the concrete case, with real names and values from the work at hand, not
  a generic diagram of the concept.
- Put a comparison side by side or stacked, with the same layout in each half,
  so the difference is the only thing that changes.
- Caption each part with the conclusion ("One band. Keep."), not a description
  of what is drawn.
- Use one color per meaning and keep it consistent across the picture.
- Color the caption text by its verdict: amber for the problem, green for the
  fix or the part to keep, muted grey for neutral notes.
- Text must fit its box: measure with `draw.textlength` and shorten the words
  rather than shrinking the font.

Look at the PNG yourself (read the file) before showing it. Fix overlaps and
clipped text first.

## Show

```sh
python3 ~/code/dotfiles/dot-agents/skills/draw-it/scripts/show.py "$TMPDIR/draw-<name>.png"
```

- Splits your own pane to the right at 50%, without taking focus.
  `--split below` suits a wide, short picture; `--ratio 60` gives it more room.
- Calling it again replaces the earlier drawing in the same tab. It never stacks
  panes and never touches panes it didn't create (it matches the `draw-it`
  label).
- The pane redraws itself when resized. Bryan closes it with `q` or the usual
  Rex close; don't close it for him.
- It prints JSON. `"ok": true` means the terminal accepted the image. It does
  not mean the picture is readable, which is why you look at the PNG first.

Then say in the conversation what the picture shows, in a few lines, with the
PNG's path. The drawing supports the explanation; it doesn't replace it.

## Limits

- PNG only. Other formats need converting first; don't add a converter for it.
- Rex gives a pane its real size only once a client takes it over, so `show.py`
  sizes the new pane from yours. If Bryan says the picture is small or cut off,
  run `show.py` again.
- On a host without `uv`, use any Python that has Pillow.
