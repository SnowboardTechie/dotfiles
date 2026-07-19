# Orchestrator Contract: <name>

| Field | Value |
|---|---|
| Lifecycle | pilot / active / paused / retired |
| Autonomy level | 0 observe / 1 recommend / 2 prepare / 3 bounded internal work / 4 bounded publication / 5 bounded continuation |
| Owner | <human or team> |
| Primary surface | Hermes Desktop Project / Matrix room / other |
| Optional surfaces | <none or explicitly authorized alternatives> |
| Canonical workspace | <absolute repository or vault path> |
| Durable state | <issue tracker, vault note, database, or checkpoint path> |
| Operating procedure | <domain skill, repository instructions, or runbook> |

## Pasteable contract

```text
/goal <one durable objective>
outcome: <observable completion condition or one concrete blocker>
verification: <evidence the orchestrator must independently establish>
constraints: <required procedure, source, scope, turn, or retry limits>
boundaries: You may <explicit bounded actions and publication authority>.
boundaries: Never <explicit prohibited actions or authority expansion>.
stop when: <missing authority, incomplete state, source conflict, exhausted bound, human decision, or completion condition>
```

Keep this block compact enough to persist and re-enqueue unchanged. Add multiple
lines under a field when the contract needs several independent conditions.
Every supported surface must substitute its own real identity and workspace
proof before kickoff; do not leave authorization placeholders in an active goal.

## Trigger and lifecycle

- **Natural trigger:** <user action, schedule, webhook event, or bounded poll>
- **Why this trigger fits:** <clock, state transition, or explicit user intent>
- **Lifecycle:** <pilot dates or activation/retirement rule>
- **No-change behavior:** <silent, checkpoint only, or concise report>
- **Initiation does not grant:** <actions that remain separately gated>

## Canonical sources, state, and reconciliation

| State domain | Authority | Read/write mode | Reconciliation rule |
|---|---|---|---|
| <scope and requirements> | <specification or decision record> | read-only | <conflict behavior> |
| <work queue> | <issue tracker or task store> | <mode> | <active/blocked/completed mapping> |
| <implementation> | <repository and forge> | <mode> | <branch/PR/candidate identity> |
| <durable context> | <vault or database> | <mode> | <capture or synchronization gate> |

Before selecting or acting, reconcile every active object and stop on incomplete,
duplicate, conflicting, or ambiguous state. Chat history is secondary context,
not canonical workflow state.

## Orchestrator ownership

The orchestrator owns:

- objective and completion judgment;
- authoritative candidate identity and state reconciliation;
- decomposition and specialist dispatch;
- synthesis and disagreement resolution;
- permission and approval gates;
- parent-run verification;
- checkpoints, escalation, and continue-or-stop decisions.

Specialists cannot broaden scope, approve their own side effects, or declare the
overall workflow complete.

## Specialist lanes

| Lane | Bounded input | Required output | Mutation policy | Verification owner |
|---|---|---|---|---|
| <independent evidence/work lane> | <exact artifact or question> | <schema or report> | read-only / isolated writes | orchestrator / named reviewer |

Use deterministic collectors instead of agents when extraction needs no
judgment. Do not parallelize lanes that edit the same candidate or depend on one
another's unresolved output.

## Authority and approvals

| Action | Allowed? | Approval source | Required evidence |
|---|---|---|---|
| Read canonical sources | yes | standing contract | source identity and freshness |
| Modify local artifacts | <yes/no> | <specific plan or standing boundary> | scoped diff and local verification |
| Publish or message | <yes/no> | <specific standing or item approval> | destination and readback |
| Merge, delete, or mutate infrastructure | no unless explicitly granted | item-specific approval | independent verification and rollback plan |

Define authority per workflow and surface, not globally for Hermes. A successful
specialist result is evidence, not publication approval.

## Idempotency and concurrency

- **Idempotency identity:** <event ID, candidate SHA, issue ID, date, or state digest>
- **Duplicate behavior:** <reuse, suppress, or stop>
- **Concurrent-run rule:** <lock, one active item, or deterministic ownership>
- **Partial-action recovery:** <readback and reconcile before retry>

## Turn, checkpoint, and resume behavior

- **Turn boundary:** <smallest coherent iteration>
- **Checkpoint:** <state and evidence written before yielding>
- **Resume:** re-read canonical state and authorization before continuing.
- **Continue automatically only when:** <next iteration is independent and safe>
- **Pause when:** <merge, decision, unavailable source, or approval is required>
- **Budget:** <maximum turns, retries, corrections, or items per activation>

## Failure and escalation

Escalate once with current status, authoritative object links, exact evidence,
and the smallest decision needed. Do not repeatedly remind without materially
changed state. Fail closed rather than infer missing authority, fabricate source
results, or continue through a prohibited boundary.

## Activation and verification evidence

Track these statuses separately:

- **Designed:** contract and procedure exist.
- **Implemented:** deterministic checks and workflow behavior pass locally.
- **Installed:** the runtime has the reviewed assets.
- **Activated:** the serving process loaded them.
- **Verified live:** the requested surface completed a representative run with
  output, delivery, mutation, and failure behavior verified as applicable.

## Completion report

Report completed outcomes, blocked items with exact missing input, parent-run
checks, side effects and readback, pending approvals, durable capture, and an
explicit confirmation that prohibited actions did not occur.
