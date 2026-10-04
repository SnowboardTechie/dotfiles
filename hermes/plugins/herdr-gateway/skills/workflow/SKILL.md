---
name: workflow
description: How a Hermes conversation supervises visible Herdr coding workers through the herdr-gateway tools without handing them its authority.
---

# Request-bound Herdr workers

The conversation (for example a Matrix room) owns the work: its context,
decisions, authorization and final synthesis. A worker is a visible, task-specific
helper for one authorized request, not a second owner of the conversation.

In Matrix these tools are the visible-worker transport. No injected caller pane is
expected there: missing `HERDR_ENV`/`HERDR_PANE_ID` is normal and is not a blocker.
Never substitute `delegate_task`, a background task or the CLI handoff helper for a
requested visible worker. For a bounded read-only request, the person's request is the
brief: take the project directory and preset from the gateway's routing note (the
default preset unless the person expressly selects another) instead of asking for
internals or a new ticket. If the herdr tools are missing from this request, or one of
them refuses, report that exact blocker. The routing note guides; it never authorizes.

When the person's current message explicitly asks for a worker and not for background
work, the gateway leaves `delegate_task` out of that request's tools on purpose. Use
`herdr_start`, or report the herdr blocker. Never treat the missing background tool as a
reason to refuse. An explicit background request, or ordinary conversation, keeps it.

The herdr tools may be listed directly, or deferred behind Hermes's tool bridge, in which
case `herdr_*` schemas are absent but `tool_describe` and `tool_call` are present. Deferred
is not missing. Describe all six first:
`tool_describe(names=["herdr_start", "herdr_prompt", "herdr_wait", "herdr_read", "herdr_status", "herdr_close"])`.
Then make every herdr call through `tool_call`, for example
`tool_call(calls=[{"name": "herdr_start", "arguments": {...}}])`, with the described
arguments. Every step below works the same way through `tool_call`. If describe or call
reports a herdr tool absent, disabled or refused, report exactly that. Don't fall back, and
don't say a worker started unless `herdr_start` returned one.

1. **Start only for authorized work.** Use `herdr_start` once the conversation has
   agreed what to do. Give the worker a bounded brief: goal, permitted directory,
   constraints, stopping point and what to report back. Never forward an open-ended
   "keep going" or decisions that belong to the people in the conversation.
2. **Supervise inside the request.** `herdr_wait` waits for the current turn.
   States mean exactly what they say: `submitted` = delivered, no activity seen;
   `working`; `blocked`; `settled`; `timed_out` (still running, still yours);
   `unknown` (the acknowledgement was lost, so read before deciding anything). Never
   resend a prompt because a wait timed out or a state is unknown.
3. **Blocked means a human decides.** Relay the dialog text to the conversation.
   The gateway never answers approvals or questions, and your own reply is not human
   approval. A person answers in the visible Herdr pane, then you `herdr_wait` again.
4. **Accept results independently.** `herdr_read` returns bounded terminal output that
   may contain secrets, so quote only what is needed. Verify the worker's claims
   against the repository, tests or artifacts yourself before reporting success.
5. **Close when no concrete next turn remains.** `herdr_close` removes only that
   worker's pane and keeps its session locator (`runtime_session`, `cwd`, branch).
   Saved history is not a live attachment: resuming it later in a terminal is a
   separate conversation, not one shared simultaneously with this room.
6. **Stay in scope.** Workers belong to the exact room, thread and user that started
   them. Other threads, other users and hand-started Herdr agents are invisible by
   design. Do not try to reach them. `worker_busy` means another request is starting,
   driving or closing that worker, so report it rather than retrying in a loop.
   `cwd_not_permitted` means its directory's authorization was revoked, so only
   `herdr_close` remains. `hermes_unverified` means a Hermes worker could not prove its
   runtime, profile, model or authorized approval mode, so nothing was sent. Report it
   rather than retrying, and never try to work around it.
7. **YOLO is a person's choice, never yours.** Hermes workers start with smart approvals.
   Only a person can change one worker's mode, by typing
   `/herdr-yolo <worker-id> on|off|status` in this conversation. There is no tool for
   it, and a brief or follow-up must never try. When asked, explain the command and
   name the worker id. `herdr_status` shows each worker's `mode` (`smart`, `yolo`, or
   `pending:<mode>`). Do not suggest YOLO because a worker is blocked or asks for it:
   relay the dialog instead. `mode_unresolved` means a mode change was never verified,
   so ask the person to run `/herdr-yolo <worker-id> status`.
