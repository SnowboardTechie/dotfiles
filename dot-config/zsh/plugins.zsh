# Zsh plugins (cross-platform loading)

# zsh-autosuggestions
if [[ -f /opt/homebrew/share/zsh-autosuggestions/zsh-autosuggestions.zsh ]]; then
  source /opt/homebrew/share/zsh-autosuggestions/zsh-autosuggestions.zsh
elif [[ -f /run/current-system/sw/share/zsh-autosuggestions/zsh-autosuggestions.zsh ]]; then
  source /run/current-system/sw/share/zsh-autosuggestions/zsh-autosuggestions.zsh
elif [[ -f /usr/share/zsh-autosuggestions/zsh-autosuggestions.zsh ]]; then
  source /usr/share/zsh-autosuggestions/zsh-autosuggestions.zsh
fi

# zsh-syntax-highlighting
if [[ -f /opt/homebrew/share/zsh-syntax-highlighting/zsh-syntax-highlighting.zsh ]]; then
  source /opt/homebrew/share/zsh-syntax-highlighting/zsh-syntax-highlighting.zsh
elif [[ -f /run/current-system/sw/share/zsh-syntax-highlighting/zsh-syntax-highlighting.zsh ]]; then
  source /run/current-system/sw/share/zsh-syntax-highlighting/zsh-syntax-highlighting.zsh
elif [[ -f /usr/share/zsh-syntax-highlighting/zsh-syntax-highlighting.zsh ]]; then
  source /usr/share/zsh-syntax-highlighting/zsh-syntax-highlighting.zsh
fi

# Initialize direnv
eval "$(direnv hook zsh)"

# Worktrunk shell integration (git worktree management)
# Enables directory switching on `wt switch` and tab completions.
# stderr is discarded: wt emits a trailing color-reset (and any config warnings)
# to stderr, which leaks past the `$(...)` capture to the TTY and trips
# Powerlevel10k's "console output during zsh initialization" instant-prompt warning.
if command -v wt >/dev/null 2>&1; then eval "$(command wt config shell init zsh 2>/dev/null)"; fi
