#!/usr/bin/env bash

# Claude Max 5-hour usage for Herdr's conditional command status entry.
# This is read-only: Claude Code owns OAuth token refresh and rotation.

CACHE_FILE="${XDG_RUNTIME_DIR:-/tmp}/herdr-claude-usage-cache"
CACHE_TTL=300

command -v jq >/dev/null 2>&1 || exit 0
command -v curl >/dev/null 2>&1 || exit 0

CREDS_FILE="$HOME/.claude/.credentials.json"
if [[ "$OSTYPE" == "darwin"* ]]; then
    CREDS_JSON=$(security find-generic-password -s "Claude Code-credentials" -w 2>/dev/null)
    if [[ -z "$CREDS_JSON" ]]; then
        [[ -f "$CREDS_FILE" ]] || exit 0
        CREDS_JSON=$(<"$CREDS_FILE")
    fi
else
    [[ -f "$CREDS_FILE" ]] || exit 0
    CREDS_JSON=$(<"$CREDS_FILE")
fi
[[ -n "$CREDS_JSON" ]] || exit 0

TOKEN=$(printf '%s' "$CREDS_JSON" | jq -r '.claudeAiOauth.accessToken // empty' 2>/dev/null)
[[ -n "$TOKEN" ]] || exit 0

cache_age() {
    local mtime
    mtime=$(stat -c %Y "$CACHE_FILE" 2>/dev/null || stat -f %m "$CACHE_FILE" 2>/dev/null)
    printf '%s\n' "$(( $(date +%s) - ${mtime:-0} ))"
}

if [[ -f "$CACHE_FILE" ]] && [[ $(cache_age) -lt $CACHE_TTL ]]; then
    UTILIZATION=$(sed -n '1p' "$CACHE_FILE")
    RESET_EPOCH=$(sed -n '2p' "$CACHE_FILE")
else
    HEADERS=$(curl -s \
        --max-time 4 \
        --connect-timeout 3 \
        --retry 0 \
        -D - \
        -o /dev/null \
        -H "Authorization: Bearer $TOKEN" \
        -H "anthropic-version: 2023-06-01" \
        -H "anthropic-beta: oauth-2025-04-20" \
        -H "Content-Type: application/json" \
        -d '{"model":"claude-haiku-4-5-20251001","max_tokens":1,"messages":[{"role":"user","content":"hi"}]}' \
        "https://api.anthropic.com/v1/messages" 2>/dev/null)

    UTILIZATION=$(printf '%s' "$HEADERS" | grep -i 'anthropic-ratelimit-unified-5h-utilization' | sed 's/.*: *//' | grep -oE '[0-9]+\.?[0-9]*' | head -1)
    RESET_EPOCH=$(printf '%s' "$HEADERS" | grep -i 'anthropic-ratelimit-unified-5h-reset' | sed 's/.*: *//' | grep -oE '[0-9]+' | head -1)

    if [[ -z "$UTILIZATION" || -z "$RESET_EPOCH" ]]; then
        if [[ -f "$CACHE_FILE" ]]; then
            UTILIZATION=$(sed -n '1p' "$CACHE_FILE")
            RESET_EPOCH=$(sed -n '2p' "$CACHE_FILE")
        else
            exit 0
        fi
    else
        printf '%s\n%s\n' "$UTILIZATION" "$RESET_EPOCH" > "${CACHE_FILE}.tmp" \
            && mv "${CACHE_FILE}.tmp" "$CACHE_FILE"
    fi
fi

[[ -n "$UTILIZATION" && -n "$RESET_EPOCH" ]] || exit 0

PCT=$(awk "BEGIN {printf \"%.0f\", $UTILIZATION * 100}" 2>/dev/null)
REMAINING=$(( RESET_EPOCH - $(date +%s) ))
[[ $REMAINING -lt 0 ]] && REMAINING=0
HOURS=$(( REMAINING / 3600 ))
MINS=$(printf "%02d" $(( (REMAINING % 3600) / 60 )))

# Glyph Rail module:  U+EC82 Claude, ↻ U+21BB quota reset.
printf ' %s%% ↻%s:%s\n' "$PCT" "$HOURS" "$MINS"
