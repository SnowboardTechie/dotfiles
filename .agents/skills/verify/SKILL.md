---
name: verify
description: Drive the dotfiles repository's setup scripts and reconcilers (setup-platform-configs.sh, scripts/setup-omarchy.sh, scripts/reconcile-*.sh, retire-agent-memory.py) the way a host runs them, --check then --apply then again, in a disposable HOME inside a macOS sandbox that can write nowhere else and reach no network, and keep evidence of every run. Use to prove a change to what setup links, appends, enables or keeps, or to see what a script would do to a home. Never touches the real HOME.
---

# Verify the dotfiles setup scripts

What a user of this repository touches is its setup: `setup-platform-configs.sh` on a macOS or NixOS host after Stow,
`scripts/setup-omarchy.sh --check|--apply` on Omarchy, and the `scripts/reconcile-*.sh` reconcilers both of them run.
Each writes links, lines and settings into `$HOME`. This skill runs them against throwaway homes and reads back what
they did.

One control command does it: `.agents/skills/verify/scripts/dotfiles-verify`. Run every command from the repository
root, the checkout being verified.

## Setup (once per shell)

```sh
export DOTFILES_VERIFY_EVIDENCE=/path/outside/the/repo/dotfiles-verify   # optional; default $TMPDIR/dotfiles-verify
V=.agents/skills/verify/scripts/dotfiles-verify
```

The evidence root must be outside the repository; the command refuses one inside it.

## Launch

There is nothing to build and no server. Each `run` makes its own scratch directory, drives one journey, and removes
the scratch when it ends, passed or failed:

```sh
$V journeys                 # list them, with what each proves
$V run agent-skills         # one journey
$V run ./my-check.sh        # your own journey file
```

The first lines name the run directory and the scratch directory. Each step is logged as `step <name>`, each claim as
`ok   <claim>`, and the run ends with `PASSED` (exit 0) or `FAILED` (exit 1) after the first `FAIL: <claim>`. Exit 2 is a
usage or setup error. A journey takes 1 to 15 s.

Every command a journey drives runs under `sandbox-exec` with:

- `HOME` set to a fresh directory under the scratch, and an emptied environment (`env -i`);
- file writes allowed only under the scratch directory, so the real `$HOME`, `~/.pi/agent`, `~/Library` and the
  checkout itself are read-only to the script under test;
- no network;
- `PATH` = stubs, then links to `bash python3 jq perl git node realpath`, then `/usr/bin:/bin:/usr/sbin:/sbin`.
  `launchctl`, `systemctl`, `stow`, `sudo`, `brew` and `defaults` are stubs that log the call and succeed, because the
  sandbox stops writes but not a request to the real launchd. `scutil` and `hostname` answer `verify-host`, so neither
  the Studio-only Hermes step nor the Gnarbox profile runs by accident. `pi`, `claude` and `omarchy` are absent unless a
  journey adds a stub.

Runs share nothing, so any number can go side by side.

## Doctor

```sh
$V doctor
```

Read-only apart from creating the evidence root and one probe directory it removes. Exits 1 on any `FAIL`. It checks
macOS and `sandbox-exec`, each tool above, that the `bash` on `PATH` is 4 or later (macOS's `/bin/bash` 3.2 is not
enough for the reconcilers), that the temporary directory (`$TMPDIR`, else `/tmp`) exists and is writable (if not it
stops there, before creating anything), the evidence root, that the sandbox really refuses a write outside the run, and that no
earlier run was left uncleaned. Run it first, and again whenever anything looks wrong.

## Drive

A journey is a bash file sourced by the control command, with `set +e`; it fails by `expect` failing. Model a new one
on the closest of the five in `journeys/`. What it gets:

