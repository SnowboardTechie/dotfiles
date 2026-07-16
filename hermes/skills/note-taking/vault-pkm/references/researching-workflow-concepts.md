# Researching workflow concepts across a vault and the web

Use this when the user asks to learn an emerging workflow concept and wants the answer grounded in their existing projects.

## Method

1. **Search the vault for the concept and its components.** New labels often postdate the user's actual practice. Search not only the fashionable term but durable primitives: feedback, iteration, evaluator, verification, retry, acceptance criteria, stop conditions, handoffs, state, playtest, review, and reconciliation.
2. **Read current orientation surfaces first.** Sample indexes/MOCs plus a few representative decisions, learnings, or workflows. Preserve archive/dormant/current classifications.
3. **Prefer primary external sources.** Use first-party engineering reports, research posts, documentation, or original technique authors. Treat vendor production anecdotes as evidence from one environment, not universal proof.
4. **Separate the label from the mechanism.** Define the concept in ordinary terms, then identify its stable parts. For AI loop engineering, the stable core is: goal/state → action → environmental observation → evaluation → revision → stop/escalate.
5. **Map existing practices before recommending new machinery.** Show which current project workflows already instantiate the pattern. This teaches by recognition and prevents needless framework adoption.
6. **Evaluate the evaluator.** A repeated model call is not a reliable loop unless feedback can discriminate correct from plausible. Prefer executable tests, primary-source checks, UI behavior, logs/metrics, parity checks, and explicit human judgment for taste or consequential decisions.
7. **Tailor by project and risk.** Coding, knowledge compilation, creative playtesting, and infrastructure need different feedback and approval boundaries. Do not recommend unattended autonomy uniformly.
8. **Offer the smallest experiment.** Suggest one recurring task, explicit success evidence, an iteration/resource limit, escalation conditions, and an end-of-run question about what reusable capability was missing.

## Durable loop-engineering lessons

- Prompt quality matters less once the bottleneck is missing tools, state, observability, or enforceable constraints.
- Externalize progress in artifacts that a fresh session can reconstruct: plans, feature lists, status files, Git history, and reproducible startup/test commands.
- Work one independently verifiable increment at a time and leave a clean resting point.
- Use mechanical enforcement for invariants and model/human judgment for ambiguous trade-offs.
- State mandatory gates explicitly in natural-language handoffs; agents should not be expected to invent approval boundaries.
- Define success, maximum attempts, resource budget, escalation trigger, safety boundary, and cleanup requirements.
- Maintain a separate garbage-collection loop for drift; do not turn every delivery task into unbounded cleanup.
- Convert repeated failures into better repository legibility, tests, tools, or documentation instead of merely lengthening prompts.

## Useful primary sources

- OpenAI, *Harness engineering: leveraging Codex in an agent-first world*: environment design, agent legibility, feedback loops, enforceable architecture, observability, and entropy management — https://openai.com/index/harness-engineering/
- Anthropic, *Building Effective AI Agents*: workflows versus agents, evaluator-optimizer, environmental ground truth, simplicity, and stopping conditions — https://www.anthropic.com/research/building-effective-agents
- Anthropic, *Effective harnesses for long-running agents*: persistent progress, feature lists, incremental work, clean state, and end-to-end verification — https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents

Recheck source dates and current guidance before presenting these as the latest state.