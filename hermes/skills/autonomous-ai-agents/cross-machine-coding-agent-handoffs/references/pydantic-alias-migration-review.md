# Reviewing Pydantic alias migrations

Use this reference when a change replaces `Field(alias=...)` with `validation_alias`, `serialization_alias`, `AliasGenerator`, or `populate_by_name`.

## Why direct model tests are insufficient

Pydantic stores these settings in different `FieldInfo` properties. Replacing:

```python
field_name: T = Field(alias="fieldName")
```

with:

```python
field_name: T = Field(
    validation_alias="fieldName",
    serialization_alias="fieldName",
)
```

can preserve parsing and `model_dump(by_alias=True)` while changing:

```python
Model.model_fields["field_name"].alias
```

from `"fieldName"` to `None`.

Generic transform validators, schema builders, mapping validators, filter classifiers, code generators, and documentation emitters may inspect `.alias` directly. Their behavior can regress even when model round-trip tests stay green.

## Review procedure

1. Inspect the before/after `FieldInfo` tuple for each changed field:

```python
info = Model.model_fields["field_name"]
print(info.alias, info.validation_alias, info.serialization_alias)
```

2. Search the full package for metadata readers, not only constructors:

- `.alias`
- `.validation_alias`
- `.serialization_alias`
- `model_fields`
- `model_config`
- alias generators and name-normalization maps

3. Classify each reader:

- model-specific and unaffected;
- generic over `BaseModel` and therefore potentially affected;
- restricted by runtime validation even if its type annotation looks generic.

Read the full call path before accepting a claim that a generic helper “only handles” one model family.

4. Reproduce a compatibility claim through the public helper, not only direct model validation. For example, if a public transform builder validates camelCase mapping keys, exercise that builder with the changed model.

5. Compare against the exact base revision. A useful probe records whether the base accepts the operation and whether the branch rejects it.

## Safe alias collection

When a generic helper promises to recognize field names and wire aliases, it should consider the alias properties relevant to its contract. For simple string aliases:

```python
names = set(model.model_fields)
for info in model.model_fields.values():
    for candidate in (
        info.alias,
        info.validation_alias,
        info.serialization_alias,
    ):
        if isinstance(candidate, str):
            names.add(candidate)
```

Do not flatten `AliasChoices` or `AliasPath` casually. Decide whether the helper's contract supports those structures and add focused tests if it does.

## Minimum regression coverage

- snake_case constructor or validation input is consumed rather than silently ignored;
- a conflicting value raises instead of falling back to a subclass default;
- camelCase input still validates;
- `model_dump(by_alias=True)` preserves the wire shape;
- generic transform/schema/mapping helpers still recognize the camelCase key;
- static checking is exercised by a committed pyright/mypy surface when the bug is static as well as runtime. If only a scratch file or downstream repo proves it, describe that honestly as verification rather than durable local coverage.

## Review smell

A report that says “wire shape unchanged” after an alias migration is incomplete until both direct serialization and metadata-consuming helpers have been checked.
