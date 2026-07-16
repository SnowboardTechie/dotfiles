# Hermes Desktop terminal-font case study

Captured from an upstream-feasibility investigation on 2026-07-16. Re-check current source, issues, and PR status before acting.

## Symptom and root cause

Powerlevel10k was configured for `nerdfont-complete`, and the user’s normal terminal selected `MesloLGS Nerd Font`. Hermes Desktop’s embedded xterm instead used a fixed stack beginning with bundled JetBrains Mono and exposed no terminal-font preference. Nerd Font private-use glyphs therefore did not render reliably.

Relevant source locations at the time:

- `apps/desktop/src/app/right-sidebar/terminal/use-terminal-session.ts`
- `apps/desktop/src/app/right-sidebar/terminal/use-agent-terminal.ts`
- `apps/desktop/src/app/settings/appearance-settings.tsx`
- `apps/desktop/src/themes/context.tsx`
- `apps/desktop/AGENTS.md`
- `apps/desktop/DESIGN.md`

The agent execution tool reported a non-interactive terminal environment, but that was transport state and not evidence about the embedded xterm PTY.

## Existing upstream work

- Issue `#37566`: Desktop font selector.
- Issue `#64790`: Appearance font selector, including terminal-font reports.
- PR `#44564`: broader interface font picker; adjacent but not necessarily terminal-safe.
- PR `#49592`: configurable terminal font family; open and conflicting at inspection time.
- Merged PR `#44642`: bundled JetBrains Mono and preloaded regular/bold/italic faces to prevent xterm cell-metric and glyph-atlas problems.

The existing terminal-font PR used backend `config.yaml` state and threaded a prop through React. That design deserved revision rather than immediate duplication.

## Architectural lesson

A font family names a resource installed on the computer rendering the Desktop UI. In remote mode the backend cannot know which fonts the client has. A terminal font therefore fits a device-local Desktop preference better than backend configuration.

A safe design should:

1. Preserve bundled JetBrains Mono as the default.
2. Store the override in a versioned Desktop preference with reset behavior.
3. Apply it to both user and agent terminal hooks.
4. On live change, load the requested face, update xterm options, refit cell geometry, invalidate the renderer glyph atlas if needed, and refresh without restarting the PTY.
5. Add preference, settings UI, terminal-application, and localization tests.

Do not automatically reuse theme `fontMono`: the terminal’s fixed bundled face was introduced specifically to preserve consistent xterm metrics.

## Alternative considered

Bundling Nerd Fonts Symbols Only would fix a subset of icon cases without a setting, but adds a comparatively large binary asset and requires license, attribution, package-size, glyph-width, and provenance review. A user-selected installed monospaced Nerd Font is the cleaner first contribution.

## Collaboration recommendation

Prefer helping the active terminal-font PR author rebase and move persistence client-side. If they agree, contribute to their branch. If the work is abandoned, a superseding PR should preserve credit, cite the prior PR, and explain the ownership change. Obtain user approval before posting comments or publishing branches.
