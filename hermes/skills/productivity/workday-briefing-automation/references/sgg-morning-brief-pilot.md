# Workday Morning Brief — Bryan / SGG Pilot

## Purpose

Prepare Bryan for SGG work by reconstructing the previous business day's resting point, showing work constraints, and recommending one concrete work outcome. Personal projects, personal reminders, and personal calendar events are handled by the separate Second Brain morning brief. The SGG brief is read-only across work mail, the work calendar, GitHub, canonical SGG notes, and project repositories. An explicitly approved two-week pilot may additionally maintain one path-bounded, noncanonical SGG workday note.

## Operational contract

- Schedule: 7:30 AM Pacific, Monday–Friday; Monday looks back to Friday.
- Hermes workdir: `/Users/bryan/code/sgg`.
- Delivery: private encrypted `SGG` Matrix room, continuable in Bryan's
  room-specific Hermes session. Mirror the labelled cron delivery into that
  session so replies retain the brief as context.
- Retain local cron output for audit/troubleshooting.
- Use an LLM-driven job with a deterministic bounded pre-run collector.
- The job may read notes, Calendar, Mail, and GitHub. It may write only the exact dated SGG workday note under the approved pilot contract below; every other source and path remains read-only.

## Notes scope and authority

“Notes” means filesystem Markdown/Obsidian vaults. **Never query Apple Notes.** Apple Calendar and Apple Mail remain valid, separate sources.

### SGG project vault

Root: `/Users/bryan/code/notes/sgg`

Read in this order:

1. `AGENTS.md`
2. `INDEX.md`
3. `status.md`
4. Topic-specific current surfaces named by the canonical files

`INDEX.md` and `status.md` are canonical. Dated plans, previews, session notes, `workdays/`, and `drafts/` are historical/noncanonical evidence unless explicitly promoted. Use Git history from the start of the previous business day to recover the recorded stopping point.

#### Workday-note pilot

Through 2026-07-30, the job maintains `workdays/YYYY-MM-DD.md` as a lightweight operational handoff:

- Read the previous business day's note for Day log and End-of-day carry-forward, but let canonical notes override it.
- For a new note, include `tags: [workday, area/sgg]`, date, `status: open`, generation timestamp, and links to `[[status]]`, `[[technical/custom-filters-spec-state]]`, and `[[technical/sgg-custom-filters-example-plan]]`.
- Put only Starting point, Intended outcome, First action, Schedule constraints, and Active watch list between `<!-- BEGIN GENERATED MORNING BRIEF -->` and `<!-- END GENERATED MORNING BRIEF -->`.
- On rerun, replace only the marker-bounded block. Preserve frontmatter, Day log, End-of-day handoff, canonical links, and all manual content outside the markers.
- Synchronize through a deterministic prepare/commit helper. Fetch first, require `main` to fast-forward safely, reject unrelated tracked or staged changes, validate one marker pair, stage only the dated note, push, and verify `HEAD == origin/main`.
- Preserve unrelated untracked content. Never force, reset, stash, or silently repair divergence. A failure becomes a Matrix warning, not a claim of synchronization.
- End a successful brief with `Workday note: synced.` only after remote verification.

The implementation helper lives at `/Users/bryan/.hermes/scripts/sgg-sync-workday-note.py`; the collector exposes today's and the previous workday's note paths. The pilot intentionally does not add an automatic end-of-day job.

Session history can supply secondary context but never outranks current vault files or live systems.

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

1. **Where work left off** — 2–5 grounded bullets and the recorded next resting point.
2. **Today's work calendar** — commitments, verified preparation, conflicts, and focus windows.
3. **Work email requiring attention** — at most 3 actionable messages; omit when empty.
4. **GitHub watch list** — at most 3 items unless something is actively broken.
5. **Recommended primary work outcome** — exactly one result.
6. **Suggested first action** — exactly one concrete next step.
7. **Unverified / needs judgment** — only real source failures, disagreements, or assumptions.

Aim for under two minutes and about fifteen or fewer substantive bullets. Distinguish verified live state, canonical recorded state, historical evidence, proposals, and inference.

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

## Rollout and tuning

1. Test every collector read path independently.
2. Run one integrated brief manually.
3. Verify the actual Matrix event, privacy, source health, previous-business-day behavior, and output length.
4. Enable the weekday pilot.
5. Remove noisy inputs before adding new ones.
6. Review the workday-note pilot on or after 2026-07-30: did it improve restart/handoff continuity, were manual sections used, and was Git churn acceptable?
7. Add an end-of-day companion only if the pilot repeatedly cannot recover a useful stopping point and Bryan actually uses the manual handoff fields.
