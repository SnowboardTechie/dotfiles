#!/usr/bin/env python3
"""Tests for the Hermes sgg provider check. The registry and the --live probe are stubbed."""

from __future__ import annotations

import contextlib
import copy
import importlib.util
import io
import json
import tempfile
import unittest
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent
SCRIPT = HERE / "scripts" / "check-sgg-providers.py"

spec = importlib.util.spec_from_file_location("check_sgg_providers", SCRIPT)
assert spec is not None and spec.loader is not None
sgg = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sgg)

REGISTRY = {
    "providers": ["anthropic", "claude-subscription-directsdk-experimental", "custom", "openai-api",
                  "openai-codex", "opencode-go", "openrouter"],
    "aliases": {"claude": ["anthropic"], "codex": ["openai-codex"], "go": ["opencode-go"],
                "local": ["custom"], "mixed": ["anthropic", "openrouter"], "openai": ["openrouter"],
                "openai-direct": ["openai-api"], "or": ["openrouter"]},
    "base_urls": {
        "anthropic": ["https://api.anthropic.com"],
        "claude-subscription-directsdk-experimental": ["process://claude-subscription-directsdk-experimental"],
        "openai": ["https://api.openai.com/v1"],
        "openai-api": ["https://api.openai.com/v1"],
        "openai-codex": ["https://chatgpt.com/backend-api/codex"],
        "opencode-go": ["https://opencode.ai/zen/go/v1"],
    },
}
DISABLES = {name: {"enabled": False}
            for name in ("custom", "go", "local", "mixed", "opencode-go", "openrouter", "or")}
PLUGIN = "claude-subscription-directsdk-experimental"
GO_ANTHROPIC = "https://opencode.ai/zen/go/v1"

CLEAN = {
    "model": {"default": "claude-opus-5-5", "provider": PLUGIN, "base_url": f"process://{PLUGIN}"},
    "auxiliary": {"title_generation": {"provider": PLUGIN, "model": "claude-sonnet-5-5"},
                  "compression": {"provider": "auto"}},
    "delegation": {"max_iterations": 250, "provider": ""},
    "fallback_providers": [{"provider": "anthropic", "model": "claude-sonnet-5-5",
                            "base_url": "https://api.anthropic.com/v1"}, "openai-codex", "openai-api"],
    "cron": {"model": "claude-sonnet-5-5", "model_provider": PLUGIN},
    "plugins": {"entries": {"herdr-gateway": {"settings": {"presets": {
        "hermes-claude": {"kind": "hermes", "provider": PLUGIN}, "claude-opus": {"kind": "claude"}}}}}},
    "providers": {
        "local-gemma4": {"api": "http://127.0.0.1:11434/v1", "default_model": "gemma4"},
        "local-studio": {"base_url": "http://Bryans-Mac-Studio.local:11434/v1"},
        **DISABLES,
    },
}
JOBS = {"jobs": [{"name": "Brief", "provider": PLUGIN}, {"name": "Prep", "provider": None, "base_url": None},
                 {"name": "Direct", "provider": "openai", "base_url": "https://api.openai.com/v1"},
                 {"name": "Local", "provider": "local-gemma4"}]}

DISABLED_RESULT = {"raised": True, "type": "ValueError",
                   "message": "provider 'opencode-go' is disabled in config (providers.opencode-go.enabled: false)"}


def registry(_python, _home):
    return copy.deepcopy(REGISTRY)


def live_disabled(_python, _home, _name):
    return dict(DISABLED_RESULT)


def live_resolves(_python, _home, _name):
    return {"raised": False}


class Profile:
    def __init__(self, config=None, jobs=None, raw: str | None = None):
        self.directory = tempfile.TemporaryDirectory()
        self.home = Path(self.directory.name)
        if raw is not None:
            (self.home / "config.yaml").write_text(raw, encoding="utf-8")
        else:
            (self.home / "config.yaml").write_text(yaml.safe_dump(config if config is not None else CLEAN))
        (self.home / "cron").mkdir()
        (self.home / "cron" / "jobs.json").write_text(json.dumps(jobs if jobs is not None else JOBS))

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.directory.cleanup()

    def run(self, *args: str, live=live_disabled, reader=registry) -> tuple[int, str]:
        out = io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
            code = sgg.main(["--home", str(self.home), *args], registry_reader=reader, live_resolver=live)
        return code, out.getvalue()


def changed(**updates) -> dict:
    config = copy.deepcopy(CLEAN)
    for path, value in updates.items():
        node = config
        keys = path.split("__")
        for key in keys[:-1]:
            node = node.setdefault(key, {})
        node[keys[-1]] = value
    return config


