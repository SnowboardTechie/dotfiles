# Fetching Tickets — CLI Reference

Long-form fetch recipes. Use them from an isolated intake child (`delegate_task`, `Task`, or `Agent`) or inline when delegation is unavailable. Loaded on demand from SKILL.md.

---

## GitHub

### Auth precheck

```bash
gh auth status || { echo "Run: gh auth login"; exit 1; }
```

### Issue — metadata + body

```bash
gh issue view {N} --repo {owner}/{repo} \
  --json number,title,body,state,labels,assignees,url,createdAt,closedAt,author
```

Fields returned:
- `number`, `title`, `body`, `state` (OPEN/CLOSED)
- `labels` — array of `{name, color, description}`
- `assignees` — array of `{login}`
- `author.login`, `createdAt`, `closedAt`

### Issue — comments

```bash
gh issue view {N} --repo {owner}/{repo} --comments
```

This returns a rendered text view. To get structured JSON for comments (needed for author + timestamp):

```bash
gh api "repos/{owner}/{repo}/issues/{N}/comments" \
  --jq '[.[] | {author: .user.login, created: .created_at, body: .body}]'
```

With pagination for issues with > 30 comments:

```bash
gh api --paginate "repos/{owner}/{repo}/issues/{N}/comments" \
  --jq '.[] | {author: .user.login, created: .created_at, body: .body}'
```

### Pull Request — metadata + review comments

```bash
gh pr view {N} --repo {owner}/{repo} \
  --json number,title,body,state,labels,assignees,url,createdAt,closedAt,mergedAt,author,baseRefName,headRefName,commits,files,reviews,comments
```

Note: `comments` on a PR view returns **issue comments** (the conversation tab). **Review comments** (inline on diff) come from a separate endpoint:

```bash
gh api "repos/{owner}/{repo}/pulls/{N}/comments" \
  --jq '[.[] | {author: .user.login, created: .created_at, path: .path, line: .line, body: .body}]'
```

### Telling an issue from a PR

If the URL path is `/pull/{N}`, it's a PR. If `/issues/{N}`, it's an issue. If you only have a number (from shorthand `owner/repo#N`), try issue first:

```bash
gh issue view {N} --repo {owner}/{repo} 2>/dev/null \
  || gh pr view {N} --repo {owner}/{repo}
```

GitHub numbering is shared between issues and PRs in a repo, so `#123` is unambiguous — it's exactly one of them.

### Rate limits

```bash
gh api rate_limit --jq '.rate'
```

If `remaining < 10` and the fetch will need more calls, stop and report to the user with the reset time. Do not auto-retry past the limit.

---

## Forgejo / Gitea / Codeberg

Use authenticated `tea api` calls. Resolve the host and owner/repo with the
shared `ship` forge parser, then choose the configured Tea login for that host.
If Tea cannot read the current checkout because of
`extensions.worktreeconfig`, run it from the temporary initialized-repository
context documented by `ship` with explicit `--login` and `--repo` values.

### Auth

Verify the matching configured login with `tea login list`. Never parse, print,
or copy Tea's stored token.

### Issue (or PR — Forgejo treats PRs as issues for this endpoint)

```bash
LOGIN="{configured-login}" # login whose URL matches the parsed host
OWNER="{owner}"
REPO="{repo}"
N="{number}"

# Basic issue/PR record
tea api --login "$LOGIN" --repo "$OWNER/$REPO" \
  "/repos/$OWNER/$REPO/issues/$N" \
  | jq '{
      number, title, body, state,
      labels: [.labels[].name],
      author: .user.login,
      created_at, closed_at,
      is_pr: (.pull_request != null),
      html_url
    }'
```

### Comments

```bash
tea api --login "$LOGIN" --repo "$OWNER/$REPO" \
  "/repos/$OWNER/$REPO/issues/$N/comments" \
  | jq '[.[] | {author: .user.login, created: .created_at, body: .body}]'
```

Paginate if needed:

```bash
page=1
while :; do
  resp=$(tea api --login "$LOGIN" --repo "$OWNER/$REPO" \
    "/repos/$OWNER/$REPO/issues/$N/comments?page=$page&limit=50")
  [[ "$resp" == "[]" ]] && break
  echo "$resp"
  page=$((page + 1))
done | jq -s 'add'
```

### PR-specific fields (if `is_pr: true`)

```bash
tea api --login "$LOGIN" --repo "$OWNER/$REPO" \
  "/repos/$OWNER/$REPO/pulls/$N" \
  | jq '{
      base: .base.ref,
      head: .head.ref,
      merged,
      mergeable,
      files_changed: .changed_files
    }'
```

### Review comments (inline diff comments)

```bash
tea api --login "$LOGIN" --repo "$OWNER/$REPO" \
  "/repos/$OWNER/$REPO/pulls/$N/reviews" \
  | jq '[.[] | {author: .user.login, state, submitted_at, body}]'
```

---

## Linked Reference Extraction

Run against the body + every comment body:

```bash
# Combine body + all comment bodies into one stream
jq -r '.body' issue.json                          > /tmp/txt
jq -r '.[].body' comments.json                   >> /tmp/txt

# Extract candidates
rg -oE '(?:[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+)?#[0-9]+|\bhttps?://[^\s)]+\b|\b[a-f0-9]{7,40}\b' /tmp/txt \
  | sort -u
```

Categorize each candidate:

| Pattern | Category |
|---|---|
| `^[a-f0-9]{7,40}$` | commit SHA |
| `^#[0-9]+$` | same-repo issue/PR ref |
| `^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+#[0-9]+$` | cross-repo issue/PR ref |
| starts with `http` | URL — parse for known forges |

### Resolve each — one level deep

**Same-repo ref `#N`** (GitHub):

```bash
gh issue view {N} --repo {owner}/{repo} --json number,title,state,url 2>/dev/null \
  || gh pr view {N} --repo {owner}/{repo} --json number,title,state,url
```

**Cross-repo `other-owner/other-repo#N`** (GitHub):

```bash
gh issue view {N} --repo {other-owner}/{other-repo} --json number,title,state,url 2>/dev/null \
  || gh pr view {N} --repo {other-owner}/{other-repo} --json number,title,state,url
```

**Commit SHA** — only if the repo is cloned locally:

```bash
git -C "$LOCAL_CLONE" log -1 --format='%h %s' "{sha}" 2>/dev/null
```

If not cloned, skip silently.

**Arbitrary URL** — fetch the title with the host's read-only web fetch/browser tool (Hermes: browser/web tooling; other hosts: `WebFetch` or equivalent). Skip on failure.

### No-recursion rule

When you resolve a linked ref, only fetch its title + state + url. Do **not** fetch its body, comments, or its own linked refs. Recursion explodes context and rarely helps.

---

## Error-handling summary

| Situation | Action |
|---|---|
| `gh auth status` fails | Stop. Tell user to `gh auth login`. |
| `FORGEJO_TOKEN` missing | Stop. Tell user to set it. |
| 404 on primary ticket | Stop. "Ticket not found. Check URL/access." |
| 403 (rate limit or perms) | Stop. Report rate-limit reset time if present in `X-RateLimit-Reset`. |
| 404 on a linked ref | Record "could not fetch" and continue. |
| Forgejo instance unreachable | Stop. "Cannot reach {host}. Check VPN/network." |