| Helper | Does |
| --- | --- |
| `$REPO` | The checkout's root |
| `new_home <name>` | Prints a fresh empty home under the scratch |
| `drive <label> <home> [VAR=value ...] -- <cmd> [args]` | Runs the command in the sandbox with that `HOME` (and its cwd); sets `RC` and `OUT`; writes `NN-<label>.txt` |
| `capture <home> <label>` | Writes `NN-<label>.tree` (every path, link target and file hash) and sets `TREE` to it |
| `expect "<claim>" <command...>` | Logs `ok   <claim>`, or `FAIL: <claim>` and ends the journey |
| `has <text> <string>`, `lacks`, `same_file a b`, `links_to <link> <target>` | Predicates for `expect` |
| `stub <name> '<body>'` | A command in front of the real tools; `__CALLS__` in the body is its call log, kept outside the home |
| `calls <home> <name>` | That stub's log for that home |
| `stub_pi` | A `pi` that edits `packages` in `~/.pi/agent/settings.json` as `pi install`/`remove` do, and a no-op `claude` |
| `mattpocock_upstream` | A local bare copy of Matt Pocock's skills repository at the ledger's pin (copied read-only from the real reconciler's checkout, `~/.local/share/mattpocock-skills` or the older `~/.pi/agent/upstreams/mattpocock-skills`, or `DOTFILES_VERIFY_MATTPOCOCK_SOURCE`; never fetched), and `GIT_UPSTREAM_ENV` to pass to `drive` so git's `insteadOf` uses it |
| `step <name>` | A heading in the log |

The commands under test are the repository's own entry points with their own flags: `--check` and `--apply` for the
reconcilers and `setup-omarchy.sh` (never with `--force`: an `omarchy` stub makes the home's host identify as Omarchy),
none for `setup-platform-configs.sh`. Seed a home the way a host leaves it (a stock Omarchy `.bashrc` and `shell.json`,
a retired link, someone else's file) with plain shell before driving.

## Evidence

Each run writes `$DOTFILES_VERIFY_EVIDENCE/<UTC time>-<journey>/`:

| File | Shows |
| --- | --- |
| `NN-<label>.txt` | The command, its home, extra environment, exit code and full output |
| `NN-<label>.tree` | A home at that moment: each path, each link's target, each file's SHA-256 prefix |
| `log.txt` | Steps, drives and claims, in order, ending `PASSED` or `FAILED` |
| `run.json` | Journey, checkout, `HEAD`, scratch path, the run's token, the processes it started (role, pid, start time), state (`running`, `finished`, `interrupted`, `cleaned`) |

Proof standards:

- Drive the script a host runs, with the flags it is run with. Never call a function inside one, and never stand in
  for the action being proved.
- Read the side effect back from the home: a link's target, a line counted in `.bashrc`, a key read with `jq`, a
  stub's call log. A script's own `Linked` or `ok` line is not the proof.
- For `--check`, compare `.tree` files before and after: the claim is that nothing changed.
- For "repeat runs change nothing", compare the trees after the first and second `--apply`.
- The stubs stand in for `pi`, `claude`, `omarchy`, `launchctl` and the network. A journey proves what the scripts
  write and which commands they ask for; it proves nothing about `pi install` really installing, launchd really loading
  the watcher, Omarchy's shell loading the plugin, or a real NixOS or Omarchy host. Say so when you report.

## Prove a journey can fail

```sh
.agents/skills/verify/scripts/prove-breaks                       # every break
.agents/skills/verify/scripts/prove-breaks --journey shell-additions
.agents/skills/verify/scripts/prove-breaks --break "bashrc"     # breaks whose name contains this
```

`scripts/breaks.json` lists deliberate breaks: a file, an exact text, its broken replacement, the journey that must
catch it and the claim it must fail at. `prove-breaks` applies each one to the checkout, runs the journey, restores the
file byte for byte, and prints `CAUGHT`, `MISSED` (journey passed), `WRONG` (failed at another claim) or `STALE` (the
text is gone from the file). It refuses to start while a file it would break has uncommitted changes, and stops if a
file was not restored. A new or changed journey counts only once a break for each of its claims is `CAUGHT`; add the
break to `breaks.json` in the same change. When a script changes and a break goes `STALE`, rewrite the break against
the new text, never delete it to get a clean run.

## Cleanup

```sh
$V cleanup                  # every run under the evidence root not yet cleaned
$V cleanup <run directory>  # one run
```

Each run makes its scratch with `mktemp` directly in `$TMPDIR` and writes a marker into it,
`.dotfiles-verify-run`: a random token, the run directory, and one line per process the run started (the run and the
journey's subshell), each with its pid and start time. `run.json` records the same token and scratch path.

Cleanup trusts nothing in `run.json` until the scratch is shown to be this run's. It refuses, and stops and removes
nothing, unless the recorded scratch is exactly `<canonical $TMPDIR>/dotfiles-verify-scratch.XXXXXX`, is a real
directory (not a link) whose canonical path is that same path, and holds a marker (not a link) whose token and run
directory match. A refused run prints `REFUSED <dir>: <reason>`, keeps its state, and makes cleanup exit 1. For an
accepted run it takes the processes from the marker and sends SIGTERM to each, journey first and its descendants
before it, only while that pid still has the recorded start time and a `dotfiles-verify run` command line. Then it
removes the scratch and marks the run `cleaned`. A recorded scratch that no longer exists stops nothing. It never
removes evidence. Ctrl-C on a run stops the journey and removes the scratch through the same path check (below).

Every temporary directory the command makes, scratch and doctor's probe alike, goes through one check. `mktemp -d`
must succeed and return an existing, non-link directory, and its canonical path must be exactly
`<canonical temporary directory>/<prefix>.XXXXXX`; otherwise the command stops with the reason and uses nothing it
returned. Every `rm -rf` of such a directory first checks the path the same way and refuses anything else (empty, the
checkout, `$HOME`, `/`). `doctor`, `run` and `cleanup` all exit non-zero, before creating anything, when the temporary
directory is missing or unwritable. The command never runs `cd ""`, which stays in place under bash before 5.3.

Prove all of this, after any change to the command:

```sh
.agents/skills/verify/scripts/cleanup-proof                          # the bash on PATH and /bin/bash
.agents/skills/verify/scripts/cleanup-proof /opt/homebrew/bin/bash   # or the bashes you name
```

It takes no path. It makes its own output directory with the command's own `make_tmp`
(`<temporary directory>/dotfiles-verify-proof.XXXXXX`), writes everything there, never removes it, and prints its path
as the last line: read `cleanup-proof.txt` there, and remove the directory yourself when done. Its only arguments are
the bashes to run under; an argument that is not an executable that runs as bash is refused before anything is made.

It first checks that refusal: given a directory, a missing file and a non-bash executable, it exits non-zero and
makes no output directory. Then it starts `doctor`, `run` and `cleanup` from a directory holding a sentinel file with
`TMPDIR` missing, then unwritable, under each bash (default: the one on `PATH` and macOS's `/bin/bash` 3.2), and
checks each exits non-zero and the sentinel survives. It then feeds `cleanup` crafted `run.json` files (a
scratch-named directory without this run's marker, another directory, a `../` path, a symlink, the checkout, `$HOME`,
`/`, an empty path, a forged marker) naming an unrelated live process whose command line is `dotfiles-verify run fake`,
and checks all are refused and survive. Last, it runs a normal journey and a hung one and checks both are cleaned with
their evidence kept.

## Gotchas

- macOS only: `sandbox-exec` is the confinement. It is deprecated by Apple but present and working on this Mac
  (2026-11-16). Without it, `run` refuses to start; don't drop the sandbox to make it run elsewhere.
- `setup-platform-configs.sh` detects the platform from `$OSTYPE`, which bash sets itself, so these runs always take the
  macOS path. The Linux and Gnarbox branches are covered by `tests/test-gnarbox-dotfiles-profile.sh`, not here.
- The bash that runs each script is the first on `PATH`. On this Mac that is Nix's (`/run/current-system/sw/bin/bash`);
  scripts with `#!/usr/bin/env bash` therefore never run under macOS's bash 3.2 here, and a 3.2-only bug would pass.
- `reconcile-pi-bots-trust.mjs` skips in every journey: the throwaway home has no `~/code/pi-bots/bots`.
  `reconcile-omarchy-clipboard-bridge.sh` skips because `wl-paste` is absent. Neither is proven here; their own tests
  cover them (`tests/test-bot-alias.sh`, `tests/test-omarchy-clipboard-bridge.sh`).
- `omarchy-setup` and `platform-setup` need Matt Pocock's pinned commit in a local clone: the real reconciler's
  checkout (`~/.local/share/mattpocock-skills`, or `~/.pi/agent/upstreams/mattpocock-skills` before current `main`), or
  `DOTFILES_VERIFY_MATTPOCOCK_SOURCE`. Without it they fail with `FAIL: setup: the pinned commit … is in none of …`.
  Nothing in this skill reaches the network.
- `bash -i` in the sandbox prints "cannot set terminal process group" and "no job control"; expected.
- These journeys complement the repository's tests (`tests/test-reconcile-*.sh` and others), which drive each script
  alone with more edge cases. This skill drives the entry points a host runs end to end. It replaces none of them.

## Keeping it current

The feature map in `features/` is the maintained list of what to verify. When a setup script changes, update the
matching feature file, journey and break in the same change. `/maintain-verification-skill` audits the map against
the scripts.
