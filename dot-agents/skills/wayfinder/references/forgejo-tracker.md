# Forgejo tracker mechanics

How a Wayfinder map physically lives on a Forgejo tracker. The
[`../scripts/forgejo_wayfinder.py`](../scripts/forgejo_wayfinder.py) adapter
implements all of it — **use the adapter, not hand-rolled API calls.** This
reference exists so you can read what it does and check its output, not so you
can reimplement it inline.

Grounded against **Forgejo 16.0.1+gitea-1.22.0** on 2026-08-19. Re-check the
version before assuming any endpoint below still behaves this way:
`tea api --login <host> /version`.

## What the API does and does not give us

| Need | Forgejo support |
|---|---|
| Blocking between issues | **Native.** `GET/POST/DELETE /repos/{owner}/{repo}/issues/{index}/dependencies` (what blocks this) and `/blocks` (what this blocks). Renders in the tracker UI, so the frontier is visible without opening the map. |
| Parent/child issues | **None.** There is no sub-issue endpoint at this version (`/issues/{index}/sub_issues` → 404). Map parentage is a managed metadata block in the ticket body. |
| Optimistic concurrency | **None.** No `If-Match` or version field on issue update, and `updated_at` is *set by* the write rather than checked against it — so it cannot arbitrate a race. The adapter uses it only as a staleness guard, and arbitrates claims by comment id instead. |
| Assignment | `assignees` on the issue. Useful for UI visibility, but it identifies a *person* — and Bryan is every session's assignee, so assignment alone cannot distinguish two of his sessions. Claims carry session identity separately. |
| Labels | Repository-scoped. **`CreateIssueOption.labels` is `array<int64>` — numeric ids, not names.** Names work in the `labels=` *query* filter and nowhere else, so the adapter resolves ids first and shows any missing label in the preview before creating it. **Trap:** a `labels=` query naming a label the repository does not have yet returns *every* issue, not none — before the first map exists the filter silently does nothing, so the adapter scopes by managed metadata and paginates rather than trusting it. |
| Comment ordering | `Comment.id` is server-assigned and monotonic. It is the **only** total order this API offers, and it is what arbitrates claims. |

## Labels

| Label | On | Meaning |
|---|---|---|
| `wayfinder:map` | the map issue | This issue is a map. The adapter refuses to read any issue as a map without it. |
| `wayfinder:ticket` | every ticket | Narrows the ticket query before metadata filtering. |
| `wayfinder:grilling` / `:research` / `:prototype` / `:task` | every ticket | The ticket's type. Mirrors the managed metadata so it is visible in the UI. |

Labels are a UI affordance and a query filter. They are never the source of
truth for which map a ticket belongs to — the metadata block is.

## The map body

```markdown
Anything written here by a human is preserved byte-for-byte.

<!-- wayfinder:map:begin v1 -->
## Destination

<what reaching the end of this map looks like: the spec, decision, or change
this effort is finding its way to. One or two lines; every session orients to
it before choosing a ticket.>

## Notes

<domain; skills every session should load; standing preferences for this effort>

## Not yet specified

<in-scope fog you cannot ticket yet; graduates as the frontier advances>

## Out of scope

<work ruled beyond the destination; closed, never graduates>
<!-- wayfinder:map:end -->
```

**Open tickets are not listed.** They are found by query, so the map never goes
stale against them. **Decided tickets are not listed in the body either**: the
decision index is the replay of the map's `index` comments (below), rendered by
`read-map` and visible on the map issue's own timeline — one comment per
decision, in server order, each naming its ticket.

**After creation, the adapter never writes the map body again — not the prose,
not the managed region.** Forgejo has no compare-and-swap on issue update, so a
body PATCH can always overwrite a human edit that landed after the adapter's
last read; no client-side lock or readback can close that window, so the write
does not exist. Everything between and around the markers belongs to Bryan.
The managed region still identifies the issue as a map (exactly one balanced
current-version region is required), and the adapter refuses an issue whose
region is missing, duplicated, or unbalanced.

