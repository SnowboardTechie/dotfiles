# Local model inventory and pruning

Use this reference when reducing Ollama/Open WebUI model storage on a homelab inference host.

## Decision workflow

1. Inventory installed tags with `ollama list`, loaded models with `ollama ps`, and total storage with `du -sh ~/.ollama/models`.
2. Query Ollama's `/api/tags` response and group tags by `digest`. Ollama deduplicates shared blobs, so deleting one of multiple tags for the same digest may reclaim no space.
3. Cross-check every installed model against all consumers before recommending deletion:
   - currently loaded Ollama models;
   - Open WebUI active/disabled model records;
   - recent Open WebUI chat usage and last-use time;
   - Hermes custom-provider, delegation, fallback, and automation configuration;
   - recency of the download, which may indicate an active evaluation.
4. Classify models as **keep**, **prune**, or **review separately**. Prefer one model per role rather than keeping several adjacent sizes or quantizations without a concrete latency/quality need.
5. Calculate recovery by unique digest, not by blindly summing tag sizes.
6. With explicit approval, update consumer configuration before deleting model data. Stop a loaded model before removing its tags.
7. Verify the exact retained tag set through both `ollama list` and `/api/tags`, rerun consumer configuration validation, and report before/after disk use.

## Refreshing a tag that is already loaded

A same-tag pull can leave three distinct states that must be reconciled:

1. `ollama list` and `/api/tags` point to the newly pulled digest.
2. `ollama ps` may still show the old digest running. After the tag moves,
   `ollama stop <tag>` can resolve the new digest and leave the old runner untouched.
3. The old model layers can remain as unreferenced blobs, so model-store usage
   temporarily grows by roughly the size of the replacement.

Use this verified sequence:

1. Record the old tag digest, loaded digest, and model-store size.
2. Pull the same exact tag and confirm the tag now points to the expected new digest.
3. Send a bounded inference to that tag. The scheduler loads the new digest and
   retires the stale runner; prove this with `ollama ps` rather than trusting
   `ollama stop` output.
4. Complete native/API/client smoke tests against the new digest before cleanup.
5. If the supervised Ollama service has no active requests, restart it through its
   declared service manager. Ollama's startup prune removes the now-unreferenced
   layers. Do not delete blob files manually.
6. Confirm the model-store size returned to the expected unique-digest total, then
   warm the intended resident models and verify their loaded digests.

A restart is a service interruption: keep it inside the approved refresh scope, use
the declared launchd/systemd unit, wait on the health endpoint instead of sleeping
blindly, and restore the prior resident set afterward.

## Open WebUI usage evidence

Open WebUI commonly stores state in `~/.open-webui/data/webui.db`. Use SQLite read-only mode. The `model.is_active` flag describes WebUI visibility, not whether an Ollama blob is safe to remove. Parse `chat.chat` JSON and inspect both its top-level `models` array and message-level `model` fields; historical usage is supporting evidence, not an automatic keep rule.

Disabled status alone is insufficient: a disabled model may still be loaded directly, referenced by Hermes, or newly downloaded for evaluation. Conversely, stale WebUI model rows for tags no longer installed consume negligible model storage and should not be counted as reclaimed bytes.

## Hermes structured-config pitfall

On the Hermes CLI version observed in July 2026, `hermes config set` correctly handled scalar values but serialized a supplied JSON array for a composite section such as `custom_providers` as a quoted YAML string. It also rewrote the YAML, dropping comments. Therefore:

- Use `hermes config set` for supported scalar/dotted settings.
- For a composite list/map, prefer `hermes config edit` or another supported structured editor, then immediately read the resulting section and run `hermes config check`.
- `hermes config edit` passes `$EDITOR` as one executable path, not a shell command with arguments. For a noninteractive edit, point `EDITOR` at an executable helper script rather than a value such as `python3 script.py`.
- Never trust a success message alone; confirm the resulting YAML shape before model deletion.

## July 2026 example

The Studio host had roughly 235 GiB of Ollama model data across many disabled Qwen 3.5 and Gemma variants. Cross-checking runtime state, WebUI usage, and Hermes references supported retaining one model per role: `qwen3.6:35b-a3b-coding-nvfp4` for coding/agents and `gemma4:31b-mlx` for general use. Removing all Qwen 3.5 tags and all other Gemma variants reduced the model directory to roughly 39 GiB. Revalidate current names, configuration, and usage before applying this example elsewhere.