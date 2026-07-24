# Zsh options and keybindings

# Keep a large shared history. nix-darwin's system default is only 2,000
# entries, which causes zsh to periodically rewrite and trim the history file.
HISTSIZE=120000
SAVEHIST=100000

# Zsh options
setopt AUTO_CD  # Type directory name to cd into it (e.g., just type '..' or '/tmp')

# Enable vi mode
bindkey -v

# Enhanced completion settings
zstyle ':completion:*' menu select
zstyle ':completion:*' matcher-list 'm:{a-zA-Z}={A-Za-z}' # Case insensitive completion
zstyle ':completion:*' list-colors "${(s.:.)LS_COLORS}" # Colored completion
