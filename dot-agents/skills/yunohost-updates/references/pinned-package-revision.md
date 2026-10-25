# Upgrading to an older package revision (skip a held version)

Use when `tools update` offers a version you'd hold (upstream advisory, open
regression), but an intermediate release is still worth installing, usually
for security fixes. Example: hold Forgejo 17.0.0 but move 16.0.1 → 16.0.6.

## 1. Find the package commit that ships the wanted version

```bash
gh api 'repos/YunoHost-Apps/<app>_ynh/commits?per_page=40' \
  --jq '.[] | "\(.sha[0:10]) \(.commit.committer.date[0:10]) \(.commit.message|split("\n")[0])"'
```

The auto-updater flow is: `ci-auto-update-<ver>` PR → `testing`, then a
"Merge pull request #N from YunoHost-Apps/testing" into the default branch.
Pick that later testing → master merge for the wanted version, not the
`ci-auto-update` merge, because only the master merge has passed the package
release gate. Ignore the repo's tags; they're stale.

## 2. Verify the commit before recommending it

```bash
gh api 'repos/YunoHost-Apps/<app>_ynh/contents/manifest.toml?ref=<sha>' --jq .content \
  | base64 -d | grep -nE '^version|url|sha256'
gh api 'repos/YunoHost-Apps/<app>_ynh/compare/<installed-sha>...<sha>' --jq '.files[].filename'
```

- The manifest `version` must be `<ver>~ynhN`, and the source URLs must point
  at the official upstream release artifacts.
- Review the package diff over the range the same way as a normal upgrade:
  new settings in `conf/`, `scripts/_common.sh` defaults (for example,
  `ynh_app_setting_set_default`) and new `doc/PRE_UPGRADE.d/` files.
- Review upstream notes for every release from installed to pinned, as
  usual.

## 3. Hand Bryan the command (it needs root)

`agent`'s sudoers rule only matches the bare `app upgrade <app>`, which
installs the latest version. A pinned upgrade adds `-u`, so Bryan runs it as
`bryan`. Use the full 40-character SHA:

```bash
ssh -p 5518 bryan@git.snowboardtechie.com
sudo yunohost app upgrade <app> -u https://github.com/YunoHost-Apps/<app>_ynh/tree/<full-sha>
```

The safety backup still runs. Tell him:

- the nightly report will keep listing the held version as pending;
- when the pinned line reaches end-of-life, per the upstream schedule.

Then verify per SKILL.md section 5 once he says it has run.
