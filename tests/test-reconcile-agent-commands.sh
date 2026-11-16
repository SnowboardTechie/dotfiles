#!/usr/bin/env bash
# Tests for scripts/reconcile-agent-commands.sh and the forgejo-map launcher it
# links. Every run uses a temporary HOME under one directory, removed on exit.
# No network: the launcher is only run with --help, or up to the point where it
# would need --origin.

set -u

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
RECON="$REPO_ROOT/scripts/reconcile-agent-commands.sh"
LAUNCHER="$REPO_ROOT/dot-agents/bin/forgejo-map"
TMP="$(mktemp -d "${TMPDIR:-/tmp}/agent-commands-test-XXXXXX")"
TMP="$(cd "$TMP" && pwd -P)"
trap 'rm -rf "$TMP"' EXIT

TESTS=0
FAILURES=0
check() { # <description> <expected> <actual>
    TESTS=$((TESTS + 1))
    if [[ "$2" == "$3" ]]; then
        echo "ok   $1"
    else
        echo "FAIL $1: expected [$2], got [$3]"
        FAILURES=$((FAILURES + 1))
    fi
}
yes_no() { if "$@"; then echo yes; else echo no; fi; }
has() { grep -qF -- "$1" <<<"$2"; }
listing() { # <dir>: names and link targets, so "nothing changed" is exact
    (cd "$1" 2>/dev/null && for f in * .[!.]*; do
        [[ -e "$f" || -L "$f" ]] || continue
        if [[ -L "$f" ]]; then echo "$f -> $(readlink "$f")"; else echo "$f (file)"; fi
    done)
}
run() { # <home> <mode>
    HOME="$1" PATH="$1/.local/bin:$PATH" bash "$RECON" "$2" 2>&1
}

check "launcher is executable" "yes" "$(yes_no test -x "$LAUNCHER")"

# --- Fresh home -------------------------------------------------------------
H="$TMP/home-fresh"
mkdir -p "$H"
out="$(run "$H" --check)"; rc=$?
check "check exits 0 on a fresh home" "0" "$rc"
check "check reports the missing link" "yes" "$(yes_no has "MISSING $H/.local/bin/forgejo-map" "$out")"
check "check creates nothing" "no" "$(yes_no test -e "$H/.local")"

out="$(run "$H" --apply)"; rc=$?
check "apply exits 0" "0" "$rc"
check "apply links forgejo-map" "$LAUNCHER" "$(readlink "$H/.local/bin/forgejo-map")"
check "apply says it linked" "yes" "$(yes_no has "Linked $H/.local/bin/forgejo-map" "$out")"

before="$(listing "$H/.local/bin")"
out="$(run "$H" --apply)"; rc=$?
check "second apply exits 0" "0" "$rc"
check "second apply reports OK" "yes" "$(yes_no has "OK   $H/.local/bin/forgejo-map" "$out")"
check "second apply changes nothing" "$before" "$(listing "$H/.local/bin")"
out="$(run "$H" --check)"; rc=$?
check "check after apply exits 0" "0" "$rc"
check "check after apply reports OK" "yes" "$(yes_no has "OK   $H/.local/bin/forgejo-map" "$out")"

# --- Its own stale link is repaired ----------------------------------------
H="$TMP/home-stale"
mkdir -p "$H/.local/bin"
gone="$TMP/removed-worktree/dot-agents/bin/forgejo-map"
ln -s "$gone" "$H/.local/bin/forgejo-map"
out="$(run "$H" --check)"; rc=$?
check "check exits 0 on a stale own link" "0" "$rc"
check "check reports the stale link" "yes" "$(yes_no has "STALE $H/.local/bin/forgejo-map" "$out")"
check "check leaves the stale link" "$gone" "$(readlink "$H/.local/bin/forgejo-map")"
out="$(run "$H" --apply)"; rc=$?
check "apply exits 0 on a stale own link" "0" "$rc"
check "apply repairs the stale link" "$LAUNCHER" "$(readlink "$H/.local/bin/forgejo-map")"

# --- A live link into another checkout is not taken over -------------------
H="$TMP/home-other-checkout"
other="$TMP/other-checkout/dot-agents/bin"
mkdir -p "$other" "$H/.local/bin"
printf '#!/bin/sh\n' >"$other/forgejo-map"
chmod +x "$other/forgejo-map"
ln -s "$other/forgejo-map" "$H/.local/bin/forgejo-map"
out="$(run "$H" --apply)"; rc=$?
check "other checkout: apply exits 1" "1" "$rc"
check "other checkout: apply reports it" "yes" "$(yes_no has "CONFLICT: $H/.local/bin/forgejo-map links to $other/forgejo-map" "$out")"
check "other checkout: apply keeps the link" "$other/forgejo-map" "$(readlink "$H/.local/bin/forgejo-map")"

# --- Foreign file and foreign link survive ---------------------------------
H="$TMP/home-foreign-file"
mkdir -p "$H/.local/bin"
printf '#!/bin/sh\necho mine\n' >"$H/.local/bin/forgejo-map"
chmod +x "$H/.local/bin/forgejo-map"
for mode in --check --apply; do
    out="$(run "$H" "$mode")"; rc=$?
    check "foreign file: $mode exits 1" "1" "$rc"
    check "foreign file: $mode reports it" "yes" "$(yes_no has "CONFLICT: $H/.local/bin/forgejo-map exists" "$out")"
    check "foreign file: $mode keeps it" "echo mine" "$(sed -n 2p "$H/.local/bin/forgejo-map")"
    check "foreign file: $mode leaves it a file" "no" "$(yes_no test -L "$H/.local/bin/forgejo-map")"
