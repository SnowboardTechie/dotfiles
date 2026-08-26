#!/usr/bin/env bash

# Host identity for Herdr's Glyph Rail: a Nerd Font glyph for the machine's
# class, then a short label. Herdr resolves command entries on the server, so
# `herdr --remote` shows the remote machine here.
#
# The glyph comes from hardware/OS rather than a hostname allowlist, so a new
# box is recognizable without editing this file. Codepoints, because these are
# tofu without a Nerd Font: 󰒋 U+F048B server, 󰌢 U+F0322 laptop,
# 󰣇 U+F08C7 Arch/Omarchy.

if [[ "$OSTYPE" == darwin* ]]; then
    case "$(sysctl -n hw.model 2>/dev/null)" in
        MacBook*) GLYPH='󰌢' ;;
        *) GLYPH='󰒋' ;;
    esac
elif [[ -f /etc/arch-release ]]; then
    GLYPH='󰣇'
else
    # Anything else reached from here is a box we attached to remotely.
    GLYPH='󰒋'
fi

HOST="$(uname -n)"
HOST="${HOST%%.*}"

# Apple-assigned names ("Bryans-Mac-Studio") are too long for a tab row.
# ponytail: every Mac laptop reads as "MBP" — add a branch if the work laptop
# ever needs its own label.
case "$HOST" in
    *Studio*) LABEL='Studio' ;;
    *MacBook*) LABEL='MBP' ;;
    *) LABEL="$HOST" ;;
esac

printf '%s %s\n' "$GLYPH" "$LABEL"
