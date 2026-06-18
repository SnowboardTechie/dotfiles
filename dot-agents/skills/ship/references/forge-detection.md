# Forge Detection

Shared forge-plumbing used by `ship`, `issue-create`, and `update-pr-description`: detect whether the current repo is hosted on GitHub or a Forgejo-family forge (Forgejo / Gitea / Codeberg / self-hosted), and parse the owner/repo and instance URL from the remote. Each calling skill decides what to do with an `unknown` result (see "Disposition" below); this doc owns the detection + parsing so the recognized-forge list and the sed patterns can't drift across the three skills.

## Detect the forge

```bash
remote_url=$(git remote get-url origin 2>/dev/null)
if [[ "$remote_url" == *"github.com"* ]]; then
  forge="github"
elif [[ "$remote_url" == *"forgejo"* || "$remote_url" == *"gitea"* || "$remote_url" == *"codeberg"* || "$remote_url" == *"snowboardtechie"* ]]; then
  forge="forgejo"
else
  forge="unknown"
fi
```

To support an additional self-hosted Forgejo/Gitea host, add its hostname substring to the `elif`. **This list is the single source of truth — update it here, not in the individual skills.**

## Parse owner/repo

```bash
# SSH:   git@github.com:owner/repo.git                → owner/repo
# HTTPS: https://github.com/owner/repo.git            → owner/repo
# SSH:   ssh://forgejo@git.example.com/owner/repo.git → owner/repo
owner_repo=$(echo "$remote_url" | sed -E 's|.*[:/]([^/]+/[^/]+?)(\.git)?$|\1|')
```

## Derive the instance base URL (Forgejo API)

```bash
instance=$(echo "$remote_url" | sed -E 's|.*(@\|//)([^:/]+).*|https://\2|')
```

## Disposition of `unknown` / ambiguity (caller-owned)

The shared detection sets `forge="unknown"` and stops there. Each skill decides what that means:

- **`ship`** — stop: "No supported forge detected — use wt merge instead."
- **`issue-create`** — ask the user which repo to file against (accept `{owner}/{repo}` shorthand or a full URL). Also confirm when there are multiple remotes, or when the user's request names a different repo than cwd.
- **`update-pr-description`** — error out with the supported-forge list. For Forgejo it otherwise relies on `tea` auto-resolving owner/repo, so manual parsing is rarely needed.