## The ticket body

```markdown
## Question

<the decision or investigation this ticket resolves>

<!-- wayfinder:ticket v1
map: 42
type: grilling
-->
```

**Claims are not in the body.** They are append-only *comments*, because a
body is overwritten and a comment is ordered. See *Concurrency* below.

The answer is not in the body either. It is posted as a resolution comment when
the ticket closes, so the question stays readable and the answer carries its own
timestamp and author.

## Managed comment records

Four record kinds, each a comment carrying one managed block. `claim`/`release`
arbitrate one **ticket**; `resolution` is an idempotency marker on the ticket;
`index` records one decided ticket on its **map**, and the map's decision index
is the replay of those records:

```markdown
<!-- wayfinder:claim v1
at: 2026-08-19T09:41:07Z
operation: 8c1d4b6f2e0a97531fbc48d20e6a7c95
session: hermes/0f3c9a21
-->

<!-- wayfinder:release v1
at: 2026-08-19T11:02:00Z
operation: 8c1d4b6f2e0a97531fbc48d20e6a7c95
session: hermes/0f3c9a21
-->

<!-- wayfinder:resolution v1
key: 4f2a9c1e0b3d5a67
map: 42
session: hermes/0f3c9a21
-->

Decision #43: Storage shape: flat, migrations stay cheap

<!-- wayfinder:index v1
at: 2026-08-19T10:15:00Z
gist: Storage shape: flat, migrations stay cheap
key: 4f2a9c1e0b3d5a67
map: 42
session: hermes/0f3c9a21
ticket: 43
-->
```

An `index` comment carries a visible line — what a human reads on the map's
timeline — *and* the record. Replay reads only the record's `gist` field; the
prose is presentation, and state never rides on prose matching.

### Ownership is an identity tuple

An `operation` is 128 bits of `secrets.token_hex`, minted per acquisition and
carried by the `claim` and `release` kinds. It is necessary but **not
sufficient**: arbitration replays the comment log keyed on the full identity
`(operation, session)`, scoped to the ticket issue the record lives on.

Every part earns its place:

- **session alone is not ownership.** One session legitimately runs nested or
  concurrent operations, and a release matched on session would clear a sibling
  operation's claim — a lost claim inflicted from the inside, which no amount of
  cross-session care prevents.
- **operation alone is not ownership either.** Every id this adapter mints is
  written into a tracker comment, so anything that can read the issue can quote
  it back. An id is a *handle*, not a credential; a release or resolve must
  also come from the session that acquired it.

From that keying:

- the earliest unreleased **acquisition** holds the ticket;
- a release clears exactly the acquisition it names, and nothing else;
- a second acquisition from the same session is a real contender, so one
  session cannot hold two overlapping claims on the same ticket;
- a repeat carrying the **identical** identity folds into the existing hold —
  the only idempotent case, and the reason a retry posts nothing. `claim`
  validates the *whole* request, including ticket identity, **before**
  considering that fast path: a retry is only a retry if it is a retry of this
  exact claim.

`index` records carry no operation: they are not acquisitions. Their identity
is the `key`, and the replay's first-record-per-key rule is what makes posting
one idempotent.

### Exact schemas


Each kind has an exact v1 schema, and a block that does not match it **exactly**
is discarded — never partially used:

| Kind | Fields |
|---|---|
| `claim` | `session`, `operation`, `at` |
| `release` | `session`, `operation`, `at` |
| `resolution` | `session`, `key`, `map` |
| `index` | `session`, `key`, `map`, `ticket`, `gist`, `at` |

Rejected: **any** line that is not `key: value` — including a blank one — a
duplicate key, an unknown key, a missing key, an empty value, a wrong metadata
version, and any value failing its validator:

