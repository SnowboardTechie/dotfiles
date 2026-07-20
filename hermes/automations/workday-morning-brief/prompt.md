Prepare Bryan's concise weekday SGG work brief, maintain today's noncanonical SGG workday note, synchronize that one note safely, and deliver the briefing in the SGG Matrix room.

The injected collector output contains bounded, read-only data only from the `Bryan @ Agile6` Apple Calendar, the work Gmail account synchronized into Apple Mail, SGG GitHub repositories, and the SGG Markdown vault. Use generatedAt as the authoritative Pacific date and time.

Scope boundary:
1. This is a work-only SGG briefing. Personal projects, personal reminders, and personal calendar events belong in the Second Brain morning brief. Never read `/Users/bryan/second-brain`, other project vaults, Apple Reminders, personal calendars, or personal mail from this job.
2. Read `/Users/bryan/code/notes/sgg/AGENTS.md`, `/Users/bryan/code/notes/sgg/INDEX.md`, and `/Users/bryan/code/notes/sgg/status.md` first. INDEX.md, status.md, and the relevant technical MOC are canonical. Dated plans, drafts, sessions, and workday notes are historical or noncanonical unless promoted by a canonical surface.
3. Read notes.sgg.workdayNotes.previousWorkdayPath when it exists. Its Day log and End-of-day handoff are noncanonical carry-forward evidence; canonical SGG state wins.
4. Except for the exact workday-note workflow below, never edit, create, commit, or push any note. Distinguish canonical state, historical evidence, proposals, and inference.

Priority and assignment grounding:
- A canonical file can contain several current threads, proposals, deadlines, and actions for different people. Canonical location establishes source authority, not that every item is Bryan's accepted priority.
- Prefer an explicit current resting point or next step over a proposed direction, onboarding idea, meeting topic, or later deadline. Live source state may refine whether that resting point is still actionable, but it does not create a new priority by itself.
- A proposal, deadline, meeting discussion, or action assigned to someone else is not Bryan's priority without an authoritative source explicitly promoting it and assigning it to Bryan.
- Preserve assignees exactly. Never turn an action owned by Kari, another teammate, or the team collectively into an individual Bryan task. A Bryan-plus-teammate coordination action remains coordination; do not expand it into solo drafting or implementation.
- Words such as `before Wednesday`, `first story`, `onboarding`, or `proposed` do not prove priority. Do not promote them merely because they sound urgent or specific.
- If no source explicitly establishes Bryan's primary outcome, say so rather than inventing one. Put the unresolved choice under **Unverified / needs judgment** and make the first action a bounded orientation step, not execution of an unaccepted proposal.

Mandatory workday-note workflow:
5. Derive DAY as YYYY-MM-DD from generatedAt. Before editing, run exactly:
   `python3 /Users/bryan/.hermes/scripts/sgg-sync-workday-note.py prepare DAY`
   If it fails, do not edit any note. Continue the briefing and report the failure clearly at the end.
6. Synthesize the briefing before writing the note. The generated block must contain concise versions of Starting point, Intended outcome, First action, Schedule constraints, and Active watch list.
7. The only writable path is notes.sgg.workdayNotes.todayPath, which must equal `/Users/bryan/code/notes/sgg/workdays/DAY.md`.
   - If absent, create it with frontmatter `tags: [workday, area/sgg]`, `date: DAY`, `status: open`, and `generated: generatedAt`; title it `# Workday — DAY`.
   - Put generated sections between exactly one `<!-- BEGIN GENERATED MORNING BRIEF -->` and `<!-- END GENERATED MORNING BRIEF -->` marker pair.
   - Outside that block, create `## Day log`, `## End-of-day handoff` with Outcome/Changed/Carry forward fields, and `## Canonical context` linking to [[status]], [[technical/custom-filters-spec-state]], and [[technical/sgg-custom-filters-example-plan]].
   - On rerun, replace only the marker-bounded text. Preserve frontmatter and every byte outside the markers. Missing or duplicated markers are a failure.
   - Link to canonical notes instead of copying detailed state. Never alter another note or another day's workday note.
8. After a successful write, run exactly:
   `python3 /Users/bryan/.hermes/scripts/sgg-sync-workday-note.py commit DAY`
   This helper is the only allowed Git synchronization path. Never run git add/commit/push directly, stage another file, force, reset, stash, or resolve divergence automatically.
9. End with `Workday note: synced.` only when the helper reports `synced: true`. Otherwise end with a concise `Workday note warning:`.

Live work sources:
10. Use collector GitHub data as live SGG state. If a relevant change is unclear, use read-only `gh` commands. Every GitHub artifact mentioned anywhere must have a verified direct clickable URL. Never comment, label, dispatch, merge, close, or mutate GitHub.
11. Calendar events are already restricted to `Bryan @ Agile6`. Convert times to America/Los_Angeles and identify conflicts and useful focus windows. Use organizer and current-user attendee metadata when deciding preparation ownership. Never infer that Bryan owns presentation or preparation from an event title. Ownership is verified only when organizer.isCurrentUser is true or another authoritative source explicitly assigns Bryan the work. Attendance does not establish ownership.
12. Use Apple Mail only for the work account. Prioritize direct requests, active-thread replies, meeting changes, and actionable automated notices. Ignore newsletters and routine notifications. Never mark messages read, move them, label them, draft, reply, or send. Never reproduce a full body.
13. If sourceErrors are present, name the unavailable source; never interpret an error or empty source as proof that nothing exists.

Output in plain Matrix-friendly Markdown:
- **Where work left off**: 2–5 grounded bullets, including the recorded resting point.
- **Today's work calendar**: timed work meetings, verified preparation needs, conflicts, and focus windows.
- **Work email requiring attention**: at most 3 actionable messages; omit if none.
- **GitHub watch list**: at most 3 items requiring attention.
- **Recommended primary work outcome**: exactly one meaningful result.
- **Suggested first action**: exactly one concrete next step.
- **Unverified / needs judgment**: only real assumptions or decisions; omit if empty.
- The required workday-note synchronization line.

Keep the brief readable in under two minutes, normally no more than 12 substantive bullets. Do not include personal content, meeting credentials, or private message bodies.