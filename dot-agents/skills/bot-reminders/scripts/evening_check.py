#!/usr/bin/env python3
"""Evening follow-up on reminders a bot created (see ../SKILL.md, section 4).

Called from a thin per-profile wrapper:

    run(bot="Home", profile_dir=...)

The lists come from <profile>/workspace/reminder-lists.json (SKILL.md section 1).
A missing file or an empty list means the bot has no connections: silent.

Prints a "Routine:" message only when a marked, non-repeating, open reminder is
due (all-day: today or earlier; timed: already past) and hasn't been asked about
for its current due date. Otherwise prints nothing, so the routine stays silent.
"""
import datetime as dt
import json
import os
import subprocess
import sys

STATE_NAME = "reminders-state.json"
LISTS_NAME = "reminder-lists.json"


def _marker(bot):
    return f"Added by {bot} bot (Hermes)"


def _read_list(name):
    out = subprocess.run(["remindctl", "list", name, "--json"],
                         capture_output=True, text=True, timeout=60)
    if out.returncode:
        raise RuntimeError(f"couldn't read Reminders list '{name}': {out.stderr.strip()[:200]}")
    return json.loads(out.stdout or "[]")


def _parse(ts):
    try:
        return dt.datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except Exception:
        return None


def _load_state(path):
    try:
        with open(path) as fh:
            return json.load(fh)
    except FileNotFoundError:
        return {}
    except Exception:
        return {}


def _save_state(path, state):
    tmp = path + ".tmp"
    with open(tmp, "w") as fh:
        json.dump(state, fh, indent=1, sort_keys=True)
    os.replace(tmp, path)


def collect(bot, lists, state, now):
    """Return (to_ask, new_state). `now` is an aware local datetime."""
    mark = _marker(bot)
    today = now.date()
    new_state, to_ask = {}, []
    for name in lists:
        for r in _read_list(name):
            if r.get("isCompleted"):
                continue
            notes = (r.get("notes") or "").rstrip()
            last = notes.splitlines()[-1].strip() if notes else ""
            if not last.startswith(mark) or "repeats" in last[len(mark):]:
                continue
            due = _parse(r.get("dueDate") or "")
            if due is None:
                continue
            # System local zone with DST rules for that instant; now.tzinfo is a fixed
            # offset and would shift all-day dates across a DST change by a day.
            local_due = due.astimezone()
            due_day = local_due.date().isoformat()
            rid = r["id"]
            prev = state.get(rid, {})
            moves = prev.get("moves", 0)
            if prev.get("due") and due_day > prev["due"]:
                moves += 1
            entry = {"due": due_day, "moves": moves}
            if prev.get("asked_for_due"):
                entry["asked_for_due"] = prev["asked_for_due"]
            is_due = (local_due.date() <= today) if r.get("dueDateIsAllDay") else (local_due <= now)
            if is_due and entry.get("asked_for_due") != due_day:
                entry["asked_for_due"] = due_day
                to_ask.append((name, r.get("title", ""), due_day, moves, rid))
            new_state[rid] = entry
    return to_ask, new_state


def connected_lists(profile_dir):
    """Names from the bot's reminder-lists.json; [] when it has none. Raises on a bad file."""
    path = os.path.join(profile_dir, "workspace", LISTS_NAME)
    try:
        with open(path) as fh:
            data = json.load(fh)
    except FileNotFoundError:
        return []
    except Exception as exc:
        raise RuntimeError(f"{LISTS_NAME} is unreadable ({exc.__class__.__name__}: {str(exc)[:120]})")
    return [entry["name"] for entry in data.get("lists", []) if entry.get("name")]


def run(bot, profile_dir, lists=None, now=None):
    now = now or dt.datetime.now().astimezone()
    workspace = os.path.join(profile_dir, "workspace")
    os.makedirs(workspace, exist_ok=True)
    state_path = os.path.join(workspace, STATE_NAME)
    try:
        if lists is None:
            lists = connected_lists(profile_dir)
        if not lists:
            return
        to_ask, new_state = collect(bot, lists, _load_state(state_path), now)
    except Exception as exc:  # one line to the bot, never a silent failure
        print(f"Routine: evening reminder check. {exc}. Tell Bryan in one line that "
              f"tonight's reminder check couldn't run, and nothing else.")
        return
    _save_state(state_path, new_state)
    if not to_ask:
        return
    lines = "\n".join(
        f"- [{lst}] {title} | due {due}" + (f" | moved {m} times" if m else "") + f" | id {rid}"
        for lst, title, due, m, rid in to_ask)
    print(f"""Routine: evening reminder check ({now:%A %b %-d}).

Reminders you added that are still open and due:
{lines}

Follow the bot-reminders skill, section 4. In one short message, ask Bryan about each: done, move to another day (suggest one specific day), or drop. For anything moved 2 or more times, ask instead whether it's still worth keeping, put off to someday, or dropped. No guilt. Change nothing until he answers.""")


if __name__ == "__main__":
    sys.exit("Import run() from a per-profile wrapper; see ../SKILL.md section 4.")
