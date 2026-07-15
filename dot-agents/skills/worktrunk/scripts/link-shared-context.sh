#!/usr/bin/env bash

set -euo pipefail

worktree="${1:-$PWD}"
worktree=$(cd "$worktree" && pwd)
git -C "$worktree" rev-parse --is-inside-work-tree >/dev/null

trunk=$(git -C "$worktree" worktree list --porcelain \
    | while IFS= read -r line; do
        case "$line" in
            "worktree "*) printf '%s\n' "${line#worktree }"; break ;;
        esac
    done)

if [[ -z "$trunk" || "$trunk" == "$worktree" ]]; then
    printf 'linked=0\n'
    exit 0
fi

linked=0
link_if_absent() {
    local source="$1" destination="$2"
    if [[ ! -e "$source" && ! -L "$source" ]]; then
        return
    fi
    if [[ -e "$destination" || -L "$destination" ]]; then
        return
    fi
    if [[ ! -d "$(dirname "$destination")" ]]; then
        return
    fi
    ln -s "$source" "$destination"
    linked=$((linked + 1))
}

while IFS= read -r source; do
    relative="${source#"$trunk"/}"
    link_if_absent "$source" "$worktree/$relative"
done < <(find "$trunk" -name AGENTS.md \
    -not -path '*/node_modules/*' \
    -not -path '*/.git/*' \
    -not -path '*/.worktrees/*' \
    -not -path '*/.claude/worktrees/*' 2>/dev/null)

# CLAUDE.md remains a symlink to AGENTS.md when the trunk uses that convention.
while IFS= read -r source; do
    relative="${source#"$trunk"/}"
    link_if_absent "$source" "$worktree/$relative"
done < <(find "$trunk" -name CLAUDE.md \
    -not -path '*/node_modules/*' \
    -not -path '*/.git/*' \
    -not -path '*/.worktrees/*' \
    -not -path '*/.claude/worktrees/*' 2>/dev/null)

for shared_dir in vault .notes; do
    link_if_absent "$trunk/$shared_dir" "$worktree/$shared_dir"
done

printf 'trunk=%s\nworktree=%s\nlinked=%s\n' "$trunk" "$worktree" "$linked"
