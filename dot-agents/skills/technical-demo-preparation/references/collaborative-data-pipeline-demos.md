# Collaborative data-pipeline demo lessons

Use these checks when a short technical demo crosses collaborators, machines, real-world data, and adoption claims.

## Verify the actual presentation machine

A successful run on the agent's current host does not prove readiness on a different presentation laptop.

- Identify the host used for rehearsal and the host used for presentation.
- On the presentation host, verify the exact commit, remote URLs, branch tracking, dependencies, fixture/cache paths, and normal interactive-shell command resolution.
- A local `main` can match an upstream merge while still tracking a stale fork. The healthy end state is the project's intended canonical `origin` and local `main` tracking canonical `origin/main`.
- Follow the repository's transport convention. Do not silently switch SSH remotes to HTTPS to bypass broken authentication; repair SSH or surface the choice.
- Keep remote repair and diagnostic Git output out of the live screen-share path.

## Credit collaborators from evidence

Inspect commit authorship, dates, linked issues, and comments before writing the opening.

- Distinguish the person who created the spike or initial prototype from the person who made it reproducible, validated, documented, or ready for adoption.
- Prefer a chronological attribution: “X proved the initial join; I built on it to make the pipeline reproducible and contract-validated.”
- Avoid “I finished” when the visible artifact began as meaningful work from a teammate.

## Explain value and future alignment

A useful short demo says more than “the command works.” Name:

1. the real user or data gap;
2. what the implementation proves against real inputs;
3. what risk it removes before stabilizing a contract;
4. how it supports adoption through SDKs, examples, or integrations.

Verify live roadmap or deliverable sources. Say **draft**, **proposed**, or **planned** when the next phase is not yet committed.

## Preview mechanism without turning into a code tour

For a three-minute demo, explain the key mechanism in one sentence. Keep the relevant implementation files open as Q&A tabs, but do not switch to the editor unless asked. Showing code is worthwhile only when one compact block carries a claim the output cannot.

## Select a real-world example deliberately

Before featuring a named organization, award, product, or incident:

- search current public context for litigation, political controversy, safety incidents, or other baggage that could hijack the discussion;
- prefer a neutral, tangible example unless controversy is the point;
- use a deterministic selector such as a stable source ID or URL, not array position;
- project enough context to understand the record, including relevant owner or awarding agency, recipient, amount, status, join target, and source.

Do not claim an example has no controversy. Say current searches did not surface controversy tied to the specific example.

## Separate command readability from output readability

When the user asks to “format the jq,” determine whether they mean the command, the output, or both.

For a readable command that preserves normal JSON output, use a multiline jq program:

```bash
jq '
  map(select(.source | endswith("STABLE_ID")))[0]
  | {
      title,
      relatedObject: .related.title,
      owner: .owner.name,
      recipient: .recipient.name,
      amount: .funding.amount,
      status: .status.value,
      source
    }
' out/results.json
```

For optional browsing of all projected records with color:

```bash
jq -C '
  map({
    title,
    relatedObject: .related.title,
    owner: .owner.name,
    recipient: .recipient.name,
    amount: .funding.amount,
    status: .status.value,
    source
  })
' out/results.json | less -R
```

`jq -C` forces ANSI color through a pipe; `less -R` preserves it. Keep all-results browsing outside the timed path.

## Keep refresh mechanics optional

When the default demo uses committed snapshots or caches, do not refresh live unless freshness is the claim. Explain the maintenance model instead: live access rewrites tracked inputs as a reviewable diff, while the default consumer path remains offline and reproducible.

## Prepare semantic Q&A

If the output contains derived values, document their exact rule and limitations. For example, a lifecycle status may be computed from a period-of-performance end date rather than copied from the source system. State the reference date, behavior for missing data, and statuses the source cannot distinguish.