done

H="$TMP/home-foreign-link"
mkdir -p "$H/.local/bin"
ln -s /usr/bin/true "$H/.local/bin/forgejo-map"
for mode in --check --apply; do
    out="$(run "$H" "$mode")"; rc=$?
    check "foreign link: $mode exits 1" "1" "$rc"
    check "foreign link: $mode reports it" "yes" "$(yes_no has "CONFLICT: $H/.local/bin/forgejo-map links to /usr/bin/true" "$out")"
    check "foreign link: $mode keeps it" "/usr/bin/true" "$(readlink "$H/.local/bin/forgejo-map")"
done

H="$TMP/home-foreign-dangling"
mkdir -p "$H/.local/bin"
ln -s "$TMP/elsewhere/forgejo-map" "$H/.local/bin/forgejo-map"
out="$(run "$H" --apply)"; rc=$?
check "dangling foreign link: apply exits 1" "1" "$rc"
check "dangling foreign link: apply keeps it" "$TMP/elsewhere/forgejo-map" "$(readlink "$H/.local/bin/forgejo-map")"

# --- The linked launcher -----------------------------------------------------
H="$TMP/home-fresh"
LINKED="$H/.local/bin/forgejo-map"
elsewhere="$TMP/not-a-repo"
mkdir -p "$elsewhere"

out="$(cd "$elsewhere" && "$LINKED" --help 2>&1)"; rc=$?
check "linked launcher --help exits 0 outside a repository" "0" "$rc"
check "linked launcher --help is the adapter's" "yes" "$(yes_no has "Deterministic Forgejo adapter" "$out")"
out="$(cd "$elsewhere" && "$LINKED" frontier --help 2>&1)"; rc=$?
check "linked launcher subcommand --help exits 0" "0" "$rc"
check "linked launcher subcommand --help names --map" "yes" "$(yes_no has "--map MAP" "$out")"

# A stub python3 records exactly what the launcher passes on, so the origin
# rule is tested without a network call.
STUB="$TMP/stub-bin"
mkdir -p "$STUB"
cat >"$STUB/python3" <<'EOF'
#!/usr/bin/env bash
printf '%s\n' "$@" >"$ARGS_LOG"
EOF
chmod +x "$STUB/python3"
launch() { # <dir> <args...>: run the linked launcher with the stub python3
    local dir="$1"; shift
    (cd "$dir" && ARGS_LOG="$TMP/args" PATH="$STUB:$PATH" "$LINKED" "$@" 2>&1)
}

repo="$TMP/repo-with-origin"
git init -q "$repo"
git -C "$repo" remote add origin ssh://git@forge.example/owner/repo.git
mkdir -p "$repo/sub/dir"
rm -f "$TMP/args"
out="$(launch "$repo/sub/dir" --tracker owner/tracker frontier --map 7)"; rc=$?
check "launcher in a repo with origin exits 0" "0" "$rc"
check "launcher fills --origin and passes the rest unchanged" \
    "$(printf '%s\n' "$REPO_ROOT/dot-agents/skills/wayfinder/scripts/forgejo_wayfinder.py" --origin ssh://git@forge.example/owner/repo.git --tracker owner/tracker frontier --map 7)" \
    "$(cat "$TMP/args" 2>/dev/null)"

rm -f "$TMP/args"
launch "$repo" --origin https://other.example/a/b --tracker owner/tracker read-map --map 3 >/dev/null; rc=$?
check "explicit --origin is kept, not duplicated" "1" "$(grep -c -- '^--origin$' "$TMP/args")"
check "explicit --origin value is passed through" "https://other.example/a/b" "$(grep -A1 -- '^--origin$' "$TMP/args" | tail -1)"

rm -f "$TMP/args"
out="$(launch "$elsewhere" --tracker owner/tracker frontier --map 7)"; rc=$?
check "launcher outside a repository exits non-zero" "2" "$rc"
check "launcher outside a repository says why" "yes" "$(yes_no has "not inside a Git repository with an 'origin' remote" "$out")"
check "launcher outside a repository runs nothing" "no" "$(yes_no test -f "$TMP/args")"

norigin="$TMP/repo-without-origin"
git init -q "$norigin"
git -C "$norigin" remote add upstream ssh://git@forge.example/owner/repo.git
out="$(launch "$norigin" --tracker owner/tracker frontier --map 7)"; rc=$?
check "launcher in a repo with no origin remote exits non-zero" "2" "$rc"
check "launcher in a repo with no origin remote runs nothing" "no" "$(yes_no test -f "$TMP/args")"

# --tracker is never inferred: the real adapter refuses without it.
out="$(cd "$repo" && "$LINKED" frontier --map 7 2>&1)"; rc=$?
check "missing --tracker is refused by the adapter" "2" "$rc"
check "missing --tracker names the option" "yes" "$(yes_no has "--tracker" "$out")"

echo ""
echo "$TESTS tests, $FAILURES failures"
[[ $FAILURES -eq 0 ]]
