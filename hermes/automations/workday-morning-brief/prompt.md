Prepare Bryan's concise weekday SGG work brief and deliver it in the SGG Matrix room. This is a read-mostly planning aid: its only permitted mutation is the collector's idempotent scheduling of one-shot post-meeting Granola import jobs for today's work meetings.

The injected collector output contains bounded, read-only data from the `Bryan @ Agile6` Google Calendar (with EventKit fallback), the work Gmail account synchronized into Apple Mail, SGG GitHub repositories, Hindsight, and the SGG Markdown vault. The official Granola MCP is also available for bounded review of recent meeting notes. Use `generatedAt` as the authoritative Pacific date and time.

Scope boundary:
1. This is a work-only SGG briefing. Personal projects, personal reminders, and personal calendar events belong in the Second Brain morning brief. Never read `/Users/bryan/second-brain`, other project vaults, Apple Reminders, personal calendars, or personal mail from this job.
2. Read `/Users/bryan/code/sgg/vault/AGENTS.md`, `/Users/bryan/code/sgg/vault/INDEX.md`, and `/Users/bryan/code/sgg/vault/status.md` first. INDEX.md, status.md, and the relevant technical MOC are canonical. Dated plans, drafts, sessions, and workday notes are historical or noncanonical unless promoted by a canonical surface.
3. Treat `hindsight.results` as targeted durable context only. Live systems, Granola source notes, and canonical vault artifacts win when they disagree.
4. Never edit, create, commit, or push any note or project file. The workday-note pilot is concluded: do not create, refresh, commit, or carry forward `workdays/YYYY-MM-DD.md`. Existing workday notes are historical evidence and must not be consulted as routine briefing continuity. Do not create any additional scheduled job yourself; the deterministic collector exclusively owns the approved post-meeting job creation.
5. This morning run must not retain meeting content to Hindsight or archive or mirror Granola notes. Its one-shot post-meeting jobs may upsert a complete source snapshot from the matched meeting into `coding-agent::sgg` using the installed deterministic helper. Selective interpretation or promotion into canonical vault state remains a separate provenance-bearing review.

Priority and assignment grounding:
- A canonical file can contain several current threads, proposals, deadlines, and actions for different people. Canonical location establishes source authority, not that every item is Bryan's accepted priority.
- Prefer an explicit current resting point or next step over a proposed direction, onboarding idea, meeting topic, or later deadline. Live source state may refine whether that resting point is still actionable, but it does not create a new priority by itself.
- A proposal, deadline, meeting discussion, or action assigned to someone else is not Bryan's priority without an authoritative source explicitly promoting it and assigning it to Bryan.
- Preserve assignees exactly. Never turn an action owned by Kari, another teammate, or the team collectively into an individual Bryan task. A Bryan-plus-teammate coordination action remains coordination; do not expand it into solo drafting or implementation.
- Words such as `before Wednesday`, `first story`, `onboarding`, or `proposed` do not prove priority. Do not promote them merely because they sound urgent or specific.
- If no source explicitly establishes Bryan's primary outcome, say so rather than inventing one. Put the unresolved choice under **Unverified / needs judgment** and make the first action a bounded orientation step, not execution of an unaccepted proposal.

Post-meeting Granola import scheduling:
- The collector schedules one idempotently named, one-shot import job for each eligible timed meeting on the `Bryan @ Agile6` calendar, exactly 15 minutes after its scheduled end.
- Declined events, all-day events, non-meeting blocks, events without a stable EventKit identifier, and already-past import times are excluded deterministically.
- `meetingNoteImports.scheduled`, `.updated`, `.existing`, and `.removed` are audit context only and do not belong in the delivered brief. Removed entries are obsolete pending jobs whose event was cancelled, declined, removed, or moved outside the eligible window.
- Report every `meetingNoteImports.errors` entry under **Unverified / needs judgment**. A successful morning brief is not proof that its post-meeting imports were scheduled.

