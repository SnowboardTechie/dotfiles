Prepare Bryan's concise weekday morning brief across his active work and project notes, maintain today's noncanonical SGG workday note, synchronize that one note safely, and deliver the briefing.

The pre-run collector output is injected as context. It contains bounded, read-only data from Apple Calendar, the work Gmail account as synced into Apple Mail, GitHub, and recent Git history from Bryan's Markdown/Obsidian vaults. Use generatedAt as the authoritative Pacific date and time for this run.

Notes scope and grounding:
1. NEVER query or use Apple Notes. "Notes" means the Markdown/Obsidian vaults below.
2. For SGG work, first read /Users/bryan/code/notes/sgg/AGENTS.md, /Users/bryan/code/notes/sgg/INDEX.md, and /Users/bryan/code/notes/sgg/status.md. INDEX.md, status.md, and the relevant technical MOC are canonical. Dated plans, drafts, sessions, and workday notes are historical/noncanonical unless promoted by a canonical surface.
3. Read notes.sgg.workdayNotes.previousWorkdayPath when it exists. Use its Day log and End-of-day handoff as noncanonical carry-forward evidence; canonical SGG state still wins.
4. For personal knowledge and projects, read /Users/bryan/second-brain/AGENTS.md before opening relevant notes. Use notes.secondBrain.previousWorkdayHistory and recentSevenDayPaths to identify recently active topics. Read only the few changed Markdown notes needed to recover current state.
5. For other code-adjacent projects, read /Users/bryan/code/notes/AGENTS.md first. Use notes.projectVaults.previousWorkdayHistory and activeVaultsFromLastSevenDays to identify recent projects. For an actionable project, read its INDEX.md and status.md when present. Seven-day activity is a candidate signal, not proof every project belongs in today's brief.
6. Except for the exact workday-note workflow below, never edit, create, commit, or push any note. Distinguish canonical state, historical evidence, proposals, and inference.

Mandatory workday-note workflow:
7. Derive DAY as YYYY-MM-DD from generatedAt. Before editing, run exactly:
   python3 /Users/bryan/.hermes/scripts/sgg-sync-workday-note.py prepare DAY
   If it fails, do not edit any note. Continue the briefing and report the workday-note failure clearly at the end.
8. Synthesize the briefing before writing the note. The generated workday block must contain concise versions of these same facts: Starting point, Intended outcome, First action, Schedule constraints, and Active watch list.
9. The only writable path is notes.sgg.workdayNotes.todayPath, which must equal /Users/bryan/code/notes/sgg/workdays/DAY.md.
   - If absent, create it with frontmatter `tags: [workday, area/sgg]`, `date: DAY`, `status: open`, and `generated: generatedAt`; title it `# Workday — DAY`.
   - Put generated sections between exactly one `<!-- BEGIN GENERATED MORNING BRIEF -->` and `<!-- END GENERATED MORNING BRIEF -->` marker pair.
   - Outside that block, create `## Day log`, `## End-of-day handoff` with Outcome/Changed/Carry forward fields, and `## Canonical context` linking to [[status]], [[technical/custom-filters-spec-state]], and [[technical/sgg-custom-filters-example-plan]].
   - If the note already exists, read it and replace only the text inside the existing generated marker pair. Preserve frontmatter and every byte outside the markers, including manual Day log and End-of-day content. If the markers are missing or duplicated, do not edit; report the failure.
   - Link to canonical notes instead of copying detailed project state. Never alter INDEX.md, status.md, technical notes, drafts, or another day's workday note.
10. After a successful write, run exactly:
    python3 /Users/bryan/.hermes/scripts/sgg-sync-workday-note.py commit DAY
    This helper is the only allowed Git synchronization path. Never run git add/commit/push directly, never stage another file, and never force, reset, stash, or resolve divergence automatically. On helper failure, leave files as-is and report that synchronization is unverified.
11. End the Matrix response with `Workday note: synced.` only when the helper reports `synced: true`. Otherwise end with a concise `Workday note warning:` describing the failure.

Other live sources:
12. Use collector GitHub data as live SGG state. If a relevant PR changed since the previous workday and the reason is unclear, use read-only `gh` commands. Every GitHub artifact mentioned anywhere in the brief or generated workday block—including pull requests, issues, commits, Actions runs/checks, discussions, releases, repositories, and project items—must include a direct clickable GitHub URL. Prefer Matrix-friendly Markdown links such as `[HHS/simpler-grants-protocol#123](https://github.com/HHS/simpler-grants-protocol/pull/123)` rather than bare numbers or unlinked titles. If the collector does not provide a URL, resolve it with a read-only `gh` command before mentioning the artifact; if a reliable URL cannot be resolved, omit the artifact rather than mention it unlinked. Never comment, label, dispatch, merge, close, or mutate GitHub.
13. Use Apple Calendar as the complete calendar source. Convert times to America/Los_Angeles. Separate all-day items from timed commitments. Mention personal events only as scheduling constraints when they affect the day; do not expose unnecessary private detail.
14. Use Apple Mail only for the work account. Prioritize direct requests, active-thread replies, meeting changes, and actionable automated notices. Ignore newsletters and routine notifications. Never mark messages read, move them, label them, draft, reply, or send. Never reproduce a full body.
15. If sourceErrors are present, name the unavailable source; never interpret an error or empty source as proof that nothing exists.

Output in plain Matrix-friendly Markdown with these sections:
- **Where work left off** — 2–5 bullets grounded in canonical SGG notes and verified live state, including the recorded next resting point. Include direct clickable URLs for every GitHub artifact mentioned.
- **Other recent projects** — at most 3 bullets from second-brain or other project vaults with a concrete open thread or next action. Omit if nothing merits attention. Include direct clickable URLs for every GitHub artifact mentioned.
- **Today's calendar** — timed meetings, relevant all-day constraints, preparation needs, conflicts, and useful focus windows.
- **Work email requiring attention** — at most 3 actionable messages; omit if none.
- **GitHub watch list** — at most 3 items requiring Bryan's attention; summarize routine remaining activity. Every item must be a direct clickable Markdown link to the relevant GitHub page.
- **Recommended primary work outcome** — exactly one meaningful result. Include direct clickable URLs for any GitHub artifacts mentioned.
- **Suggested first action** — exactly one concrete next step. Include direct clickable URLs for any GitHub artifacts mentioned.
- **Unverified / needs judgment** — only real assumptions or decisions; omit if empty.
- The required workday-note sync line.

Keep the brief readable in under two minutes, normally no more than about 15 substantive bullets. Do not create tasks, send communications, modify calendar or mail, or change repositories except through the exact workday-note helper. Do not include meeting credentials or private message content.
