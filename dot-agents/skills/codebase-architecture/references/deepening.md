# Deepening

How to deepen a cluster of shallow modules safely, given its dependencies. Uses
the vocabulary in [`../SKILL.md`](../SKILL.md): **module**, **interface**,
**seam**, **adapter**. Adapted from Matt Pocock's `codebase-design/DEEPENING.md`;
see [`dot-agents/upstreams/mattpocock-skills.json`](../../../upstreams/mattpocock-skills.json).

## Dependency categories

Classify a deepening candidate's dependencies first. The category determines how
the deepened module is tested across its seam.

### 1. In-process

Pure computation, in-memory state, no I/O. Always deepenable: merge the modules
and test through the new interface directly. No adapter needed.

### 2. Local-substitutable

Dependencies with a local test stand-in — PGlite for Postgres, a tmpdir or
in-memory filesystem, a fake clock. Deepenable if the stand-in exists. Test the
deepened module with the stand-in running in the suite. The seam is **internal**;
no port appears at the module's external interface.

Prefer this over mocking whenever a stand-in exists: it exercises the real query
or path semantics a mock would have to invent.

### 3. Remote but owned (ports and adapters)

Your own services across a network boundary. Define a **port** at the seam. The
deep module owns the logic; transport is injected as an **adapter**. Tests use an
in-memory adapter; production uses HTTP, gRPC, or a queue.

The recommendation shape: *"Define a port at the seam, implement an HTTP adapter
for production and an in-memory adapter for tests, so the logic sits in one deep
module even though it is deployed across a network."*

### 4. True external

Third-party services you do not control. The deepened module takes the external
dependency as an injected port; tests supply a mock adapter. See
[`tdd/references/mocking.md`](../../tdd/references/mocking.md) for what makes
that mock honest.

## Seam discipline

- **One adapter means a hypothetical seam. Two means a real one.** Do not
  introduce a port unless at least two adapters are justified — typically
  production plus test. A single-adapter seam is indirection wearing a costume.
- **Internal seams are not external seams.** A deep module may have internal
  seams used by its own tests. Do not expose them through the interface merely
  because the tests use them; that widens the interface and re-shallows the
  module.

## Testing strategy: replace, don't layer

- Old unit tests against the shallow modules become waste once tests exist at
  the deepened module's interface. Delete them — keeping both means every change
  costs two edits and the old tests pin the shape you just removed.
- Write the new tests at the deepened module's interface. **The interface is the
  test surface.**
- Assert on observable outcomes through the interface, not internal state.
- A test that has to change when the implementation changes was testing past the
  interface.
