#!/usr/bin/env bash

set -euo pipefail

remote_url="${1:-}"
if [[ -z "$remote_url" ]]; then
    echo "usage: parse-forge-remote.sh <remote-url>" >&2
    exit 2
fi

case "$remote_url" in
    *://*)
        case "$remote_url" in
            http://*|https://*|ssh://*) ;;
            *)
                echo "unsupported remote URL: $remote_url" >&2
                exit 1
                ;;
        esac
        ;;
esac

case "$remote_url" in
    http://*|https://*)
        scheme="${remote_url%%://*}"
        rest="${remote_url#*://}"
        authority="${rest%%/*}"
        if [[ "$authority" == "$rest" ]]; then
            echo "remote URL has no repository path: $remote_url" >&2
            exit 1
        fi
        path="${rest#*/}"
        authority="${authority##*@}"
        host="${authority%%:*}"
        instance="$scheme://$authority"
        ;;
    ssh://*)
        rest="${remote_url#*://}"
        authority="${rest%%/*}"
        if [[ "$authority" == "$rest" ]]; then
            echo "remote URL has no repository path: $remote_url" >&2
            exit 1
        fi
        path="${rest#*/}"
        host="${authority##*@}"
        host="${host%%:*}"
        instance="https://$host"
        ;;
    *:*)
        # SCP-style SSH remote: user@host:owner/repo.git
        authority="${remote_url%%:*}"
        path="${remote_url#*:}"
        host="${authority##*@}"
        instance="https://$host"
        ;;
    *)
        echo "unsupported remote URL: $remote_url" >&2
        exit 1
        ;;
esac

path="${path#/}"
path="${path%/}"
path="${path%.git}"
repo="${path##*/}"
parent="${path%/*}"
owner="${parent##*/}"

if [[ -z "$host" || -z "$owner" || -z "$repo" || "$parent" == "$path" ]]; then
    echo "could not parse forge host and owner/repo from: $remote_url" >&2
    exit 1
fi

printf '%s\t%s/%s\t%s\n' "$host" "$owner" "$repo" "$instance"
