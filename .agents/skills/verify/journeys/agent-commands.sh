# agent-commands.sh
# forgejo-map in ~/.local/bin: linked, runs through the link, a stale link of a removed worktree is repaired, a foreign file or live link elsewhere is reported with exit 1 and kept.
R="$REPO/scripts/reconcile-agent-commands.sh"
SRC="$REPO/dot-agents/bin/forgejo-map"

step "fresh home: check, then apply"
H="$(new_home fresh)"
drive check "$H" -- "$R" --check
expect "check exits 0" test "$RC" -eq 0
expect "check says it would link" has "$OUT" "MISSING $H/.local/bin/forgejo-map (would link)"
expect "check wrote nothing" test ! -e "$H/.local"
drive apply "$H" -- "$R" --apply
expect "apply exits 0" test "$RC" -eq 0
expect "forgejo-map links to this checkout" links_to "$H/.local/bin/forgejo-map" "$SRC"
drive apply-again "$H" -- "$R" --apply
expect "second apply exits 0 and reports OK" bash -c '[[ $1 -eq 0 ]] && grep -qF "OK   $2" <<<"$3"' _ "$RC" "$H/.local/bin/forgejo-map" "$OUT"

step "the linked command runs through the link"
drive help "$H" -- "$H/.local/bin/forgejo-map" --help
expect "--help exits 0" test "$RC" -eq 0
expect "--help is the Wayfinder adapter's" has "$OUT" "Deterministic Forgejo adapter for Wayfinder maps"
mkdir -p "$H/not-a-repo"
drive no-origin "$H/not-a-repo" -- "$H/.local/bin/forgejo-map" frontier
expect "outside a repository, no --origin stops with exit 2" test "$RC" -eq 2
expect "and says to pass --origin" has "$OUT" "pass --origin"

step "a stale link left by a removed worktree is repaired"
H="$(new_home stale)"
mkdir -p "$H/.local/bin"
ln -s "/gone/dotfiles.old-worktree/dot-agents/bin/forgejo-map" "$H/.local/bin/forgejo-map"
drive check-stale "$H" -- "$R" --check
expect "check exits 0 and calls it stale" bash -c '[[ $1 -eq 0 ]] && grep -qF "STALE" <<<"$2"' _ "$RC" "$OUT"
expect "check left the stale link" test "$(readlink "$H/.local/bin/forgejo-map")" = /gone/dotfiles.old-worktree/dot-agents/bin/forgejo-map
drive apply-stale "$H" -- "$R" --apply
expect "apply exits 0" test "$RC" -eq 0
expect "the link now points here" links_to "$H/.local/bin/forgejo-map" "$SRC"

step "foreign entries are kept and fail the run"
for kind in file live-link; do
    H="$(new_home "foreign-$kind")"
    mkdir -p "$H/.local/bin" "$H/other-checkout/dot-agents/bin"
    if [[ $kind == file ]]; then
        printf '#!/bin/sh\necho mine\n' >"$H/.local/bin/forgejo-map"
    else
        printf '#!/bin/sh\necho other\n' >"$H/other-checkout/dot-agents/bin/forgejo-map"
        ln -s "$H/other-checkout/dot-agents/bin/forgejo-map" "$H/.local/bin/forgejo-map"
    fi
    capture "$H" "foreign-$kind-before"; BEFORE="$TREE"
    for mode in check apply; do
        drive "foreign-$kind-$mode" "$H" -- "$R" "--$mode"
        expect "$kind, $mode: exits 1" test "$RC" -eq 1
        expect "$kind, $mode: reports the conflict" has "$OUT" "CONFLICT"
    done
    capture "$H" "foreign-$kind-after"
    expect "$kind: left exactly as it was" same_file "$BEFORE" "$TREE"
done
