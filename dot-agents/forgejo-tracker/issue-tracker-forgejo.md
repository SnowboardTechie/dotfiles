# Issue tracker: Forgejo

Issues and specs for this workspace live as issues in the private Forgejo repository `<owner>/<repo>` on
`<host>`. Use `tea` and `tea api` for general issue work, and the `forgejo-map` command for everything Wayfinder
does (see **Wayfinding operations**).

## Conventions

Pass the repository and login on every `tea` call, so the target never depends on the directory you run it from:
`--repo <owner>/<repo> --login <host>`. Written below as `$R`.

- **Create an issue**: `tea issues create $R --title "..." --description-file body.md`. Labels go on with
  `--labels "a,b"`. Write the body to a file for anything longer than a line.
- **Read an issue**: `tea issues <number> $R --comments --output json` (the body and every comment, in full, as
  `.body` and `.comments[].body`). For
  the comments alone use `tea api --login <host> '/repos/<owner>/<repo>/issues/<number>/comments'`; not
  `tea comments list`, which cuts each body short.
- **List issues**: `tea issues list $R --state open --fields index,title,labels,body --output json`, with
  `--labels "..."` and `--state open|closed|all` as needed. A `--labels` filter naming a label the repository
  doesn't have can match every issue rather than none, so check the name with `tea labels list $R` first.
- **Parent and child issues**: Forgejo has **no sub-issues** (`/issues/<n>/sub_issues` returns 404). Wayfinder
  tickets belong to their map through a metadata block in the ticket body that only `forgejo-map` reads. For
  other issues, put `Part of #<parent>` at the top of the child body.
- **Blocking**: Forgejo's **native issue dependencies**, shown in the tracker's own UI. Read the blockers with
  `tea api --login <host> '/repos/<owner>/<repo>/issues/<n>/dependencies'`. Count the open ones with
  `... | jq '[.[] | select(.state == "open")] | length'` (0 means startable). Add an edge between Wayfinder tickets
  with `forgejo-map ... wire-blocking` (below). For other issues, add it in the Forgejo UI or ask Bryan; no
  command for it has been tried here yet.
- **Comment on an issue**: `tea comment $R <number> "..."`, or `--description "..."` for a longer body.
- **Apply / remove labels**: `tea issues edit $R --add-labels "..." <number>` / `--remove-labels "..."`.
- **Close**: post the explanation first with `tea comment $R <number> "..."`, then `tea issues close $R <number>`.
- **Never edit an issue body after creation.** Forgejo has no compare-and-swap on an issue update, so an edit can
  silently overwrite one Bryan made. Anything new goes in a comment.

File issues only into `<owner>/<repo>`. Never file into `mattpocock/skills`, and never into a public repository.

## Pull requests as a triage surface

**PRs as a request surface: no.** _(Set to `yes` if this workspace treats external PRs as feature requests;
`/triage` reads this flag.)_

When set to `yes`: read with `tea pulls <number> $R --comments`; list with
`tea pulls list $R --state open --fields index,title,author,labels --output json`; label with
`tea pulls edit $R --add-labels "..." <number>`; close with `tea pulls close $R <number>`.

## When a skill says "publish to the issue tracker"

Create a Forgejo issue in `<owner>/<repo>`, as in **Create an issue** above. A Wayfinder map or ticket is created
with `forgejo-map` instead (see below).

## When a skill says "fetch the relevant ticket"

Read it as in **Read an issue** above. For a Wayfinder ticket, `forgejo-map ... list-tickets --map <map>` also gives
its type, blockers and claim.

## Wayfinding operations

Used by `/wayfinder`. The **map** is a single issue labelled `wayfinder:map`; its **tickets** are issues that name
the map in their metadata block. All of it goes through the `forgejo-map` command, never hand-written API calls: it
checks the repository is private, re-reads the map and ticket before every write, and reads every write back.

Every call names the tracker. Run it inside a checkout whose `origin` remote is on `<host>` (any checkout of the
workspace will do), and the command fills in `--origin` from it; elsewhere, add `--origin <git remote URL>`:

```sh
forgejo-map --tracker <owner>/<repo> <command> [arguments]
```

`forgejo-map <command> --help` lists each command's arguments. Its usage line names the script behind the command,
`forgejo_wayfinder.py`, and shows `--origin` as required; `forgejo-map` supplies that. Output is JSON.

**Writes preview first.** Without `--apply`, a write prints `DRY RUN` with the exact steps and changes nothing.
To perform it, run the same command again with `--apply` placed **before the command name**
(`forgejo-map --tracker <owner>/<repo> --apply claim ...`); `--apply` after it is refused. Where the preview prints
an id (`--creation` for a new map or ticket, `--operation` for a claim), the apply must carry that exact id. Repeat
every other argument unchanged too, `--at` included, so what is written is what was previewed.

**The repository must be private.** `forgejo-map` refuses a public repository outright;
`forgejo-map --tracker <owner>/<repo> check-private` confirms eligibility.

**Issue bodies are never edited after creation**, not the map's and not a ticket's. Where `/wayfinder` says to
change the map body (graduate fog out of **Not yet specified**, add a line to **Out of scope**, update a ticket),
post that as a comment on the map or the ticket instead, and leave the body for Bryan.

