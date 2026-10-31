# Security review

Review scope: this plugin and its installer behavior in the same Git candidate.

## Provenance and execution privilege

Repository-owned Python using only the standard library (plus Hermes's own
`agent.session_client_env` and `hermes_constants`, imported defensively).
Hermes plugins are not sandboxed: the code runs with the gateway's privileges.
The manifest requests no capabilities and activation denies tool override. Any
source change needs a new review before deployment.

## Data flow

- Reads four non-secret values from the session's bound client environment:
  `REX_SESSION`, `REX_BLOCK`, `REX_BIN_DIR`, `REX_SERVER`.
- Reads one row (`title`, `title_source`) from `state.db`, opened read-only.
- Runs the Rex CLI (`$REX_BIN_DIR/rex`, else the fixed Rex Beta app path) with
  an argument vector, never a shell: `block inspect`, `window inspect`,
  `window rename`. Each call has a 5-second timeout and no stdin.
- The only data leaving Hermes is the session title, written as a tab label to
  the local Rex server. It opens no network connection itself and logs nothing
  beyond debug-level outcomes (no titles or messages).

## Trust boundary

`REX_BIN_DIR` comes from the client's environment, which is Bryan's own local
shell (the gateway applies client env only for clients it proves are on its
host). A local process that could forge it could already run code as Bryan.

## Failure behavior

Every error is swallowed and logged at debug level; a missing Rex, a failed
rename, or a locked database leaves the tab unchanged and never affects a turn.
At most one follower thread runs per session.
