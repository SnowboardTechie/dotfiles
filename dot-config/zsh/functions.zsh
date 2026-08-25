# Custom shell functions

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
