# Hermes named custom providers

Use this reference when adding a private OpenAI-compatible endpoint to Hermes while preserving the current default provider.

## Config shape

Hermes accepts named endpoints under `custom_providers`:

```yaml
custom_providers:
  - name: my-endpoint
    base_url: https://models.example.test/v1
    key_env: MY_ENDPOINT_API_KEY
    api_mode: chat_completions
    model: qwen-coder:latest
    models:
      qwen-coder:latest:
        context_length: 131072
```

Keep the credential in `~/.hermes/.env` (mode `0600`) and reference it with `key_env`. Do not put the value in `config.yaml`.

## Safely reusing another client's credential

When another client uses a file-backed key, copy it without printing it:

1. Read the source file into a shell variable with newlines removed.
2. Upsert `NAME=value` in `~/.hermes/.env` using a script that does not emit the value.
3. Set the file mode to `0600`.
4. Verify only that the variable exists and is non-empty.

Avoid command tracing (`set -x`) while handling the key.

## Verification sequence

1. Authenticated `GET <base_url>/models`; report status and model IDs only.
2. Reload with `hermes_cli.config.load_config()` and confirm `custom_providers` is a list.
3. Normalize with `get_compatible_custom_providers()` and ensure the provider appears.
4. Run `hermes config check`.
5. Run a real smoke test:

```bash
hermes chat \
  -q 'Reply with exactly: LOCAL_MODEL_OK' \
  --provider custom:my-endpoint \
  --model 'qwen-coder:latest' \
  --toolsets safe \
  --quiet
```

6. Confirm the output is exactly `LOCAL_MODEL_OK` and the exit code is zero.
7. Confirm `model.provider` and `model.default` still point to the user's prior default.

## Switching from a live session

Named custom providers use triple syntax because model IDs may themselves contain colons:

```text
/model custom:my-endpoint:qwen-coder:latest
```

The parser treats the first segment as `custom`, the second as the named endpoint, and the remainder as the model ID.

## Known configuration trap

`hermes config set` stores some structured JSON/YAML arguments as strings. A printed success message does not prove the schema is correct. Reload and type-check. If necessary, update `config.yaml` with a YAML parser while preserving every unrelated key.

## Context metadata

Hermes tool-heavy sessions require a sufficiently large context window. Copy honest limits from the source configuration or server metadata. Do not raise the declared value merely to bypass validation; instead warn that the smaller model may not be suitable for full agent sessions.