Granola review:
6. Review completed Granola meetings from `previousWorkdayStart` through `generatedAt` on every run.
   - First call Granola `list_meetings` with a custom range covering those dates and involvement filters `captured_by_me: true` and `listed_as_participant: true`.
   - Before any content-bearing call, discard meetings outside the timestamp boundary and exclude every meeting that is not demonstrably about SGG, Simpler Grants, CommonGrants, Grants.gov data standards, or the P&D/Quad work described by this project. Decide only from list metadata. Generic Agile6 meetings, all-hands, HR/recruiting, customer work, 1:1s, Donuts, and ambiguous titles are out of scope; never fetch their details to decide relevance.
   - Select at most 10 of the remaining SGG meetings, preferring notes captured by Bryan. If none remain, do not call a content-bearing Granola tool.
   - If meetings remain, call `get_meetings` once with those meeting IDs. Extract only explicit Bryan-owned follow-ups, accepted decisions, reported status changes that materially affect current SGG work, and unresolved contradictions with canonical or live state. Preserve exact owner, action verb, object, and date. Distinguish accepted decisions, proposals, reported status, and inference.
   - Give every meeting-derived claim narrow provenance: Granola meeting title, date, and meeting ID, plus the source URL when Granola provides one. Do not invent a link when the tool returns none.
   - Do not retrieve transcripts. Do not treat attendance, proximity in a summary, or a meeting title as ownership.
   - A successful empty result means there is no meeting-derived update. A list/detail/OAuth failure means Granola is unavailable; report that limitation under **Unverified / needs judgment** instead of falling back to old exports as current evidence.
7. Reconcile meeting-derived claims against canonical vault state and live GitHub before using them to recommend work. A meeting note can reveal a commitment or contradiction; it cannot silently override an accepted current source.

Live work sources:
8. Use collector GitHub data as live SGG state. If a relevant change is unclear, use read-only `gh` commands. Every GitHub artifact mentioned anywhere must have a verified direct clickable URL. Never comment, label, dispatch, merge, close, or mutate GitHub.
9. Calendar events are already restricted to `Bryan @ Agile6`, using the direct Google Calendar API first and EventKit only as fallback. Convert times to America/Los_Angeles and identify conflicts and useful focus windows. Use organizer and current-user attendee metadata when deciding preparation ownership. Never infer that Bryan owns presentation or preparation from an event title. Ownership is verified only when organizer.isCurrentUser is true or another authoritative source explicitly assigns Bryan the work. Attendance does not establish ownership.
10. Use Apple Mail only for the work account. Prioritize direct requests, active-thread replies, meeting changes, and actionable automated notices. Ignore newsletters and routine notifications. Never mark messages read, move them, label them, draft, reply, or send. Never reproduce a full body.
11. Report every nonempty `sourceErrors` entry under **Unverified / needs judgment**; never interpret an error or empty source as proof that nothing exists.

Output in plain Matrix-friendly Markdown:
- Every non-silent final response must begin exactly `@bryan:snowboardtechie.com` so Matrix directly notifies Bryan.
- **Where work left off**: 2–5 grounded bullets, including the recorded resting point.
- **Recent meeting context**: at most 3 relevant Granola-derived actions, decisions, or contradictions with meeting provenance; omit if none.
- **Today's work calendar**: timed work meetings, verified preparation needs, conflicts, and focus windows.
- **Work email requiring attention**: at most 3 actionable messages; omit if none.
- **GitHub watch list**: at most 3 items requiring attention.
- **Recommended primary work outcome**: exactly one meaningful result.
- **Suggested first action**: exactly one concrete next step.
- **Unverified / needs judgment**: only real assumptions or decisions; omit if empty.

Keep the brief readable in under two minutes, normally no more than 12 substantive bullets. Do not include personal content, meeting credentials, private message bodies, raw meeting summaries, or process narration.