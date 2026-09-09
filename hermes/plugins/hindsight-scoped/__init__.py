"""Hindsight with automatic memory scoped to primary interactive sessions.

Use Hermes's supported external MemoryProvider extension point. The bundled
provider owns all transport, credentials, storage, tools, and lifecycle behavior.
"""
from __future__ import annotations

import logging

from agent.memory_provider import is_trivial_prompt  # pyright: ignore[reportMissingImports]
from agent.skill_commands import extract_user_instruction_from_skill_message  # pyright: ignore[reportMissingImports]
from hermes_cli.config import load_config_readonly  # pyright: ignore[reportMissingImports]
from plugins.memory.hindsight import HindsightMemoryProvider  # pyright: ignore[reportMissingImports]
from tools.hook_output_spill import get_spill_config  # pyright: ignore[reportMissingImports]

logger = logging.getLogger(__name__)


class ScopedHindsightMemoryProvider(HindsightMemoryProvider):
    @property
    def name(self) -> str:
        return "hindsight-scoped"

    def initialize(self, session_id: str, **kwargs) -> None:
        super().initialize(session_id, **kwargs)
        # Cron currently passes agent_context="primary", so platform is an
        # independent boundary. Never mutate shared config or process env:
        # gateway chats and scheduler runs may coexist in the same process.
        if kwargs.get("platform") == "cron" or kwargs.get("agent_context", "primary") != "primary":
            self._memory_mode = "tools"
            self._auto_recall = False
            self._auto_retain = False

    def prefetch(self, query: str, *, session_id: str = "") -> str:
        # The supported pre_llm_call hook owns automatic recall. The core
        # MemoryManager imposes an unconfigurable 8s deadline here, shorter than
        # measured Hindsight recall. Never issue a duplicate request or inject
        # the prior turn's memory after its deadline.
        return ""

    def queue_prefetch(self, query: str, *, session_id: str = "") -> None:
        pass


def recall_before_turn(*, session_id="", user_message="", platform="", parent_session_id="", **kwargs):
    # The host supplies these fields, not a string inside the user's prompt.
    if platform == "cron" or parent_session_id or not isinstance(user_message, str):
        return None
    config = load_config_readonly() or {}
    if (config.get("memory") or {}).get("provider") != "hindsight-scoped":
        return None
    query = extract_user_instruction_from_skill_message(user_message)
    if not query or is_trivial_prompt(query):
        return None
    provider = ScopedHindsightMemoryProvider()
    try:
        provider.initialize(session_id, platform=platform, agent_context="primary")
        if not provider._auto_recall or provider._memory_mode == "tools":
            return None
        # Below the supported plugin hook's 30s deadline. No core monkeypatch,
        # process-global timeout, model call, retain, or configuration mutation.
        provider._timeout = 25
        context = HindsightMemoryProvider.prefetch(provider, query, session_id=session_id)
        # A generic head/tail spill discards high-ranked facts after the first
        # 500 chars. Keep a bounded ranked prefix inline instead.
        cap = min(8000, get_spill_config()["max_chars"])
        if len(context) > cap:
            suffix = "\n[More recalled context omitted; use hindsight_recall for details.]"
            context = context[:max(0, cap - len(suffix))].rsplit("\n", 1)[0] + suffix
            context = context[:cap]
        logger.info("Hindsight automatic recall: session=%s memories=%d chars=%d",
                    session_id, provider._last_recall_count, len(context))
        return {"context": context} if context else None
    finally:
        provider.shutdown()


def register(ctx) -> None:
    ctx.register_memory_provider(ScopedHindsightMemoryProvider())
    # Provider discovery passes a collector without lifecycle hooks;
    # ordinary plugin discovery supplies the real PluginContext.
    if hasattr(ctx, "register_hook"):
        ctx.register_hook("pre_llm_call", recall_before_turn)
