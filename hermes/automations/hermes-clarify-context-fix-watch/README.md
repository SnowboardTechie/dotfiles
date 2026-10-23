# Hermes clarify-context fix watch

Bryan requested this watch on 2026-10-23.

Problem: with Claude 5.x, text meant for Bryan before a `clarify` question card is
often written into a thinking block, so the card arrives without context. Hermes
loses nothing; the API response has no text block. Upstream tracks it as
NousResearch/hermes-agent#133320, with a proposed fix in PR #134690 that steers the
model from the clarify tool description. Bryan's state.db showed the pattern on
all 13 Claude clarify calls checked on 2026-10-23.

Workarounds this watch exists to retire:

1. `dot-agents/skills/grilling/SKILL.md`: "Ask in the final message, not on a
   clarify card" (commits fbb406c and 53423f4).
2. The Hermes user-profile memory entry starting "Bryan sees only final messages
   and clarify cards ... put decision questions in the final message".

`Watch Hermes clarify-context fix` runs daily at 09:25 Pacific, model-free, and
alerts the private Second Brain Matrix room once per transition:

- upstream main's clarify description gains the steer, or the PR merges;
- the runtime checkout Bryan runs (`$HERMES_HOME/hermes-agent`) has it;
- the issue closes or the PR closes unmerged without the steer upstream (stalled).

The detector parses `CLARIFY_SCHEMA`'s description statically and looks for a
mention of reasoning or thinking. A refactor it can't recognize, or any retrieval
failure, is an alert, not a silent pending. No fetched code runs. State lives in
`$HERMES_HOME/state/hermes-clarify-context-fix-watch.json`.

After the runtime alert: restart the desktop app and gateway, test a visible
summary followed by a card several times, then revisit the workarounds with
Bryan. Retire this watcher afterwards: the manifest entries, prompt, README,
script, test and the installed copy under `~/.hermes/scripts`.

Source: `hermes/scripts/check-hermes-clarify-context-fix.py`.
Tests: `python3 hermes/test_hermes_clarify_context_fix_watch.py`.
