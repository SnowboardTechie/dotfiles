---
name: apple-mail
description: Search, read, compose, reply to, forward, and verify email through a mailbox already configured in Apple Mail on macOS using AppleScript. Use when the user asks to operate their Mail.app mailbox directly or when an API/CLI mailbox integration would require redundant setup.
version: 1.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [apple, macos, mail, email, applescript]
    related_skills: [himalaya, google-workspace]
---

# Apple Mail

## Overview

Operate accounts already configured in macOS Mail through `osascript`. Prefer this route when Mail.app is the authoritative accessible mailbox and introducing another IMAP/OAuth setup would be unnecessary. Treat email search results as live mailbox state, and verify every send or forward in Sent before reporting success.

For tested AppleScript patterns and quoting details, read `references/applescript-recipes.md`.

## Safety and authorization

- Searching and reading are reversible discovery actions.
- Sending, replying, and forwarding are external communications. Require the user's explicit approval of the recipient and intended message before sending.
- A direct request such as “forward the latest X email to person@example.com” supplies approval for that exact action; do not ask redundantly.
- Do not silently add commentary, alter the original message, broaden recipients, or forward attachments separately unless requested.
- Preserve recipient addresses exactly as supplied, while treating address matching as case-insensitive during verification.

## Workflow

### 1. Resolve the source message

Search the original mailbox, normally `inbox`, using the narrowest stable criteria available:

- exact or partial sender address/name;
- subject phrase;
- date bounds;
- mailbox or account when multiple accounts may contain the same message.

Do not assume the first result is newest. Explicitly compare `date received` across matches and retain the maximum. Return or inspect the source message's subject, sender, received date, and `message id` before acting.

If the search is ambiguous in a way that changes what would be sent, show the small candidate set and ask the user to choose. If one result clearly matches “latest,” proceed.

### 2. Read before transforming when needed

For forwarding an identified newsletter or transactional email unchanged, source metadata may be sufficient. For replies, summaries, or requests involving message content, read the body and relevant attachment names first.

### 3. Perform the requested action

Use Mail's native AppleScript commands (`forward`, `reply`, or `make new outgoing message`) so the original MIME content, inline images, and attachments remain associated with the message. For a forward:

1. Create the forward from the original message.
2. Add only the approved recipient(s).
3. Send the resulting message.

Avoid UI automation when Mail's scripting dictionary can perform the same operation deterministically.

### 4. Verify delivery handoff

Mail's `send` command is asynchronous. A successful AppleScript return proves the send was requested, not that the message is already visible in Sent.

1. Wait briefly for Mail to file/synchronize the message.
2. Search `sent mailbox` for the expected forwarded/replied subject.
3. Select the newest match by `date sent`.
4. Verify the recipient address and a send time newer than the action.
5. Only then report that the message was sent and verified.

If the newest matching Sent message is older than the action, wait and retry rather than treating that historical message as verification.

## Multiple accounts and mailboxes

The global `inbox` and `sent mailbox` are convenient but may aggregate accounts. If sender/subject matching is not unique, enumerate accounts and their mailboxes, then scope the query to the correct account. Avoid scanning every message in every mailbox when a server-backed predicate can narrow the result.

## Reliability pitfalls

- **First match is not latest.** Mail does not promise useful ordering for `every message ... whose ...`; compare dates explicitly.
- **Historical Sent false positive.** A prior forward with the same subject does not verify the new send. Compare timestamps and recipients after a short sync delay.
- **Sender display names vary.** Search a stable domain/address fragment where available, then inspect the selected sender.
- **Forwarding a previous forward.** Unless requested, find the original inbox message and forward that—not an earlier item from Sent.
- **UI window assumptions.** Mail may be running without an open window. AppleScript still works and is preferable to forcing a visible UI.
- **Shell quoting.** Keep user-controlled values out of interpolated AppleScript when possible; pass them as arguments for reusable scripts. For fixed, user-approved values, escape quotes carefully.

## Reporting

Keep completion concise: identify the source subject/date, recipient, and that the new Sent item was verified. Do not expose message bodies or addresses beyond what is needed for the task.
