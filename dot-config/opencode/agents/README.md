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

┌──────────┐┌──────────┐┌──────────┐┌──────────────┐┌───────────┐┌──────────┐┌──────────┐┌──────────┐
│ CALLIOPE ││  FORGE   ││  GAMEDEV ││   KINDLE     ││   PRISM   ││   SAGE    ││  WORKDAY  ││COMMITSMSG│
│(content) ││(deepwork)││(Burnt Ice)││  (flow)     ││ (reflect) ││(research) ││  (work)   ││  (git)   │
└──────────┘└──────────┘└──────────┘└──────────────┘└──────────┘└──────────┘└──────────┘└──────────┘
```

## Quick Reference

| I want to... | Use |
|--------------|-----|
| Create/modify an agent | `@demiurge` |
| Write a blog post/newsletter | `@calliope` |
| Plan deep work sessions | `@forge` |
| Get unstuck / find flow | `@kindle` |
| Start/end work day | `@workday` (`start my day` / `EOD`) |
| Check PRs / sprint status | `@workday` (`check my PRs` / `sprint status`) |
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
| `workday-*` | Specific workday workflows (morning, eod, prs, reviews, sprint, pr-review) |
| `gamedev` | Burnt Ice project context |
| `worktrunk` | Worktree management, plus the canonical trunk resolution every agent uses for trunk-scoped state paths |
