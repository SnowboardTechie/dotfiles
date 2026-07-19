# SGG PR/review event pilot

## Decision

Use a deterministic, deliver-only Hermes webhook for high-signal GitHub review
updates. Do not start an agent from an untrusted event payload.

## Scope

Repositories:

- `HHS/simpler-grants-protocol`
- `common-grants/py-cg-grants-gov`
- `common-grants/ts-cg-grants-gov`

Accepted events:

- a non-bot reviewer submits or dismisses a review on a PR authored by
  `SnowboardTechie`;
- a non-bot user creates a review-thread or PR-conversation comment on a PR
  authored by `SnowboardTechie`;
- a non-bot user requests `SnowboardTechie` as a reviewer.

Self-authored updates, bot events, unrelated repositories, edits, pushes, CI
chatter, labels, milestones, and issue-only comments are silent. Add event types
only after an accepted pilot report demonstrates a missing decision signal.

## Pipeline

```text
GitHub signed event
  -> Cloudflare ingress
  -> loopback-only Hermes webhook listener
  -> per-route HMAC and idempotency checks
  -> sgg-pr-review-event.py
  -> one read-only gh api PR readback
  -> fixed deliver-only Matrix template
  -> private SGG room
```

The route script outputs only bounded, sanitized fields. It replaces `@` and
angle brackets in untrusted titles/comments to avoid mentions and markup. It
returns no output for ignored events. A failed GitHub readback preserves the
event report but labels source health as unavailable.

## Delivery template

```text
**SGG PR update**
[{repo}#{number}: {title}]({url})
- Change: {change}
- Detail: {detail}
- Current state: {state}
- GitHub readback: {source_health}
```

## Authority

Allowed:

- receive GitHub events for the three named repositories;
- read current PR state with `gh api`;
- post the fixed report to the private SGG Matrix room.

Never comment, review, label, merge, close, dispatch workflows, modify GitHub
settings after activation, write repositories or vaults, or invoke an agent from
the event. Webhook installation and public ingress are separate item-approved
infrastructure changes. HMAC secrets remain local and must never enter Git.

## Activation gates

- [ ] Private encrypted SGG room exists and Bryan has joined.
- [ ] `sgg-pr-review-event.py` is installed as a regular file under
      `~/.hermes/scripts/`; the webhook sandbox must not resolve it outside that
      directory.
- [ ] Hermes webhook listener binds only to loopback.
- [ ] A persistent Cloudflare ingress route exposes only the webhook path.
- [ ] A strong per-route secret is installed in Hermes and each GitHub hook.
- [ ] The gateway is restarted through nix-darwin, its actual supervisor.
- [ ] A signed representative payload produces one Matrix event ID.
- [ ] Replaying the same delivery ID is suppressed.
- [ ] An irrelevant or self-authored payload produces no Matrix event.
- [ ] GitHub hook readback matches only the approved event types and URL.

Until every gate passes, status is implemented locally, not activated or live.
