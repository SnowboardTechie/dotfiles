# HERDR STATUS RAIL (Glyph Rail)

Paths are relative to the repo root. The rail is `dot-config/herdr/config.toml` `[ui] tab_bar_right` + the module scripts beside it (`claude-usage.sh`, `codex-usage.py`, `openrouter-spend.py`, `host-label.sh`).

- One Nerd Font glyph per module, joined by `tab_bar_right_separator = " \ue0b3 "`. Keep that TOML escape spelling: U+E0B3 is BMP Private Use Area and text pipelines strip it far more readily than the Plane-15 Nerd Font glyphs, which is how it silently became two spaces once already. `tests/test-herdr-glyph-rail.py` is the regression guard.
- `theme.name = "terminal"` keeps Herdr on the host terminal's ANSI palette, so colors are NOT defined here — do not add a Nightfly hex table.
- Only `zoom`, `hostname`, `datetime`, `text`, `command` entry types exist; a glyph-prefixed module must be `command`, since `hostname` takes no prefix.
- Validate with `HERDR_CONFIG_PATH=$PWD/dot-config/herdr/config.toml herdr config check` (it rejects unknown themes and unsupported `strftime` directives).
- `codex-usage.py` reads the OpenAI OAuth credential from Hermes first, then Codex CLI, and reports the most-used base quota window as one compact percentage with its reset countdown; it is read-only and leaves refresh/rotation to the owning client. `tests/test-herdr-codex-usage.py` pins rendering and cache fallback.
- `openrouter-spend.py` reports **account-wide** spend via `POST /api/v1/analytics/query` — it needs an OpenRouter **management key** at `~/.secrets/openrouter/management-key` (mode 0600, never in Git); an `sk-or-v1` inference key gets `403 Only management keys can access analytics`.
- **Never drop `granularity: "hour"` from that query.** Without it the API snaps `time_range` out to whole UTC days — a one-minute window returns the entire day — so a trailing-24h request silently becomes "yesterday in full plus today so far", measured live at 42.4 hours and 2.04x the true figure. Hourly buckets are clipped to the requested range and are exactly additive (summing a day's hours reproduces the day total to the last decimal); quiet hours are omitted, so no rows means $0, not an error. `tests/test-herdr-openrouter-spend.py` pins the granularity.
- Do not "fix" it back to a local or simpler source: `/credits` is lifetime-only and `/auth/key`'s `usage_daily` is per-key and midnight-UTC-resetting, so neither is an account-wide rolling 24h.

## COMMANDS

```bash
# Validate a Herdr config without touching the live one, then test its modules
HERDR_CONFIG_PATH="$PWD/dot-config/herdr/config.toml" herdr config check
python3 tests/test-herdr-glyph-rail.py   # guards the U+E0B3 divider + glyph-led rail
python3 tests/test-herdr-openrouter-spend.py   # stubs the analytics API; no key or network needed
bash tests/test-herdr-claude-usage.sh
bash tests/test-herdr-host-label.sh
```
