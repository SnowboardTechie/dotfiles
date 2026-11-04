#!/usr/bin/env python3
"""Check that the Hermes `sgg` profile can reach only SGG's approved model providers.

SGG is government work. Bryan settled on 2026-11-04 which providers it may use
(durable-pi-workspace vault, decisions/2026-10-28-workspace-claude-subscriptions.md,
"SGG's model providers"; durable-pi-workspace#337). This script is the Hermes half of that
hard line. It fails, naming each violation, when:

- a provider named in the `sgg` config (model, fallbacks, auxiliary, delegation, cron,
  enabled `providers.*` blocks, plugin presets) or in an `sgg` cron job is outside the set;
- a provider in Hermes's own registry, or an alias of one, that is outside the set is not
  switched off with `providers.<name>.enabled: false` in the `sgg` config. Hermes checks that
  switch against the name as requested, before resolving aliases, so aliases need their own
  entry (`go` reaches `opencode-go` past `providers.opencode-go.enabled: false`);
- with --live: resolving `opencode-go` (and each of its aliases) under the `sgg` profile does
  not raise Hermes's disabled-provider error.

Unreadable config or registry is a violation, never a pass. The script never writes to
~/.hermes and never prints a credential. --print-disables prints the YAML the profile is
missing; --cron prints one message for no-agent delivery only when something is wrong.
"""

from __future__ import annotations

import argparse
import glob
import ipaddress
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, Callable, Iterable
from urllib.parse import urlsplit

import yaml

# SGG's approved Hermes providers, from the decision record named above. Anthropic (the Claude
# subscription plugin and the API), OpenAI direct (API and Codex), and local Studio models. Jev
# is not a Hermes provider. Adding one is Bryan's decision.
APPROVED_PROVIDERS = frozenset({
    "claude-subscription-directsdk-experimental",
    "anthropic",
    "openai",
    "openai-api",
    "openai-codex",
})
# An alias is approved only when every provider it resolves to is approved. A `base_url` (or
# `api`/`url`) beside an approved provider must be that provider's own host, read from
# Hermes's registry (the Claude plugin's is `process://claude-subscription-directsdk-experimental`).
URL_KEYS = ("base_url", "api", "url")
# Plus any provider named `local-*` that the profile itself defines under `providers:` with a
# loopback or Studio LAN endpoint.
LOCAL_PREFIX = "local-"
STUDIO_LAN_HOSTS = frozenset({"bryans-mac-studio.local"})
# Values that name no provider: inherit the main route.
INHERIT_VALUES = frozenset({"", "auto", "main"})
# Hermes's own reading of `enabled` (hermes_cli/config_providers.py, is_provider_enabled).
FALSE_WORDS = frozenset({"false", "0", "no", "off"})
DISABLED_ERROR = "is disabled in config"
LIVE_PROBE = "opencode-go"

MENTION = "@bryan:snowboardtechie.com"
HERMES_ROOT = Path(os.environ.get("HERMES_ROOT", Path.home() / ".hermes"))
PROFILE = "sgg"

