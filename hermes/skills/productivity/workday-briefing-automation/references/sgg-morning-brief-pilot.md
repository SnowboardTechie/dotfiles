# Workday Morning Brief — Bryan / SGG

## Purpose

Prepare Bryan for SGG work by reconstructing the previous business day's resting point, showing work constraints, and recommending one concrete work outcome. Personal projects, personal reminders, and personal calendar events are handled by the separate Second Brain morning brief. The SGG brief is read-only across work mail, the work calendar, GitHub, the `coding-agent::sgg` Hindsight bank, canonical SGG notes, and project repositories.

## Operational contract

- Schedule: 7:30 AM Pacific, Monday–Friday; Monday looks back to Friday.
- Hermes workdir: `/Users/bryan/code/sgg`.
- Delivery: private encrypted `SGG` Matrix room, continuable in Bryan's
  room-specific Hermes session. Mirror the labelled cron delivery into that
  session so replies retain the brief as context.
- Retain local cron output for audit/troubleshooting.
- Use an LLM-driven job with a deterministic bounded pre-run collector.
- The job may read Hindsight, notes, Calendar, Mail, and GitHub. It never writes notes or mutates any source.

## Notes scope and authority

“Notes” means filesystem Markdown/Obsidian vaults. **Never query Apple Notes.** Apple Calendar and Apple Mail remain valid, separate sources.

### SGG project vault

Root: `/Users/bryan/code/sgg/vault`

Read in this order:

1. `AGENTS.md`
2. `INDEX.md`
3. `status.md`
4. Topic-specific current surfaces named by the canonical files

`INDEX.md` and `status.md` are canonical. Dated plans, previews, session notes, `workdays/`, and `drafts/` are historical/noncanonical evidence unless explicitly promoted. Use vault-scoped Git history from the private SGG workspace repository from the start of the previous business day as recent-change evidence, not as proof that every changed note is a current priority.

Canonical placement does not make every recorded proposal or teammate action Bryan's priority. Prefer the explicit current resting point or accepted next step, preserve assignees exactly, and do not expand a coordination action into solo drafting or implementation. A deadline or detailed onboarding idea is not a priority signal by itself. If no authoritative source explicitly establishes Bryan's primary outcome, report that ambiguity instead of manufacturing one from the most recent or detailed thread.

#### Hindsight and the vault

The collector performs one bounded, read-only recall against
`coding-agent::sgg`, grounded with current open SGG pull requests and recent
vault commit subjects. Hindsight supplies durable decisions, commitments, and
conclusions; it does not establish volatile PR state or today's priority by
itself. Cross-check those claims against live systems and exact vault/Git
artifacts. Suppress generated-workday refreshes, routine sync/migration logs,
generic repository summaries, personal material, and completed initiatives
without new activity. A Hindsight-only item cannot enter the resting point,
recommended outcome, or first action without substantive previous-workday
corroboration or an explicit currently active marker in a canonical surface. A
A recall failure is a visible source error.

The vault remains Bryan's curated review interface and exact-artifact layer.
It is not the sole agent-memory system and must not be bulk-ingested into
Hindsight by this job.

#### Granola meeting review

The cron reviews completed SGG meeting notes from the previous-business-day
boundary through briefing time. It first lists meeting metadata, excludes every
meeting that is not demonstrably SGG/CommonGrants/P&D work, then fetches details
for at most ten in one bounded call. It never fetches an ambiguous meeting to
decide whether that meeting is relevant.

The cron-facing `granola` MCP alias exposes only `list_meetings` and
`get_meetings`; MCP resources and prompts are disabled. The separate
`granola_full` alias preserves all interactive Granola tools for user-directed
research. Declarative cron reconciliation fails closed unless both aliases,
their OAuth endpoint, and their exact tool filters match the manifest.

Meeting-derived claims preserve title, date, meeting ID, explicit owner, action
verb/object, and epistemic status. A source URL is included only when Granola
returns one. Meeting notes cannot silently override canonical vault or live
GitHub state. The cron never retrieves transcripts, archives notes, or retains
meeting content into Hindsight; every Granola source failure remains visible.

#### Concluded workday-note pilot

The scheduled `workdays/YYYY-MM-DD.md` experiment ended on 2026-08-21 after
running beyond its 2026-07-30 review date. The job no longer reads, creates,
refreshes, commits, or carries those notes forward. Existing workday notes are
historical evidence for explicitly dated investigations only.

The collector's vault Git window ends at the close of the previous business
day. Current-day briefing/configuration maintenance is not previous-workday SGG
delivery and must not appear as work left off.

## Calendar

