# Forge Detection

Shared forge plumbing for `ship`, `issue-create`, and `update-pr-description`.
It detects GitHub versus Forgejo-family hosts and parses host, owner/repo, and
instance URL without GNU-only or non-portable regular expressions.

## Parse the remote first

Use the linked helper at `scripts/parse-forge-remote.sh` in the `ship` skill
directory. Locate that directory through the active agent's skill loader; do not
copy its parsing logic into each caller.

```bash
remote_url=$(git remote get-url origin 2>/dev/null) || {
  echo "origin remote not found" >&2
  exit 1
}

# Replace <ship-skill-dir> with the resolved directory of the loaded ship skill.
IFS=$'\t' read -r forge_host owner_repo instance \
  < <(<ship-skill-dir>/scripts/parse-forge-remote.sh "$remote_url")
```

The parser supports:

- `git@github.com:owner/repo.git`
- `https://github.com/owner/repo.git`
- `ssh://forgejo@git.example.com/owner/repo.git`
- Codeberg and other Forgejo/Gitea remotes using the same URL forms

It emits one tab-delimited row:

```text
<host>  <owner/repo>  <scheme://host[:port]>
```

A malformed or unsupported remote exits nonzero. Treat that as `unknown`; do
not guess a repository.

## Detect the forge from the parsed host

```bash
case "$forge_host" in
  github.com)
    forge="github"
    ;;
  codeberg.org|git.snowboardtechie.com|*forgejo*|*gitea*)
    forge="forgejo"
    ;;
  *)
    forge="unknown"
    ;;
esac
```

To support another self-hosted Forgejo/Gitea instance, add its exact hostname
to this case. This reference is the single source of truth for recognized
hosts.

## Caller-owned disposition

- **`ship`** — stop with the supported-forge list. Do not silently switch to a
  different merge or publication path.
- **`issue-create`** — ask which repository to use. Confirm when multiple
  remotes exist or the request names a repository other than the current one.
- **`update-pr-description`** — stop with the supported-forge list.

All public writes still require Bryan's approval immediately before the API or
CLI call unless he explicitly pre-authorized that action in the current task.
