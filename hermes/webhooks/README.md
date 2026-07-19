# Hermes webhook pilots

Webhook contracts live here; executable route filters live in `../scripts/` and
are installed through `manifest.json`. Keep event initiation separate from agent
authority, make accepted payloads explicit, and require signed representative
events plus destination readback before calling a route live.

- [`sgg-pr-review.md`](sgg-pr-review.md) — deterministic, read-only SGG review
  updates to a private Matrix room.
