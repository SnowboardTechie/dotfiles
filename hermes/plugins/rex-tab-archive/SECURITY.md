# Security review

Review scope: this plugin and its installer behavior in the same Git candidate.

## Provenance and execution privilege

Repository-owned Python using only the standard library (plus Hermes's own
`agent.session_client_env`, `hermes_constants` and `hermes_state_registry`,
imported defensively). Hermes plugins are not sandboxed: the code runs with the
gateway's privileges. The manifest requests no capabilities and activation
denies tool override. Any source change needs a new review before deployment.

## Data flow

- Reads four non-secret values from the session's bound client environment:
  `REX_SESSION`, `REX_BLOCK`, `REX_BIN_DIR`, `REX_SERVER`.
- Writes `rex-tab-archive.json` in the Hermes home: Rex window/session IDs, the
  Rex binary directory and server address, Hermes session IDs and the
  `state.db` path. No titles, messages or credentials. Entries unseen for 30
  days are dropped; written atomically (temp file + rename).
- Runs the Rex CLI (`$REX_BIN_DIR/rex`, else the fixed Rex Beta app path) with
  an argument vector, never a shell: `block inspect`, `window inspect`, and
  `wait --for 3600s`. Inspect calls time out after 10 seconds; `wait` after its
  slice plus 60 seconds. No stdin.
- The only state change: sets `archived`/`auto_archived` on the closed tab's
  sessions through Hermes's own `SessionDB` (the idle sweep's lineage archive).
  Nothing is deleted; pinned sessions are skipped. It opens no network
  connection itself and logs session IDs and outcomes only.

## Trust boundary

`REX_BIN_DIR` comes from the client's environment, which is Bryan's own local
shell (the gateway applies client env only for clients it proves are on its
host). A local process that could forge it, or edit the registry file in the
Hermes home, could already run code as Bryan. The worst a forged Rex answer can
do is hide (never delete) sessions recorded for that tab.

## Failure behavior

Every error is swallowed and logged at debug level; a missing Rex, a failed
wait, or a locked database leaves sessions as they were and never affects a
turn. At most one watcher thread (and one `rex wait` child) runs per tab per
gateway process; a child orphaned by a gateway restart exits within an hour.
