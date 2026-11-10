#!/usr/bin/env python3
"""Remember which agent session runs in each Rex pane; resume them after a Rex server restart.

A Rex server restart (upgrade, crash, reboot) restores its sessions, tabs, and panes, but
every pane comes back as a fresh login shell: the Claude, Hermes, and Pi sessions that were
running in them are gone. This tool closes that gap.

  snapshot  Record, for every Rex pane, the agent session in its foreground.
  restore   If the server instance changed since the snapshot, type each recorded resume
            command into its pane -- only when that pane is back at an idle shell.
  watch     Loop forever: restore when the instance changes, otherwise snapshot. Run by launchd.
  status    Print the saved snapshot.

Session discovery is read-only and keyed by the agent's PID:
  Claude Code  <config dir>/sessions/<pid>.json        (~/.claude, ~/.claude-personal, ...)
  Hermes       ~/.hermes[/profiles/<p>]/runtime/active_sessions.json
  Pi           ~/.pi/agent/runtime/rex-agent-sessions/<pid>.json, written by
               dot-pi/agent/extensions/rex-agent-sessions.ts

Every rex call passes --autostart=false so this tool never starts a server by itself.
"""
import argparse
import json
import os
import shlex
import subprocess
import sys
import time
from pathlib import Path

HOME = Path(os.environ.get("REX_AGENT_SESSIONS_HOME") or Path.home())
STATE = Path(os.environ.get("REX_AGENT_SESSIONS_STATE") or HOME / ".local/state/rex-agent-sessions")
SNAPSHOT = STATE / "snapshot.json"
SHELLS = {"zsh", "bash", "fish", "sh"}
INTERVAL = 30
RESTORE_WINDOW = 600  # seconds after a restart to keep waiting for panes to reach a shell


def log(message):
    print(time.strftime("%Y-%m-%dT%H:%M:%S ") + message, flush=True)


def rex_binary():
    override = os.environ.get("REX_AGENT_SESSIONS_REX")
    if override:
        return override
    versions = HOME / "Library/Application Support/com.superlogical.rex/RexServer/Versions"
    numbered = sorted((p for p in versions.glob("*") if p.name.isdigit()), key=lambda p: int(p.name))
    for base in list(reversed(numbered)) + [versions / "Current"]:
        candidate = base / "Rex Server.app/Contents/MacOS/rex"
        if candidate.is_file():
            return str(candidate)
    if os.environ.get("REX_BIN_DIR"):
        return os.path.join(os.environ["REX_BIN_DIR"], "rex")
    return "rex"


def rex(*args, parse=True):
    out = subprocess.run([rex_binary(), "--autostart=false", *args], capture_output=True,
                         text=True, timeout=20, check=True).stdout
    return json.loads(out) if parse else out


def read_json(path):
    try:
        return json.loads(Path(path).read_text())
    except (OSError, ValueError):
        return None


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    os.chmod(path.parent, 0o700)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2) + "\n")
    os.chmod(tmp, 0o600)
    tmp.replace(path)


# ---- agent discovery ---------------------------------------------------------------------

def claude_session(pid):
    for config in sorted(HOME.glob(".claude*")):
        data = read_json(config / "sessions" / f"{pid}.json")
        if data and data.get("sessionId") and data.get("pid") == pid:
            env = "" if config.name == ".claude" else f"CLAUDE_CONFIG_DIR={shlex.quote(str(config))} "
            return {"agent": "claude", "session": data["sessionId"], "cwd": data.get("cwd"),
                    "command": f"{env}command claude --resume {shlex.quote(data['sessionId'])}"}
    return None


def hermes_session(pid):
    homes = [("default", HOME / ".hermes")]
    homes += [(p.name, p) for p in sorted((HOME / ".hermes/profiles").glob("*")) if p.is_dir()]
    for profile, root in homes:
        data = read_json(root / "runtime/active_sessions.json") or {}
        for entry in data.get("entries", []):
            if entry.get("pid") == pid and entry.get("session_id"):
                flag = "" if profile == "default" else f"-p {shlex.quote(profile)} "
                return {"agent": "hermes", "session": entry["session_id"], "cwd": None,
                        "command": f"command hermes {flag}--resume {shlex.quote(entry['session_id'])}"}
    return None