| Field | Valid |
|---|---|
| `session` | `[A-Za-z0-9][A-Za-z0-9._/-]{0,127}` |
| `operation` | 32 lowercase hex characters |
| `key` | 16 lowercase hex characters |
| `ticket`, `map` | a **positive** integer, 1–18 digits, no leading zero |
| `gist` | one safe line: nonempty, ≤300 chars, no CR/LF, not a heading or bare bullet, no HTML comment or Wayfinder marker |
| `at` | ISO 8601 UTC that **parses to a real instant** |

Two of those are stricter than they look, and deliberately:

- **Zero is not an issue number.** Forgejo numbers issues from 1, so `0` is a
  missing value dressed as one. There is no synthetic `ticket: 0` fallback
  anywhere: if the adapter cannot determine the ticket a record belongs to,
  that is an error, not a default. The same rule covers **server-returned
  ids**: a created issue or comment that comes back numbered `0` or below is
  not a created object, a record carried by a nonpositive comment id has no
  position in the replay order and never arbitrates or indexes, and a comment
  POST whose echo lacks a positive id fails its readback.
- **A timestamp must be a real instant, not an ISO-shaped string.**
  `2026-99-99T99:99:99Z` matches every plausible regex; it is additionally
  parsed with `datetime.strptime` and round-tripped, so an impossible month,
  day, hour, minute, or second is refused. Only `Z` is accepted — an offset form
  would make two records' order depend on reading their zones.

Blank lines are rejected rather than skipped because padding a reader tolerates
is padding a forger can hide behind. Permissive parsing is how a truncated write
or a hand-edited comment silently takes a claim, so a rejected record can
neither arbitrate nor satisfy readback or idempotency.

Rendering shares the same validators, so the adapter cannot emit a record its
own reader would reject — and a value one accepts and the other refuses is a
test failure, not a latent surprise. Every field value must also be a single
safe line: a newline or a `-->` inside a value would let it forge or terminate
the block it lives in.

The resolution `key` is a deterministic digest of map, ticket, and answer text.
It is what makes resolution retryable: a retry recognizes its own earlier
comment and skips that step, while a genuinely different answer does not
masquerade as one.

**Markers are matched structurally, never by substring.** Every managed block in
a comment is parsed — not just the first — and a resolution counts only when its
kind, metadata version, `key`, `map`, and `session` all match exactly. Answer
prose that happens to contain `key: …`, a marker for a different map, and a
marker written by an older metadata version are all *not* this resolution.

Assets created while resolving a ticket are **linked** from the issue, never
pasted into it.

## Operations

Every mutating command previews by default. `--apply` performs it.

**Tea/worktree pitfall:** some Tea builds use a Git parser that refuses
repositories carrying `extensions.worktreeConfig` with
`core.repositoryformatversion does not support extension: worktreeconfig`.
Because every adapter invocation already receives an explicit `--origin`,
capture the script, origin, and any input files as absolute paths, then run the
adapter from a known non-repository directory. Do not rewrite or disable an
intentional repository Git setting merely to work around Tea; if repository
instructions declare the setting accidental, repair it separately.

