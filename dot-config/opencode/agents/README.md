---
description: Documentation file - not an agent
disable: true
---

# OpenCode Agents

Personal AI agent system for thinking, workflow automation, and development assistance.

## Architecture

```
                                 ┌─────────────┐
                                 │    MUSE     │  ← Primary thinking partner
                                 └──────┬──────┘
   ┌──────────┬──────────┬──────────┬───┴───┬──────────┬──────────┐
   ▼          ▼          ▼          ▼       ▼          ▼          ▼
┌──────────┐┌──────────┐┌──────────┐┌──────────┐┌──────────┐┌──────────┐┌──────────┐
│ ARCHIVIST││   SAGE   ││  SCRIBE  ││   PYRE   ││ DEMIURGE ││ CALLIOPE ││  PRISM   │
│ (recall) ││(research)││ (write)  ││ (delete) ││ (forge)  ││(content) ││(reflect) │
└──────────┘└──────────┘└──────────┘└──────────┘└──────────┘└──────────┘└──────────┘

┌────────────┐ ┌────────────┐ ┌──────────┐ ┌──────────┐
│  WORKDAY   │ │  GAMEDEV   │ │  FORGE   │ │  KINDLE  │
│   (work)   │ │(Burnt Ice) │ │(deepwork)│ │ (flow)   │
└────────────┘ └────────────┘ └──────────┘ └──────────┘
```

## Quick Reference

| I want to... | Use |
|--------------|-----|
| Think through a problem | `@muse` |
| Find past notes | `@muse` → `@archivist` |
| Research something external | `@muse` → `@sage` |
| Capture an insight | `@muse` → `@scribe` (auto) |
| Delete old notes | `@muse` → `@pyre` |
| Create/modify an agent | `@muse` → `@demiurge` |
| Write a blog post/newsletter | `@muse` → `@calliope` |
| Reflect on a conversation | `@muse` → `@prism` |
| Plan deep work sessions | `@forge` |
| Get unstuck / find flow | `@kindle` |
| Start/end work day | `@workday` (`start my day` / `EOD`) |
| Check PRs / sprint status | `@workday` (`check my PRs` / `sprint status`) |
| Game dev session | `@gamedev` (`dev session`) |

## Agent Files

Each agent is defined in `~/.config/opencode/agents/{name}.md` with YAML frontmatter (model, tools, skills) and prose instructions. Model overrides go in `oh-my-openagent.json`.

## Skills

| Skill | Purpose |
|-------|---------|
| `agent-workspace` | Working directory conventions, worktree resolution, `.notes` setup |
| `athena-notes` | Note templates and patterns |
| `obsidian` | Vault paths, wikilinks, formatting |
| `workday-*` | Specific workday workflows (morning, eod, prs, reviews, sprint, pr-review) |
| `gamedev` | Burnt Ice project context |
