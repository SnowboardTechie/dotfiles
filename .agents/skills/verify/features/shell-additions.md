# Shell additions in ~/.bashrc

On Omarchy the login shell is Omarchy's bash. `scripts/reconcile-shell-additions.sh` appends one marked line to an
existing `~/.bashrc` that sources `dot-config/shell/aliases.sh`; `scripts/reconcile-bash-enhancements.sh` appends one
guarded Ble.sh line and links `~/.config/blesh/init.sh` to the repository's. Neither creates or rewrites `~/.bashrc`.

## Sub-features

- `no-bashrc`: both exit 0 and `~/.bashrc` is still absent.
- `append`: check changes nothing; apply leaves the original lines first and adds the aliases line and the Ble.sh line
  once each, the aliases line under its marker, and links the Ble.sh settings; a second apply appends nothing.
- `interactive`: a fresh `bash -i` in that home has `alias gs='git status'` and the `grb` function, and Omarchy's own
  `alias ls=eza` line is still there.
- `hand-edited`: a `.bashrc` that already sources some other `dot-config/shell/aliases.sh` gets a warning
  (`unexpected line`) and no change.
- `own-blesh`: an existing `~/.config/blesh/init.sh` of Bryan's is kept, with a warning.

## How to get to it (user POV)

- Steps two and three of `scripts/setup-omarchy.sh`, or each script with `--check|--apply`. Then open a new terminal.

## Driving it with dotfiles-verify

Preconditions:

- `doctor` passes. No stubs.

- `$V run shell-additions`. The `interactive` step runs `bash -ic 'alias gs; type grb'` in the home the `append` step
  left, so it loads exactly what was appended.

## Gotchas

- Ble.sh itself is not installed here, so its guarded line is inert; that it loads on Omarchy is not proven.
- The interactive shell is the bash on `PATH` (Nix's 5.x here), not Omarchy's build.
- `bash -i` prints "cannot set terminal process group" and "no job control" with no terminal; expected.