REGISTRY_SNIPPET = r"""
import json
from hermes_cli.auth_plugin_providers import canonical_registry_rows
from hermes_cli.models_catalog_static import listed_canonical_providers
from hermes_cli import providers as hermes_providers
from providers import list_providers

names = set()
aliases = {}

def alias(name, canonical):
    name = str(name or "").strip().lower()
    canonical = str(canonical or "").strip().lower()
    if name and canonical and name != canonical:
        aliases.setdefault(name, set()).add(canonical)

base_urls = {}

def own_url(name, value):
    name = str(name or "").strip().lower()
    if name and isinstance(value, str) and value.strip():
        base_urls.setdefault(name, set()).add(value.strip())

for pid, row in canonical_registry_rows():
    names.add(pid)
    own_url(pid, getattr(row, "inference_base_url", ""))
names.update(entry.slug for entry in listed_canonical_providers())
try:  # `openai` is a direct-API alias with no registry row; its endpoint lives here.
    from hermes_cli.runtime_provider_custom import _DIRECT_API_BASE_URLS
    for name, value in _DIRECT_API_BASE_URLS.items():
        own_url(name, value)
except Exception:
    pass
for profile in list_providers():
    names.add(profile.name)
    own_url(profile.name, getattr(profile, "base_url", ""))
    for field in ("aliases", "overlay_aliases"):
        for name in getattr(profile, field, ()) or ():
            alias(name, profile.name)
for name, canonical in hermes_providers.ALIASES.items():
    alias(name, canonical)
# Older private tables some paths still consult; optional so a refactor doesn't hide the rest.
for module, attr in (("hermes_cli.auth", "_PROVIDER_ALIASES"), ("hermes_cli.models_catalog_static", "_PROVIDER_ALIASES")):
    try:
        table = getattr(__import__(module, fromlist=[attr]), attr)
        for name, canonical in table.items():
            alias(name, canonical)
    except Exception:
        pass
print(json.dumps({"providers": sorted(str(n).lower() for n in names if n),
                  "aliases": {k: sorted(v) for k, v in sorted(aliases.items())},
                  "base_urls": {k: sorted(v) for k, v in sorted(base_urls.items())}}))
"""

LIVE_SNIPPET = r"""
import json, sys
from hermes_cli.runtime_provider import resolve_runtime_provider
try:
    resolve_runtime_provider(requested=sys.argv[1])
except BaseException as error:
    print(json.dumps({"raised": True, "type": type(error).__name__, "message": str(error)[:300]}))
else:
    print(json.dumps({"raised": False}))
"""


class Unreadable(Exception):
    """A file or the registry could not be read; reported as a violation."""


# ── reading ───────────────────────────────────────────────────────────────────────────────


def load_config(home: Path) -> dict:
    path = home / "config.yaml"
    try:
        value = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, yaml.YAMLError) as error:
        raise Unreadable(f"cannot read {path}: {type(error).__name__}") from None
    if not isinstance(value, dict):
        raise Unreadable(f"{path} is not a YAML mapping")
    return value


def load_jobs(home: Path) -> list[dict]:
    path = home / "cron" / "jobs.json"
    if not path.exists():
        return []
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise Unreadable(f"cannot read {path}: {type(error).__name__}") from None
    jobs = value.get("jobs") if isinstance(value, dict) else value
    if not isinstance(jobs, list):
        raise Unreadable(f"{path} has no jobs list")
    return [job for job in jobs if isinstance(job, dict)]


def hermes_python() -> str | None:
    explicit = os.environ.get("HERMES_PYTHON")
    if explicit:
        return explicit
    found = glob.glob(str(HERMES_ROOT / "installs" / "*" / "environments" / "*" / "venv" / "bin" / "python"))
    return max(found, key=os.path.getmtime) if found else None


def run_hermes(python: str | None, home: Path, snippet: str, *args: str) -> dict:
    """Run *snippet* in the Hermes venv with HERMES_HOME=*home*. Only its JSON line is read;
    stderr is never echoed, so nothing Hermes logs can leak into our output."""
    if not python:
        raise Unreadable("no Hermes venv python found (set HERMES_PYTHON)")
    env = dict(os.environ, HERMES_HOME=str(home))
    try:
        result = subprocess.run([python, "-c", snippet, *args], env=env, cwd=str(home),
                                capture_output=True, text=True, timeout=120)
    except (OSError, subprocess.TimeoutExpired) as error:
        raise Unreadable(f"Hermes probe did not run: {type(error).__name__}") from None
    lines = [line for line in result.stdout.splitlines() if line.startswith("{")]
    if result.returncode != 0 or not lines:
        raise Unreadable(f"Hermes probe exited {result.returncode} with no result")
    try:
        return json.loads(lines[-1])
    except json.JSONDecodeError:
        raise Unreadable("Hermes probe printed an unparsable result") from None


def read_registry(python: str | None, home: Path) -> dict:
    """Every provider name Hermes's registry knows under *home*, and its aliases."""
    value = run_hermes(python, home, REGISTRY_SNIPPET)
    if not value.get("providers"):
        raise Unreadable("Hermes's provider registry came back empty")
    return value


