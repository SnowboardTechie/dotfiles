"""Request-level routing note: native Herdr workers for an authorized Matrix conversation.

A plugin skill is never listed in the system prompt's ``<available_skills>``, and an existing
conversation restores its persisted prompt, so neither reaches a conversation that already
learned to refuse. ``llm_request`` middleware runs on every provider request after Codex
preflight. For a non-delegated, trusted Matrix origin that the current settings admit, it
appends one delimited note to the provider's instruction surface. Anywhere else it adds
nothing. The note is guidance, not authorization: the handlers still authorize every herdr_*
call, and no other request field (history, tools, model, cache keys) is touched.
"""

from __future__ import annotations

import json

from . import schemas
from .policy import Refusal, authorize, load_settings, require_not_delegated, runtime_origin

FRAME_START = "<herdr-gateway-routing>"
FRAME_END = "</herdr-gateway-routing>"
MAX_LISTED = 16
NATIVE_TOOLS = frozenset(s["name"] for s in schemas.ALL)


def _listed(items: list[str]) -> str:
    more = len(items) - MAX_LISTED
    return "; ".join(items[:MAX_LISTED]) + (f"; and {more} more" if more > 0 else "")


def _declared(tools) -> set:
    """Function names a Chat Completions or Responses ``tools`` list declares."""
    names = set()
    for tool in tools if isinstance(tools, list) else []:
        if isinstance(tool, dict):
            fn = tool.get("function")
            names.add((fn if isinstance(fn, dict) else tool).get("name"))
    return names


def note(settings: dict, entry: dict, tools_available: bool) -> str:
    """The routing note for one admitted origin, from validated settings only."""
    head = ("Routing note from the herdr-gateway plugin for this authorized Matrix conversation. "
            "It is guidance, not authorization.")
    no_pane = ("Matrix has no injected CLI caller pane: missing HERDR_ENV/HERDR_PANE_ID is normal "
               "here and never a blocker. Never substitute delegate_task, a background task or the "
               "CLI handoff helper for a requested visible worker, and disregard any earlier reply in "
               "this conversation that refused visible workers for that reason.")
    if not tools_available:
        lines = [head,
                 "- The native herdr tools are not available in this request, so no visible Herdr "
                 "worker can be started from it. If the person asks for one, say exactly that.",
                 f"- {no_pane}"]
        return "\n".join([FRAME_START, *lines, FRAME_END])
    default = settings["default_preset"]
    presets = [f"{name} ({preset['kind']}{', default' if name == default else ''})"
               for name, preset in settings["presets"].items()]
    choice = (f"Omit preset to use the default ({default}); use another preset only when the "
              "person expressly selects it." if default else
              "No default preset is configured: use the preset the person selects.")
    lines = [
        f"{head} The herdr_* tools authorize every call; their refusals are real blockers to report.",
        "- When the person asks for a worker, coding agent or visible pane to do work, load skill "
        "herdr-gateway:workflow with skill_view, then use herdr_start and supervise with "
        "herdr_wait, herdr_read, herdr_status, herdr_prompt and herdr_close.",
        f"- {no_pane}",
        "- For a bounded read-only request the person's request is the brief: resolve the project "
        "and preset from the lists below and start the worker, without asking for internal paths, "
        "preset names or a new ticket. Substantial implementation keeps this conversation's usual "
        "authorization.",
        f"- {choice} Never start a worker nobody asked for; YOLO stays the person's own "
        "/herdr-yolo choice.",
        f"- Permitted project directories: {_listed([json.dumps(p) for p in entry['projects']])}",
        f"- Presets: {_listed(presets)}",
        "- A project outside these directories, or any herdr_* refusal, is a blocker to report, "
        "not a reason to fall back.",
    ]
    return "\n".join([FRAME_START, *lines, FRAME_END])


def _with_note(request: dict, api_mode, text: str) -> dict | None:
    """A new request with ``text`` appended to the instruction surface, or None to leave it."""
    if api_mode == "codex_responses":
        instructions = request.get("instructions")
        if not isinstance(instructions, str) or not isinstance(request.get("input"), list):
            return None
        return None if text in instructions else {**request, "instructions": f"{instructions}\n\n{text}"}
    if api_mode != "chat_completions":
        return None  # anthropic_messages etc.: unverified shapes (OAuth renames tools on the wire)
    messages = request.get("messages")
    if not isinstance(messages, list) or not messages:
        return None
    first = messages[0]
    if not isinstance(first, dict) or first.get("role") not in ("system", "developer"):
        return None
    content = first.get("content")
    if isinstance(content, str):
        if text in content:
            return None
        content = f"{content}\n\n{text}"
    elif isinstance(content, list):
        if any(isinstance(part, dict) and part.get("text") == text for part in content):
            return None
        content = [*content, {"type": "text", "text": text}]
    else:
        return None
    return {**request, "messages": [{**first, "content": content}, *messages[1:]]}


def middleware(ctx):
    """The ``llm_request`` callback: origin and settings are re-read on every request."""

    def herdr_gateway_routing(request=None, session_id="", api_mode="", **_):
        if not isinstance(request, dict):
            return None
        try:
            settings = load_settings(ctx)
            require_not_delegated()
            origin = runtime_origin(session_id or None)
            entry = authorize(settings, origin)
        except Refusal:
            return None  # outside the configured scope: add nothing, reveal nothing
        if origin["platform"] != "matrix":
            return None
        tools_available = NATIVE_TOOLS <= _declared(request.get("tools"))
        routed = _with_note(request, api_mode, note(settings, entry, tools_available))
        if routed is None:
            return None
        return {"request": routed, "source": "herdr-gateway", "reason": "matrix native worker routing"}

    return herdr_gateway_routing
