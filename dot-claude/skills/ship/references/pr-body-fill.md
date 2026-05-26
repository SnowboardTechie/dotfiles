# Filling a PR Body from a Template

Shared fill discipline used by **both** `ship` (Step 6, at PR creation) and `update-pr-description` (Step 4, on an existing PR). Each calling skill handles its own **template detection** and supplies its own **source material** (see their call sites); this doc owns the **strip + fill** mechanics so the two can't drift apart.

## Inputs (the calling skill provides these)

- **Template text** — from wherever the caller found it: a repo `*template*.md` file for `ship` (the PR doesn't exist yet), or the live PR body for `update-pr-description`. May be absent if the repo has no template.
- **Source material** — the authoritative content to fill from: a handed-in review/summary artifact if there is one (e.g. `issue-work`'s `summary.md`), otherwise the commit history + diff.

## Fill discipline (template present)

1. **Sections as structure.** Use the template's headings, in its order, as the body's structure.
2. **Follow the template's own instructions.** If it tells you to delete a placeholder, check a box, or fill a field a certain way, do that.
3. **Strip all instruction/placeholder text** before posting:
   - `> ` blockquote instructions
   - `<!-- ... -->` HTML comments
   - italic / parenthetical placeholders like `_(describe your change)_`
   Remove every style — don't assume only one is present.
4. **Fill every section** from the source material. **Never leave a section empty** — write `N/A` (or a one-line reason) if it genuinely doesn't apply.
5. **Checkboxes.** Check `[x]` the ones that apply; for the rest, leave unchecked or annotate `_N/A — reason_` per the template's intent.
6. **Link issues.** If the branch name, commits, or original body reference issue numbers, link them in the appropriate section (e.g. `Closes #N`).
7. **Be specific and factual.** Drive every claim from the source material, never from boilerplate.

## No template

The caller owns the no-template fallback (e.g. `ship` writes a Summary / Key files / Testing / Commits structure). This doc governs only the template-present path.