def resolve_live(python: str | None, home: Path, name: str) -> dict:
    return run_hermes(python, home, LIVE_SNIPPET, name)


# ── rules ─────────────────────────────────────────────────────────────────────────────────


def enabled(block: Any) -> bool:
    if not isinstance(block, dict):
        return True
    flag = block.get("enabled", True)
    if isinstance(flag, str):
        return flag.strip().lower() not in FALSE_WORDS
    return bool(flag)


def endpoint(block: dict) -> str:
    """The URL a block points at: the first `base_url`/`api`/`url` value that has a scheme and host."""
    for key in URL_KEYS:
        value = block.get(key)
        if isinstance(value, str) and value.strip():
            parts = urlsplit(value.strip())
            if parts.scheme and parts.netloc:
                return value.strip()
    return ""


def host_key(url: str) -> str:
    parts = urlsplit(url)
    host = (parts.hostname or "").lower()
    if not host:
        return ""
    return f"process:{host}" if parts.scheme == "process" else host


def local_host(url: str) -> bool:
    host = (urlsplit(url).hostname or "").lower()
    if not host:
        return False
    if host == "localhost" or host in STUDIO_LAN_HOSTS:
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def bare(name: str) -> str:
    name = name.strip().lower()
    return name.split(":", 1)[1] if name.startswith("custom:") else name


def local_provider_ok(name: str, cfg: dict) -> bool:
    if not name.startswith(LOCAL_PREFIX):
        return False
    providers = cfg.get("providers")
    block = providers.get(name) if isinstance(providers, dict) else None
    return isinstance(block, dict) and enabled(block) and local_host(endpoint(block))


def approved_targets(name: str, aliases: dict[str, list[str]]) -> list[str]:
    """The approved providers *name* resolves to, or [] when it names anything unapproved."""
    if name in APPROVED_PROVIDERS:
        return [name]
    targets = aliases.get(name) or []
    return list(targets) if targets and all(target in APPROVED_PROVIDERS for target in targets) else []


def approved(name: str, cfg: dict, aliases: dict[str, list[str]]) -> bool:
    name = bare(name)
    return local_provider_ok(name, cfg) or bool(approved_targets(name, aliases))


def own_hosts(name: str, registry: dict) -> set[str]:
    base_urls = registry.get("base_urls") or {}
    targets = approved_targets(bare(name), registry.get("aliases") or {})
    return {host_key(url) for target in targets for url in base_urls.get(target, [])} - {""}


def approved_hosts(registry: dict) -> set[str]:
    hosts: set[str] = set()
    for name in APPROVED_PROVIDERS:
        hosts |= own_hosts(name, registry)
    return hosts


def _containers(node: Any, path: str) -> Iterable[tuple[str, dict]]:
    if isinstance(node, dict):
        yield path, node
        for key, value in node.items():
            yield from _containers(value, f"{path}.{key}" if path else str(key))
    elif isinstance(node, list):
        for index, value in enumerate(node):
            yield from _containers(value, f"{path}[{index}]")


# A reference: (where the provider is named, provider name or None to inherit, endpoint, where it is).
Ref = tuple[str, "str | None", str, str]


def _refs_of(path: str, block: dict) -> list[Ref]:
    url = endpoint(block)
    url_where = next((f"{path}.{key}" for key in URL_KEYS if block.get(key) == url), path) if url else ""
    named = [(f"{path}.{key}", block[key]) for key in ("provider", "model_provider")
             if key in block and not isinstance(block[key], (dict, list))]
    refs: list[Ref] = []
    for where, value in named:
        name = None if value is None or str(value).strip().lower() in INHERIT_VALUES else str(value)
        refs.append((where, name, url, url_where))
    if not named and url:
        refs.append((path, None, url, url_where))
    return refs


