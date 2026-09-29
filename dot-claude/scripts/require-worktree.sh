#!/usr/bin/env bash
# PreToolUse guard: work repos (GitHub HHS, common-grants, agilesix) take
# changes only in linked worktrees. In their main checkout it denies edits to
# non-ignored files, commits, and in-place branch switches.
# Test: bash tests/test-require-worktree.sh

GUARDED_ORIGIN='github\.com[:/](HHS|common-grants|agilesix)/'

input=$(cat)

deny() {
  jq -n --arg r "$1" '{hookSpecificOutput: {hookEventName: "PreToolUse",
    permissionDecision: "deny", permissionDecisionReason: $r}}'
  exit 0
}

hint() {
  echo "$1 is the main checkout of a work repo, so changes go in a worktree." \
    "From $1 run \`wt switch --create bryan/<issue-id>-<subject>\` (or reuse" \
    "one from \`wt list\`), then $2 in that worktree."
}

near_dir() {
  local d=$1
  while [[ ! -d $d ]]; do d=$(dirname "$d"); done
  echo "$d"
}

# Echo the checkout root if $1 is inside the main checkout of a guarded repo.
guarded_trunk() {
  local top
  top=$(git -C "$(near_dir "$1")" rev-parse --show-toplevel 2>/dev/null) || return 1
  [[ -d $top/.git ]] || return 1  # a linked worktree's .git is a file
  git -C "$top" remote get-url origin 2>/dev/null | grep -Eq "$GUARDED_ORIGIN" || return 1
  echo "$top"
}

resolve() {  # resolve BASE PATH -> absolute PATH
  local p=${2//[\'\"]/}
  p=${p/#\~/$HOME}
  [[ $p == /* ]] || p=$1/$p
  echo "$p"
}

check_git() {
  local dir=$1 sub top def target= a create=0
  shift
  while [[ $1 == -* ]]; do
    case $1 in
      -C) dir=$(resolve "$dir" "$2"); shift 2 || return 0 ;;
      -c) shift 2 || return 0 ;;
      *) shift ;;
    esac
  done
  sub=$1
  shift
  [[ $sub == commit || $sub == switch || $sub == checkout ]] || return 0
  top=$(guarded_trunk "$dir") || return 0
  [[ $sub == commit ]] && deny "$(hint "$top" "commit")"
  for a in "$@"; do
    case $a in
      -b|-B|-c|-C|--create|--force-create|--orphan) create=1 ;;
      --) return 0 ;;  # checkout -- <paths> restores files
      -*) ;;
      *) target=${target:-$a} ;;
    esac
  done
  ((create)) && deny "$(hint "$top" "create the branch")"
  def=$(git -C "$top" symbolic-ref --short -q refs/remotes/origin/HEAD)
  def=${def#origin/}
  [[ $target == "${def:-main}" ]] && return 0
  if [[ $sub == switch ]] ||
    git -C "$top" show-ref -q --verify "refs/heads/$target" ||
    git -C "$top" show-ref -q --verify "refs/remotes/origin/$target"; then
    deny "$(hint "$top" "switch branches")"
  fi
}

check_bash() {
  local cmd dir seg top
  local -a w
  cmd=$(jq -r '.tool_input.command // empty' <<<"$input")
  [[ $cmd == *git* || $cmd == *gh* ]] || return 0
  dir=$(jq -r '.cwd // empty' <<<"$input")
  dir=${dir:-$PWD}
  # ponytail: splits on shell separators and newlines without quote handling,
  # so a heredoc line that starts with "git commit" can misfire; swap in a real
  # shell parser if that ever bites.
  while IFS= read -r seg; do
    read -ra w <<<"$seg"
    while [[ ${w[0]} == *=* ]]; do w=("${w[@]:1}"); done  # VAR=val prefixes
    case ${w[0]} in
      cd) dir=$(resolve "$dir" "${w[1]:-$HOME}") ;;
      git) check_git "$dir" "${w[@]:1}" ;;
      gh)
        if [[ ${w[1]} == pr && ${w[2]} == checkout ]] && top=$(guarded_trunk "$dir"); then
          deny "$(hint "$top" "check the PR out")"
        fi
        ;;
    esac
  done < <(tr ';|&()' '\n\n\n\n\n' <<<"$cmd")
}

case $(jq -r '.tool_name // empty' <<<"$input") in
  Edit|Write|MultiEdit|NotebookEdit)
    file=$(jq -r '.tool_input.file_path // .tool_input.notebook_path // empty' <<<"$input")
    [[ -n $file ]] || exit 0
    near=$(near_dir "$(dirname "$file")")
    top=$(guarded_trunk "$near") || exit 0
    # Ignored files (AGENTS.md, the vault link) never enter history.
    git -C "$near" check-ignore -q -- "${file#"$near"/}" && exit 0
    deny "$(hint "$top" "redo this edit at the same relative path")"
    ;;
  Bash) check_bash ;;
esac
exit 0
