# Good and bad tests

Worked examples for the rules in [`../SKILL.md`](../SKILL.md). Adapted from Matt
Pocock's `tdd/tests.md`; see
[`dot-agents/upstreams/mattpocock-skills.json`](../../../upstreams/mattpocock-skills.json).

The examples are TypeScript because the upstream ones were. The rules are
language-agnostic — the same three failure modes appear in `pytest`, `go test`,
and `cargo test`.

## Good: behavior through the public interface

```typescript
test("user can checkout with valid cart", async () => {
  const cart = createCart();
  cart.add(product);
  const result = await checkout(cart, paymentMethod);
  expect(result.status).toBe("confirmed");
});
```

- Tests what a caller cares about.
- Uses only the public surface.
- Survives internal refactors.
- Names WHAT, not HOW.
- One logical assertion.

## Bad: implementation-coupled

```typescript
// BAD — asserts on an internal collaborator's call
test("checkout calls paymentService.process", async () => {
  const mockPayment = jest.mock(paymentService);
  await checkout(cart, payment);
  expect(mockPayment.process).toHaveBeenCalledWith(cart.total);
});
```

Red flags: mocking internal collaborators, testing private methods, asserting on
call counts or ordering, a name that describes HOW.

**The tell**: the test breaks when you refactor, but behavior did not change.

## Bad: verifying through a side channel

```typescript
// BAD — bypasses the interface to check the database directly
test("createUser saves to database", async () => {
  await createUser({ name: "Alice" });
  const row = await db.query("SELECT * FROM users WHERE name = ?", ["Alice"]);
  expect(row).toBeDefined();
});

// GOOD — verifies through the same interface a caller would use
test("createUser makes user retrievable", async () => {
  const user = await createUser({ name: "Alice" });
  const retrieved = await getUser(user.id);
  expect(retrieved.name).toBe("Alice");
});
```

The side-channel version passes even if `getUser` is broken, which is exactly
the failure a caller would hit.

## Bad: tautological

```typescript
// BAD — the expected value is recomputed the way the code computes it
test("calculateTotal sums line items", () => {
  const items = [{ price: 10 }, { price: 5 }];
  const expected = items.reduce((sum, i) => sum + i.price, 0);
  expect(calculateTotal(items)).toBe(expected);
});

// GOOD — the expected value is an independent literal
test("calculateTotal sums line items", () => {
  expect(calculateTotal([{ price: 10 }, { price: 5 }])).toBe(15);
});
```

The tautological form passes by construction: it can never disagree with the
code, so it can never catch a bug in it. The same shape hides in hand-derived
snapshots and in constants asserted equal to themselves.
