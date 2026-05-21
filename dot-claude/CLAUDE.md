# Global Instructions

- Never add `Co-Authored-By: Claude` (or any Claude-as-author) trailer to commit messages or PR descriptions.
- When creating PRs, default to draft (`gh pr create --draft`). Use the repo's PR template (`.github/pull_request_template.md`) if present. Never commit to main directly — verify `git branch --show-current` first.
- The user's project agent notes live in `AGENTS.md`, with `CLAUDE.md` as a symlink to it so the harness's CLAUDE.md autoload picks up the same content. Both filenames are in the user's global gitignore (`~/.config/git/ignore`) and should stay there. Don't propose creating a separate (non-symlink) `CLAUDE.md` alongside an existing `AGENTS.md`, don't suggest tracking either file, and don't suggest removing the global ignore.
- Preserve links when summarizing or re-sharing content (plan files, daily notes, PR/issue bodies). Don't strip markdown links to bare identifiers (`#740`, `PR #755`) — the user clicks them.
