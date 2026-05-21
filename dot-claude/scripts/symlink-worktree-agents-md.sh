#!/usr/bin/env bash
# SessionStart hook: when a session starts inside a git worktree (not the main
# checkout), mirror personal/gitignored shared resources from the main repo:
#   - Every AGENTS.md file (path-preserving)
#   - Whole directories listed in SHARED_DIRS (e.g. .notes)
#
# Idempotent: skips anything that already exists. No-op outside a worktree, or
# in the main checkout itself. Exits 0 unconditionally so a failure here can
# never block session start.
#
# Payload (stdin, JSON): SessionStart provides `.cwd`. Falls back to $PWD.

set -uo pipefail

SHARED_DIRS=(".notes")
LOG_FILE="/Users/bryan/.claude/scripts/symlink-worktree-agents-md.log"

input=$(cat)

{
  echo "=== $(date -u +%Y-%m-%dT%H:%M:%SZ) hook invoked ==="
  echo "PWD=$PWD"
  echo "PAYLOAD: $input"
} >> "$LOG_FILE" 2>/dev/null

worktree=$(printf '%s' "$input" | jq -r '.cwd // empty' 2>/dev/null)
worktree=${worktree:-$PWD}
worktree=$(cd "$worktree" 2>/dev/null && pwd) || { echo "RESULT: cwd not resolvable" >> "$LOG_FILE" 2>/dev/null; exit 0; }

git -C "$worktree" rev-parse --is-inside-work-tree >/dev/null 2>&1 || { echo "RESULT: not in git" >> "$LOG_FILE" 2>/dev/null; exit 0; }

main=$(git -C "$worktree" worktree list --porcelain 2>/dev/null \
  | awk '/^worktree / { print $2; exit }')
[ -n "$main" ] || { echo "RESULT: no main worktree found" >> "$LOG_FILE" 2>/dev/null; exit 0; }
if [ "$main" = "$worktree" ]; then
  echo "RESULT: in main checkout, skipping" >> "$LOG_FILE" 2>/dev/null
  exit 0
fi

linked=0
while IFS= read -r src; do
  rel="${src#"$main"/}"
  dst="$worktree/$rel"

  if [ -e "$dst" ] || [ -L "$dst" ]; then
    continue
  fi

  parent=$(dirname "$dst")
  [ -d "$parent" ] || continue

  if ln -s "$src" "$dst" 2>/dev/null; then
    linked=$((linked+1))
  fi
done < <(find "$main" -name AGENTS.md \
  -not -path '*/node_modules/*' \
  -not -path '*/.git/*' \
  -not -path '*/.claude/worktrees/*' \
  2>/dev/null)

for dir_name in "${SHARED_DIRS[@]}"; do
  src_dir="$main/$dir_name"
  dst_dir="$worktree/$dir_name"

  [ -d "$src_dir" ] || continue
  if [ -e "$dst_dir" ] || [ -L "$dst_dir" ]; then
    continue
  fi

  if ln -s "$src_dir" "$dst_dir" 2>/dev/null; then
    linked=$((linked+1))
  fi
done

echo "RESULT: main=$main worktree=$worktree linked=$linked" >> "$LOG_FILE" 2>/dev/null
exit 0
