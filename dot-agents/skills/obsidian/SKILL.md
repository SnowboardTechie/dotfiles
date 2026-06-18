---
name: obsidian
description: Obsidian vault patterns - wikilinks, iCloud paths, cross-referencing, error handling
---

# Obsidian Skill

Shared patterns for working with Obsidian vaults.

## CRITICAL: When to Use This Skill

> **This skill is for DIRECT vault work only.**
> 
> If you're in a **project repo** (simpler-grants-protocol, burnt-ice, etc.), use `.notes/` instead.
> The `.notes/` symlink automatically maps to the correct vault.

### Decision Tree

```
Working directory is a code repo (has .git, package.json, etc.)?
  YES → Use `.notes/` - DO NOT use Obsidian paths
  NO  → Working dir is ~/notes/{vault}?
    YES → Use `./` (current directory)
    NO  → Something's wrong, ask user
```

**NEVER use iCloud paths when in a project context.**

---

## Vault Locations (Direct Access Only)

These paths are ONLY for when you're working directly in the vault, not from a project repo.

```
BASE_PATH="~/notes"
```
| Vault | Path | Purpose |
|-------|------|---------|
| Workday | `${BASE_PATH}/workday` | Work - Simpler Grants development |
| Second Brain | `${BASE_PATH}/second-brain` | Personal - vehicles, hobbies, learning |
| Burnt Ice | `${BASE_PATH}/burnt-ice` | Personal - Game development |

---

## Wikilink Syntax

**ALWAYS use Obsidian wikilinks for cross-referencing within a vault.**

### Link Patterns

| Pattern | Syntax | Example | Use Case |
|---------|--------|---------|----------|
| Basic | `[[Note]]` | `[[GDD]]` | Link to note by name |
| Display text | `[[Note\|text]]` | `[[GDD\|design doc]]` | Custom link text |
| Header | `[[Note#Header]]` | `[[mechanics#Combat]]` | Link to section |
| Header + display | `[[Note#Header\|text]]` | `[[mechanics#Combat\|combat system]]` | Section with custom text |
| Block | `[[Note#^block-id]]` | `[[GDD#^core-loop]]` | Link to specific block |
| Embed note | `![[Note]]` | `![[template]]` | Embed full note |
| Embed section | `![[Note#Header]]` | `![[GDD#Summary]]` | Embed specific section |
| Embed image | `![[image.png]]` | `![[diagram.png]]` | Embed image |
| Embed sized | `![[image.png\|300]]` | `![[hero.png\|400]]` | Image with width |

### Best Practices

1. **Prefer wikilinks over markdown links** - `[[Note]]` not `[Note](Note.md)`
2. **Use display text for clarity** - `[[architecture#Signals\|signal patterns]]` reads better
3. **Link to headers when specific** - `[[mechanics#Temperature]]` not just `[[mechanics]]`
4. **Backlink when capturing ideas** - Link new notes back to source docs

### Common Patterns in Output

```markdown
# Good examples
Per [[mechanics#Temperature System]], the range is...
See [[GDD#Core Loop]] for design rationale.
Related: [[roadmap]], [[architecture]]
- Bug affects [[mechanics#Flamethrower|flamethrower]] system

# Avoid
Per mechanics#Temperature System...  (no wikilink)
See [GDD](design/GDD.md)...           (markdown link)
```

---

## Daily Note Naming

```
# Format: DDMonYYYY.md
27Jan2026.md
03Feb2026.md
```

---

## Error Handling

### Vault Inaccessible
Vaults may be unavailable due to sync issues or path problems.

**When vault is inaccessible:**
1. Report the specific error to user
2. Check for path issues (emoji in folder names)
3. If still failing, output content to chat instead of file
4. Suggest user check syncthing/sync status
### Path with Emoji/Spaces

Always quote paths containing emoji or spaces:
```bash
# Good
cat ~/notes/workday/daily/06Mar2026.md
cat "~/notes/workday/Agent 🤖/PR Reviews/note.md"
```

---

## Cross-Vault Considerations

Bryan has multiple vaults. **Do not create links between vaults** - wikilinks only work within a single vault.

If referencing content from another vault:
- Quote the content inline
- Note the source vault for context
- Don't use `[[link]]` syntax for cross-vault references

---

## Frontmatter Pattern

```markdown
---
created: {date}
tags: [tag1, tag2]
related: [[Note1]], [[Note2]]
---

# Note Title

Content...
```
