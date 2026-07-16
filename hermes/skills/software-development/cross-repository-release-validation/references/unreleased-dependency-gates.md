# Unreleased Dependency Gates: Validation Recipe

Use this reference after reading the parent skill. Substitute repository-specific commands and paths; preserve exact SHAs in the evidence.

## Python wheel → Python consumer

```bash
# Upstream SDK checkout/worktree is pinned to the candidate SHA.
cd "$SDK/lib/python-sdk"
poetry build -f wheel
WHEEL=$(printf '%s\n' "$PWD"/dist/*.whl | head -n 1)

# Downstream consumer uses the exact wheel; no dependency re-resolution.
cd "$CONSUMER"
poetry install
poetry run pip install --force-reinstall --no-deps "$WHEEL"

# Verify package identity/surface before testing.
poetry run python - <<'PY'
from importlib.metadata import version
print(version("common-grants-sdk"))
# Import one candidate-only symbol or inspect the installed module path here.
PY

make checks
make test
```

For a type-only defect, run `make checks` before editing and retain the exact diagnostic count as RED. If a candidate runtime test already passes, remove it unless it protects an independently required behavior.

Add a focused runtime probe when serialization matters:

```python
value = build_consumer_model(...)
assert value.changed_field == expected
wire = value.model_dump(by_alias=True)
assert wire["wireAlias"] == expected_wire_value
```

## TypeScript tarball → TypeScript consumer

```bash
# Upstream monorepo pinned to candidate SHA.
cd "$SDK"
pnpm install --frozen-lockfile
pnpm --filter @scope/sdk build

TARBALL_DIR=$(mktemp -d)
cd "$SDK/path/to/sdk-package"
pnpm pack --pack-destination "$TARBALL_DIR"
SDK_TGZ=$(printf '%s\n' "$TARBALL_DIR"/scope-sdk-*.tgz | head -n 1)

# Consumer: preserve clean tracked manifests around a temporary artifact override.
cd "$CONSUMER"
pnpm install --frozen-lockfile
pnpm add --save-dev "$SDK_TGZ"
pnpm run ci
git restore -- package.json pnpm-lock.yaml
```

Then pack the consumer too and install both tarballs into a separate playground/harness. Run a real downstream scenario that imports only published exports and asserts the wire request/response shape.

Afterward:

```bash
git -C "$CONSUMER" status --short --branch
git -C "$PLAYGROUND" status --short --branch
```

Both should be clean. If the repository already provides a local-SDK harness, prefer it over hand-rolled installation.

## Hosted CI dependency gate

After pushing:

```bash
gh pr checks "$PR" --repo "$REPO"
gh run view "$RUN_ID" --repo "$REPO" --log-failed
```

Classify every residual failure:

| Evidence | Interpretation |
|---|---|
| Only candidate symbols are missing; old published version is installed | Expected publication gate |
| Diagnostics addressed by the patch remain | Local environment/provenance mismatch or incomplete fix |
| Format/lint/test failure unrelated to missing symbols | Real regression; repair before release |
| CI dependency version differs from expectation | Dependency metadata/lockfile issue |

Never summarize the first case as “CI passed.” Say: local candidate verification is green; hosted CI remains red on the published dependency, with the exact residual error count/class.

## Final evidence checklist

- Upstream full SHA and artifact filename
- Downstream full SHA
- Installed package version/source or candidate-only symbol proof
- Checker error/warning counts
- Test counts
- Packaged integration scenario result
- Hosted CI residual failure class/count
- Clean worktrees and restored manifests
- Explicit statement that merge/publish actions were not taken unless separately authorized