```bash
S="$PWD/dot-agents/skills/wayfinder/scripts/forgejo_wayfinder.py"
ORIGIN=$(git remote get-url origin)
# If Tea rejects this checkout:
TEA_CWD=$(mktemp -d)
trap 'rmdir "$TEA_CWD"' EXIT
# Then prefix each invocation below with: (cd "$TEA_CWD" && python3 "$S" ...)
TRACKER=bryan/sgg-workspace     # explicit, never inferred

python3 "$S" --origin "$ORIGIN" --tracker "$TRACKER" check-private
python3 "$S" --origin "$ORIGIN" --tracker "$TRACKER" read-map     --map 42
python3 "$S" --origin "$ORIGIN" --tracker "$TRACKER" list-tickets --map 42
python3 "$S" --origin "$ORIGIN" --tracker "$TRACKER" frontier     --map 42

python3 "$S" --origin "$ORIGIN" --tracker "$TRACKER" create-map \
    --title "Migrate the grants catalog" --managed-file map.md            # preview
python3 "$S" ... create-map --title "…" --managed-file map.md --apply     # write

python3 "$S" ... create-ticket --map 42 --title "Pick the storage shape" \
    --question-file q.md --type grilling [--apply]
python3 "$S" ... wire-blocking --map 42 --blocked 44 --blocked-by 43 [--apply]
# Claim prints the operation id it minted. Keep it — nothing else will do.
python3 "$S" ... claim   --map 42 --ticket 43 --session hermes/0f3c9a21 \
    --at 2026-08-19T09:41:07Z [--assignee bryan] [--apply]
#   → { "won": true, "operation": "8c1d4b6f2e0a97531fbc48d20e6a7c95", … }
# Retrying an interrupted claim: pass the same id back, and nothing is posted.
python3 "$S" ... claim   --map 42 --ticket 43 --session hermes/0f3c9a21 \
    --at 2026-08-19T09:41:07Z --operation 8c1d4b6f2e0a97531fbc48d20e6a7c95 --apply

# Who holds it, what is queued behind them, and the exact command for each.
python3 "$S" ... claim-status --map 42 --ticket 43

python3 "$S" ... release --map 42 --ticket 43 --session hermes/0f3c9a21 \
    --operation 8c1d4b6f2e0a97531fbc48d20e6a7c95 \
    --at 2026-08-19T11:02:00Z [--apply]
python3 "$S" ... resolve --map 42 --ticket 43 --session hermes/0f3c9a21 \
    --operation 8c1d4b6f2e0a97531fbc48d20e6a7c95 \
    --answer-file answer.md \
    --index-line "Storage shape: flat, migrations stay cheap" \
    --at 2026-08-19T10:15:00Z [--apply]
```

`--operation` is **required** on `release` and `resolve`, and optional on
`claim` (omit to mint one, pass one to retry idempotently). Every command takes
`--session` too, because the operation is only half the identity. Read both
from the `claim` output, from `claim-status`, or from the holder named in a
refusal. There is no session-only form and no operation-only form: the first
would clear a sibling operation's claim, and the second would let anyone who
can read the tracker drop someone else's.

A `resolve` reports `resolved: true` only when an index record with this
resolution's exact key replays on the map. Anything else comes back with a
`recovery` line; re-running the same resolve performs only the steps that did
not land, and the replay's first-record-per-key rule makes any duplicate
converge.

Creation is **two passes**: create the tickets, then wire the blocking edges.
Issues need ids before they can reference each other.

`--at` is required to `--apply` a resolution: the index record is a managed
record, and every managed record carries a timestamp.

The `--index-line` is the decision's gist. It must be a single safe line —
nonempty, no CR/LF, not a heading, not a bare bullet, no HTML comment or
Wayfinder marker, and within a length bound. It becomes the index comment's
visible line and its `gist` field, so anything that could forge structure or a
managed marker is refused before preview.

## Credentials

The adapter never reads, prints, stores, or serializes a token.

- **`auto` and `tea` both use `tea api`**, which supplies its own configured
  credential. No secret enters this process. `auto` does **not** upgrade to
  token transport just because a `FORGEJO_TOKEN` happens to be exported —
  binding an ambient credential to whatever host an origin URL named is the
  failure that rule exists to prevent.
- **`--transport token` is opt-in and host-pinned.** It requires the host to be
  listed in `WAYFINDER_FORGEJO_HOSTS` and refuses otherwise. The token is read
  once and used only as an `Authorization` header on that exact host; it never
  appears in an error message, and the transport's `repr` does not carry it.
- **Redirects are refused outright.** `urllib` would replay the `Authorization`
  header on a redirect target, and the Forgejo API has no reason to redirect, so
  every redirect is an error rather than a judgment call.