def config_refs(cfg: dict) -> list[Ref]:
    """Every place the config names a provider or sets an endpoint for one."""
    refs: list[Ref] = []
    model = cfg.get("model")
    if isinstance(model, dict):
        refs += _refs_of("model", model)
    for section in ("fallback_providers", "fallback_model", "auxiliary", "delegation", "moa"):
        if section not in cfg:
            continue
        if section == "fallback_providers" and isinstance(cfg[section], list):
            refs += [(f"{section}[{index}]", value, "", "") for index, value in enumerate(cfg[section])
                     if isinstance(value, str) and value.strip().lower() not in INHERIT_VALUES]
        for path, block in _containers(cfg[section], section):
            refs += _refs_of(path, block)
    cron = cfg.get("cron")
    if isinstance(cron, dict):
        refs += _refs_of("cron", cron)
    plugins = cfg.get("plugins")
    if isinstance(plugins, dict):
        for path, block in _containers(plugins, "plugins"):
            if re.search(r"\.settings\.presets\.[^.]+$", path):
                refs += _refs_of(path, block)
    return refs


def endpoint_violation(ref: Ref, cfg: dict, registry: dict) -> str | None:
    where, name, url, url_where = ref
    if not url:
        return None
    host = host_key(url) or "(none)"
    if name is None:
        if local_host(url) or host in approved_hosts(registry):
            return None
        return (f"{url_where} points at host {host!r} with no provider named,"
                " and that host is no approved provider's")
    if not approved(name, cfg, registry.get("aliases") or {}):
        return None  # already reported as an unapproved provider
    if bare(name).startswith(LOCAL_PREFIX):
        return None if local_host(url) else (
            f"{url_where} sends {name!r} to host {host!r}, which is not loopback or Studio's LAN")
    own = own_hosts(name, registry)
    if host in own:
        return None
    return (f"{url_where} sends {name!r} to host {host!r}, not its own"
            f" ({', '.join(sorted(own)) or 'none known to Hermes'})")


def config_violations(cfg: dict, registry: dict) -> list[str]:
    aliases = registry.get("aliases") or {}
    found = []
    for ref in config_refs(cfg):
        where, name, _url, _url_where = ref
        if name is not None and not approved(name, cfg, aliases):
            found.append(f"{where} names provider {name!r}, which SGG may not use")
        problem = endpoint_violation(ref, cfg, registry)
        if problem:
            found.append(problem)
    providers = cfg.get("providers")
    if isinstance(providers, dict):
        for name, block in providers.items():
            if not enabled(block):
                continue
            name = str(name).strip().lower()
            if name.startswith(LOCAL_PREFIX) and not local_provider_ok(name, cfg):
                url = endpoint(block) if isinstance(block, dict) else ""
                found.append(f"providers.{name} is enabled with endpoint {url or '(none)'!r},"
                             " which is not loopback or Studio's LAN")
            elif not approved(name, cfg, aliases):
                found.append(f"providers.{name} is enabled, and SGG may not use {name!r}")
            elif isinstance(block, dict) and not name.startswith(LOCAL_PREFIX):
                problem = endpoint_violation((f"providers.{name}", name, endpoint(block), f"providers.{name}"),
                                             cfg, registry)
                if problem:
                    found.append(problem)
    return found


def cron_violations(jobs: list[dict], cfg: dict, registry: dict) -> list[str]:
    aliases = registry.get("aliases") or {}
    found = []
    for job in jobs:
        label = f"cron job {job.get('name') or job.get('id')!r}"
        value = job.get("provider")
        name = None if value is None or str(value).strip().lower() in INHERIT_VALUES else str(value)
        if name is not None and not approved(name, cfg, aliases):
            found.append(f"{label} names provider {name!r}, which SGG may not use")
        url = job.get("base_url") if isinstance(job.get("base_url"), str) else ""
        problem = endpoint_violation((label, name, url.strip(), f"{label} base_url"), cfg, registry)
        if problem:
            found.append(problem)
    return found


def missing_disables(cfg: dict, registry: dict) -> list[str]:
    """Registry providers and aliases outside the approved set that the config leaves enabled."""
    providers = cfg.get("providers")
    if not isinstance(providers, dict):
        providers = {}
    aliases = registry.get("aliases") or {}
    candidates = set(registry.get("providers") or []) | set(aliases)
    missing = []
    for name in sorted(candidates):
        if approved(name, cfg, aliases):
            continue
        if name not in providers or enabled(providers.get(name)):
            missing.append(name)
    return missing


