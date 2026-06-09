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

# Worktrunk: create worktree and add agent tmux window to current session
# Usage: wcode <branch-name> [prompt for opencode]
# Creates a worktree via wt switch -c, then adds a new tmux window
# to the current session running opencode in that worktree directory.
function wcode {
  local branch="$1"
  if [[ -z "$branch" ]]; then
    echo "Usage: wcode <branch-name> [prompt]"
    return 1
  fi
  shift
  local prompt="$*"

  # Must be inside a git repo
  if ! git rev-parse --show-toplevel >/dev/null 2>&1; then
    echo "Error: not in a git repository"
    return 1
  fi

  # Must be inside tmux
  if [[ -z "$TMUX" ]]; then
    echo "Error: wcode requires an active tmux session"
    return 1
  fi

  # Create worktree; skip only tmux rename hook since wcode manages tmux itself
  # WT_SKIP_TMUX_RENAME prevents the post-switch hook from renaming the current window
  (WT_SKIP_TMUX_RENAME=1 wt switch --create "$branch")
  local wt_exit=$?
  if [[ $wt_exit -ne 0 ]]; then
    echo "Error: failed to create worktree for branch: $branch"
    return 1
  fi

  # Get the worktree path from wt list
  local worktree_path
  worktree_path=$(wt list --format=json | jq -r ".[] | select(.branch == \"$branch\") | .path")

  if [[ -z "$worktree_path" || "$worktree_path" == "null" ]]; then
    echo "Error: could not find worktree path for branch: $branch"
    return 1
  fi

  # Add a new tmux window to the current session at the worktree path
  local sanitized_branch="${branch//\//-}"
  tmux new-window -n "$sanitized_branch" -c "$worktree_path"

  # Launch opencode in the new window
  if [[ -n "$prompt" ]]; then
    tmux send-keys -t ":$sanitized_branch" "opencode" C-m
    # Brief pause to let opencode initialize, then send the prompt
    sleep 2
    tmux send-keys -t ":$sanitized_branch" "$prompt" C-m
  else
    tmux send-keys -t ":$sanitized_branch" "opencode" C-m
  fi

  echo "Worktree '$branch' created at $worktree_path"
  echo "Tmux window '$sanitized_branch' added with opencode"
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

# Code function: opens editor in specified project directory or current directory
# Resolves $1 by checking ~/code/$1 first, then any ~/code/*/$1 (org-style
# containers like HHS/, common-grants/, games/). Auto-discovers new containers
# so adding a new org dir needs no edit here.
function code {
  local target_dir

  if [[ -n $1 && $1 != "." ]]; then
    local dir="$HOME/code/$1"

    if [[ -d $dir ]]; then
      target_dir="$dir"
    else
      local matches=()
      local container
      for container in "$HOME"/code/*/; do
        [[ -d "${container}$1" ]] || continue
        # Skip if the container itself is a git repo (it's a project, not an org dir)
        [[ -d "${container}.git" ]] && continue
        matches+=("${container}$1")
      done

      if (( ${#matches[@]} == 0 )); then
        echo "Directory $1 not found in ~/code or any ~/code/*/ container"
        return 1
      elif (( ${#matches[@]} > 1 )); then
        echo "Ambiguous: $1 exists in multiple containers:"
        printf '  %s\n' "${matches[@]}"
        echo "Using first match. Disambiguate with: code <container>/$1"
      fi
      target_dir="${matches[1]}"
    fi
  else
    target_dir="$PWD"
  fi

  cd "$target_dir" || return 1

  local session_script="$HOME/.tmux/code-editor.sh"
  if [[ ! -x $session_script ]]; then
    echo "Session script $session_script not found or not executable"
    return 1
  fi

  "$session_script"
}

# pair-agents: a global hub for Claude background agents.
# Unlike `code`, this ignores any argument and always opens at ~/code, so the
# `claude agents` dashboard sees background sessions across every project.
function pa {
  cd "$HOME/code" || return 1

  local session_script="$HOME/.tmux/pair-agents.sh"
  if [[ ! -x $session_script ]]; then
    echo "Session script $session_script not found or not executable"
    return 1
  fi

  "$session_script"
}
