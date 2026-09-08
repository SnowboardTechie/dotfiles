#!/usr/bin/env bash

# Claude Max 5-hour usage for Herdr's conditional command status entry.
# This is read-only: Claude Code owns OAuth token refresh and rotation.

CACHE_FILE="${XDG_RUNTIME_DIR:-/tmp}/herdr-claude-usage-cache"
CACHE_TTL=300

MODE="${1:-render}"
case "$MODE" in
    render|--check-capacity) ;;
    *)
        printf 'usage: %s [--check-capacity]\n' "$0" >&2
        exit 64
        ;;
esac

usage_unavailable() {
    if [[ "$MODE" == "--check-capacity" ]]; then
        printf 'Claude capacity could not be verified\n' >&2
        exit 69
    fi
    exit 0
}

command -v jq >/dev/null 2>&1 || usage_unavailable
command -v curl >/dev/null 2>&1 || usage_unavailable

CREDS_FILE="$HOME/.claude/.credentials.json"
if [[ "$OSTYPE" == "darwin"* ]]; then
    CREDS_JSON=$(security find-generic-password -s "Claude Code-credentials" -w 2>/dev/null)
    if [[ -z "$CREDS_JSON" ]]; then
        [[ -f "$CREDS_FILE" ]] || usage_unavailable
        CREDS_JSON=$(<"$CREDS_FILE")
    fi
else
    [[ -f "$CREDS_FILE" ]] || usage_unavailable
    CREDS_JSON=$(<"$CREDS_FILE")
fi
[[ -n "$CREDS_JSON" ]] || usage_unavailable

TOKEN=$(printf '%s' "$CREDS_JSON" | jq -r '.claudeAiOauth.accessToken // empty' 2>/dev/null)
[[ -n "$TOKEN" ]] || usage_unavailable

cache_age() {
    local mtime
    mtime=$(stat -c %Y "$CACHE_FILE" 2>/dev/null || stat -f %m "$CACHE_FILE" 2>/dev/null)
    printf '%s\n' "$(( $(date +%s) - ${mtime:-0} ))"
}

if [[ "$MODE" == "render" && -f "$CACHE_FILE" ]] && [[ $(cache_age) -lt $CACHE_TTL ]]; then
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
        if [[ "$MODE" == "render" && -f "$CACHE_FILE" ]]; then
            UTILIZATION=$(sed -n '1p' "$CACHE_FILE")
            RESET_EPOCH=$(sed -n '2p' "$CACHE_FILE")
        else
            usage_unavailable
        fi
    else
        printf '%s\n%s\n' "$UTILIZATION" "$RESET_EPOCH" > "${CACHE_FILE}.tmp" \
            && mv "${CACHE_FILE}.tmp" "$CACHE_FILE"
    fi
fi

[[ -n "$UTILIZATION" && -n "$RESET_EPOCH" ]] || usage_unavailable

PCT=$(awk "BEGIN {printf \"%.0f\", $UTILIZATION * 100}" 2>/dev/null)
[[ "$PCT" =~ ^[0-9]+$ ]] || usage_unavailable
REMAINING=$(( RESET_EPOCH - $(date +%s) ))
[[ $REMAINING -lt 0 ]] && REMAINING=0
HOURS=$(( REMAINING / 3600 ))
MINS=$(printf "%02d" $(( (REMAINING % 3600) / 60 )))

if [[ "$MODE" == "--check-capacity" ]]; then
    if [[ "$PCT" -ge 100 ]]; then
        printf 'Claude 5-hour capacity exhausted (%s%%); reset in %s:%s\n' \
            "$PCT" "$HOURS" "$MINS" >&2
        exit 75
    fi
    printf 'Claude 5-hour capacity available: %s%%; reset in %s:%s\n' \
        "$PCT" "$HOURS" "$MINS"
    exit 0
fi

# Glyph Rail module:  U+EC82 Claude, ↻ U+21BB quota reset.
printf ' %s%% ↻%s:%s\n' "$PCT" "$HOURS" "$MINS"