def registry_violations(cfg: dict, registry: dict) -> list[str]:
    aliases = registry.get("aliases") or {}
    found = []
    for name in missing_disables(cfg, registry):
        via = f" (an alias of {', '.join(aliases[name])})" if name in aliases else ""
        found.append(f"Hermes provider {name!r}{via} is not disabled: providers.{name}.enabled: false is missing")
    return found


def live_violations(results: dict[str, dict]) -> list[str]:
    found = []
    for name, result in results.items():
        if result.get("raised") and DISABLED_ERROR in str(result.get("message", "")):
            continue
        if result.get("raised"):
            found.append(f"resolving {name!r} under sgg raised {result.get('type')}: {result.get('message')}"
                         " instead of the disabled-provider error")
        else:
            found.append(f"resolving {name!r} under sgg succeeded; it must fail as disabled")
    return found


# ── running ───────────────────────────────────────────────────────────────────────────────


def check(home: Path, *, live: bool, python: str | None,
          registry_reader: Callable[[str | None, Path], dict] = read_registry,
          live_resolver: Callable[[str | None, Path, str], dict] = resolve_live) -> list[str]:
    try:
        cfg = load_config(home)
    except Unreadable as error:
        return [str(error)]
    violations: list[str] = []
    try:
        registry = registry_reader(python, home)
    except Unreadable as error:
        violations.append(f"cannot read Hermes's provider registry: {error}")
        registry = {"providers": [], "aliases": {}, "base_urls": {}}
    aliases = registry.get("aliases") or {}
    violations += config_violations(cfg, registry)
    try:
        violations += cron_violations(load_jobs(home), cfg, registry)
    except Unreadable as error:
        violations.append(str(error))
    violations += registry_violations(cfg, registry)
    if live:
        names = [LIVE_PROBE] + sorted(a for a, targets in aliases.items() if LIVE_PROBE in targets)
        results = {}
        for name in names:
            try:
                results[name] = live_resolver(python, home, name)
            except Unreadable as error:
                violations.append(f"cannot resolve {name!r} under sgg: {error}")
        violations += live_violations(results)
    return violations


def disables_yaml(names: list[str]) -> str:
    if not names:
        return ""
    return yaml.safe_dump({"providers": {name: {"enabled": False} for name in names}},
                          sort_keys=False, default_flow_style=False)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--home", type=Path, default=HERMES_ROOT / "profiles" / PROFILE,
                        help="the sgg profile's HERMES_HOME (default: %(default)s)")
    parser.add_argument("--live", action="store_true", help="also resolve opencode-go under the profile")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--cron", action="store_true", help="silent when clean; one alert message otherwise; exit 0")
    mode.add_argument("--print-disables", action="store_true",
                      help="print the providers.<name>: {enabled: false} entries the profile is missing")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None, *,
         registry_reader: Callable[[str | None, Path], dict] = read_registry,
         live_resolver: Callable[[str | None, Path, str], dict] = resolve_live) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    python = hermes_python()
    if args.print_disables:
        try:
            names = missing_disables(load_config(args.home), registry_reader(python, args.home))
        except Unreadable as error:
            print(f"sgg provider check: {error}", file=sys.stderr)
            return 2
        sys.stdout.write(disables_yaml(names))
        return 0
    violations = check(args.home, live=args.live, python=python,
                       registry_reader=registry_reader, live_resolver=live_resolver)
    if args.cron:
        if violations:
            lines = [f"{MENTION} The Hermes sgg profile can reach providers SGG may not use"
                     f" ({len(violations)} problem{'s' if len(violations) != 1 else ''}):"]
            lines += [f"- {violation}" for violation in violations]
            lines.append("SGG may use only Anthropic, OpenAI direct, Jev and local Studio models"
                         " (decision 2026-10-28, \"SGG's model providers\"). Missing disables:"
                         " check-sgg-providers.py --print-disables.")
            print("\n".join(lines))
        return 0
    if violations:
        print(f"sgg provider check FAILED ({len(violations)}):")
        for violation in violations:
            print(f"- {violation}")
        return 1
    print("sgg provider check passed" + (" (live)" if args.live else ""))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
