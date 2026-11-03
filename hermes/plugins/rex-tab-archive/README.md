# Rex tab archive

Archives a Hermes CLI/TUI conversation when Bryan closes the Rex tab it ran in,
so finished terminal conversations stop crowding the Desktop session list.

- After each CLI/TUI turn (`post_llm_call`), if the session's client sent
  `REX_SESSION` and `REX_BLOCK` (through `terminal.client_env_passthrough`), the
  plugin records the Rex window (tab) holding that block in
  `$HERMES_HOME/rex-tab-archive.json` and keeps one daemon thread per tab
  blocked in `rex wait -s SESSION WINDOW` (in one-hour slices).
- Archives only on a close Rex reports live: `rex wait` exits 0 naming the tab
  (or its whole Rex session), and `rex window inspect` then says "not found".
  Every Hermes session that ran in that tab (including earlier ones from `/new`)
  is archived.
- A tab that is already gone when a watcher starts (closed while the gateway
  was down, or a Rex server restart) is forgotten, not archived. A server
  disconnect is retried with backoff and never archives. The
  `sessions.auto_archive` idle sweep covers whatever this misses.
- The archive is the idle sweep's kind (`auto_archived`): nothing is deleted,
  `session_search` still finds it, and it stays resumable (`hermes --resume`,
  `/resume`, or Desktop's archived view). Pinned sessions are never archived.
- Un-hiding is Hermes's: opening a session is a read, so it comes back only when
  you send a message in it *and* the gateway had already marked it ended (a
  closed CLI is ended `orphan_end_grace_s`, default 5 minutes, after its tab
  closes). Resume within those 5 minutes and it keeps working but stays hidden.
- A resumed session keeps the `REX_*` of the tab that created it (Hermes freezes
  a session's `client_env` at `session.create`), so the plugin cannot see the
  new tab: closing it archives nothing, and the idle sweep handles it instead.
  The same limit leaves `rex-tab-title` unable to name a resumed session's tab.
- After a gateway restart, watchers re-arm from the registry on the first agent
  turn the new gateway runs (any platform, cron included).

Tests: `python3 hermes/test_rex_tab_archive_plugin.py`.
