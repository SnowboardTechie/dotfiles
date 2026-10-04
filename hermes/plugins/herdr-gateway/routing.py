"""Request-level routing: native Herdr workers for an authorized Matrix conversation.

A plugin skill is never listed in the system prompt's ``<available_skills>``, and an existing
conversation restores its persisted prompt, so neither reaches a conversation that already
learned to refuse. ``llm_request`` middleware runs on every provider request after Codex
preflight. For a non-delegated, trusted Matrix origin that the current settings admit, it
appends one delimited note to the provider's instruction surface. The note names the native
entrypoint the request actually offers: the six herdr_* schemas directly, Hermes's
progressive-disclosure bridge (tool_describe, then tool_call) when they are deferred, or
neither, as a blocker. When that request's current
user message explicitly asks for a worker and not for background work, it also omits the
``delegate_task`` function schema from that one outgoing request, so the invisible background
transport cannot be chosen for it. Anywhere else it adds nothing. The note is guidance, not
authorization: the handlers still authorize every herdr_* call. History, model, cache keys,
other tool schemas and Hermes's own tool registry are never touched.
"""

from __future__ import annotations

import json
import re

from . import schemas
from .policy import Refusal, authorize, load_settings, require_not_delegated, runtime_origin

FRAME_START = "<herdr-gateway-routing>"
FRAME_END = "</herdr-gateway-routing>"
MAX_LISTED = 16
NATIVE_NAMES = [s["name"] for s in schemas.ALL]
NATIVE_TOOLS = frozenset(NATIVE_NAMES)
# Hermes's progressive-disclosure bridge (tools/tool_search.py) and the argument each takes.
BRIDGE = {"tool_describe": "names", "tool_call": "calls"}
DELEGATE = "delegate_task"
HEAD = 400  # characters of the current user message inspected; the request form must lead it
# A worker request leading the message: optional greeting, polite or "I want" form, a verb,
# then a worker, coding agent or pane. Framework messages ([ASYNC DELEGATION …], [IMPORTANT: …],
# [SYSTEM: …], [Replying to …]) start with "[" and never match.
_WORKER_REQUEST = re.compile(
    r"(?:(?:hey|hi|ok(?:ay)?|so|@?hermes)\b[\s,:!.-]*)*"
    r"(?:(?:(?:can|could|would|will)\s+you\s+)?(?:please\s+)?"
    r"(?:have|get|ask|start|launch|spawn|use|send|open|spin\s+up|fire\s+up)"
    r"|i(?:'d|\s+would)?\s+(?:like|want|need))\s+"
    r"(?:(?:an?|another|one|some)\s+)?"
    r"(?:(?:new|fresh|separate|visible|read-only|herdr|claude|codex|hermes)\s+)*"
    r"(?:worker|coding[\s-]agent|pane)s?\b",
    re.IGNORECASE)
_BACKGROUND = re.compile(r"\bbackground\b", re.IGNORECASE)
_VISIBLE = re.compile(r"\bvisible\b|\b(?:not|no|never|don't|dont|without)\s+(?:\w+\s+){0,3}background\b",
                      re.IGNORECASE)


def _listed(items: list[str]) -> str:
    more = len(items) - MAX_LISTED
    return "; ".join(items[:MAX_LISTED]) + (f"; and {more} more" if more > 0 else "")


def _functions(tools) -> dict:
    """Function schemas a Chat Completions or Responses ``tools`` list declares, by name."""
    found = {}
    for tool in tools if isinstance(tools, list) else []:
        if isinstance(tool, dict) and tool.get("type") == "function":
            fn = tool.get("function")
            fn = fn if isinstance(fn, dict) else tool
            found.setdefault(fn.get("name"), fn)
    return found


def _surface(tools) -> str:
    """How a request reaches the native tools: "direct" (all six schemas declared), "deferred"
    (both bridge functions, each taking its argument) or "unavailable". The bridge is a discovery
    route, not proof that the herdr tools are enabled or authorized."""
    found = _functions(tools)
    if NATIVE_TOOLS <= found.keys():
        return "direct"

    def takes(name, arg):
        params = found.get(name, {}).get("parameters")
        return isinstance(params, dict) and isinstance(params.get("properties"), dict) and arg in params["properties"]

    return "deferred" if all(takes(name, arg) for name, arg in BRIDGE.items()) else "unavailable"


