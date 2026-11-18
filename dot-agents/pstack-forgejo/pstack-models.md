# pstack model configuration

Per-role model overrides for pstack skills. Each pstack SKILL.md names its defaults in a Models section; the values here override those defaults. Delete a line to fall back to the skill default. A value of `inherit-parent` or `auto` runs that role on the parent session's model (the `Agent` call omits `model`); an alias entry in a panel list still counts toward that panel's fan-out. A model may carry a reasoning effort, as in `opus @xhigh` (levels: low, medium, high, xhigh, max); the role's subagent then runs at that level, each entry of a panel list on its own. `default effort` sets the level for a value without one; `session` uses the runtime's platform mapping to start from the parent session's effort. `session hook: off` stops the supported runtime's pstack routing hook from injecting the poteto-mode mandate; any other value, or no line, leaves it on.

This sheet runs on one machine. It is tracked in the dotfiles repository (`dot-agents/pstack-forgejo/pstack-models.md`) and linked into the pstack Pi agent directory by `scripts/reconcile-pi-pstack.sh`; edit it there, and see `models.md` beside it for what each line was proven with. Panels are two wide, never the ten live lanes upstream sizes for cloud machines: one Claude model and a second, different Claude model, not a model from another family. Only the scheduled ticket runner reads this sheet, and no scheduled job spends on OpenCode Go, whose subscription is kept for the bots Bryan talks to (decided 2026-11-17).

pi models: opus=claude-code/claude-opus-5-5, fable=claude-code/claude-fable-5-2, sonnet=claude-code/claude-sonnet-5-5, haiku=claude-code/claude-haiku-5-5

feature, refactoring: sonnet
bug-fix: opus
perf-issue: opus
hillclimb: opus
judgment and prose: opus
strongest judgment: fable
how explorer: opus
how explainer: opus
why investigators: opus
why synthesizer: opus
reflect tooling: opus
reflect judgment, divergent, synthesizer: opus
arena runners: opus, fable
arena cross-judge pool: fable, sonnet
swarm workers: opus
architect runners: opus, fable
interrogate reviewers: opus, fable
thermos reviewers: opus
no-comments reviewer: opus

default effort: session
session hook: off
