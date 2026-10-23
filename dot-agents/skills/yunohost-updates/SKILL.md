---
name: yunohost-updates
description: Use when checking, reviewing, running, or monitoring YunoHost server upgrades. Approval-gated per app.
version: 1.2.0
author: Bryan Thompson
license: MIT
metadata:
  hermes:
    tags: [yunohost, vps, upgrades, release-notes, forgejo, synapse]
    related_skills: [private-service-operations, remote-service-readiness]
---

# YunoHost Server Updates

Bryan's YunoHost server (`snowboardtechie`, Debian 12 bookworm, Hostinger VPS
at the public IP behind `snowboardtechie.com`) hosts Forgejo, Synapse, Element,
Cinny, GoToSocial, Phanpy, Prosody, Coturn and mail. It is deliberately NOT on
the home tailnet and its config is not in nix-configs. This skill covers:
listing pending updates, reviewing release notes for breaking changes, getting
Bryan's approval, and monitoring the upgrade he runs.

## Access model (do not widen it)

- SSH as the non-admin YunoHost user `agent`, key `~/.ssh/yunohost-agent`,
  port 5518 (port 22 is closed). The host key is already trusted under
  `[git.snowboardtechie.com]:5518`:

  ```bash
  ynh() { ssh -o BatchMode=yes -o IdentitiesOnly=yes -i ~/.ssh/yunohost-agent \
    -o HostKeyAlias='[git.snowboardtechie.com]:5518' -p 5518 \
    agent@snowboardtechie.com "$@"; }
  ```

