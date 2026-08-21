# When to mock

Rules behind step 4 of [`../SKILL.md`](../SKILL.md). Adapted from Matt Pocock's
`tdd/mocking.md`; see
[`dot-agents/upstreams/mattpocock-skills.json`](../../../upstreams/mattpocock-skills.json).

## Mock at real system boundaries only

Mock:

- external APIs you do not control (payment, email, third-party SDKs);
- time and randomness;
- the network;
- databases and the filesystem *sometimes* — prefer a real test database or a
  local substitute (PGlite, tmpdir, in-memory FS) when one exists, because a
  substitute exercises the real query or path semantics a mock invents.

Never mock:

- your own modules and classes;
- internal collaborators;
- anything you control and could just as easily call.

A mock of something you own asserts that your code calls your code. That is a
restatement of the implementation, not a test of behavior.

## Designing for honest mocking

**Accept dependencies, do not construct them.**

```typescript
// Testable
function processPayment(order, paymentClient) {
  return paymentClient.charge(order.total);
}

// Hard to test — the boundary is welded shut
function processPayment(order) {
  const client = new StripeClient(process.env.STRIPE_KEY);
  return client.charge(order.total);
}
```

**Prefer an SDK-shaped interface over one generic fetcher.**

```typescript
// GOOD — each operation is independently mockable
const api = {
  getUser: (id) => fetch(`/users/${id}`),
  getOrders: (userId) => fetch(`/users/${userId}/orders`),
  createOrder: (data) => fetch("/orders", { method: "POST", body: data }),
};

// BAD — the mock needs conditional logic to know which call it is answering
const api = {
  fetch: (endpoint, options) => fetch(endpoint, options),
};
```

With the SDK shape each mock returns one specific value, test setup carries no
branching, and the test reads as a list of the endpoints it actually exercises.

## One adapter is not a seam

If the only implementation behind an injected interface is the production one
plus its mock, that is the standard two — fine. If you are injecting a port that
will only ever have a single implementation and no test double, you have added
indirection, not testability. `codebase-architecture` has the vocabulary for
that call.
