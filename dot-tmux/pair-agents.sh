#!/usr/bin/env bash

# Tmux session for pairing with Claude background agents
# Creates a session with 3 windows: cli, agents, nvim
# Launched from ~/code as a global hub (see the `pa` zsh function)

# Ensure we have a proper TTY for tmux
if [[ ! -t 0 ]]; then
  exec </dev/tty
fi

SESSION_NAME="pair-agents"

# Check if session already exists
tmux has-session -t "$SESSION_NAME" 2>/dev/null

if [ $? != 0 ]; then
  # Create new session with first window (cli)
  tmux new-session -d -s "$SESSION_NAME" -n "cli"

  # Window 2: agents
  tmux new-window -t "$SESSION_NAME:2" -n "agents"
  tmux send-keys -t "$SESSION_NAME:2" "claude agents" C-m

  # Window 3: nvim
  tmux new-window -t "$SESSION_NAME:3" -n "nvim"
  tmux send-keys -t "$SESSION_NAME:3" "nvim ." C-m

fi

# Always land on the agents window (2) when launching or re-attaching
tmux select-window -t "$SESSION_NAME:2"

# Attach to the session (or switch if already in tmux)
if [[ -n "$TMUX" ]]; then
  tmux switch-client -t "$SESSION_NAME"
else
  tmux attach-session -t "$SESSION_NAME"
fi