- `agent` has passwordless sudo, from `/etc/sudoers.d/zz-agent`, for exactly:
  - read-only: `/usr/bin/yunohost tools update`, `/usr/bin/yunohost app list`,
    `/usr/bin/yunohost tools versions`, `/usr/bin/yunohost log list`, and
    `/usr/bin/yunohost tools update --output-as json` (used by the nightly
    report's scripts);
  - upgrades, one exact command per target with no extra flags:
    `/usr/bin/yunohost tools upgrade system` and
    `/usr/bin/yunohost app upgrade <app>` for element, phanpy, gotosocial,
    synapse, forgejo, cinny, prosody, coturn. A newly installed app needs
    Bryan to add its own line. Multi-app upgrades don't match, so upgrade
    one app per command.
- Having the rule is not approval. Run an upgrade only after Bryan's explicit
  yes for that item in the current conversation.
- `agent` has an ACL granting read access to `/var/log/yunohost` (including the
  default ACL for new files), so operation logs can be tailed without sudo.
- Backups, `yunohost diagnosis`, `app setting`, `log show` and any upgrade
  with flags need root. Bryan runs those as `bryan` with his password; hand him
  the exact command.

### Sudo pitfalls (each failure emails Bryan)

- sudoers matches arguments exactly. `sudo -n /usr/bin/yunohost app list`
  works; `... app list --output-as json` or any added flag is refused, and
  every refused sudo sends Bryan a "a password is required" security email.
  Never probe with `sudo -n true` or similar.
- Why `agent` and not `bryan`: YunoHost serves sudo rules from LDAP
  (`nsswitch: sudoers: files ldap`, `cn=admins,ou=sudo`: `%admins ALL`). Sudo
  uses the last matching rule, so for any admin the LDAP password-required rule
  overrides any NOPASSWD file rule. Keep `agent` out of the `admins` group.
- Never allow `yunohost log show` via sudo: its `--share` flag uploads logs to
  YunoHost's public paste service. Read the log files directly instead.

## Nightly report and Matrix approvals

The Hermes cron job "YunoHost update report" (tracked in dotfiles
`hermes/manifest.json`, prompt at
`hermes/automations/yunohost-update-report/prompt.md`) runs at 20:00 Pacific.
Its monitor `check-yunohost-updates.py` prints a stable pending snapshot, and
the agent only runs when that snapshot changes, so a held item is reported once,
not nightly. A changed snapshot runs `collect-yunohost-updates.py`, which adds
bounded upstream release-note excerpts and recent issue titles, and a
**zero-tool** assessor posts a threaded report to the private
"Server Updates" Matrix room. The cron run cannot upgrade anything: it has no
tools.

When Bryan replies in that thread asking for upgrades, his reply is the
approval for exactly the items he names. Then:

1. Restate the items and versions you'll upgrade, and run them one at a time
   (section 3). Don't add items he didn't name, even "safe" ones.
2. If an item he names is marked hold or needs a check, say so in one line
   and ask before running it.
3. Synapse is the Matrix homeserver, so this room goes offline while it
   upgrades. Say so before starting it, run it last, then post the result once
   Matrix is back.
4. Report each upgrade's result and verification in the thread (sections 4–5).

## 1. Check what is pending (read-only)

```bash
ynh 'sudo -n /usr/bin/yunohost tools versions; sudo -n /usr/bin/yunohost tools update; sudo -n /usr/bin/yunohost app list; df -h / | tail -1'
ynh 'ls -t /var/log/yunohost/operations/*.yml | head -10'   # recent operations
ynh 'grep -h " install \| upgrade " /var/log/dpkg.log | tail -20'  # incl. unattended-upgrades
```

`tools update` prints each upgradable app with `current_version`,
`new_version`, the package repo `url`, `new_revision`, and any manifest
`notifications` (pre-upgrade warnings). It also lists system packages and
`important_yunohost_upgrade` / `pending_migrations`. In `--output-as json`,
`system` is `[]` when apt has nothing, but a dict of category → package list
(e.g. `{"misc utils and libs": [...]}`) when it does; parse both. The server runs
`unattended-upgrades` (security packages install automatically) and Bryan
sometimes upgrades through the web admin, so check recent operations before
assuming anything is pending.

## 2. Review release notes before recommending anything

For every pending item, review BOTH layers between the installed and target
versions. Do not skim headlines; read upgrade/breaking sections in full.

1. **YunoHost package** (`github.com/YunoHost-Apps/<app>_ynh`):
   - manifest `notifications` shown by `tools update`;
   - `doc/PRE_UPGRADE.d/<version>.md` and `doc/POST_UPGRADE.d/` for any version
     in the range;
   - recent commits (`gh api repos/YunoHost-Apps/<app>_ynh/commits`), and
     `scripts/_common.sh` / `scripts/upgrade` / `conf/` when upstream changes a
     config default or adds a startup check: confirm how the package templates
     that setting and what its default is.
2. **Upstream app**, every release in the range, not just the target:
   - Forgejo: release bodies point at
     `https://codeberg.org/forgejo/forgejo/raw/branch/forgejo/release-notes-published/<ver>.md`.
     Strip `<!-- ... -->` comments, then read the "Breaking features",
     "Breaking bug fixes" and "Security" sections. Also check the release body
     for an "Attention" banner and search recent issues
     (`codeberg.org/api/v1/repos/forgejo/forgejo/issues?q=<ver>`) for regressions.
   - Synapse: `docs/upgrade.md` on `element-hq/synapse` has one
     "Upgrading to vX" section per release that needs admin attention. Read
     every section in the range; GitHub release bodies are only links.
   - Element / Phanpy: GitHub releases; grep for Security, ⚠️ Important,
     Deprecations, removals.
   - GoToSocial: Codeberg releases `superseriousbusiness/gotosocial`. The
     "Migration notes", "config.yaml" and "Database Migrations" sections matter.
     Note when the package lags upstream.
   - YunoHost core / major Debian jumps: YunoHost forum release announcements
     (forum.yunohost.org, "Announcement" category) and any `pending_migrations`.
3. **Classify** each item as one of:
   - *safe*: no breaking changes that affect this install;
   - *needs a check*: a breaking change that depends on settings you can't read
     as `agent`, so name the setting and how Bryan can check it;
   - *hold*: an upstream advisory against upgrading, an open regression on a
     feature Bryan uses, or a required manual migration.
   Call out security fixes in the range, because skipping an upgrade has a cost
   too. If the package only offers a version you'd hold, say whether an older
   package revision exists and that pinning it is a separate decision.
4. Cite each finding with its source URL. Separate what the notes say from
   your inference about whether it affects this server.

## 3. Get Bryan's decision

Present a per-item table: current → target, verdict, the reason with its
source, and the exact command. Recommend an order. Run the lowest-risk items
first and one consequential app (Forgejo, Synapse, GoToSocial) at a time.
Nothing gets upgraded without his explicit yes for each item.

After approval, run each upgrade yourself, detached in `screen` (installed;
tmux is not), so a dropped SSH session can't kill it. YunoHost takes a safety
backup (`<app>-pre-upgrade1`) before each app upgrade:

```bash
ynh 'screen -dmS ynh-<app> bash -c "sudo -n /usr/bin/yunohost app upgrade <app> > ~/upgrade-<app>.out 2>&1; echo EXIT=\$? >> ~/upgrade-<app>.out"'
```

Use `tools upgrade system` the same way for system packages. If Bryan prefers
to run it himself, he can SSH in as `bryan`
(`ssh -p 5518 bryan@git.snowboardtechie.com`) or use the web admin at
`https://snowboardtechie.com/yunohost/admin` → Applications → Upgrade. Never
suggest `--no-safety-backup` unless he asks.

## 4. Monitor the run

Follow `~/upgrade-<app>.out` (ends with `EXIT=<code>`) and the newest
operation log, without sudo:

```bash
ynh 'tail -3 ~/upgrade-<app>.out'
ynh 'ls -t /var/log/yunohost/operations/ | head -4'
ynh 'tail -n 40 /var/log/yunohost/operations/<id>.log'
ynh 'cat /var/log/yunohost/operations/<id>.yml'  # success / error / ended_at
```

Poll at a sensible interval (30–60 s). Report the phase you can see: safety
backup, source download, install, migrations, service restart. Then report the
final `success`/`error` field from the `.yml`. Respect app warnings, e.g.
GoToSocial's post-upgrade DB migrations: tell Bryan to wait and never suggest a
restart mid-migration. On failure, quote the error lines from the log and note
that YunoHost restores the safety backup automatically on a failed app
upgrade. Confirm the restore from the log rather than assuming it happened.

## 5. Verify afterwards

```bash
ynh 'sudo -n /usr/bin/yunohost app list'   # versions now match targets
curl -sS -o /dev/null -w '%{http_code} %{url_effective}\n' -L https://<domain_path>
```

Check every upgraded app's URL. For Forgejo also run
`git ls-remote git@git.snowboardtechie.com:<owner>/<repo>.git` and, with
Bryan's go-ahead, a real push to a scratch repo, because v17-era regressions hit pushes and merges. For Synapse
check `https://matrix.snowboardtechie.com/_matrix/client/versions`. Ask Bryan
to run `sudo yunohost diagnosis run` (or wait for the twice-daily diagnosis
email) for a whole-server health readback. Report only what you verified.

## Pitfalls

- The Server Updates room only stays decryptable for Bryan because its ID is
  in `AUTHORIZED_ROOMS` in dotfiles `hermes/plugins/matrix-key-recovery/`.
  Without that, Hermes shares room keys over stale Olm sessions and every post
  shows "Unable to decrypt". A replacement room needs the same entry, then
  `install.py` and a gateway restart, which Bryan runs outside Hermes. Messages
  sent before the fix can't be recovered; repost them.
- Expected run times seen so far: Element ~20 s; Phanpy ~3.5 min (Node
  build); GoToSocial ~30 s plus a ~1.3 GB safety backup. GoToSocial's backup
  logs `could not change directory to "/home/yunohost.backup/tmp/..."` and
  `Permission denied`. This appears to be the database dump's user not being
  able to enter the backup dir, so it's harmless while the backup still reports
  `SUCCESS Backup created`. Treat it as a failure if that SUCCESS line is
  missing.
- Synapse's package builds LiveKit/lk-jwt with goenv. A stale
  `/opt/goenv/shims/.goenv-shim` lock (e.g. left by an interrupted rehash)
  makes `goenv` exit non-zero, so the upgrade fails during resource
  provisioning, before the upgrade script, and Synapse keeps running the old
  version. Check for that file (and `pgrep -af goenv`) before a Synapse
  upgrade. Removing it needs root, so Bryan runs `sudo rm` on it.
- Treating the package's offered version as vetted: forgejo_ynh shipped
  17.0.0 the day after Forgejo published an advisory against upgrading.
- Reviewing only the target release: a 6-release Synapse jump has several
  "Upgrading to" sections.
- Reading root-only app settings by guessing: say which setting matters and
  ask Bryan (`sudo yunohost app setting <app> <key>`), or check the app's
  config panel.