def note(settings: dict, entry: dict, surface: str) -> str:
    """The routing note for one admitted origin, from validated settings only."""
    head = ("Routing note from the herdr-gateway plugin for this authorized Matrix conversation. "
            "It is guidance, not authorization.")
    no_pane = ("Matrix has no injected CLI caller pane: missing HERDR_ENV/HERDR_PANE_ID is normal "
               "here and never a blocker. Never substitute delegate_task, a background task or the "
               "CLI handoff helper for a requested visible worker, and disregard any earlier reply in "
               "this conversation that refused visible workers for that reason.")
    if surface == "unavailable":
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
    ask = ("- When the person asks for a worker, coding agent or visible pane to do work, load skill "
           "herdr-gateway:workflow with skill_view")
    if surface == "direct":
        route = (f"{ask}, then use herdr_start and supervise with herdr_wait, herdr_read, "
                 "herdr_status, herdr_prompt and herdr_close.")
    else:
        route = (f"{ask}. The herdr tools are deferred behind Hermes's tool bridge in this request: "
                 f"first tool_describe(names={json.dumps(NATIVE_NAMES)}), then "
                 'tool_call(calls=[{"name": "herdr_start", "arguments": {...}}]) with the described '
                 "arguments, and supervise the same way through tool_call (herdr_wait, herdr_read, "
                 "herdr_status, herdr_prompt, herdr_close). Described tools stay callable only through "
                 "tool_call. The bridge is a discovery route, not proof the herdr tools are enabled: if "
                 "tool_describe or tool_call reports one absent, disabled or refused, report exactly "
                 "that, with no background substitute and no claim that a worker started.")
    lines = [
        f"{head} The herdr_* tools authorize every call; their refusals are real blockers to report.",
        route,
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
    """``request`` with ``text`` on its instruction surface (itself if already there), or None
    for an unsupported shape."""
    if api_mode == "codex_responses":
        instructions = request.get("instructions")
        if not isinstance(instructions, str) or not isinstance(request.get("input"), list):
            return None
        return request if text in instructions else {**request, "instructions": f"{instructions}\n\n{text}"}
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
            return request
        content = f"{content}\n\n{text}"
    elif isinstance(content, list):
        if any(isinstance(part, dict) and part.get("text") == text for part in content):
            return request
        content = [*content, {"type": "text", "text": text}]
    else:
        return None
    return {**request, "messages": [{**first, "content": content}, *messages[1:]]}


def _current_user_text(items) -> str:
    """Text of the most recent user message (Responses ``input_text`` or Chat string/text parts).
    Assistant history, function calls and tool output are never read."""
    for item in reversed(items):
        if isinstance(item, dict) and item.get("role") == "user" and item.get("type", "message") == "message":
            content = item.get("content")
            if isinstance(content, str):
                return content
            return " ".join(part["text"] for part in content if isinstance(part, dict)
                            and part.get("type") in ("input_text", "text")
                            and isinstance(part.get("text"), str)) if isinstance(content, list) else ""
    return ""


def _asks_for_visible_worker(text: str) -> bool:
    """True when ``text`` leads with an explicit worker request that does not ask for background
    work (any "background" in the inspected prefix, unless negated or "visible" is said). A small
    pattern for the supported request forms, deliberately not a general English parser."""
    head = " ".join(text[:HEAD].replace("\u2019", "'").split())
    return bool(_WORKER_REQUEST.match(head)) and (not _BACKGROUND.search(head) or bool(_VISIBLE.search(head)))


def _is_delegate(entry) -> bool:
    """A Responses or Chat Completions function schema, or named tool_choice, for delegate_task."""
    if not isinstance(entry, dict) or entry.get("type") != "function":
        return False
    fn = entry.get("function")
    return (fn if isinstance(fn, dict) else entry).get("name") == DELEGATE


def _select_transport(request: dict, api_mode) -> dict:
    """``request`` without its delegate_task function schema when its current user message asks
    for a visible worker; otherwise ``request`` itself. A named delegate_task tool_choice becomes
    "auto". Every other schema, entry and field is kept as is."""
    tools = request.get("tools")
    items = request.get("input" if api_mode == "codex_responses" else "messages")
    if not isinstance(tools, list) or not _asks_for_visible_worker(_current_user_text(items)):
        return request
    selected = {**request, "tools": [tool for tool in tools if not _is_delegate(tool)]}
    if _is_delegate(request.get("tool_choice")):
        selected["tool_choice"] = "auto"
    return selected if selected != request else request


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
        routed = _with_note(request, api_mode, note(settings, entry, _surface(request.get("tools"))))
        if routed is None:
            return None
        # Even with the native tools missing, a visible request gets no background substitute.
        routed = _select_transport(routed, api_mode)
        if routed is request:
            return None
        return {"request": routed, "source": "herdr-gateway", "reason": "matrix native worker routing"}

    return herdr_gateway_routing
