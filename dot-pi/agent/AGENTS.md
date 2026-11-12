# Global Pi Instructions

- Never add AI attribution or `Co-authored-by` trailers.
- Be direct and concise; reference file paths explicitly.
- Follow repository-local `AGENTS.md` and `CONTRIBUTING.md` over these defaults.
- Use a Worktrunk-managed linked worktree for tracked project edits and commits.
- Exception: when Bryan gives a note to capture in a vault, commit the vault-only change directly to `main` in the canonical checkout and push it. Don't open a branch, worktree or PR, and don't ask for approval. If the repository's `main` runs CI on push, still wait for that run to pass.
- Safe repository maintenance may run in the primary checkout when explicitly requested or needed to finish an approved workflow, including `git status`, `git fetch`, `git pull --ff-only`, `git stash`, `git stash pop`, and Worktrunk worktree management. Preserve unrelated changes.
- Never use `git checkout` or `git switch` to change branches; use `wt switch` instead.
- Before writing to a project or personal vault, load the `vault-pkm` skill and any vault-local `AGENTS.md`.
- When posting PR review findings, use separate inline comments on the relevant files and lines.
- Verify delegated findings against source files before presenting them.
- `dotfiles` and `nix-configs` usually skip PRs, unlike Bryan's other repos. Work in a linked worktree, then fast-forward `main` and push once the change is verified. Don't open a PR or ask whether to, unless Bryan asks for one.
- Present web views, including copy-paste views of drafts, through a tailnet-only `tailscale serve` HTTPS URL on this Mac's ts.net name. Don't use a local `file://` path or a localhost URL. Check that the URL loads before sharing it.
