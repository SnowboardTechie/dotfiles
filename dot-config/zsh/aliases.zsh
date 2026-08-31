# Aliases
# Portable aliases live in dot-config/shell/aliases.sh, shared with bash on
# Omarchy hosts. This file loads them and adds what only the fully-owned
# zsh machines (macOS/NixOS) should have.

# Resolve the shared file relative to this (possibly symlinked) file, so it
# works before and after stow deploys ~/.config/shell.
_shared_aliases="${${(%):-%N}:A:h}/../shell/aliases.sh"
[[ -f "$_shared_aliases" ]] || _shared_aliases="${XDG_CONFIG_HOME:-$HOME/.config}/shell/aliases.sh"
[[ -f "$_shared_aliases" ]] && source "$_shared_aliases"
unset _shared_aliases

# eza ls-family — personal flavors for machines this repo fully owns.
# (Deliberately not shared: Omarchy ships its own eza aliases and keeps them.)
alias ls="eza --icons"
alias ll="eza -lah --icons"
alias la="eza -a --icons"
alias lla="eza -la"
alias lsa="eza -lah"
alias lt="eza --tree --icons"

# Nix flake update alias
alias nix-flake-update="nix flake update --flake $HOME/code/nix-configs"

# Host-guarded Nix update/upgrade commands are functions in functions.zsh.

# Use macOS system SSH for UseKeyChain support (macOS only)
if [[ "$OSTYPE" == "darwin"* ]]; then
  alias ssh='/usr/bin/ssh'
fi
