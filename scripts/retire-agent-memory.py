#!/usr/bin/env python3
"""retire-agent-memory.py — remove retired third-party agent-memory wiring.

Hindsight, context-mode, and claude-mem were retired on 2026-09-29. Their
installers merged entries into machine-local JSON that setup never owned
outright (Omarchy, non-stowed peers). This removes only those known entries:

  ~/.claude/settings.json          Hindsight and context-mode-cache-heal hooks;
                                   context-mode / claude-mem plugins + marketplaces
  ~/.claude.json                   Hindsight / context-mode MCP servers (user + project)
  ~/.pi/agent/settings.json        the Hindsight Pi extension
  ~/.config/opencode/opencode.json the Hindsight plugin / MCP entry

Every foreign entry, the model and all other settings, native memory,
history, and any data directory are left alone. Nothing is deleted from disk
except JSON entries. --check never writes; --apply is idempotent. A file that
changes between read and replace (a running Claude rewrites ~/.claude.json) is
left untouched and reported; rerun once the writer is idle. Unreadable or
malformed targets exit nonzero.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

HINDSIGHT_RUNTIME = "/.hindsight/coding-agents"
HINDSIGHT_API_HOST = "bryans-mac-studio.tail5ba690.ts.net:9443"
CACHE_HEAL_HOOK = "context-mode-cache-heal"
RETIRED_PLUGINS = ("context-mode@context-mode", "claude-mem@thedotmack")
RETIRED_MARKETPLACES = {"context-mode": "mksglu/context-mode", "thedotmack": "thedotmack/claude-mem"}
RETIRED_MCP_NAMES = ("hindsight", "context-mode")
# Not JSON, so only reported: the native uninstaller or a person removes them.
LEFTOVERS = (
    ".claude/hooks/context-mode-cache-heal.mjs",
    ".claude/skills/hindsight-coding-agent",
    ".hindsight/coding-agents",
)


def retired_hook(command: object) -> str | None:
    """Name the retired integration a hook belongs to; never echo the command."""
    if not isinstance(command, str):
        return None
    if HINDSIGHT_RUNTIME in command:
        return "hindsight"
    if CACHE_HEAL_HOOK in command:
        return CACHE_HEAL_HOOK
    return None


def retired_mcp(name: str, config: object) -> bool:
    text = json.dumps(config)
    return (
        name.lower() in RETIRED_MCP_NAMES
        or HINDSIGHT_RUNTIME in text
        or HINDSIGHT_API_HOST in text
    )


def prune_hooks(settings: dict, removed: list[str]) -> None:
    hooks = settings.get("hooks")
    if not isinstance(hooks, dict):
        return
    for event in list(hooks):
        groups = hooks[event]
        if not isinstance(groups, list):
            continue
        kept_groups = []
        for group in groups:
            entries = group.get("hooks") if isinstance(group, dict) else None
            if not isinstance(entries, list):
                kept_groups.append(group)
                continue
            kept = []
            for entry in entries:
                category = retired_hook(entry.get("command")) if isinstance(entry, dict) else None
                if category:
                    removed.append(f"hook {event}: {category}")
                else:
                    kept.append(entry)
            if kept:
                kept_groups.append({**group, "hooks": kept})
        if kept_groups:
            hooks[event] = kept_groups
        elif groups:
            del hooks[event]


def prune_claude_settings(settings: dict, removed: list[str]) -> None:
    prune_hooks(settings, removed)
    plugins = settings.get("enabledPlugins")
    if isinstance(plugins, dict):
        for name in RETIRED_PLUGINS:
            if name in plugins:
                del plugins[name]
                removed.append(f"plugin {name}")
    marketplaces = settings.get("extraKnownMarketplaces")
    if isinstance(marketplaces, dict):
        for name, repo in RETIRED_MARKETPLACES.items():
            source = (marketplaces.get(name) or {}).get("source") or {}
            if isinstance(source, dict) and source.get("repo") == repo:
                del marketplaces[name]
                removed.append(f"marketplace {name}")


def prune_mcp_servers(servers: object, scope: str, removed: list[str]) -> None:
    if not isinstance(servers, dict):
        return
    for name in [name for name, config in servers.items() if retired_mcp(name, config)]:
        del servers[name]
        removed.append(f"mcp {scope}: {name}")


def prune_claude_state(state: dict, removed: list[str]) -> None:
    prune_mcp_servers(state.get("mcpServers"), "user", removed)
    for project, config in (state.get("projects") or {}).items():
        if isinstance(config, dict):
            prune_mcp_servers(config.get("mcpServers"), f"project {project}", removed)


def prune_list_entries(settings: dict, keys: tuple[str, ...], removed: list[str]) -> None:
    for key in keys:
        entries = settings.get(key)
        if not isinstance(entries, list):
            continue
        kept = [entry for entry in entries if not (isinstance(entry, str) and HINDSIGHT_RUNTIME in entry)]
        removed.extend(f"{key}: hindsight runtime" for _ in range(len(entries) - len(kept)))
        settings[key] = kept


def prune_pi(settings: dict, removed: list[str]) -> None:
    prune_list_entries(settings, ("extensions", "packages"), removed)


def prune_opencode(settings: dict, removed: list[str]) -> None:
    prune_list_entries(settings, ("plugin",), removed)
    prune_mcp_servers(settings.get("mcp"), "opencode", removed)


class ConcurrentChange(RuntimeError):
    pass


def write_json(path: Path, value: dict, original: bytes) -> None:
    """Replace the file atomically through any symlink, unless it changed since it was read."""
    # ponytail: compare-then-replace leaves a sub-millisecond window; a real
    # lock would need every writer (Claude itself) to honor it.
    target = path.resolve()
    mode = target.stat().st_mode & 0o7777
    descriptor, temporary = tempfile.mkstemp(prefix=f".{target.name}.", dir=target.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(value, handle, indent=2, ensure_ascii=False)
            handle.write("\n")
        os.chmod(temporary, mode)
        if target.read_bytes() != original:
            raise ConcurrentChange(f"{path} changed while it was being cleaned")
        os.replace(temporary, target)
    except BaseException:
        Path(temporary).unlink(missing_ok=True)
        raise


def reconcile(home: Path, apply: bool) -> tuple[int, int]:
    targets = (
        (home / ".claude" / "settings.json", prune_claude_settings),
        (home / ".claude.json", prune_claude_state),
        (home / ".pi" / "agent" / "settings.json", prune_pi),
        (home / ".config" / "opencode" / "opencode.json", prune_opencode),
    )
    total = failures = 0
    for path, prune in targets:
        if not path.is_file():
            continue
        try:
            original = path.read_bytes()
            value = json.loads(original.decode("utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            print(f"  ERROR: unreadable {path}: {type(exc).__name__}")
            failures += 1
            continue
        if not isinstance(value, dict):
            print(f"  ERROR: {path} is not a JSON object")
            failures += 1
            continue
        removed: list[str] = []
        prune(value, removed)
        if not removed:
            print(f"  ok: {path}")
            continue
        if apply:
            try:
                write_json(path, value, original)
            except ConcurrentChange as exc:
                print(f"  ERROR: {exc}; left untouched, rerun when idle")
                failures += 1
                continue
        total += len(removed)
        verb = "removed" if apply else "would remove"
        for item in removed:
            print(f"  {verb} from {path}: {item}")

    installed = home / ".claude" / "plugins" / "installed_plugins.json"
    if installed.is_file():
        text = installed.read_text(encoding="utf-8", errors="replace")
        for name in RETIRED_PLUGINS:
            if f'"{name}"' in text:
                print(f"  still installed: {name} — run: claude plugin uninstall --scope user --keep-data {name}")
    for relative in LEFTOVERS:
        if (home / relative).exists() or (home / relative).is_symlink():
            print(f"  leftover (not removed): ~/{relative}")
    return total, failures


def main(argv: list[str]) -> int:
    if len(argv) != 1 or argv[0] not in {"--check", "--apply"}:
        print("Usage: retire-agent-memory.py (--check | --apply)", file=sys.stderr)
        return 2
    apply = argv[0] == "--apply"
    home = Path.home()
    print(f"Retired agent-memory cleanup ({argv[0][2:]}) for {home}")
    total, failures = reconcile(home, apply)
    print(f"  summary: {total} retired entr{'y' if total == 1 else 'ies'} {'removed' if apply else 'found'}"
          + (f", {failures} file(s) failed" if failures else ""))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
