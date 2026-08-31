# Review Artifact Contract

The root owns candidate evidence, report admission, disposition, and all vault
writes. Reviewers own only isolated scratch artifacts beneath their designated
state roots.

## Evidence manifest

The root writes one immutable JSON manifest under the confined review state
root. It contains:

- PR URL/repository/number/author and `expected_pr_head_ref`;
- `base_sha`, `head_sha`, `merge_base_sha`, and `diff_sha256`;
- canonical worktree identities and complete changed-path inventory;
- deterministic `lane_selection.risk_selected` plus `risk_reason`;
- every bound evidence file's state-root-relative path and SHA-256.

The manifest excludes itself from its file map. Record its exact digest as
`evidence_manifest_sha256`. Resolve every path canonically under the state root;
reject missing files, symlink escapes, and hash mismatches.

## Lane and model bundles

Each selected lane emits Markdown plus a JSON identity/hash sidecar. Lane
frontmatter carries the lane, reviewer family, all four candidate fields, and
the evidence-manifest SHA-256. The model-family orchestrator emits:

- one advisory Markdown report using `templates/model-review.md`;
- one JSON sidecar naming reviewer family, provider, primary model,
  `models_used`, candidate identity, manifest digest, exact required lanes,
  lane artifact paths/hashes, report path/hash, and Herdr route evidence;
- complete route identity: surface, agent name, pane ID, runtime session ID,
  launch route, canonical worktree root/common-dir/branch, and state root.

Run `scripts/validate-review-artifacts.py` with caller-supplied model predicates.
It validates paths, hashes, exact identities, deterministic lanes, advisory
frontmatter, Herdr route completeness, and observed models. A missing, stale,
model-mismatched, or malformed report yields `INCOMPLETE` and no verdict. Both
Claude and GPT reports are required before root adjudication.

## Root disposition

The root copies admitted Claude and GPT Markdown byte-for-byte. It never edits
an advisory report and verifies the copied hash. The root alone writes the
canonical adjudication using `templates/adjudication.md`, classifying every
source lead as confirmed, rejected, or unresolved with root-owned evidence.
Reviewer consensus changes investigation priority only; it is not proof.

## Vault placement

After proving the target project's existing vault and reading vault-local
instructions, use:

```text
reviews/<owner>-<repo>/pr-<number>/<head-sha8>/claude.md
reviews/<owner>-<repo>/pr-<number>/<head-sha8>/gpt.md
reviews/<owner>-<repo>/pr-<number>/<head-sha8>/adjudication.md
```

The two advisory notes have `canonical: false` and are immutable: they are never
overwritten. A later head SHA receives a new directory. The adjudication has
`canonical: true`. `reviews/INDEX.md` links canonical adjudications, not raw
model notes; link it once from the vault root index only when local conventions
permit.

Only the instigating root may copy, write, index, commit, push, fetch, or
synchronize the vault. Reviewers never receive vault write access. Before sync,
follow `vault-pkm` and vault-local `AGENTS.md`, name exact task-owned paths,
validate frontmatter/links/hashes, and stage only those paths. After push, fetch
and verify local/remote SHA equality.

An incomplete or stale attempt may retain already admitted immutable advisory
notes plus a canonical status note, but it cannot claim a review verdict or
clean/readiness status.
