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

## Rex tab titles (plugin)

`hermes/plugins/rex-tab-title/` + `hermes/test_rex_tab_title_plugin.py`

- Renames the Rex tab (a Rex *window*, not the Rex session) holding the session's `REX_BLOCK` to the Hermes session title: the instant `derived` title at once, upgraded to the `llm`/`user` title when one lands (model titling can time out). Fires from `post_llm_call`, where the session's client env is bound; `os.environ` in the gateway has no `REX_*`.
- Only replaces Rex's generated `Window xxxxxxxx` label or a label the same gateway process wrote, so hand-named tabs stay put.
- Managed by `install.py` (frozen copy + enable); a gateway restart activates it. Source changes need `SECURITY.md` re-reviewed.

## Rex tab archive (plugin)

`hermes/plugins/rex-tab-archive/` + `hermes/test_rex_tab_archive_plugin.py`

- Archives every Hermes session that ran in a Rex tab when that tab closes. `post_llm_call` records the tab (window holding `REX_BLOCK`) in `$HERMES_HOME/rex-tab-archive.json`; one daemon thread per tab blocks in `rex wait -s SESSION WINDOW --for 3600s`.
- Archives only on a live close: `rex wait` exit 0 naming the window (or its Rex session), then `rex window inspect` exit 3 "not found". Measured Rex answers: close → 0 + `{"window_id"}`; whole session closed → 0 + `{"session_id"}`; `--for` timeout → 1 "timed out"; missing target → 3 "not found"; `wait` needs `-s`.
- A tab already gone when a watcher starts, or a server disconnect, never archives. Uses the idle sweep's `_auto_archive_lineage`; pinned sessions are skipped. Pairs with `sessions.auto_archive` (machine-local config) for anything it misses.
- Un-hide is Hermes's: mounting/resuming is a read; the first sent message calls `reopen_session` (which drops sweep archives) only when `ended_at` is set, i.e. after the gateway's `orphan_end_grace_s` (default 300 s) has ended the closed CLI. Measured: a resume inside the grace keeps working but stays hidden.
- A session's `client_env` (all `REX_*`) is frozen at `session.create`; resume never refreshes it. A session resumed in a new tab still names its first tab's block, so neither this plugin nor `rex-tab-title` can see the new tab.
- Watchers re-arm from the registry on the first agent turn after a gateway restart. Activate or reload with `hermes plugins disable/enable rex-tab-archive` after `install.py` copies it (hot reload, no restart).