- **Map**: `forgejo-map --tracker <owner>/<repo> create-map --title "<name>" --managed-file map.md`, then the same
  with `--creation <id from the preview>` and `--apply`. `map.md` holds the **Destination**, **Notes**, **Not yet
  specified** and **Out of scope** sections; there is no **Decisions so far** section in the body (see Resolve).
  The command adds the `wayfinder:map` label.
- **Load the map**: `forgejo-map --tracker <owner>/<repo> read-map --map <map>`. `managed` is the body sections;
  `decisions` is **Decisions so far**, one entry per decided ticket, each with its `ticket` number and `gist`.
  Take the ticket names from `list-tickets` when writing them for Bryan.
- **Child ticket**: `forgejo-map --tracker <owner>/<repo> create-ticket --map <map> --title "<name>" --question-file q.md --type grilling|research|prototype|task`,
  then the same with `--creation <id>` and `--apply`. `q.md` holds the question text only; the command adds the
  `## Question` heading, the metadata block linking it to the map, and the `wayfinder:ticket` and
  `wayfinder:<type>` labels. The label is the type, as `/wayfinder` says.
- **List the map's tickets**: `forgejo-map --tracker <owner>/<repo> list-tickets --map <map>`: every ticket, open
  and closed, with `state`, `ticket_type`, `blocked_by` and `claim`. The map's open tickets are the entries with
  `state: open`, claimed and blocked ones included; the frontier is the subset `frontier` returns.
- **Blocking**: `forgejo-map --tracker <owner>/<repo> wire-blocking --map <map> --blocked <ticket> --blocked-by <ticket>`,
  then the same with `--apply`. One edge per call, after every ticket exists. It is Forgejo's native dependency.
- **Frontier query**: `forgejo-map --tracker <owner>/<repo> frontier --map <map>`: the open tickets with no open
  blocker and no claim. **It returns them in issue-number order.** That is the map order on this tracker, unless
  the map's **Notes** ask for a different order (for example "planning's tickets come first"): then the Notes win,
  and "the first frontier ticket in order" means the first in the Notes' order, by issue number within it. Tickets
  carry no field for such a grouping, so judge it from titles, questions and what each ticket blocks, and tell
  Bryan which ticket you took and why.
- **Claim**: on this tracker, "assign it to yourself" means **`claim`**. A claim is a comment the command posts on
  the ticket, carrying a session name and an operation id; it is **not** the Forgejo assignee, and an assignee
  alone doesn't take a ticket off the frontier. Bryan is every session's assignee, so the assignee can't tell two
  sessions apart.
  - `forgejo-map --tracker <owner>/<repo> claim --map <map> --ticket <ticket> --session <session> --at <now>`
    previews and prints a fresh operation id. Then run
    `forgejo-map --tracker <owner>/<repo> --apply claim --map <map> --ticket <ticket> --session <session> --at <now> --operation <id>`.
  - `<session>` is any name for this session that no other session uses: letters, digits, `.`, `_`, `/`, `-`,
    starting with a letter or digit, up to 128 characters. `pi/<ticket>-<short topic>` reads well on the tracker;
    `pi/<first 8 characters of the session id>` will also do. `<now>` is UTC, `date -u +%Y-%m-%dT%H:%M:%SZ`.
  - Read `won` in the result. `false` means another session holds the ticket: stand down and take the next one.
  - **Keep the session and the operation id.** `release` and `resolve` need both, and there's no other way to
    them except `claim-status`. `--assignee` is optional and only adds the Forgejo assignee for the UI; leave it
    off.
- **Who holds a ticket**: `forgejo-map --tracker <owner>/<repo> claim-status --map <map> --ticket <ticket>` gives
  the holder's session and operation, any queued claims, and the exact release command for each.
- **Release** (giving a ticket back unresolved):
  `forgejo-map --tracker <owner>/<repo> release --map <map> --ticket <ticket> --session <session> --operation <id> --at <now>`,
  then the same with `--apply`. Never release a claim this session didn't make: a holder that looks abandoned
  may be slow. A claim that looks stale (old, with no activity since) is reported to Bryan with its
  `claim-status`, and he decides.
- **Resolve**: `forgejo-map --tracker <owner>/<repo> resolve --map <map> --ticket <ticket> --session <session> --operation <id> --answer-file answer.md --index-line "<one-line gist>" --at <now>`,
  then the same with `--apply`. That one command does all of `/wayfinder`'s step 4: it posts `answer.md` as the
  resolution comment, appends the gist to the map's **Decisions so far** (as a comment on the map, never a body
  edit), and closes the ticket. Only the session and operation holding the claim can resolve. Check
  `resolved: true` in the result; otherwise run the printed `recovery` command, which repeats only what didn't
  land. The gist is one plain line: no heading, bullet, line break or HTML comment.
- **Ruling a ticket out of scope**: comment why with `tea comment $R <ticket> "..."`, close it with
  `tea issues close $R <ticket>`, and post the **Out of scope** line as a comment on the map.

The map and ticket body shapes, the claim and index records, and how claims are decided between racing sessions
are described in `dot-agents/skills/wayfinder/references/forgejo-tracker.md` in the `bryan/dotfiles` repository.

## Labels

The triage label this workspace maps `ready-for-agent` to (in `docs/agents/triage-labels.md`) is this workspace's
choice. Bryan's `loop-issue` builds, unattended, any issue carrying the literal label `ready-for-agent`; map the
role to that label only if that is wanted here. `wayfinder:` labels are the only labels a map or ticket carries.
