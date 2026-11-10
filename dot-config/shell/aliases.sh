# Portable shell aliases — shared by zsh (macOS/NixOS) and bash (Omarchy).
#
# Contract: bash- and zsh-compatible only (plain aliases, [[ ]], simple
# functions). No prompt, completion, or platform-owned behavior. Anything
# tool-dependent is guarded with `command -v` so sourcing is safe on hosts
# where the tool is absent.
#
# Loaded by:
#   - dot-config/zsh/aliases.zsh (full-ownership macOS/NixOS installs)
#   - a marked source line in ~/.bashrc on Omarchy, managed by
#     scripts/reconcile-shell-additions.sh
#
# The eza ls-family (ls/ll/la/lt...) is intentionally NOT here: Omarchy ships
# its own eza aliases, and those win on Omarchy hosts. The zsh config defines
# the personal flavors for machines this repo fully owns.

# Modern tool replacements
if command -v bat >/dev/null 2>&1; then
  alias cat="bat"
fi
if command -v nvim >/dev/null 2>&1; then
  alias vim="nvim"
  alias vi="nvim"
fi

# Utility aliases
alias clr="clear"
if command -v podman >/dev/null 2>&1; then
  alias docker="podman"
fi
if command -v fzf >/dev/null 2>&1; then
  alias fman="compgen -c | fzf | xargs man"
fi
# Studio-only Claude agent view for Hermes-managed background sessions.
if command -v scutil >/dev/null 2>&1; then
  _local_hostname="$(scutil --get LocalHostName 2>/dev/null)"
else
  _local_hostname="$(hostname -s 2>/dev/null)"
fi
if [[ "$_local_hostname" == "Bryans-Mac-Studio" ]] && command -v claude >/dev/null 2>&1; then
  alias hermes-claude='CLAUDE_CONFIG_DIR="$HOME/.hermes/claude-code-worker" claude agents'
  # Claude Code on Bryan's personal Max subscription, from any directory.
  alias claude-personal='CLAUDE_CONFIG_DIR="$HOME/.claude-personal" claude'
  # Same split as hermes below: under ~/code/sgg plain `claude` uses the default login
  # (the Agile Six work seat); everywhere else it uses the personal subscription. An
  # explicit CLAUDE_CONFIG_DIR always wins; `command claude` reaches the work seat anywhere.
  claude() {
    if [[ -z "$CLAUDE_CONFIG_DIR" ]]; then
      case "$PWD/" in
        "$HOME/code/sgg/"*) ;;
        *) CLAUDE_CONFIG_DIR="$HOME/.claude-personal" command claude "$@"; return ;;
      esac
    fi
    command claude "$@"
  }
fi
if [[ "$_local_hostname" == "Bryans-Mac-Studio" ]] && command -v hermes >/dev/null 2>&1; then
  # Work sessions under ~/code/sgg open the sgg profile (work subscription); everywhere
  # else Hermes keeps its default profile (personal). Only chat-style starts are routed:
  # no subcommand, a leading flag or `chat`, and no explicit profile or HERMES_HOME.
  hermes() {
    local _arg _route=1
    case "$PWD/" in
      "$HOME/code/sgg/"*) ;;
      *) _route=0 ;;
    esac
    [[ -n "$HERMES_HOME" ]] && _route=0
    case "${1:-}" in
      ""|-*|chat) ;;
      *) _route=0 ;;
    esac
    for _arg in "$@"; do
      case "$_arg" in
        -p|--profile|--profile=*) _route=0 ;;
      esac
    done
    if [[ $_route -eq 1 ]]; then
      command hermes -p sgg "$@"
    else
      command hermes "$@"
    fi
  }
fi
unset _local_hostname
# Pi follows the claude rule above: under ~/code/sgg plain `pi` uses the default Claude
# login (the work seat); everywhere else the personal plan. pi-claude-code passes
# PI_CLAUDE_CODE_CONFIG_DIR on as CLAUDE_CONFIG_DIR; the work seat means leaving it
# unset. An explicit PI_CLAUDE_CODE_CONFIG_DIR or CLAUDE_CONFIG_DIR wins, and
# `command pi` reaches the work seat anywhere. `/seat` inside Pi shows the seat in use.
# Only defined where the personal login exists.
if [[ -d "$HOME/.claude-personal" ]] && command -v pi >/dev/null 2>&1; then
  pi() {
    if [[ -z "$PI_CLAUDE_CODE_CONFIG_DIR" && -z "$CLAUDE_CONFIG_DIR" ]]; then
      case "$PWD/" in
        "$HOME/code/sgg/"*) ;;
        *) PI_CLAUDE_CODE_CONFIG_DIR="$HOME/.claude-personal" command pi "$@"; return ;;
      esac
    fi
    command pi "$@"
  }
fi

# Git aliases
alias ga="git add"
alias gb="git branch"
alias gd="git diff"
alias gs="git status"
alias gst="git status"
alias gp="git push"
alias gl="git log --oneline --graph"
alias gco="git checkout"
alias gcob="git checkout -b"
alias gaa="git add --all"
alias gcm="git commit -m"
alias gbd="git branch -d"
alias gbD="git branch -D"
alias gpl="git pull"
alias gpF="git push --force"

# Git rebase helper
# Defaults to 3 commits back, otherwise use argument passed as:
# - Count if integer: interactive rebase last N commits
# - Commit hash or branch name if string: rebase onto that ref
# Example usage:
#   grb           # interactive rebase last 3 commits
#   grb 6         # interactive rebase last 6 commits
#   grb feature   # rebase onto branch 'feature'
#   grb abc1234   # rebase onto commit abc1234
grb() {
  local commits=${1:-3}
  if [[ $commits =~ ^[0-9]+$ ]]; then
    git rebase -i HEAD~$commits
  else
    git rebase $commits
  fi
}

# Navigation aliases (guarded: only for directories present on this host)
if [[ -d "$HOME/code/dotfiles" ]]; then
  alias dotfiles="cd ~/code/dotfiles"
fi
if [[ -d "$HOME/code/nix-configs" ]]; then
  alias nix-configs="cd ~/code/nix-configs"
fi
if [[ -d "$HOME/code/sgg/HHS/simpler-grants-protocol" ]]; then
  alias sgp="cd ~/code/sgg/HHS/simpler-grants-protocol"
fi
if [[ -d "$HOME/second-brain" ]]; then
  alias second-brain="cd ~/second-brain/"
fi

# Worktrunk aliases (git worktree management)
if command -v wt >/dev/null 2>&1; then
  alias wls="wt list"
  alias wsw="wt switch"
  alias wrm="wt remove"
  alias wmg="wt merge"
fi