class CleanProfile(unittest.TestCase):
    def test_clean_profile_passes(self) -> None:
        with Profile() as profile:
            self.assertEqual(profile.run(), (0, "sgg provider check passed\n"))
            self.assertEqual(profile.run("--live"), (0, "sgg provider check passed (live)\n"))
            self.assertEqual(profile.run("--cron", "--live"), (0, ""))

    def test_alias_of_an_approved_provider_passes(self) -> None:
        with Profile(changed(model={"provider": "claude", "base_url": "https://api.anthropic.com"})) as profile:
            self.assertEqual(profile.run()[0], 0)


class ConfigRule(unittest.TestCase):
    def assertFails(self, config, *needles, jobs=None) -> None:
        with Profile(config, jobs) as profile:
            code, out = profile.run()
        self.assertEqual(code, 1, out)
        for needle in needles:
            self.assertIn(needle, out)

    def test_model_provider(self) -> None:
        self.assertFails(changed(model__provider="opencode-go"), "model.provider names provider 'opencode-go'")

    def test_alias_of_a_forbidden_provider(self) -> None:
        self.assertFails(changed(model__provider="go"), "model.provider names provider 'go'")

    def test_fallback_providers(self) -> None:
        self.assertFails(changed(fallback_providers=["openrouter"]), "fallback_providers[0] names provider 'openrouter'")
        self.assertFails(changed(fallback_providers=[{"provider": "opencode-go", "model": "glm"}]),
                         "fallback_providers[0].provider names provider 'opencode-go'")

    def test_auxiliary(self) -> None:
        self.assertFails(changed(auxiliary__vision={"provider": "openrouter"}),
                         "auxiliary.vision.provider names provider 'openrouter'")

    def test_delegation(self) -> None:
        self.assertFails(changed(delegation__provider="opencode-go"), "delegation.provider names provider 'opencode-go'")

    def test_cron_model_provider(self) -> None:
        self.assertFails(changed(cron__model_provider="opencode-go"), "cron.model_provider names provider 'opencode-go'")

    def test_plugin_preset(self) -> None:
        config = copy.deepcopy(CLEAN)
        config["plugins"]["entries"]["herdr-gateway"]["settings"]["presets"]["hermes-claude"]["provider"] = "go"
        self.assertFails(config, "plugins.entries.herdr-gateway.settings.presets.hermes-claude.provider names provider 'go'")

    def test_enabled_unapproved_providers_block(self) -> None:
        self.assertFails(changed(providers__deepseek={"base_url": "https://api.deepseek.com"}),
                         "providers.deepseek is enabled, and SGG may not use 'deepseek'")

    def test_local_with_cloud_base_url(self) -> None:
        config = changed(providers__local_cloud={"base_url": "https://opencode.ai/zen/go/v1"})
        config["providers"]["local-cloud"] = config["providers"].pop("local_cloud")
        config["model"]["provider"] = "local-cloud"
        self.assertFails(config, "providers.local-cloud is enabled with endpoint 'https://opencode.ai/zen/go/v1'",
                         "model.provider names provider 'local-cloud'")

    def test_local_not_defined_in_profile(self) -> None:
        self.assertFails(changed(model__provider="local-elsewhere"), "model.provider names provider 'local-elsewhere'")


class CronRule(unittest.TestCase):
    def test_cron_job_provider(self) -> None:
        jobs = {"jobs": [*JOBS["jobs"], {"name": "Sneaky", "provider": "opencode-go"}]}
        with Profile(jobs=jobs) as profile:
            code, out = profile.run()
        self.assertEqual(code, 1)
        self.assertIn("cron job 'Sneaky' names provider 'opencode-go'", out)

    def test_unreadable_jobs(self) -> None:
        with Profile() as profile:
            (profile.home / "cron" / "jobs.json").write_text("{not json")
            code, out = profile.run()
        self.assertEqual(code, 1)
        self.assertIn("jobs.json", out)


class RegistryRule(unittest.TestCase):
    def test_missing_disable_is_named(self) -> None:
        config = copy.deepcopy(CLEAN)
        del config["providers"]["opencode-go"]
        config["providers"]["go"] = {"enabled": True}
        with Profile(config) as profile:
            code, out = profile.run()
        self.assertEqual(code, 1)
        self.assertIn("Hermes provider 'opencode-go' is not disabled", out)
        self.assertIn("Hermes provider 'go' (an alias of opencode-go) is not disabled", out)

    def test_string_false_counts_as_disabled(self) -> None:
        config = copy.deepcopy(CLEAN)
        config["providers"]["opencode-go"] = {"enabled": "off"}
        with Profile(config) as profile:
            self.assertEqual(profile.run()[0], 0)

    def test_new_registry_provider_is_caught(self) -> None:
        def grown(_python, _home):
            value = registry(_python, _home)
            value["providers"].append("brand-new-cloud")
            return value

        with Profile() as profile:
            code, out = profile.run(reader=grown)
        self.assertEqual(code, 1)
        self.assertIn("Hermes provider 'brand-new-cloud' is not disabled", out)

    def test_unreadable_registry_fails(self) -> None:
        def broken(_python, _home):
            raise sgg.Unreadable("Hermes probe exited 1 with no result")

        with Profile() as profile:
            code, out = profile.run(reader=broken)
        self.assertEqual(code, 1)
        self.assertIn("cannot read Hermes's provider registry", out)