def pi_session(pid):
    data = read_json(HOME / ".pi/agent/runtime/rex-agent-sessions" / f"{pid}.json")
    if data and data.get("pid") == pid and data.get("sessionFile"):
        return {"agent": "pi", "session": data["sessionFile"], "cwd": data.get("cwd"),
                "command": f"command pi --session {shlex.quote(data['sessionFile'])}"}
    return None


def agent_in(process):
    """The agent session a pane's process tree is running, foreground first."""
    chain = [process.get("foreground")] + list(process.get("ancestors") or [])
    for proc in chain:
        if not proc or not proc.get("pid"):
            continue
        for finder in (claude_session, hermes_session, pi_session):
            found = finder(proc["pid"])
            if found:
                found["pid"] = proc["pid"]
                found["cwd"] = found["cwd"] or proc.get("cwd")
                return found
    return None


# ---- snapshot / restore ------------------------------------------------------------------

def panes():
    for session in rex("ls", "--json").get("sessions", []):
        sid = session["session_id"]
        for block in rex("block", "ls", "-s", sid, "--json").get("blocks", []):
            if block.get("flavor", "").startswith("com.superlogical.terminal"):
                yield sid, session.get("label"), block


def process_of(sid, bid):
    try:
        return rex("block", "call", "-s", sid, "-b", bid, "process")
    except (subprocess.CalledProcessError, ValueError):
        return None


def snapshot(instance):
    entries = []
    for sid, label, block in panes():
        process = process_of(sid, block["block_id"])
        agent = process and agent_in(process)
        if agent:
            entries.append({"session_id": sid, "session_label": label,
                            "block_id": block["block_id"], **agent})
    write_json(SNAPSHOT, {"instance_id": instance, "taken_at": time.time(), "panes": entries})
    return entries


def at_idle_shell(process):
    """True once a restored pane is a login shell with nothing running in it."""
    fg = (process or {}).get("foreground") or {}
    ancestors = (process or {}).get("ancestors") or []
    return fg.get("name") in SHELLS and all(a.get("name") in SHELLS | {"login"} for a in ancestors)


def restore(instance, snap):
    """Resume each recorded agent whose pane is at an idle shell. Returns panes still waiting."""
    pending = []
    done = set(snap.get("restored", []))
    for entry in snap.get("panes", []):
        key = entry["block_id"]
        if key in done:
            continue
        process = process_of(entry["session_id"], key)
        if process is None:
            pending.append(key)  # pane missing or not ready yet; the restore window bounds this
            continue
        if agent_in(process):
            done.add(key)  # something already resumed it
            continue
        if not at_idle_shell(process):
            pending.append(key)
            continue
        command = entry["command"]
        if entry.get("cwd"):
            command = f"cd -- {shlex.quote(entry['cwd'])} && {command}"
        rex("send", "-s", entry["session_id"], "-b", key, command, parse=False)
        rex("send-key", "-s", entry["session_id"], "-b", key, "enter", parse=False)
        log(f"resumed {entry['agent']} session {entry['session']} in {key}")
        done.add(key)
    snap["restored"] = sorted(done)
    write_json(SNAPSHOT, snap)
    return pending


def current_instance():
    try:
        return rex("whoami", "--json").get("instance_id")
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, ValueError, OSError):
        return None  # server down or restarting


def tick():
    instance = current_instance()
    if not instance:
        return
    snap = read_json(SNAPSHOT) or {}
    previous = snap.get("instance_id")
    if previous and previous != instance:
        snap.setdefault("restart_seen_at", time.time())
        pending = restore(instance, snap)
        waited = time.time() - snap["restart_seen_at"]
        if pending and waited < RESTORE_WINDOW:
            return  # keep the old snapshot until those panes reach a shell
        if pending:
            log(f"gave up on {len(pending)} pane(s) that never reached an idle shell")
    snapshot(instance)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("command", choices=["snapshot", "restore", "watch", "status"])
    args = parser.parse_args()
    if args.command == "status":
        print(json.dumps(read_json(SNAPSHOT) or {}, indent=2))
    elif args.command == "snapshot":
        instance = current_instance()
        if not instance:
            sys.exit("Rex server is not running")
        for entry in snapshot(instance):
            print(f"{entry['agent']:7} {entry['block_id']}  {entry['cwd']}")
    elif args.command == "restore":
        tick()
    else:
        log("watching Rex for server restarts")
        while True:
            try:
                tick()
            except Exception as exc:  # keep the agent alive through transient Rex errors
                log(f"error: {exc}")
            time.sleep(INTERVAL)


if __name__ == "__main__":
    main()
