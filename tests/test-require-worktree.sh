#!/usr/bin/env bash
# Exercises dot-claude/scripts/require-worktree.sh against throwaway repos.
set -e
hook="$(cd "$(dirname "$0")/.." && pwd)/dot-claude/scripts/require-worktree.sh"
tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT
g() { git -c core.hooksPath=/dev/null -c commit.gpgsign=false \
  -c user.name=t -c user.email=t@example.com "$@"; }

g init -q -b main "$tmp/work"
g -C "$tmp/work" remote add origin git@github.com:HHS/example.git
echo AGENTS.md >"$tmp/work/.gitignore"
g -C "$tmp/work" add .gitignore
g -C "$tmp/work" commit -qm init
g -C "$tmp/work" branch feature
g -C "$tmp/work" worktree add -q -b topic "$tmp/work.topic"
g init -q -b main "$tmp/personal"
g -C "$tmp/personal" remote add origin ssh://forgejo@git.snowboardtechie.com/bryan/p.git

fails=0
expect() {
  local got
  got=$(printf '%s' "$2" | bash "$hook" | jq -r '.hookSpecificOutput.permissionDecision')
  if [[ ${got:-allow} != "$1" ]]; then
    echo "FAIL: want $1 for $2"
    fails=$((fails + 1))
  fi
}
edit() { jq -nc --arg f "$1" '{tool_name: "Edit", tool_input: {file_path: $f}}'; }
sh_in() { jq -nc --arg d "$1" --arg c "$2" '{tool_name: "Bash", cwd: $d, tool_input: {command: $c}}'; }

expect deny "$(edit "$tmp/work/README.md")"
expect deny "$(edit "$tmp/work/new/dir/file.ts")"
expect allow "$(edit "$tmp/work/AGENTS.md")"
expect allow "$(edit "$tmp/work.topic/README.md")"
expect allow "$(edit "$tmp/personal/README.md")"
expect deny "$(sh_in "$tmp/work" 'git commit -m x')"
expect deny "$(sh_in "$tmp" 'git -C work commit -m x')"
expect deny "$(sh_in "$tmp" "cd $tmp/work && git add . && git commit -m x")"
expect deny "$(sh_in "$tmp/work" 'GIT_EDITOR=true git commit')"
expect allow "$(sh_in "$tmp/work.topic" 'git commit -m x')"
expect allow "$(sh_in "$tmp/personal" 'git commit -m x')"
expect deny "$(sh_in "$tmp/work" 'git switch -c other')"
expect deny "$(sh_in "$tmp/work" 'git checkout -b other')"
expect deny "$(sh_in "$tmp/work" 'git switch feature')"
expect deny "$(sh_in "$tmp/work" 'git checkout feature')"
expect deny "$(sh_in "$tmp/work" 'gh pr checkout 12')"
expect allow "$(sh_in "$tmp/work" 'git switch main')"
expect allow "$(sh_in "$tmp/work" 'git checkout -- README.md')"
expect allow "$(sh_in "$tmp/work" 'git pull && wt switch --create bryan/other')"
expect allow "$(sh_in "$tmp/work" 'git -C')"

if ((fails)); then
  echo "$fails failed"
  exit 1
fi
echo "ok"
