---
name: server-update-checks
description: Use when Bryan asks to look over or check the server updates Steve's YunoHost report marked "needs a check", or invokes this skill. Settles each one with read-only checks and gives him the approval line to paste to Steve.
---

# Server update checks

Steve (pi-bots) posts the YunoHost update report in Bryan's Server Updates room each morning. Its model has no tools
and never touches the server, so an item whose safety depends on the server's own setup comes out **needs a check**,
with the command that would settle it. This skill is the check: read the latest report, settle every needs-a-check
item from the change itself and from the server's state, read only, and tell Bryan what to approve.

Bryan approves upgrades by replying to Steve. This skill upgrades nothing.

## The server, read only

Load the `yunohost-updates` skill and follow its "Access model" section for how to reach the server: SSH as `agent`
with `~/.ssh/yunohost-agent`, its `ynh` helper, and the sudo pitfalls.

The checks stay read only:

- Run commands as `agent`, without sudo, that only read: `dpkg -l`, `apt-cache rdepends --installed`,
  `php<ver> -m`, `systemctl is-active` / `is-enabled`, `readlink`, `findmnt`, `cat` of a file `agent` can read
  (`/etc/fstab`, `/etc/fail2ban/`), `ls`, `df`, `free`.
- The only sudo is the read-only list in `yunohost-updates`, word for word. Any other sudo is refused and emails
  Bryan.
- Write nothing on the server, and run no YunoHost or service command that changes state.
  `yunohost tools regen-conf --dry-run` counts as one: it runs YunoHost's hook scripts as root and rewrites its
  pending directory.

`agent` cannot read `/etc/nginx/`, the app directories under `/var/www/`, or `/var/cache/yunohost/`. When a check
needs one of those, it needs root: give Bryan the exact command to run himself and leave that item needs-a-check.

## Steps

1. **Read the latest report.** On the Mac Studio, the report job keeps each run's Pi session, holding both the data
   it was given and what it posted:

   ```bash
   pi-bots job runs yunohost-report --limit 1     # when it ran and whether it posted
   python3 - <<'EOF'
   import glob, json
   path = sorted(glob.glob("/Users/bryan/.local/state/pi-bots/jobs/yunohost-report/sessions/*.jsonl"))[-1]
   for line in open(path):
       m = json.loads(line).get("message") or {}
       if m.get("role") in ("user", "assistant"):
           c = m["content"]
           print(f"===== {m['role']}\n" + (c if isinstance(c, str) else "".join(p.get("text", "") for p in c)))
   EOF
   ```

   The assistant text is the post. The user text holds the collected data: the pending set, the apps'
   `releaseNotes` and the system packages' `systemReleaseNotes` (changelog entries, links, `errors`). If Bryan means a
   different post (one sent by hand), ask him to paste it. Done when you have every item the post marked **needs a
   check**, each with its reason and the check it named.

2. **Confirm it is still pending**, in case the server has moved since the morning:
   `ynh 'sudo -n /usr/bin/yunohost tools update --output-as json'`. Drop an item that is no longer pending and say
   so.

3. **Settle each item.** For each needs-a-check item, find exactly what the upgrade changes, then check the server
   for the conditions that change touches:
   - **YunoHost core** (`yunohost`, `moulinette`, `ssowat`): compare the two tags on GitHub to see every
     configuration file and hook the release changes. The tags are `debian/<version>`:
     `https://api.github.com/repos/YunoHost/yunohost/compare/debian/<current>...debian/<new>`, with
     `Accept: application/vnd.github.diff` for the diff. Read each changed `conf/` template and `hooks/conf_regen/`
     script, and each linked pull request, then check the server's current state for what they touch: services
     running, a systemd unit's state, a mount, a fail2ban jail, the HTTP version the sites serve
     (`curl -s -o /dev/null -w '%{http_version}' https://<domain>/`).
   - **A library** (a removed format, a changed default): find who uses it on the server with
     `apt-cache rdepends --installed <package>` and the PHP modules loaded (`php<ver> -m`), then judge the change
     against those users.
   - **An app**: follow `yunohost-updates` section 2 for the package's own notes, then check the setting it
     depends on, if `agent` can read it.

   List the security fixes in each item's range too (every CVE and GHSA in its changelog entries and, for PHP, the
   version's whole section of `https://www.php.net/ChangeLog-<major>.php`), since waiting on them has a cost. When
   the report's data has no `systemReleaseNotes` (runs before 2026-11-19), fetch the changelogs from the sources
   pi-bots' `jobs/yunohost/system_notes.py` names.

   Done when every item has a verdict, **safe** or **hold**, with what you checked and what you found. An item
   whose deciding fact needs root stays **needs a check**, with the command Bryan runs.

4. **Report to Bryan.** One short paragraph per item: the verdict, what the upgrade will change on his server
   (what restarts, what behaves differently afterwards), and the evidence, each fact marked as checked on the
   server or read from a source with its link. Then the approval line, in a code block he can copy into Steve's
   thread:

   ```
   upgrade <every app ID now safe, joined with "and", Synapse last>
   ```

   `system` goes in only when every system package is now safe, because they upgrade together. Items the report
   called safe or on hold keep their verdicts, unless your check found something that changes one: say which and
   why.