class LiveRule(unittest.TestCase):
    def test_resolving_go_must_raise_disabled(self) -> None:
        with Profile() as profile:
            self.assertEqual(profile.run()[0], 0)  # without --live the probe never runs
            code, out = profile.run("--live", live=live_resolves)
        self.assertEqual(code, 1)
        self.assertIn("resolving 'opencode-go' under sgg succeeded", out)
        self.assertIn("resolving 'go' under sgg succeeded", out)

    def test_other_errors_are_not_enough(self) -> None:
        def missing_key(_python, _home, name):
            return {"raised": True, "type": "AuthError", "message": f"No usable credentials found for provider {name!r}."}

        with Profile() as profile:
            code, out = profile.run("--live", live=missing_key)
        self.assertEqual(code, 1)
        self.assertIn("raised AuthError", out)

    def test_probe_names_come_from_the_registry(self) -> None:
        seen = []

        def record(_python, _home, name):
            seen.append(name)
            return dict(DISABLED_RESULT)

        with Profile() as profile:
            profile.run("--live", live=record)
        self.assertEqual(seen, ["opencode-go", "go"])


class Unreadable(unittest.TestCase):
    def test_bad_yaml(self) -> None:
        with Profile(raw="model: [unclosed\n") as profile:
            code, out = profile.run()
        self.assertEqual(code, 1)
        self.assertIn("cannot read", out)

    def test_not_a_mapping(self) -> None:
        with Profile(raw="- just a list\n") as profile:
            code, out = profile.run()
        self.assertEqual(code, 1)
        self.assertIn("not a YAML mapping", out)

    def test_missing_config(self) -> None:
        with Profile() as profile:
            (profile.home / "config.yaml").unlink()
            code, out = profile.run()
        self.assertEqual(code, 1)
        self.assertIn("cannot read", out)

    def test_print_disables_refuses_unreadable(self) -> None:
        with Profile(raw="model: [unclosed\n") as profile:
            self.assertEqual(profile.run("--print-disables")[0], 2)


class PrintDisables(unittest.TestCase):
    def test_merged_output_makes_it_pass(self) -> None:
        config = copy.deepcopy(CLEAN)
        for name in DISABLES:
            del config["providers"][name]
        config["providers"]["openrouter"] = {"enabled": True, "base_url": "https://openrouter.ai/api/v1"}
        with Profile(config) as profile:
            self.assertEqual(profile.run()[0], 1)
            code, block = profile.run("--print-disables")
            self.assertEqual(code, 0)
            patch = yaml.safe_load(block)
            self.assertEqual(sorted(patch["providers"]), sorted(DISABLES))
            for name, entry in patch["providers"].items():
                config["providers"].setdefault(name, {}).update(entry)
            (profile.home / "config.yaml").write_text(yaml.safe_dump(config))
            self.assertEqual(profile.run(), (0, "sgg provider check passed\n"))
            self.assertEqual(profile.run("--print-disables"), (0, ""))


class ApprovedOpenAI(unittest.TestCase):
    def test_openai_api_and_its_alias_are_approved_and_never_disabled(self) -> None:
        config = copy.deepcopy(CLEAN)
        for name in DISABLES:
            del config["providers"][name]
        config["model"] = {"provider": "openai-direct", "base_url": "https://api.openai.com/v1"}
        with Profile(config) as profile:
            code, out = profile.run()
            self.assertNotIn("openai-api", out)
            self.assertNotIn("openai-direct", out)
            block = yaml.safe_load(profile.run("--print-disables")[1])
        self.assertNotIn("openai-api", block["providers"])
        self.assertNotIn("openai-direct", block["providers"])
        self.assertIn("mixed", block["providers"])  # resolves to an approved and an unapproved provider


