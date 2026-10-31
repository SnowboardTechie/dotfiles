# HERMES — MAINTAINER NOTES

Paths are relative to the dotfiles repo root.

## Studio-native Hermes Matrix dependencies

`hermes/matrix-native/` + `hermes/reconcile_matrix_native.py`

- The Studio installer invokes the tracked native build recipe.
- Verified source checksum + one-line libolm compiler fix, current managed Python ABI, local wheel/build receipt, and an enabled dependency-only plugin; no upstream edits or Linux proxy.
- Use `--check`/`--apply`; test with `python3 hermes/test_matrix_native.py`.
- Never delete Matrix crypto state or rotate credentials for a dependency-only repair.

## Rex program status (runtime patch)

`hermes/runtime-patches/rex-program-status.*` + `hermes/test_hermes_rex_program_status.py`

- Classic CLI reports turn state to Rex with OSC 7501 (`state=working|blocked|done|error:app=hermes[:kind=permission|question|auth]`), only when `TERM_PROGRAM=rex`. Rex has no Hermes integration; this is what gives Hermes Claude-style tab activity and alerts.
- Two files, pinned by blob and SHA256 in the manifest; apply with `git apply` per the manifest, restart CLI sessions. A Hermes update that touches either file makes the test fail closed until the patch is re-cut against the new base.
- Bell/OSC 9 notifications are stock Hermes, enabled machine-locally: `display.bell_on_complete` and `display.bell_on_prompt`.
- Probe in Rex with `zsh -ic 'hermes …'`: `rex run`'s login-shell PATH resolves `hermes` to a Nix store build, not this checkout.
