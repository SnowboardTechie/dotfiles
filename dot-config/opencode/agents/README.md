---
description: Documentation file - not an agent
disable: true
---

# OpenCode Agents

Personal AI agent system for thinking, workflow automation, and development assistance.

## Architecture

```
┌─────────────┐
│  DEMIURGE   │   ← Agent craftsman (create/modify agents)
└─────────────┘

┌──────────┐┌──────────┐┌──────────┐┌──────────────┐┌───────────┐┌──────────┐┌──────────┐
│ CALLIOPE ││  FORGE   ││  GAMEDEV ││   KINDLE     ││   PRISM   ││   SAGE    ││COMMIT-MSG│
│(content) ││(deepwork)││(Burnt Ice)││  (flow)     ││ (reflect) ││(research) ││  (git)   │
└──────────┘└──────────┘└──────────┘└──────────────┘└──────────┘└──────────┘└──────────┘
```

## Quick Reference

| I want to... | Use |
|--------------|-----|
| Create/modify an agent | `@demiurge` |
| Write a blog post/newsletter | `@calliope` |
| Plan deep work sessions | `@forge` |
| Get unstuck / find flow | `@kindle` |
| Game dev session | `@gamedev` (`dev session`) |
| Research something external | `@sage` |
| Reflect on a conversation | `@prism` |
| Generate commit messages | `@commit-msg` |

## Agent Files

Each agent is defined in `~/.config/opencode/agents/{name}.md` with YAML frontmatter (model, tools, skills) and prose instructions.

## Skills

| Skill | Purpose |
|-------|---------|
| `obsidian` | Vault paths, wikilinks, formatting |
| `gamedev` | Burnt Ice project context |
| `worktrunk` | Worktree management, plus the canonical trunk resolution every agent uses for trunk-scoped state paths |
