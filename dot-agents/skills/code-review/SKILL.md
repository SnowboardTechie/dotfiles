---
name: code-review
description: Review a diff against a fixed point along separate lanes — Standards (does it follow this repo's documented conventions?), Spec (does it do what the issue/plan asked?), and Risk when the change touches security, data, or unattended behavior. Use when asked to review a branch, PR, or "changes since X", or when `pr-self-review` needs the lane definitions.
---

# Code Review

Review the diff between `HEAD` and a fixed point along **separate lanes**, so
one lane cannot mask another. Code can follow every convention and implement the
wrong thing; it can implement exactly the right thing and break every
convention. Merging the reports would hide both.

This skill owns the **lane definitions**. `pr-self-review` owns the loop that
runs them, validates their findings, and applies corrections. Standalone review
of someone else's branch starts here.

Provenance: adapted from Matt Pocock's `code-review`. Upstream pin, accepted and
rejected upstream rules, and the watched source list live in
[`dot-agents/upstreams/mattpocock-skills.json`](../../upstreams/mattpocock-skills.json).

## 1. Pin the fixed point

Whatever the user named — a SHA, branch, tag, `main`, `HEAD~5`. If they named
nothing, ask.

```bash
git rev-parse <fixed-point>          # must resolve
git diff <fixed-point>...HEAD        # three-dot: compare against the merge-base
git log <fixed-point>..HEAD --oneline
```

Confirm the ref resolves and the diff is non-empty **before** dispatching any
reviewer. A bad ref should fail here, not inside three parallel children.

## 2. Select the lanes

Standards and Spec **always** run. Risk runs on trigger. The selection is
deterministic, not a judgment call:

Use these two commands **exactly** — same literal as `pr-self-review` and the
classifier's own `--help`:

```bash
git diff --name-status -z -M -C --find-copies-harder <fixed-point>...HEAD -- > name-status
git diff                 -M -C --find-copies-harder <fixed-point>...HEAD -- > unified.diff

python3 dot-agents/skills/pr-self-review/scripts/select_review_lanes.py \
  --repo <owner/repo> --name-status-from name-status --diff-from unified.diff
```

Feed it **both**. Name-status is the authority on *which paths moved* — a
content-identical rename's source, a copy from an untouched source, and a
binary deletion appear nowhere in a unified diff, and `-M -C
--find-copies-harder` is what makes Git report the first two as moves rather
than as unrelated adds. The diff supplies *content* signals, so a neutral
filename like `src/parser.py` calling `json.loads` still selects Risk. Omitting
either is recorded as a weakness in the output rather than passing silently, and
a malformed inventory is refused rather than partially parsed.

It reports the selected lanes and the reason for each. It can never suppress
Standards or Spec, unrecognized security-adjacent content fails closed to Risk,
and it always selects Risk for Bryan's CairnOS regardless of what the diff
touches. See `pr-self-review` for the full contract.

Without the classifier available, apply the same rule by hand and say you did.

## 3. Identify the sources each lane needs

**Standards sources**: whatever the repository documents about how code should
be written — `AGENTS.md`, `CONTRIBUTING.md`, `CODING_STANDARDS.md`, and the
conventions visible in neighboring code.

**Spec source**, in this order: issue references in the commit messages, a path
the user passed, the approved plan in the effort's state directory, a spec under
`docs/` or `specs/` matching the branch. If none exists, say so — the Spec lane
reports "no spec available" rather than inventing an intent to measure against.

**Risk sources**: the changed paths themselves, plus whatever the repository
documents about its security model, data handling, or deployment.

## 4. Run the lanes

Run them as **parallel children** so they cannot pollute each other's context —
Hermes `delegate_task`, or the host's `Task`/`Agent`. On Hermes, never exceed
three active children. Without delegation, run them serially with the same
briefs; do not merge them into one prompt.

Each child gets the diff command, the commit list, its own sources, and its own
brief. Each writes `review-{lane}.md`.

### Standards lane

> Report, per file or hunk: (a) every place the diff violates a **documented**
> standard — cite the file and the rule; and (b) any baseline smell you spot —
> name it and quote the hunk. A documented repository standard **overrides** the
> baseline: where the repo endorses something the baseline would flag, suppress
> it. Documented breaches can be hard violations; baseline smells are **always**
> judgment calls. Skip anything tooling already enforces. Under 400 words.

The baseline travels with the brief — the child has no other access to it:

- **Mysterious Name** — a name that doesn't reveal what it does or holds. →
  Rename; if no honest name comes, the design is murky.
- **Duplicated Code** — the same logic shape in more than one hunk or file. →
  Extract, call from both.
- **Feature Envy** — a method reaching into another object's data more than its
  own. → Move it onto the data it envies.
- **Data Clumps** — the same few fields travelling together. → Bundle into one
  type.
- **Primitive Obsession** — a string or primitive standing in for a domain
  concept. → Give the concept its own small type.
- **Repeated Switches** — the same cascade on the same type recurring. →
  Polymorphism, or one shared map.
- **Shotgun Surgery** — one logical change forcing scattered edits. → Gather
  what changes together.
- **Divergent Change** — one module edited for several unrelated reasons. →
  Split so each changes for one reason.
- **Speculative Generality** — abstraction or hooks for needs the spec does not
  have. → Delete; inline back until a real need shows.
- **Message Chains** — long `a.b().c().d()` the caller shouldn't depend on. →
  Hide the walk behind one method.
- **Middle Man** — a thing that mostly delegates onward. → Cut it, call the real
  target.
- **Refused Bequest** — a subclass ignoring most of what it inherits. → Drop the
  inheritance, use composition.

Also carry: excess test sensitivity (a test that breaks on refactor without a
behavior change), and interface shape that is wider than its implementation
earns. Both are judgment calls.

### Spec lane

> Report: (a) requirements the spec asked for that are **missing or partial**;
> (b) behavior in the diff that was **not asked for** (scope creep); (c)
> requirements that look implemented but where the implementation is **wrong**;
> (d) anything crossing an explicitly recorded **out-of-scope** boundary or
> reversing an accepted decision. Quote the spec line for each finding. Under
> 400 words.

The Spec lane reads the ticket; it does not read minds. An obligation nobody
implemented leaves **no diff line to object to**, which is why the caller runs
an independent acceptance-criteria sweep on top of this lane rather than
treating an empty Spec report as proof.

### Risk lane (conditional)

> Report concrete, exploitable or operationally dangerous behavior introduced or
> exposed by this diff, in these areas: authentication and authorization;
> secrets and credential handling; private or personal data; untrusted input and
> injection; network calls and redirects; filesystem paths and permissions;
> persistence and migrations; queues and retries; concurrency and locking;
> deployment, promotion, and rollback; package publication; agent permissions
> and unattended mutation; memory retention. For each, state the attacker or
> operator, the path they take, and the consequence. Do not report generic
> hardening advice with no path in this diff. Under 400 words.

## 5. Report

Present the reports under `## Standards`, `## Spec`, and `## Risk` headings,
verbatim or lightly cleaned. **Do not merge or rerank across lanes** — that is
the exact collapse the separation prevents.

End with one line per lane: how many findings, and the worst one *within that
lane*. Do not pick a single winner across lanes.

Reviewer output is **advice, not a verdict**. When a caller owns disposition
(`pr-self-review` does), it validates each finding independently before acting.
Several lanes agreeing raises the cost of being wrong, not the confidence that
you are right — they read the same files and can share a blind spot.

## Related

- `pr-self-review` — the loop: lane selection, validation, correction bound.
- `select_review_lanes.py` — the deterministic classifier.
- `tdd` / `diagnosing-bugs` — what a validated finding usually routes into.
- `codebase-architecture` — when a Standards finding is really a design finding.