Apple Calendar on Studio is canonical for synchronized work events. The SGG collector includes only `Bryan @ Agile6`; personal and shared calendars belong to the Second Brain morning brief.

- Collect read-only through EventKit; use AppleScript only as a fallback.
- Separate timed and all-day events; infer focus windows. Collect bounded organizer, current-user attendee, and attendee-count metadata. Assign preparation only when Bryan is the organizer or another authoritative source explicitly assigns it; never infer ownership from an event title or attendee status alone.
- Mention private events only as scheduling constraints when relevant.
- Do not collect calendar notes or meeting descriptions into the briefing payload because they can contain join credentials and passcodes.
- Treat collector failure as source unavailability, not an empty day.

## Work email

Use the work Gmail account as synchronized into Apple Mail. A second direct Gmail API collector is intentionally omitted: it duplicated the same mailbox while adding unnecessary OAuth/client setup.

- Collect bounded metadata from Apple Mail account `Google`, mailbox `INBOX`.
- Prioritize direct requests, active-thread replies, meeting changes, and useful alerts.
- Ignore newsletters and routine automation.
- Read bodies only if metadata is insufficient; never reproduce full private content.
- Never mark read, move, label, archive, draft, reply, or send.

If local Mail later proves incomplete or stale, establish the concrete reliability gap before proposing direct Gmail OAuth.

## GitHub

Use read-only `gh` access for:

- `HHS/simpler-grants-protocol`
- `HHS/simpler-grants-gov`
- `common-grants/py-cg-grants-gov`
- `common-grants/ts-cg-grants-gov`

Check authored PRs, assigned reviews, actionable comments/requested changes, meaningful state changes, and failed CI. Limit normal output to three items. Do not treat Renovate activity in `simpler-grants-gov` as Bryan-owned work. Never comment, label, merge, close, or dispatch workflows.

## Output contract

1. **Where work left off** — 1–4 grounded bullets covering work that actually changed or remained active since the previous workday.
2. **Recent meeting context** — at most 3 relevant Granola-derived actions, decisions, status changes, or contradictions with meeting provenance; omit when empty.
3. **Today's work calendar** — commitments, verified preparation, conflicts, and focus windows.
4. **Work email requiring attention** — at most 3 actionable messages; omit when empty.
5. **GitHub watch list** — at most 3 genuinely actionable or materially changed items.
6. **Recommended primary work outcome** — exactly one result.
7. **Suggested first action** — exactly one concrete next step.
8. **Unverified / needs judgment** — every source failure plus real disagreements or assumptions.

Aim for under two minutes and about ten or fewer substantive bullets. Distinguish verified live state, durable Hindsight context, canonical recorded state, historical evidence, proposals, and inference.

When no accepted primary outcome is recorded, do not promote a recently updated
PR into the first action. Use a neutral orientation/decision step. Likewise, do
not invent meeting preparation or suggest bringing a topic into a meeting unless
an authoritative source assigns it or places it on the agenda.

## Studio gateway ownership and delivery verification

Studio's Hermes launchd services are owned by `nix-configs`. The Darwin Nix CLI package intentionally excludes Matrix, while the declared gateway service runs the managed venv at:

`/Users/bryan/.hermes/hermes-agent/venv/bin/python`

Do not follow a generic `hermes gateway start` “stale service” suggestion without first inspecting the plist owner and runtime path; it can replace the nix-darwin definition with the Matrix-less Nix runtime. Restore/restart the service through the `nix-configs` source of truth (normally `darwin-rebuild switch --flake .#studio` from an external terminal) and verify the launchd program path points to the managed venv.

A cron run is not proven delivered merely because synthesis completed, a local output file exists, or `last_status=ok`. Verify all of:

1. Gateway reports the Matrix adapter connected with E2EE and joined rooms.
2. Cron delivery logs contain `Matrix: sent event <event-id>`.
3. Cron logs record delivery to the intended Matrix room.
4. `last_delivery_error` is empty.
5. Cron logs record a delivery mirror into the same room session, and SQLite
   contains the labelled cron context as a user-role turn.

When Hermes cannot restart its own gateway safely, put the exact external-terminal command in the same visible user question that asks for the result; do not ask whether they ran an instruction that may not have been shown.

## Operational verification and tuning

1. Test every collector read path independently.
2. Run one integrated brief manually.
3. Verify the actual Matrix event, privacy, source health, previous-business-day behavior, and output length.
4. Verify Hindsight recall uses `coding-agent::sgg`, never prints its API token,
   and fails visibly without blocking the other sources.
5. Remove noisy recall patterns before broadening the query or adding sources.
6. Keep CairnOS excluded until Bryan explicitly accepts it as a mature tracking
   source.
