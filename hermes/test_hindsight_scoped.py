"""Exercise the real Hermes provider lifecycle with only the remote API stubbed.

Run with Hermes's Python; no live configuration or memory bank is touched.
"""
from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

ROOT = Path(__file__).resolve().parent
PLUGIN = ROOT / "plugins" / "hindsight-scoped" / "__init__.py"

HAS_HERMES = importlib.util.find_spec("hindsight_client") is not None


@unittest.skipUnless(HAS_HERMES, "run with Hermes's Python for provider integration tests")
class ScopedHindsightTest(unittest.TestCase):
    def setUp(self):
        import hindsight_client  # pyright: ignore[reportMissingImports]
        from hermes_constants import reset_hermes_home_override, set_hermes_home_override  # pyright: ignore[reportMissingImports]

        spec = importlib.util.spec_from_file_location("scoped_hindsight_test", PLUGIN)
        assert spec and spec.loader
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        self.provider_class = module.ScopedHindsightMemoryProvider
        self.recall = module.recall_before_turn
        self.tmp = tempfile.TemporaryDirectory(prefix="hermes-memory-test-")
        self.addCleanup(self.tmp.cleanup)
        self.home = Path(self.tmp.name)
        self.config_path = self.home / "hindsight" / "config.json"
        self.config_path.parent.mkdir()
        self.config = {
            "mode": "local_external", "api_url": "http://127.0.0.1:1",
            "api_key": "unit-test-only", "bank_id": "unit-test",
            "memory_mode": "hybrid", "auto_recall": True, "auto_retain": True,
            "recall_sync": True, "retain_async": False,
            "recall_types": ["observation", "world", "experience"],
        }
        self.config_path.write_text(json.dumps(self.config))
        token = set_hermes_home_override(self.home)
        (self.home / "config.yaml").write_text("memory:\n  provider: hindsight-scoped\n")
        self.addCleanup(reset_hermes_home_override, token)
        self.client = SimpleNamespace(
            arecall=AsyncMock(return_value=SimpleNamespace(
                results=[SimpleNamespace(text="An authorized worktree trust prompt needs no second approval.")]
            )),
            aretain_batch=AsyncMock(return_value=SimpleNamespace()),
            aclose=AsyncMock(),
        )
        api = patch.object(hindsight_client, "Hindsight", return_value=self.client)
        api.start()
        self.addCleanup(api.stop)
        # The only other network boundary is the server version capability probe.
        version = patch("urllib.request.urlopen")
        response = version.start().return_value.__enter__.return_value
        response.read.return_value = b'{"version":"0.9.1"}'
        self.addCleanup(version.stop)

    def provider(self, platform="cli", agent_context="primary"):
        provider = self.provider_class()
        provider.initialize("test-" + platform, platform=platform, agent_context=agent_context)
        self.addCleanup(provider.shutdown)
        return provider

    def test_interactive_first_turn_automatically_recalls(self):
        for platform in ("cli", "desktop", "matrix"):
            with self.subTest(platform=platform):
                provider = self.provider(platform)
                text = self.recall(session_id="test-" + platform, platform=platform,
                                   user_message="Should I ask about trusting the authorized worktree?")["context"]
                self.assertIn("needs no second approval", text)
                self.assertEqual(provider.prefetch("No duplicate recall"), "")
        self.assertEqual(self.client.arecall.await_count, 3)
        self.assertEqual(self.client.arecall.call_args.kwargs["types"],
                         ["observation", "world", "experience"])

    def test_interactive_turn_automatically_retains(self):
        provider = self.provider()
        provider.sync_turn("Trust this authorized worktree without asking again.", "Understood.")
        provider.shutdown()
        self.client.aretain_batch.assert_awaited_once()
        content = self.client.aretain_batch.call_args.kwargs["items"][0]["content"]
        self.assertIn("without asking again", content)

    def test_cron_never_automatically_recalls_or_retains(self):
        # The installed scheduler labels agent_context=primary even for cron.
        provider = self.provider("cron", "primary")
        self.assertIsNone(self.recall(session_id="cron", platform="cron", user_message="Private meeting content"))
        self.assertEqual(provider.prefetch("Private meeting content"), "")
        provider.queue_prefetch("Private meeting content")
        provider.sync_turn("Private meeting content", "A meeting summary")
        provider.on_session_switch("second-cron-session")
        provider.shutdown()
        self.client.arecall.assert_not_awaited()
        self.client.aretain_batch.assert_not_awaited()
        self.assertIn("tools mode", provider.system_prompt_block())

    def test_nonprimary_context_keeps_explicit_memory_only(self):
        for context in ("cron", "subagent", "flush"):
            with self.subTest(context=context):
                provider = self.provider("cli", context)
                self.assertEqual(provider.prefetch("Do not inject this"), "")
                provider.sync_turn("Do not retain this", "Background response")
                provider.shutdown()
        self.client.arecall.assert_not_awaited()
        self.client.aretain_batch.assert_not_awaited()

    def test_cron_policy_does_not_mutate_config_or_sibling(self):
        before = self.config_path.read_bytes()
        cron = self.provider("cron")
        interactive = self.provider("cli")
        self.assertIn("needs no second approval", self.recall(
            session_id="interactive", platform="cli", user_message="Trust policy"
        )["context"])
        self.assertEqual(interactive.prefetch("No duplicate recall"), "")
        self.assertEqual(cron.prefetch("Trust policy"), "")
        self.assertEqual(self.config_path.read_bytes(), before)

    def test_explicit_tools_remain_available_for_authorized_callers(self):
        provider = self.provider("cron")
        self.assertEqual({tool["name"] for tool in provider.get_tool_schemas()},
                         {"hindsight_recall", "hindsight_retain", "hindsight_reflect"})
        self.assertIn("needs no second approval", provider.handle_tool_call(
            "hindsight_recall", {"query": "Trust policy"}
        ))
        self.client.arecall.assert_awaited_once()

    def test_explicit_configuration_opt_out_is_respected(self):
        self.config.update(auto_recall=False, auto_retain=False)
        self.config_path.write_text(json.dumps(self.config))
        provider = self.provider()
        self.assertIsNone(self.recall(session_id="opt-out", platform="cli", user_message="Trust policy"))
        self.assertEqual(provider.prefetch("Trust policy"), "")
        provider.sync_turn("Do not save", "Opted out")
        provider.shutdown()
        self.client.arecall.assert_not_awaited()
        self.client.aretain_batch.assert_not_awaited()


    def test_hook_skips_other_providers_subagents_and_trivial_turns(self):
        self.assertIsNone(self.recall(platform="cli", parent_session_id="parent", user_message="Trust policy"))
        self.assertIsNone(self.recall(platform="cli", user_message="continue"))
        (self.home / "config.yaml").write_text("memory:\n  provider: hindsight\n")
        self.assertIsNone(self.recall(platform="cli", user_message="Trust policy"))
        self.client.arecall.assert_not_awaited()

    def test_recall_timeout_is_bounded_below_hook_deadline(self):
        import hindsight_client  # pyright: ignore[reportMissingImports]

        self.recall(platform="cli", user_message="Trust policy")
        self.assertEqual(hindsight_client.Hindsight.call_args.kwargs["timeout"], 25.0)

    def test_recall_keeps_top_ranked_facts_inline_instead_of_head_tail_spill(self):
        from tools.hook_output_spill import spill_if_oversized  # pyright: ignore[reportMissingImports]

        self.client.arecall.return_value = SimpleNamespace(results=[
            SimpleNamespace(text="Current correction: independent sessions can run concurrently."),
            SimpleNamespace(text="Current correction: accept the authorized worktree trust prompt."),
        ] + [SimpleNamespace(text="Older context " + "x" * 300) for _ in range(60)])
        context = self.recall(platform="cli", user_message="What are the current corrections?")["context"]
        self.assertLessEqual(len(context), 8000)
        self.assertIn("independent sessions", context)
        self.assertIn("authorized worktree", context)
        self.assertEqual(spill_if_oversized(context), context)


if __name__ == "__main__":
    unittest.main()
