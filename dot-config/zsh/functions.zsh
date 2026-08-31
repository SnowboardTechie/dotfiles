# Custom shell functions

# Identify the nix-configs host represented by this machine's local hostname.
function _nix_config_host {
  local local_hostname=""
  if (( $+commands[scutil] )); then
    local_hostname="$(scutil --get LocalHostName 2>/dev/null)"
  fi
  if [[ -z "$local_hostname" ]]; then
    local_hostname="$(hostname -s 2>/dev/null)"
  fi

  case "${local_hostname:l}" in
    *a6*mbp*|*a6*macbook*) print -r -- "a6mbp" ;;
    *studio*) print -r -- "studio" ;;
    *macbook*|mbp) print -r -- "mbp" ;;
    gnarbox) print -r -- "gnarbox" ;;
    *inix*) print -r -- "inix" ;;
    *) print -r -- "unknown" ;;
  esac
}

function _nix_apply_host {
  local action="$1"
  local target="$2"
  local current="$(_nix_config_host)"
  local current_label="$current"

  case "$current" in
    studio) current_label="Mac Studio (studio)" ;;
    mbp) current_label="MacBook Pro (mbp)" ;;
    a6mbp) current_label="A6 MacBook Pro (a6mbp)" ;;
    gnarbox) current_label="Gnarbox (gnarbox)" ;;
    inix) current_label="Intel Mac (inix)" ;;
  esac

  if [[ "$current" != "$target" ]]; then
    print -u2 -r -- "Refusing $action-$target: this machine is $current_label, not $target."
    return 1
  fi

  local reply=""
  print -r -- "Current machine: $current_label"
  printf 'Continue with %s-%s? [Y/n] ' "$action" "$target"
  if ! read -r reply; then
    print -r -- "Cancelled."
    return 1
  fi
  if [[ -n "$reply" && "${reply:l}" != "y" && "${reply:l}" != "yes" ]]; then
    print -r -- "Cancelled."
    return 1
  fi

  if [[ "$action" == "upgrade" ]]; then
    nix flake update --flake "$HOME/code/nix-configs" || return 1
  fi

  if [[ "$target" == "gnarbox" ]]; then
    sudo nixos-rebuild switch --flake "$HOME/code/nix-configs/#$target"
  else
    sudo darwin-rebuild switch --flake "$HOME/code/nix-configs/#$target"
  fi
}

function update-mbp { _nix_apply_host update mbp }
function update-a6mbp { _nix_apply_host update a6mbp }
function update-studio { _nix_apply_host update studio }
function update-gnarbox { _nix_apply_host update gnarbox }
function update-inix { _nix_apply_host update inix }

function upgrade-mbp { _nix_apply_host upgrade mbp }
function upgrade-a6mbp { _nix_apply_host upgrade a6mbp }
function upgrade-studio { _nix_apply_host upgrade studio }
function upgrade-gnarbox { _nix_apply_host upgrade gnarbox }
function upgrade-inix { _nix_apply_host upgrade inix }

# Git rebase function
# Defaults to 3 commits back, otherwise use argument passed as:
# - Count if integer: interactive rebase last N commits
# - Commit hash or branch name if string: rebase onto that ref
# Example usage:
#   grb           # interactive rebase last 3 commits
#   grb 6         # interactive rebase last 6 commits
#   grb feature   # rebase onto branch 'feature'
#   grb abc1234   # rebase onto commit abc1234
function grb {
  local commits=${1:-3}
  if [[ $commits =~ ^[0-9]+$ ]]; then
    git rebase -i HEAD~$commits
  else
    git rebase $commits
  fi
}

# Open an Obsidian vault by path.
# Usage:
#   obsidian              # open current directory
#   obsidian .            # open current directory
#   obsidian ~/notes/foo  # open that path
function obsidian {
  local target="${1:-.}"
  if [[ ! -d "$target" ]]; then
    echo "Error: not a directory: $target" >&2
    return 1
  fi
  local abs
  abs="$(cd "$target" && pwd -P)" || return 1

  # Walk up from $abs to find the vault root (directory containing .obsidian/).
  local root="$abs"
  while [[ "$root" != "/" && ! -d "$root/.obsidian" ]]; do
    root="${root:h}"
  done
  if [[ ! -d "$root/.obsidian" ]]; then
    echo "Error: no Obsidian vault at or above $abs (no .obsidian/ found)" >&2
    return 1
  fi

  # If the vault is already registered in obsidian.json, use the URI scheme
  # (brings a running Obsidian to the front and opens the vault instantly).
  local config="$HOME/Library/Application Support/obsidian/obsidian.json"
  local vault_name=""
  if [[ -r "$config" ]]; then
    while IFS= read -r vpath; do
      [[ -z "$vpath" ]] && continue
      local resolved
      resolved="$(cd "$vpath" 2>/dev/null && pwd -P)" || resolved="$vpath"
      if [[ "$root" == "$resolved" ]]; then
        vault_name="${resolved:t}"
        break
      fi
    done < <(jq -r '.vaults | to_entries[] | .value.path' "$config" 2>/dev/null)
  fi

  if [[ -n "$vault_name" ]]; then
    local encoded
    encoded="$(printf '%s' "$vault_name" | jq -sRr @uri)"
    open "obsidian://open?vault=$encoded"
  else
    # Unregistered but valid vault — hand the folder to Obsidian.app, which
    # will register and open it.
    open -a Obsidian "$root"
  fi
}
