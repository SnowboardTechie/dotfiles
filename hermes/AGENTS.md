# HERMES — MAINTAINER NOTES

Paths are relative to the dotfiles repo root.

## Personal routines read Apple Notes

`hermes/scripts/personal_notes.py` (+ the three `personal-*.py` collectors)

- Bounded title search + exact-id read through the `apple-notes-pkm` helper; never the frozen vault.
- Weekly hub/spoke titles: `YYYY-MM-DD-weekly-plan`, `YYYY-MM-DD-daily-check-in` in `Second Brain/Journal`.
- `hermes/test_morning_brief_split.py` pins it.

## Studio-native Hermes Matrix dependencies

`hermes/matrix-native/` + `hermes/reconcile_matrix_native.py`

- The Studio installer invokes the tracked native build recipe.
- Verified source checksum + one-line libolm compiler fix, current managed Python ABI, local wheel/build receipt, and an enabled dependency-only plugin; no upstream edits or Linux proxy.
- Use `--check`/`--apply`; test with `python3 hermes/test_matrix_native.py`.
- Never delete Matrix crypto state or rotate credentials for a dependency-only repair.