- **Request paths are validated.** A leading `//`, an embedded scheme, CR/LF, or
  a traversal segment is refused, so a path can never steer a credentialed
  request off its pin.

Owner, repository, and host are validated against strict patterns before any
request. Never scrape a token out of Tea's configuration, and never pass one on
a command line where it lands in shell history and process listings.

## Indexing decisions

Two tickets can be legitimately claimed at once, so two resolutions can finish
at the same moment. A shared mutable body would make those writes — and any
concurrent human edit — a race that this API's missing compare-and-swap cannot
decide, so no such body exists here.

There is nothing to serialize: the index write is an **append**.
Each resolution posts one `index` comment on the map, Forgejo assigns it a
monotonic id, and the decision index *is* the replay of those comments:

1. every schema-valid `index` record, in comment-id order;
2. first record per `key` wins — a retry, even one that rewords its gist,
   carries the same key and can never add a second entry, while an identical
   gist for a different ticket carries a different key and can never satisfy
   this one;
3. malformed, wrong-version, and nonpositive-id records never appear.

Two concurrent resolutions post two comments; neither can overwrite the
other's, and neither touches the map body, so a human editing the map at any
instant loses nothing. There is no lock, no lock recovery, and no held state a
crashed session can leave behind: a resolution that died mid-flight is finished
by re-running the same resolve.

`read-map` renders the replayed index alongside the map body. On the tracker
itself, the same decisions are readable as ordinary comments on the map issue,
newest last, each starting with its visible `Decision #N: …` line.

## Concurrency

Claiming is **append, then arbitrate by server order**:

1. Preflight the ticket, and read every managed record. A foreign active claim
   → stand down and report who holds it, without writing.
2. Post **one** claim comment. Forgejo assigns it a monotonic id.
3. Re-read every managed record and replay them in comment-id order. The
   **earliest unreleased operation wins**. If that is not ours, stand down.

Two contenders cannot both proceed, and the reason is worth stating precisely:
both compute the winner from the *same ordered comment list*, so the answer does
not depend on whose write landed last. The earlier body-overwrite scheme did
depend on that, which is exactly how it could let both racers believe they won.

`at` is client-supplied and never overrides comment order — only the id is
server-assigned. That is deliberate: a contender with a skewed clock, or one
that simply lies, cannot take a ticket from an earlier claimant.

**Only the current claimant operation may resolve.** `resolve` requires
`--session` *and* `--operation`, and refuses unless the active claim is exactly
that operation. Two sessions cannot resolve the same decision differently, and
neither can two operations of one session.

**A loser cleans up after itself.** A contender that posts a claim and *then*
loses arbitration withdraws **its own operation** before standing down.
Otherwise that record stays queued and becomes the active claim the moment the
winner releases — silently handing the ticket to a session that already walked
away. The withdrawal is verified as "this operation is no longer live", not as
"someone else is winning": a losing claim that is merely not winning is exactly
the zombie the withdrawal exists to prevent. If the withdrawal itself fails, the
outcome says `STILL QUEUED` and prints the exact `release` command, rather than
reporting a clean loss over a claim that is still queued.

**Stale claims are surfaced, never expired.** A session that died between
posting and standing down leaves a claim behind, and it stays visible: the next
session sees the ticket as claimed and can read the exact operation from
`claim-status`, then release it explicitly. The adapter will not release someone
else's claim, because a holder that looks abandoned may be merely slow, and
stealing it loses work.

## One guarded write path

Every external mutation goes through a single helper rather than each call site
remembering its own preflights. In order, every write:

1. re-reads the map and/or ticket and requires the **exact** issue number the
   request asked for, exactly one balanced current-version managed region (maps),
   and both the `wayfinder:ticket` and matching `wayfinder:{type}` labels
   agreeing with exact metadata (tickets);
2. where applicable, requires the exact active claim **identity tuple**;
3. where applicable, snapshots the dependency set the write will be measured
   against;
