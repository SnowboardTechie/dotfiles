---
tags: [session, demo]
created: YYYY-MM-DD
updated: YYYY-MM-DD
date: YYYY-MM-DD
status: active
source-checked: YYYY-MM-DD
---

# [Meeting] demo runbook: [Result] (YYYY-MM-DD)

[One sentence describing the audience, time limit, live format, and exact artifact being demonstrated.]

## Verified state

- Source artifact: [PR, issue, release, deployment, or commit URL]
- Exact candidate: `[commit, version, or deployment identity]`
- Local/demo environment: `[path or URL]`
- `[install command]` completed
- `[test/typecheck/build command]` passes
- Exact live sequence rehearsed on YYYY-MM-DD
- Live command duration: [N seconds]
- Output result: [count and validation/error result]

## Story in one sentence

[Starting input or problem] now [observable behavior], producing [verified outcome] for [consumer or stakeholder].

## Live demo

### 1. Set up before screen sharing

```bash
cd [demo path]
[one lightweight readiness check]
```

[Screen hygiene note: terminal size, editor position, windows to avoid, secrets posture.]

### 2. Opening, [N] seconds

> [What question the work answered.]
>
> [Why the live path is credible and what the audience is about to see.]

### 3. Run the scenario, [N] seconds

```bash
[one build, request, or scenario command]
```

> [Narrate two or three decisive output facts. Explain any count expansion or contraction.]

### 4. Inspect one result, [N] seconds

```bash
[stable selector plus compact field projection]
```

> [Explain the result in audience language and name the most tangible value.]

### 5. Close, [N] seconds

> [State what the result proves, current merge/release status, and what it enables.]

Prepared spoken word count: [N]
Estimated delivery time: [N seconds at N words per minute]
Total target including commands: [N]
Reserved buffer: [N]

## Canned fallback

If the live path fails, show this section and use the same narration.

### Successful command output

```text
[Condensed output captured during rehearsal]
```

### Representative result

```json
[Exact compact result captured during rehearsal]
```

## Likely questions

**[Question about contract or join key]?**

[Short grounded answer.]

**[Question about counts or partial coverage]?**

[Explain the funnel honestly.]

**Is this live data?**

[State snapshot/live/cache provenance and refresh date.]

**What makes it reproducible?**

[Name fixtures, pinned inputs, schemas, reference comparison, and credential posture.]

**What does this prove?**

[Bounded claim. Distinguish reference implementation from production readiness.]

## Pre-meeting checklist

- [ ] Exact source candidate reverified
- [ ] Dependencies ready
- [ ] Correctness gates pass
- [ ] Exact live sequence rerun
- [ ] Canned output still matches
- [ ] Talk track remains under target
- [ ] Terminal enlarged and positioned
- [ ] Runbook open beside terminal
- [ ] No secrets or unrelated windows visible
