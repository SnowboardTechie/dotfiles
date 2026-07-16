# Local LLM Context Diagnostics

Use this reference when a user reports context limits, truncation, slow long chats, or cancellations through a homelab AI endpoint such as Open WebUI backed by Ollama.

## Identify the actual stack first

Do not infer the backend from the chat surface currently in use. Start with the named endpoint and trace its service chain:

1. Resolve/fetch the endpoint to identify the frontend.
2. Search declarative host and service modules for the domain and relevant services.
3. Confirm the live frontend-to-inference URL and process/service labels.
4. Only then inspect model/provider context behavior.

Keep these systems distinct even when they share one host:

- Hermes agent chat and its configured provider/model
- Open WebUI and its selected model metadata
- Ollama and the model actually loaded for inference
- Cloudflare Tunnel or another reverse proxy in front of the UI

A domain pointing to Open WebUI does not imply that Hermes's own provider, model, quota, or compression settings apply.

## Four different quantities

Report these separately:

1. **Native model maximum** — model metadata from Ollama's `/api/show`.
2. **Allocated runtime context** — `context_length` from `/api/ps` or `n_ctx_slot` in runner logs.
3. **Current request size** — prompt token count in runner logs.
4. **Conversation retention policy** — Open WebUI truncation/compaction settings.

Do not call a deployment “maxed out” merely because a UI warns about tokens. Verify whether the latest request was truncated, whether Ollama allocated the native maximum, and whether compaction is enabled.

## Read-only probes

```bash
ollama --version
curl -fsS http://127.0.0.1:11434/api/tags
curl -fsS http://127.0.0.1:11434/api/ps
curl -fsS http://127.0.0.1:11434/api/show \
  -d '{"model":"<tag>","verbose":false}'
```

From `/api/show`, inspect model-info keys ending in `.context_length`. From `/api/ps`, inspect each loaded model's `context_length` and memory allocation.

Inspect the Ollama launchd/systemd environment for overrides such as context size, KV-cache type, parallelism, and loaded-model limits. Absence of a global context override is not itself a problem when requests or model metadata select the full window.

For Open WebUI, inspect only non-secret configuration relevant to:

- selected/default models
- per-model parameters such as `num_ctx`
- global default model parameters
- context compaction enablement and threshold
- Ollama base URL

Open WebUI commonly stores these in its SQLite database. Use read-only SQLite access, select narrow keys, and redact API keys/tokens. Do not dump chats or user content to diagnose model capacity.

## Interpret logs carefully

Useful Ollama runner fields include:

- `n_ctx_slot` — allocated context window
- `task.n_tokens` / prompt token totals — current request size
- `truncated = 0|1` — whether the request was actually truncated
- prompt-processing timing — long-context latency
- `context canceled` — request cancellation, not proof of context overflow

A request can be well below the native maximum and still take several minutes to prefill. Client cancellation, reverse-proxy behavior, browser retries, or user interruption may then look like a context-limit problem. Separate these from a true overflow.

## Remediation order

1. If allocated context is below the model's native maximum, raise the request/model `num_ctx` or the appropriate Ollama setting, then verify `/api/ps` after a real request.
2. If allocated context already equals the native maximum, do not falsely raise metadata or force RoPE scaling without model-specific evidence and quality testing.
3. For long-running chats, enable Open WebUI context compaction at a conservative threshold. This extends conversational continuity by summarizing old turns; it does not increase raw model context and can lose detail.
4. If prefill latency causes cancellations, compact earlier or reduce retained context before changing proxies.
5. To exceed the native maximum with raw tokens, select and validate a model that natively supports a larger window.

## Studio snapshot (July 2026; revalidate before reuse)

At the time of the diagnostic:

- `ai.thompson.codes` served Open WebUI through Cloudflare and used local Ollama on Studio.
- Installed active choices included Qwen and Gemma variants whose Ollama metadata advertised 262,144-token native windows.
- Ollama had Qwen loaded at `context_length: 262144`, confirming full native allocation.
- A recent request contained about 139K prompt tokens with `truncated = 0`, but prompt processing took roughly 458 seconds and some requests ended as `context canceled`.
- Open WebUI context compaction was disabled; an 80K threshold existed but was inactive.

The durable conclusion was not merely “the limit is 262K.” It was: full native context was allocated, the observed request had not overflowed, latency/cancellation had to be distinguished from truncation, and Open WebUI compaction was the practical continuity mechanism.