class EndpointRule(unittest.TestCase):
    def assertFails(self, config, *needles, jobs=None) -> None:
        with Profile(config, jobs) as profile:
            code, out = profile.run()
        self.assertEqual(code, 1, out)
        for needle in needles:
            self.assertIn(needle, out)

    def test_approved_provider_moved_anywhere_it_is_named(self) -> None:
        moved = {"provider": "anthropic", "base_url": GO_ANTHROPIC}
        cases = {
            "model.base_url": changed(model=dict(moved)),
            "fallback_providers[0].base_url": changed(fallback_providers=[dict(moved)]),
            "fallback_model.base_url": changed(fallback_model=dict(moved)),
            "auxiliary.vision.base_url": changed(auxiliary__vision=dict(moved)),
            "delegation.base_url": changed(delegation=dict(moved)),
            "moa.slots[0].base_url": changed(moa={"slots": [dict(moved)]}),
            "cron.base_url": changed(cron={"model_provider": "anthropic", "base_url": GO_ANTHROPIC}),
        }
        preset = copy.deepcopy(CLEAN)
        preset["plugins"]["entries"]["herdr-gateway"]["settings"]["presets"]["hermes-claude"]["base_url"] = GO_ANTHROPIC
        cases["plugins.entries.herdr-gateway.settings.presets.hermes-claude.base_url"] = preset
        for where, config in cases.items():
            with self.subTest(where=where):
                name = "'anthropic'" if where != "plugins.entries.herdr-gateway.settings.presets.hermes-claude.base_url" \
                    else f"'{PLUGIN}'"
                self.assertFails(config, f"{where} sends {name} to host 'opencode.ai', not its own")

    def test_api_and_url_keys_count(self) -> None:
        self.assertFails(changed(auxiliary__vision={"provider": "anthropic", "api": GO_ANTHROPIC}),
                         "auxiliary.vision.api sends 'anthropic' to host 'opencode.ai'")
        self.assertFails(changed(auxiliary__vision={"provider": "anthropic", "url": GO_ANTHROPIC}),
                         "auxiliary.vision.url sends 'anthropic' to host 'opencode.ai'")

    def test_alias_uses_its_providers_hosts(self) -> None:
        self.assertFails(changed(model={"provider": "claude", "base_url": GO_ANTHROPIC}),
                         "model.base_url sends 'claude' to host 'opencode.ai', not its own (api.anthropic.com)")

    def test_plugin_must_stay_on_its_process(self) -> None:
        self.assertFails(changed(model={"provider": PLUGIN, "base_url": "process://something-else"}),
                         f"model.base_url sends '{PLUGIN}' to host 'process:something-else'")

    def test_cron_job_base_url(self) -> None:
        jobs = {"jobs": [{"name": "Moved", "provider": "anthropic", "base_url": GO_ANTHROPIC}]}
        self.assertFails(CLEAN, "cron job 'Moved' base_url sends 'anthropic' to host 'opencode.ai'", jobs=jobs)

    def test_cron_job_inheriting_with_foreign_base_url(self) -> None:
        jobs = {"jobs": [{"name": "Bare", "provider": None, "base_url": GO_ANTHROPIC}]}
        self.assertFails(CLEAN, "cron job 'Bare' base_url points at host 'opencode.ai' with no provider named", jobs=jobs)

    def test_providers_block_of_an_approved_provider(self) -> None:
        self.assertFails(changed(providers__anthropic={"base_url": GO_ANTHROPIC}),
                         "providers.anthropic sends 'anthropic' to host 'opencode.ai'")

    def test_local_reference_with_cloud_base_url(self) -> None:
        self.assertFails(changed(fallback_providers=[{"provider": "local-gemma4", "base_url": GO_ANTHROPIC}]),
                         "fallback_providers[0].base_url sends 'local-gemma4' to host 'opencode.ai',"
                         " which is not loopback or Studio's LAN")

    def test_inheriting_model_base_url(self) -> None:
        self.assertFails(changed(model={"provider": "auto", "base_url": GO_ANTHROPIC}),
                         "model.base_url points at host 'opencode.ai' with no provider named")
        self.assertFails(changed(model={"default": "x", "base_url": GO_ANTHROPIC}),
                         "model.base_url points at host 'opencode.ai' with no provider named")
        for url in ("https://api.anthropic.com", "http://127.0.0.1:11434/v1"):
            with Profile(changed(model={"provider": "", "base_url": url})) as profile:
                self.assertEqual(profile.run()[0], 0, url)

    def test_unknown_own_host_fails_closed(self) -> None:
        def no_urls(_python, _home):
            value = registry(_python, _home)
            del value["base_urls"]["openai-codex"]
            return value

        with Profile(changed(model={"provider": "openai-codex", "base_url": "https://chatgpt.com/backend-api/codex"})) as profile:
            self.assertEqual(profile.run()[0], 0)
            code, out = profile.run(reader=no_urls)
        self.assertEqual(code, 1)
        self.assertIn("not its own (none known to Hermes)", out)


class CronMode(unittest.TestCase):
    def test_one_message_and_exit_zero(self) -> None:
        with Profile(changed(model__provider="opencode-go")) as profile:
            code, out = profile.run("--cron")
        self.assertEqual(code, 0)
        self.assertTrue(out.startswith("@bryan:snowboardtechie.com The Hermes sgg profile"))
        self.assertIn("- model.provider names provider 'opencode-go'", out)
        self.assertNotIn("\n\n", out.strip())


if __name__ == "__main__":
    unittest.main()
