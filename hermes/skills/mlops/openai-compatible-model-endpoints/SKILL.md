---
name: openai-compatible-model-endpoints
description: Configure and verify self-hosted or private OpenAI-compatible model endpoints across agent clients without exposing credentials or replacing a working default provider.
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    created_by: agent
    tags: [openai-compatible, self-hosted, local-models, providers, ollama, open-webui]
---

# OpenAI-Compatible Model Endpoints

Use this skill when connecting an agent or coding client to a self-hosted/private endpoint that implements the OpenAI API shape, including Open WebUI, Ollama's `/v1` API, vLLM, LM Studio, or an internal gateway.

## Principles

- Inspect an existing working client configuration first; reuse its exact base URL, model IDs, context limits, and credential source rather than guessing.
- Never print, read into chat, or commit API-key contents. Check only whether the credential source exists and is non-empty.
- Prefer a named secondary provider so the user's current cloud/default model remains unchanged.
- Treat `/models` reachability as a prerequisite, not sufficient verification. Finish with a real inference through the target client.
- Preserve model IDs exactly, including colons and tags.

## Workflow

1. **Discover the working connection**
   - Locate the existing client's provider block and default model.
   - Extract only non-secret fields: base URL, credential reference path or environment-variable name, model IDs, context limits, and API transport.
   - Confirm the referenced credential exists without displaying its value.

2. **Confirm endpoint compatibility**
   - Request `<base_url>/models` using the credential in a shell variable.
   - Report only the HTTP status and returned model IDs.
   - Ensure the endpoint is OpenAI-compatible and determine whether it expects chat completions, responses, or another transport.

3. **Configure the new client safely**
   - Register a named provider instead of replacing the active default.
   - Put credential values in the client's secret store or private `.env`; keep only a `key_env`/credential reference in normal config.
   - Copy model-specific context metadata when known.
   - Keep the existing default provider/model unless the user explicitly asks to change it.

4. **Validate config parsing**
   - Reload config through the application's own parser and inspect the resulting type and normalized provider view.
   - Do not trust a CLI's success message alone.
   - Run the application's config checker or doctor command.

5. **Run end-to-end inference**
   - Invoke the client with the named provider and an exact-output smoke-test prompt.
   - Use a minimal/safe toolset if available so the test isolates inference.
   - Confirm the process exits successfully and the expected text is returned.

6. **Verify no collateral changes**
   - Confirm the original default provider/model is unchanged.
   - If work occurred from a repository, verify its working tree remains unchanged unless repo edits were intended.
   - Tell the user the exact provider-switch syntax and note any models below the client's minimum context requirement.

## Selecting Apple Silicon models and quantizations

Before advising a user to replace a working local model, obtain the exact model ID and serving command. Treat the base model, quantization, and runtime as separate choices: a label such as `NVFP4` does not establish whether the checkpoint is an NVIDIA-targeted source model, an MLX conversion, or a package served by Ollama.

Do not recommend higher precision merely because unified memory can hold it. Apple Silicon inference is commonly memory-bandwidth constrained, and a lower-bit model may deliver materially better throughput with equivalent agent reliability. Prefer an A/B test on representative tool-calling and multi-step tasks; move to higher precision only when it measurably fixes schema adherence, tool-call parsing, reasoning stability, or task completion.

For the verification sequence, common naming traps, and a worked Qwen MoE example, read `references/apple-silicon-model-selection.md`.

## Pitfalls

### Structured values passed to config CLIs may become strings

A command such as `config set custom_providers '[{...}]'` may report success while persisting a scalar string rather than a YAML/JSON list. Always reload through the client parser and assert the value's type. If the CLI cannot preserve structured types, perform a targeted YAML edit that retains all unrelated configuration.

### A successful `/models` call is not enough

Gateways may expose model discovery while rejecting chat requests, mishandling model tags, or lacking tool-call support. Always run one real client inference after configuration.

### Context windows differ by client

A model accepted by a lightweight coding client may be rejected by a tool-heavy agent with a larger minimum context requirement. Preserve accurate context metadata and warn rather than inflating it.

### Runtime sessions may cache provider state

Provider registration usually affects new sessions or the model picker. Do not claim the already-running conversation changed models unless an explicit switch succeeded.

## Supporting material

- See `references/hermes-named-custom-providers.md` for the Hermes-specific named-provider shape, verification sequence, and safe credential-copy pattern.
