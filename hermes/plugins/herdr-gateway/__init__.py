"""herdr-gateway: request-bound, origin-scoped Herdr workers for Hermes.

Adapted from https://github.com/steven-terrana/hermes-herdr-plugin (MIT,
Copyright (c) 2026 Steven Terrana) at c33aa2eb2e27087134eb03c9b807eea44e61b9a5.
See LICENSE and README.md for provenance and divergence.
"""

from __future__ import annotations

from pathlib import Path

from . import schemas
from .tools import Handlers


def register(ctx):
    handlers = Handlers(ctx)
    for schema in schemas.ALL:
        method = schema["name"].removeprefix("herdr_")
        ctx.register_tool(name=schema["name"], toolset="herdr", schema=schema,
                          handler=getattr(handlers, method))
    ctx.register_skill("workflow", Path(__file__).parent / "skills" / "workflow" / "SKILL.md",
                       description="Supervising request-bound Herdr workers from a conversation")
    # A person's native command, dispatched before any agent turn; deliberately not a tool.
    ctx.register_command("herdr-yolo", handlers.yolo_command,
                         description="Show or change one owned Hermes worker's YOLO approval bypass",
                         args_hint="<worker-id> on|off|status")
