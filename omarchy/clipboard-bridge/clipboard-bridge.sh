#!/usr/bin/env bash
# clipboard-bridge.sh — share this machine's text clipboard with a Mac, and
# through that Mac's Universal Clipboard with the other Apple devices.
#
# One SSH connection carries both directions. Nothing is installed on the Mac:
# the small loop it runs is sent as the SSH command. Each copy travels as one
# base64 line.
#
#   here -> Mac:  wl-paste --watch  ->  ssh stdin   ->  pbcopy
#   Mac -> here:  pasteboard poll   ->  ssh stdout  ->  wl-copy
#
# Entries a password manager marks as concealed are skipped on both sides.
# The script handles one connection and then exits; the systemd user unit
# written by scripts/reconcile-omarchy-clipboard-bridge.sh restarts it.

set -euo pipefail

# A multiple of 3, so one byte more always makes a longer base64 line.
MAX_BYTES=999999
HOST_FILE="${CLIPBOARD_BRIDGE_HOST_FILE:-$HOME/.config/clipboard-bridge/host}"
# Hash of the last entry that crossed in either direction, so a copy is not
# sent back to the side it came from.
LAST_FILE="${XDG_RUNTIME_DIR:-/tmp}/clipboard-bridge.last"

# Runs on the Mac under /bin/bash 3.2.
read -r -d '' REMOTE_LOOP <<'REMOTE' || true
set -u
dir=$(mktemp -d) || exit 1
poller=""
trap '[ -n "$poller" ] && kill "$poller" 2>/dev/null; rm -rf "$dir"' EXIT
# Prints: <change count> <1 if concealed> <1 if it holds text>
state() {
  osascript -l JavaScript -e 'ObjC.import("AppKit"); var p=$.NSPasteboard.generalPasteboard; var t=ObjC.deepUnwrap(p.types)||[]; p.changeCount+" "+(t.some(function(x){return /ConcealedType|TransientType/.test(x)})?1:0)+" "+(t.indexOf("public.utf8-plain-text")>=0?1:0)' 2>/dev/null
}
digest() { shasum -a 256 | cut -d" " -f1; }
main=$$
(
  last=$(state); last=${last%% *}
  while kill -0 "$main" 2>/dev/null; do
    sleep 1
    set -- $(state)
    [ $# -eq 3 ] || continue
    [ "$1" = "$last" ] && continue
    last=$1
    [ "$2" = 0 ] && [ "$3" = 1 ] || continue
    b64=$(pbpaste | base64 | tr -d "\n")
    [ -n "$b64" ] && [ ${#b64} -le 1400000 ] || continue
    h=$(printf %s "$b64" | digest)
    [ "$h" = "$(cat "$dir/last" 2>/dev/null)" ] && continue
    printf %s "$h" > "$dir/last"
    printf "%s\n" "$b64"
  done
) &
poller=$!
while IFS= read -r line; do
  [ -n "$line" ] || continue
  printf %s "$line" | digest > "$dir/last"
  printf %s "$line" | base64 -D | pbcopy
done
REMOTE

digest() { sha256sum | cut -d' ' -f1; }

# Called by wl-paste --watch with the copied text on stdin. Prints one base64
# line for the Mac, or nothing when the entry should stay here.
encode() {
    local types b64 hash
    [[ ${CLIPBOARD_STATE:-} == "sensitive" ]] && return 0
    types=$(timeout 2s wl-paste --list-types 2>/dev/null || true)
    grep -qx 'x-kde-passwordManagerHint' <<<"$types" && return 0
    b64=$(timeout 2s head -c $((MAX_BYTES + 1)) | base64 -w0) || return 0
    [[ -n $b64 ]] || return 0
    (( ${#b64} <= MAX_BYTES / 3 * 4 )) || return 0
    hash=$(printf %s "$b64" | digest)
    [[ $hash == "$(cat "$LAST_FILE" 2>/dev/null || true)" ]] && return 0
    printf %s "$hash" > "$LAST_FILE"
    printf '%s\n' "$b64"
}

# Reads base64 lines from the Mac and puts each on the local clipboard.
receive() {
    local line
    while IFS= read -r line; do
        [[ -n $line ]] || continue
        printf %s "$line" | base64 -d >/dev/null 2>&1 || continue
        printf %s "$line" | digest > "$LAST_FILE"
        printf %s "$line" | base64 -d | wl-copy
    done
}

run() {
    local host self remote_b64
    if [[ ! -s $HOST_FILE ]]; then
        echo "clipboard-bridge: no Mac configured in $HOST_FILE" >&2
        exit 78
    fi
    host=$(head -n 1 "$HOST_FILE")
    self=$(readlink -f "${BASH_SOURCE[0]}")
    remote_b64=$(printf %s "$REMOTE_LOOP" | base64 -w0)

    # wl-paste --watch reports the current entry when it starts. Record it
    # first, so a reconnect does not overwrite the Mac with an old copy.
    umask 077
    timeout 2s wl-paste --type text --no-newline 2>/dev/null | base64 -w0 | digest > "$LAST_FILE" || true

    wl-paste --type text --watch "$self" _encode \
        | ssh -T -o BatchMode=yes -o ConnectTimeout=10 \
              -o ServerAliveInterval=15 -o ServerAliveCountMax=3 \
              "$host" "/bin/bash -c \"\$(echo $remote_b64 | base64 -D)\"" \
        | {
            receive
            # The connection ended. Stop the watcher so the pipeline finishes.
            pkill -P "$$" -x wl-paste 2>/dev/null || true
        }
    exit 1
}

case "${1:-run}" in
    _encode) encode ;;
    run) run ;;
    *) echo "Usage: clipboard-bridge.sh [run]" >&2; exit 2 ;;
esac
