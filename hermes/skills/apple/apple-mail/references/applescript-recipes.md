# Apple Mail AppleScript recipes

These patterns were validated on macOS Mail in July 2026. They are examples to adapt, not a substitute for narrowing the source query and confirming recipients.

## Find the newest matching inbox message

Mail does not guarantee that `every message ... whose ...` is ordered, so compare `date received` explicitly.

```applescript
tell application "Mail"
  set matches to (every message of inbox whose sender contains "Rainshadow")
  set latestMsg to missing value

  repeat with m in matches
    if latestMsg is missing value or date received of m > date received of latestMsg then
      set latestMsg to m
    end if
  end repeat

  if latestMsg is missing value then return "NOT_FOUND"

  return (message id of latestMsg) & tab & ¬
    (date received of latestMsg as string) & tab & ¬
    (sender of latestMsg) & tab & ¬
    (subject of latestMsg)
end tell
```

For stronger matching, combine predicates when Mail accepts them, or retrieve a narrow candidate set and inspect sender, subject, and date before sending.

## Forward the original message unchanged

```applescript
tell application "Mail"
  -- Resolve latestMsg using the search pattern above.
  if latestMsg is missing value then error "Source email not found"

  set forwardedMessage to forward latestMsg with opening window
  tell forwardedMessage
    make new to recipient at end of to recipients with properties {address:"recipient@example.com"}
    send
  end tell
end tell
```

Use the original inbox message rather than a previous copy in Sent unless the user explicitly asks to forward the forward.

## Verify the newest matching Sent message

A send request can return before the new message appears in Sent. Wait a few seconds, then query Sent and compare `date sent` explicitly.

```applescript
tell application "Mail"
  set matches to (every message of sent mailbox whose subject contains "EXPECTED SUBJECT")
  set latestMsg to missing value

  repeat with m in matches
    if latestMsg is missing value or date sent of m > date sent of latestMsg then
      set latestMsg to m
    end if
  end repeat

  if latestMsg is missing value then return "NOT_FOUND"

  set recipientList to ""
  repeat with r in to recipients of latestMsg
    set recipientList to recipientList & (address of r) & ","
  end repeat

  return (date sent of latestMsg as string) & tab & recipientList & tab & (subject of latestMsg)
end tell
```

Verification must establish that the newest match was created after the current action. An older item with the same subject is not sufficient. Compare recipient addresses case-insensitively.

## Running from the shell

Short scripts can be supplied as repeated `osascript -e` arguments. For longer or reusable automation, save a `.applescript` script and pass variable values as `argv` to avoid interpolating user-controlled strings into AppleScript source.

Example fixed-value invocation shape:

```sh
osascript \
  -e 'tell application "Mail"' \
  -e 'set matches to (every message of inbox whose sender contains "SENDER FRAGMENT")' \
  -e 'return (count of matches)' \
  -e 'end tell'
```

## Observed synchronization behavior

In a successful forward, the Mail `send` command returned immediately, while the new Sent item became queryable several seconds later. A first verification query selected an older same-subject forward; a five-second retry exposed the new message. The durable lesson is to verify timestamp + recipient after a brief delay, not merely subject presence.