4. re-reads the repository and requires it private — **last**, the final network
   round trip before the mutation;
5. performs exactly one write, from the state already captured. The write reads
   nothing: a read there would put a round trip between the privacy check and
   the mutation, which is the window this ordering exists to close;
6. reads the state back and verifies the **exact** result.

Step 4's position is the point. Checking privacy first and then issuing three
more reads leaves a window in which the repository is made public while the
adapter is still deciding, and the write then lands on a tracker it approved a
round trip ago. So there is no `_patch_issue` helper that does GET-then-PATCH:
read preparation and the direct `PATCH`/`POST` are separate, and the staleness
guard the old helper provided is subsumed by the guard's own read, which is
strictly fresher.

What "exact" means, per family:

| Write | Verified |
|---|---|
| label creation | exact name, colour, description, and the id the create reported |
| map creation | a number **absent from a pre-write snapshot**, exact title, byte-exact body, exact label set, and full map identity |
| ticket creation | the same, plus exact metadata map/type and the matching type label |
| dependency | exact expected set = pre-write snapshot + the requested edge; a missing edge, a dropped unrelated edge, and an unexpected extra all fail |
| assignment | the assignee set **equals** the requested set; a retained pre-existing assignee fails |
| comment records (claim, release, resolution, index) | a **positive** comment id the API returned, naming a comment **absent from a pre-write snapshot**, with a byte-exact body |
| close | exact `closed` state **and** ticket identity still intact |
| release | a new exact drop record **and** the exact acquisition now inactive |

The pre-write snapshots matter as much as the comparisons. Without them, "a
valid map came back" is satisfied by an existing map the transport echoed
instead of creating, and "a record with these fields exists" is satisfied by the
record an *earlier* attempt wrote — so a retry whose write is swallowed reports
success, or reports a zombie that is not there.

This covers, without exception: label creation, map and ticket creation,
dependency wiring, the claim comment, the assignee patch, a losing claim's
withdrawal, a normal release, the resolution comment, the ticket close, and the
index record.

Step 6 exists because a 2xx is not proof of storage: a proxy, a retry layer, or
a half-applied API call can all acknowledge a write that never persisted. A
write that cannot be read back fails the operation.

Steps 1–4 run immediately before **each** write, not once when the operation
started. Between two steps a repository can be made public, a label can be
removed, a ticket can be re-pointed at another map, or a claim can change hands,
and a check at entry would not see any of it.

**Authority drift stops the operation, never gets patched around.** A guard
that fails mid-resolution raises with the exact refusal; the partial state is
retryable by re-running the same resolve, and nothing is ever written to a
tracker the adapter can no longer identify.

## Scoping

Every operation is scoped to one map's ticket set:

- `list-tickets` filters by the metadata `map:` field *and* version *and*
  type, not by label alone, so a ticket belonging to another map — or written
  by a future metadata version — is never picked up.
- **Every mutation preflights.** Immediately before each write, the adapter
  re-reads and revalidates repository privacy, the issue number the API
  actually returned, the required label, the metadata version and type, and the
  map association. A body marker alone is not identity: anyone can paste one
  into an unrelated issue.
- `claim`, `release`, `resolve`, and `wire-blocking` re-read the ticket and
  refuse if its metadata names a different map, and re-read the map itself and
  refuse if it is not labelled `wayfinder:map` or the API returns a different
  issue number.
- `read-map` refuses an issue that is not labelled `wayfinder:map`.
- Nothing closes, deletes, labels, comments on, or assigns any issue outside the
  map and tickets explicitly supplied.

## Verification

Every write is followed by a read: a created ticket is re-read for its metadata,
a dependency is re-read from `/dependencies`, an assignment is re-read for the
exact login, a close is re-read for `state`, a claim or release is re-read for
its exact operation id, and an index record is re-read as a new comment with
the exact body posted — then proven present in the replayed decision index. A
write the adapter cannot verify raises rather than reporting success.
