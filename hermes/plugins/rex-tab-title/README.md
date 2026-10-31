# Rex tab title

Names the Rex tab a Hermes CLI/TUI conversation runs in after that session's
title, so a Rex session with one tab per Hermes conversation reads like a list
of tasks instead of `Window 1a2b3c4d`.

- After each CLI/TUI turn (`post_llm_call`), if the session's client sent
  `REX_SESSION` and `REX_BLOCK` (through `terminal.client_env_passthrough`), a
  daemon thread names the tab holding `REX_BLOCK` from the instant (`derived`)
  title, then polls up to 90 seconds for the title model's title (or a `/title`
  set by Bryan) and switches to it. Model titling can time out outright, so the
  instant title is the floor, not a placeholder to skip.
- A tab is renamed only while it carries Rex's generated `Window xxxxxxxx`
  label or a label this gateway process wrote. A tab Bryan named by hand is
  left alone. After a gateway restart, tabs the plugin named earlier count as
  hand-named, so they keep their label.
- `/new` in the same tab renames it again once the new session is titled.

Tests: `python3 hermes/test_rex_tab_title_plugin.py`.
