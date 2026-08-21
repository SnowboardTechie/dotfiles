# Workspace contract

What a guided-learning workspace is, and what may exist inside it. Enforced by
step 0 of [`../SKILL.md`](../SKILL.md).

## Resolution

The workspace is an **absolute path inside a vault**, named by Bryan or carried
forward from a prior session. Three refusals, in order:

| Condition | Response |
|---|---|
| No absolute path supplied | Ask for one. Never infer from the current working directory. |
| Path resolves inside the installed skill directory or `dot-agents/skills/` | Refuse. Explain that skill directories are shared version-controlled procedure, not personal state. |
| Path is outside a vault Bryan named, or on a cloud-sync path | Refuse and ask where it belongs. |

The pilot workspace is `~/second-brain/Learning/Agent-Assisted Planning/`.

## Layout

```
<workspace>/
├── INDEX.md            # mission, observable success, constraints, out of scope,
│                       # current orientation, links
├── RESOURCES.md        # curated high-trust sources and what each is good for
└── learning-records/   # created lazily, on the first approved record only
    └── 0001-<slug>.md
```

That is the whole layout. `INDEX.md` and `RESOURCES.md` exist from the start
because a mission with no stated success criteria cannot be assessed against,
and ungrounded teaching is the failure mode this skill most needs to avoid.

## Created lazily, never scaffolded

`learning-records/` comes into existence when the first record is approved — not
before. An empty directory of records reads as "nothing learned yet" when the
truth is "no session has happened yet", and the two are different facts.

## Never created

None of these is adopted from the upstream `teach` workspace:

- `lessons/` and any HTML lesson output
- `assets/`, shared stylesheets, quiz widgets, simulators, diagram helpers
- `reference/*.html` cheat sheets
- `NOTES.md` as a separate scratchpad — preferences belong in `INDEX.md` under
  constraints, where they are read every session
- any spaced-repetition schedule, cron, or reminder

Each was rejected for the same reason: it is machinery that must be maintained
before it has been shown to help. If real use earns one, it gets added
deliberately, with Bryan's approval, at that point.

## Vault rules win

The vault's own `AGENTS.md` governs frontmatter, filenames, linking, and commit
discipline inside the workspace. Read it first every session; where it
disagrees with anything here, it wins.

For `~/second-brain/`, that means hierarchical `tags:` as a YAML list, a
`created:` date, a `status:`, `[[wikilinks]]` over Markdown links, and
`second-brain(<Type>): <topic>` commit subjects.

## The zone stays in the vault

The workspace is Bryan's exact, curated knowledge. It is never bulk-copied into
Hindsight, never summarized into an agent memory as a substitute for the
records, and never published anywhere. Hindsight may hold a *reference* to the
zone; it never holds the zone.
