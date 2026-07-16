# Hermes porting checklist

Use this reference when the destination is Hermes Agent.

## Inventory targets

Inspect all of these before recommending a migration:

- `skills/*/SKILL.md` plus `references/`, `templates/`, `scripts/`, `examples/`
- Global and project `AGENTS.md`, `CLAUDE.md`, `.hermes.md`
- Claude/OpenCode custom agents
- Scheduled tasks and monitors
- Hooks and permission files
- Setup scripts that curate symlinks or skill arrays
- Existing Hermes skills, cron jobs, config, and profile-local precedence

## Structural probe

A shared pool can contain skills accepted by one runtime but rejected by Hermes. Validate every candidate before adding it to `skills.external_dirs` or a symlink set.

```python
from pathlib import Path
import re
import yaml

root = Path("/path/to/shared/skills")
errors = []

for path in sorted(root.glob("*/SKILL.md")):
    text = path.read_text()
    match = re.match(r"^---\n(.*?)\n---\n", text, re.S)
    if not match:
        errors.append((path.parent.name, "invalid frontmatter delimiters"))
        continue

    try:
        frontmatter = yaml.safe_load(match.group(1))
    except Exception as exc:
        errors.append((path.parent.name, f"invalid YAML: {exc}"))
        continue

    for key in ("name", "description"):
        if not frontmatter.get(key):
            errors.append((path.parent.name, f"missing {key}"))

    if len(str(frontmatter.get("description", ""))) > 1024:
        errors.append((path.parent.name, "description exceeds 1024 chars"))

print(errors or "valid")
```

Common failures found in shared pools:

- A prose-only “skill” with no YAML frontmatter.
- An unquoted one-line description containing `Key: value`, which YAML parses as an illegal nested mapping.
- References to absent source-framework plugins or skills.
- Local state paths such as `~/.claude/workflow-name/` embedded throughout the procedure.

## Source-to-Hermes mappings

| Source pattern | Hermes adaptation |
|---|---|
| Claude `AskUserQuestion` | `clarify` |
| Claude/OpenCode `Agent` or `Task` | `delegate_task`; respect configured concurrency |
| Four simultaneous reviewers with a three-child limit | Batch 3+1, or redesign into three non-overlapping lenses |
| Claude plan mode | `plan` skill and `.hermes/plans/` |
| Claude scheduled task | `cronjob` with a self-contained prompt and attached skills |
| Fixed-output monitor | `cronjob` with `script` and `no_agent=True` |
| Claude memory plugin | Hermes memory for stable facts; `session_search` for history |
| Context-management plugin | Native compression and session facilities |
| Permission allow/deny list | Hermes approvals/security config plus explicit workflow gates |
| Custom reviewer agent | Delegated prompt or reference inside the owning review skill |
| Custom intake agent | Delegated intake phase inside the owning issue workflow |
| Shared skill symlinks | Curated symlink list or `skills.external_dirs` |
| Repeated skill combination | Hermes skill bundle |

## Hermes external-directory behavior

Hermes can scan shared pools configured under `skills.external_dirs`.

Important properties:

- Local Hermes skills win name collisions.
- External skills are fully indexed and invokable.
- Missing external paths are skipped.
- External directories are not read-only boundaries. If writable, skill-management actions may modify them in place.

Therefore, expose a whole shared pool only when every skill is valid and desirable. For a mixed personal pool, prefer a curated Hermes list or a curated external directory of symlinks.

## Safety review for automation

For every scheduled or autonomous workflow, inspect all success and failure branches for:

- Posting comments or reviews
- Creating or editing issues/PRs
- Applying labels
- Sending messages or email
- Pushing branches
- Merging or deleting branches

If the user's policy requires approval and no user is present, the unattended behavior should produce a report or draft rather than mutate the remote system. Do not preserve an old automation's side effects merely because it used to run elsewhere.

## Staleness review

Check live sources before retaining a monitor or project automation:

- Does the watched issue remain open?
- Has the awaited stable release shipped?
- Does the target remote branch still exist?
- Are project mappings and responsible teammates current?
- Does the scheduled prompt reference an agent identity that no longer exists?

A fired monitor is an action item plus a retirement candidate, not a timeless reusable skill.

## Recommended disposition vocabulary

Use exactly one primary disposition per artifact:

- **Adapt first**: personalized procedure with durable value.
- **Project-local/on-demand**: useful but domain-bound.
- **Merge/mine for parts**: overlap where selected rules belong in an umbrella.
- **Retire/skip**: stale, malformed, redundant, or conflicting.

Report metadata failures and live stale-state findings outside the conceptual classification so the user can distinguish “good workflow, bad port” from “workflow no longer needed.”
