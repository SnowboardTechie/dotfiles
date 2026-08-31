# Auto Suspend

Personal Omarchy shell service that suspends the host after 45 minutes of
uninhibited user idle time.

## Behavior

- Uses Quickshell's `IdleMonitor` with `respectInhibitors: true` so applications
  and Hyprland window rules can inhibit idle behavior.
- Watches the same state file managed by Omarchy's stock **Stay Awake**
  indicator and `omarchy toggle idle`, so either control also disables auto
  suspend.
- Runs `systemctl suspend` directly. Omarchy's existing
  `omarchy-sleep-lock.service` locks the session before sleep.
- Does not replace or modify Omarchy's built-in screensaver and lock timers.

The timeout is intentionally version-controlled in `Service.qml` rather than
written into Omarchy-owned configuration.

## Deployment

`scripts/reconcile-omarchy-auto-suspend.sh` links this directory into
`~/.config/omarchy/plugins/`, enables its service entry additively in
`~/.config/omarchy/shell.json`, and preserves any foreign file collision.

Check runtime state with:

```bash
omarchy-shell autoSuspend status
```
