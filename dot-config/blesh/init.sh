# ble.sh user settings (linked to ~/.config/blesh/init.sh by
# scripts/reconcile-bash-enhancements.sh). ble.sh sources this after loading.

# foot answers the terminal-version query (DA2) with a zero-padded version,
# e.g. "1;012800;0" for 1.28.0. ble.sh compares those fields with ((...)),
# which reads a leading 0 as octal, so every prompt printed
#   ((: 012800: value too great for base
# Store the reply with each numeric field in base 10 instead.
_dotfiles_blesh_decimal_DA2R() {
  local IFS=';' field
  local -a fields=() out=()
  read -r -a fields <<< "$1"
  for field in "${fields[@]}"; do
    [[ $field =~ ^[0-9]+$ ]] && field=$((10#$field))
    out+=("$field")
  done
  _ble_term_DA2R="${out[*]}"
}

if declare -F ble/term/DA2/notify >/dev/null; then
  function ble/term/DA2/notify {
    [[ $_ble_term_DA2R ]] || _dotfiles_blesh_decimal_DA2R "$1"
  }
  # Repair a reply recorded before this file was (re)sourced.
  [[ $_ble_term_DA2R ]] && _dotfiles_blesh_decimal_DA2R "$_ble_term_DA2R"
fi
