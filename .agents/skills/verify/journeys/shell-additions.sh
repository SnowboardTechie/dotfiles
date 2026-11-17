# shell-additions.sh
# The marked lines in ~/.bashrc: appended once to an existing file, never created, a hand-edited reference left alone; and a fresh interactive bash then has the shared aliases.
SA="$REPO/scripts/reconcile-shell-additions.sh"
BE="$REPO/scripts/reconcile-bash-enhancements.sh"
LINE="[[ -f \"$REPO/dot-config/shell/aliases.sh\" ]] && source \"$REPO/dot-config/shell/aliases.sh\""

step "no ~/.bashrc: never created"
H="$(new_home no-bashrc)"
for r in "$SA" "$BE"; do
    drive "no-bashrc-$(basename "$r" .sh)" "$H" -- "$r" --apply
    expect "$(basename "$r") exits 0" test "$RC" -eq 0
done
expect "~/.bashrc still does not exist" test ! -e "$H/.bashrc"

step "stock bashrc: check, apply, apply again"
H="$(new_home stock)"
printf '# Omarchy default\nalias ls=eza\n' >"$H/.bashrc"
mkdir -p "$H/.config/omarchy"; echo '{}' >"$H/.config/omarchy/shell.json"   # Omarchy's own config
cp "$H/.bashrc" "$SCRATCH/stock-bashrc"
capture "$H" before; BEFORE="$TREE"
for r in "$SA" "$BE"; do
    drive "check-$(basename "$r" .sh)" "$H" -- "$r" --check
    expect "$(basename "$r") check exits 0" test "$RC" -eq 0
done
capture "$H" after-check
expect "check left the home unchanged" same_file "$BEFORE" "$TREE"
for r in "$SA" "$BE"; do drive "apply-$(basename "$r" .sh)" "$H" -- "$r" --apply; done
expect "the original lines are untouched, first" test "$(head -2 "$H/.bashrc")" = "$(cat "$SCRATCH/stock-bashrc")"
expect "the aliases source line is present exactly once" test "$(grep -cxF "$LINE" "$H/.bashrc")" -eq 1
expect "the aliases line is marked" has "$(cat "$H/.bashrc")" "# dotfiles shell additions (managed by scripts/reconcile-shell-additions.sh)"
expect "the Ble.sh line is present exactly once" test "$(grep -cF '/usr/share/blesh/ble.sh' "$H/.bashrc")" -eq 1
expect "Ble.sh settings link to the repository's" links_to "$H/.config/blesh/init.sh" "$REPO/dot-config/blesh/init.sh"
cp "$H/.bashrc" "$SCRATCH/applied-bashrc"
capture "$H" after-apply; APPLIED="$TREE"
expect "apply changed only ~/.bashrc and the Ble.sh settings link" \
    bash -c 'diff <(grep -v "^\.bashrc \|^\.config/blesh" "$1") <(grep -v "^\.bashrc \|^\.config/blesh" "$2") >/dev/null' _ "$BEFORE" "$APPLIED"
for r in "$SA" "$BE"; do drive "apply-again-$(basename "$r" .sh)" "$H" -- "$r" --apply; done
expect "a second apply appends nothing" same_file "$H/.bashrc" "$SCRATCH/applied-bashrc"
capture "$H" after-second-apply
expect "a second apply left the home identical" same_file "$APPLIED" "$TREE"

step "a fresh interactive bash has the shared aliases"
drive interactive "$H" -- bash -ic 'alias gs; type grb >/dev/null && echo grb-defined'
expect "gs is git status" has "$OUT" "alias gs='git status'"
expect "grb is defined" has "$OUT" "grb-defined"
expect "Omarchy's own alias still wins" bash -c 'grep -q "^alias ls=eza" "$1"' _ "$H/.bashrc"

step "a hand-edited reference is left alone"
H="$(new_home hand-edited)"
printf 'source ~/old/dotfiles/dot-config/shell/aliases.sh\n' >"$H/.bashrc"
cp "$H/.bashrc" "$SCRATCH/hand-bashrc"
drive apply-hand "$H" -- "$SA" --apply
expect "exits 0" test "$RC" -eq 0
expect "warns about the unexpected line" has "$OUT" "unexpected line"
expect "~/.bashrc is unchanged" same_file "$H/.bashrc" "$SCRATCH/hand-bashrc"

step "Bryan's own Ble.sh settings are kept"
H="$(new_home own-blesh)"
printf '# x\n' >"$H/.bashrc"
mkdir -p "$H/.config/blesh" && echo "mine" >"$H/.config/blesh/init.sh"
drive apply-own-blesh "$H" -- "$BE" --apply
expect "warns and keeps the file" bash -c 'grep -q "is not this repository" <<<"$1" && [[ ! -L "$2" && "$(cat "$2")" == mine ]]' _ "$OUT" "$H/.config/blesh/init.sh"
