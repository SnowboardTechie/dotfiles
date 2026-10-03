"""Tool schemas: what the model sees.

No schema carries origin, agent kind, model, permission or launch-argument
fields. Those come from Hermes's runtime binding and operator presets only.
"""

_WORKER = {"type": "string", "description": "Worker id returned by herdr_start"}
_WAIT = {
    "type": "integer",
    "description": "Seconds to wait synchronously for the turn to settle (bounded by the operator)",
}
_GUIDE = (" Matrix (this conversation) owns authority and decisions; workers carry a bounded "
          "brief and you accept their results independently. See skill herdr-gateway:workflow.")

HERDR_START = {
    "name": "herdr_start",
    "description": (
        "Start one visible, task-specific coding worker in a new unfocused Herdr workspace for "
        "work this conversation has authorized, and submit its brief. The worker belongs only to "
        "this room, thread and user. Returns a worker id plus the truthful turn state: submitted "
        "(no activity observed yet), working, blocked (approval/question for the human, answered in "
        "the Herdr pane), settled, timed_out or unknown." + _GUIDE
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "task": {"type": "string", "description": "Short kebab-case task slug, e.g. fix-auth-bug"},
            "cwd": {"type": "string", "description": "Absolute project directory permitted for this room"},
            "prompt": {"type": "string", "description": "Bounded task brief for the worker"},
            "preset": {"type": "string", "description": "Operator preset name (default preset if omitted)"},
            "wait_seconds": _WAIT,
        },
        "required": ["task", "cwd", "prompt"],
        "additionalProperties": False,
    },
}

HERDR_PROMPT = {
    "name": "herdr_prompt",
    "description": (
        "Send a follow-up turn to one of this conversation's own idle workers. Refused while a turn "
        "is unsettled, blocked or unknown; never resends a lost prompt." + _GUIDE
    ),
    "parameters": {
        "type": "object",
        "properties": {"worker": _WORKER,
                       "prompt": {"type": "string", "description": "Follow-up instruction"},
                       "wait_seconds": _WAIT},
        "required": ["worker", "prompt"],
        "additionalProperties": False,
    },
}

HERDR_WAIT = {
    "name": "herdr_wait",
    "description": (
        "Wait up to wait_seconds for this conversation's worker's current turn to settle, without "
        "sending anything. A timeout keeps the worker and its ownership intact."
    ),
    "parameters": {
        "type": "object",
        "properties": {"worker": _WORKER, "wait_seconds": _WAIT},
        "required": ["worker"],
        "additionalProperties": False,
    },
}

HERDR_READ = {
    "name": "herdr_read",
    "description": (
        "Read bounded recent terminal output from one of this conversation's own workers, after "
        "verifying it is still exactly the recorded worker. Output may contain secrets; quote only "
        "what the conversation needs."
    ),
    "parameters": {
        "type": "object",
        "properties": {"worker": _WORKER,
                       "lines": {"type": "integer", "description": "Rows to read, 1-400 (default 120)"}},
        "required": ["worker"],
        "additionalProperties": False,
    },
}

HERDR_STATUS = {
    "name": "herdr_status",
    "description": "List this conversation's own workers with live, identity-checked status.",
    "parameters": {
        "type": "object",
        "properties": {"include_closed": {"type": "boolean",
                                          "description": "Include closed workers and their locators"}},
        "required": [],
        "additionalProperties": False,
    },
}

HERDR_CLOSE = {
    "name": "herdr_close",
    "description": (
        "Close one of this conversation's own workers once no concrete next turn remains: verifies "
        "identity, closes only its recorded pane, confirms absence, keeps result/session locators. "
        "Safe to retry."
    ),
    "parameters": {
        "type": "object",
        "properties": {"worker": _WORKER},
        "required": ["worker"],
        "additionalProperties": False,
    },
}

ALL = [HERDR_START, HERDR_PROMPT, HERDR_WAIT, HERDR_READ, HERDR_STATUS, HERDR_CLOSE]
