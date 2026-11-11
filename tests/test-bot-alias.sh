#!/usr/bin/env bash
# Tests the `bot` function in dot-config/shell/aliases.sh (bash and zsh), its helper
# dot-config/shell/bot-tab.py, and scripts/reconcile-pi-bots-trust.mjs.
# A fake `rex` records its calls and answers from fixture JSON; a fake Pi package
# stands in for Pi's trust store. Temporary HOMEs and bot directories only.

set -u

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ALIASES="$REPO_ROOT/dot-config/shell/aliases.sh"
TRUST="$REPO_ROOT/scripts/reconcile-pi-bots-trust.mjs"
TESTS=0
FAILURES=0
TMP="$(cd "$(mktemp -d "${TMPDIR:-/tmp}/bot-alias-test-XXXXXX")" && pwd -P)"
trap 'rm -rf "$TMP"' EXIT
export PYTHONDONTWRITEBYTECODE=1

check() { # <description> <expected> <actual>
    TESTS=$((TESTS + 1))
    if [[ "$2" == "$3" ]]; then
        echo "ok   $1"
    else
        echo "FAIL $1: expected '$2', got '$3'"
        FAILURES=$((FAILURES + 1))
    fi
}

contains() { # <description> <needle> <haystack>
    TESTS=$((TESTS + 1))
    if [[ "$3" == *"$2"* ]]; then
        echo "ok   $1"
    else
        echo "FAIL $1: '$2' not in '$3'"
        FAILURES=$((FAILURES + 1))
    fi
}

# --- fixtures -------------------------------------------------------------------
H="$TMP/home"
BOTS="$H/code/pi-bots/bots"
mkdir -p "$BOTS/bob" "$BOTS/steve" "$BOTS/.retired/old" "$BOTS/nopersona" "$BOTS/Bad" "$TMP/bin"
for b in bob steve .retired/old Bad; do echo persona >"$BOTS/$b/AGENTS.md"; done

# Fake rex: logs each call to $REX_LOG and answers from $REX_FIXTURES.
REX="$TMP/bin/rex"
cat >"$REX" <<'EOF'
#!/usr/bin/env python3
import json, os, sys
args = sys.argv[1:]
with open(os.environ["REX_LOG"], "a") as log:
    log.write(" ".join(args) + "\n")
fx = json.load(open(os.environ["REX_FIXTURES"]))
words = [a for a in args if a not in ("--autostart=false", "--json")]
while words and words[0] in ("--timeout", "-C"):
    words = words[2:]
key = " ".join(words[:2])
if key in fx.get("fail", {}):
    print(fx["fail"][key], file=sys.stderr); sys.exit(1)
answers = {"ls": "sessions", "window ls": "windows", "client ls": "clients", "api call": "view"}
for prefix, name in answers.items():
    if key == prefix or key.startswith(prefix + " "):
        print(json.dumps(fx.get(name, {}))); sys.exit(0)
EOF
chmod +x "$REX"

SID="session:bots-1"
fixtures() { # <file> [extra python dict items]
    python3 - "$1" "${2:-}" <<'EOF'
import json, sys
fx = {
    "sessions": {"sessions": [{"session_id": "session:other", "label": "Pi"}, {"session_id": "session:bots-1", "label": "bots"}]},
    "windows": {"windows": [{"window_id": "window:bob", "label": "bob"}, {"window_id": "window:steve", "label": "steve"}]},
    "clients": {"clients": [{"client_id": "client:studio", "info": {"kind": "app"}, "connection_state": "connected"},
                            {"client_id": "client:gone", "info": {"kind": "app"}, "connection_state": "lost"},
                            {"client_id": "client:cli", "info": {"kind": "cli"}}]},
    "view": {"windows": [
        {"layers": [{"blocks": [{"block_id": "block:other", "owner": "client:studio"}]}]},
        {"layers": [{"blocks": [{"block_id": "block:unowned"},
                                {"block_id": "block:me", "owner": "client:mbp"}]}]}]},
}
if sys.argv[2]:
    fx.update(eval(sys.argv[2]))
json.dump(fx, open(sys.argv[1], "w"))
EOF
}

shell_opts() { [[ "$1" == zsh ]] && echo -f || echo --norc; }

# run <shell> <fixtures> <cmd> [env...]: source the aliases in a clean shell, run cmd.
# Prints stdout+stderr, then "rc=N".
run() {
    local sh="$1" fx="$2" cmd="$3"; shift 3
    : >"$TMP/rex.log"
    env -i PATH="/usr/bin:/bin:/opt/homebrew/bin" HOME="$H" PI_BOTS_REX="$REX" \
        REX_LOG="$TMP/rex.log" REX_FIXTURES="$fx" PYTHONDONTWRITEBYTECODE=1 "$@" \
        "$sh" "$(shell_opts "$sh")" -c 'source "$1" && eval "$2"; echo "rc=$?"' _ "$ALIASES" "$cmd" 2>&1
}

FX="$TMP/fx.json"; fixtures "$FX"

for sh in bash zsh; do
    command -v "$sh" >/dev/null 2>&1 || { echo "skip $sh (not installed)"; continue; }

    out="$(run "$sh" "$FX" 'bot')"
    check "$sh: bot lists the bots (AGENTS.md, valid names, not .retired)" $'bob\nsteve\nrc=0' "$out"

    out="$(run "$sh" "$FX" 'bot bob' REX_SESSION=session:desk REX_BLOCK=block:me)"
    check "$sh: bot bob succeeds" "rc=0" "$out"
    contains "$sh: bot bob makes Bob's tab active in the bots session" \
        "window focus -s $SID window:bob" "$(cat "$TMP/rex.log")"
    contains "$sh: bot bob switches the app that owns the calling pane" \
        "-C client:mbp do session.select session_id=$SID window_id=window:bob" "$(cat "$TMP/rex.log")"

    out="$(run "$sh" "$FX" 'bot bob' REX_SESSION=session:desk REX_BLOCK=block:unowned)"
    contains "$sh: an unowned pane falls back to the only connected app (a lost one doesn't count)" \
        "-C client:studio do session.select session_id=$SID window_id=window:bob" "$(cat "$TMP/rex.log")"

    out="$(run "$sh" "$FX" 'bot steve')"
    check "$sh: outside Rex, bot steve succeeds" "rc=0" "$out"
    contains "$sh: outside Rex, the only connected app is switched" \
        "-C client:studio do session.select session_id=$SID window_id=window:steve" "$(cat "$TMP/rex.log")"

    out="$(run "$sh" "$FX" 'bot carol')"
    contains "$sh: an unknown bot is refused, naming the bots" "no bot 'carol'" "$out"
    contains "$sh: an unknown bot lists the known ones" "(bots: bob, steve)" "$out"
    contains "$sh: an unknown bot exits 2" "rc=2" "$out"
    check "$sh: an unknown bot calls no rex" "" "$(cat "$TMP/rex.log")"

    out="$(run "$sh" "$FX" 'bot nopersona')"
    contains "$sh: a directory without AGENTS.md is no bot" "rc=2" "$out"
    out="$(run "$sh" "$FX" 'bot old')"
    contains "$sh: a retired bot is no bot" "rc=2" "$out"
    out="$(run "$sh" "$FX" 'bot ../bob')"
    contains "$sh: a path is refused" "rc=2" "$out"
    out="$(run "$sh" "$FX" 'bot bob steve')"
    contains "$sh: two names are a usage error" "usage: bot [<name>]" "$out"

    mkdir -p "$BOTS/carol"; echo persona >"$BOTS/carol/AGENTS.md"
    out="$(run "$sh" "$FX" 'bot')"
    contains "$sh: a bot made after the shell started is listed" "carol" "$out"
    rm -rf "$BOTS/carol"

    FX2="$TMP/fx-nosession.json"; fixtures "$FX2" '{"sessions": {"sessions": []}}'
    out="$(run "$sh" "$FX2" 'bot bob')"
    contains "$sh: no bots session is an error" "no 'bots' Rex session" "$out"
    contains "$sh: no bots session exits 1" "rc=1" "$out"

    FX3="$TMP/fx-notab.json"; fixtures "$FX3" '{"windows": {"windows": [{"window_id": "window:steve", "label": "steve"}]}}'
    out="$(run "$sh" "$FX3" 'bot bob')"
    contains "$sh: a bot with no tab yet is reported" "bob has no tab" "$out"
    check "$sh: a bot with no tab is never given one" "" "$(grep -E 'window (new|close)|^new ' "$TMP/rex.log")"

    FX4="$TMP/fx-refused.json"; fixtures "$FX4" '{"fail": {"do session.select": "refused: Remote Control is off"}}'
    out="$(run "$sh" "$FX4" 'bot bob' REX_SESSION=session:desk REX_BLOCK=block:me)"
    contains "$sh: an app that refuses still leaves the tab active (rc 0)" "rc=0" "$out"
    contains "$sh: an app that refuses is reported" "Remote Control" "$out"

    FX5="$TMP/fx-twoapps.json"; fixtures "$FX5" '{"clients": {"clients": [{"client_id": "client:a", "info": {"kind": "app"}}, {"client_id": "client:b", "info": {"kind": "app"}}]}}'
    out="$(run "$sh" "$FX5" 'bot bob')"
    contains "$sh: two apps and no pane: tab active, no app picked" "no single Rex app" "$out"
    check "$sh: two apps and no pane: no app is switched" "" "$(grep 'session.select' "$TMP/rex.log")"

    out="$(run "$sh" "$FX" 'bot bob' PI_BOTS_DIR="$TMP/elsewhere")"
    contains "$sh: no bot directories, no bot function" "not found" "$out"

    mkdir -p "$TMP/elsewhere/zed"; echo persona >"$TMP/elsewhere/zed/AGENTS.md"
    out="$(run "$sh" "$FX" 'bot' PI_BOTS_DIR="$TMP/elsewhere")"
    check "$sh: PI_BOTS_DIR names the bot directories" $'zed\nrc=0' "$out"
    rm -rf "$TMP/elsewhere"

    # Completion offers the bots, read at completion time.
    if [[ "$sh" == bash ]]; then
        out="$(env -i PATH="/usr/bin:/bin:/opt/homebrew/bin" HOME="$H" bash --norc -c \
            'source "$1"; COMP_WORDS=(bot s); COMP_CWORD=1; _bot_complete; echo "${COMPREPLY[*]}"' _ "$ALIASES" 2>&1)"
        check "bash: completion offers matching bots" "steve" "$out"
        out="$(env -i PATH="/usr/bin:/bin:/opt/homebrew/bin" HOME="$H" bash --norc -c \
            'source "$1"; COMP_WORDS=(bot ""); COMP_CWORD=1; _bot_complete; echo "${COMPREPLY[*]}"' _ "$ALIASES" 2>&1)"
        check "bash: completion offers only valid bot names (not Bad, .retired, no AGENTS.md)" "bob steve" "$out"
        out="$(env -i PATH="/usr/bin:/bin:/opt/homebrew/bin" HOME="$H" bash --norc -c \
            'source "$1"; complete -p bot' _ "$ALIASES" 2>&1)"
        check "bash: completion is registered" "complete -F _bot_complete bot" "$out"
    fi
done

# The real rex is found from a pane's REX_BIN_DIR when PI_BOTS_REX is unset.
mkdir -p "$TMP/rexbin"; cp "$REX" "$TMP/rexbin/rex"
: >"$TMP/rex.log"
env -i PATH="/usr/bin:/bin:/opt/homebrew/bin" HOME="$H" REX_BIN_DIR="$TMP/rexbin" REX_LOG="$TMP/rex.log" \
    REX_FIXTURES="$FX" PYTHONDONTWRITEBYTECODE=1 bash --norc -c 'source "$1" && bot bob' _ "$ALIASES" >/dev/null 2>&1
contains "rex is found through REX_BIN_DIR" "window focus -s $SID window:bob" "$(cat "$TMP/rex.log")"

# A checkout path with a space, $ and a backtick is used as is, never expanded.
ODD="$TMP/odd \$HOME \`false\`/shell"
mkdir -p "$ODD"; cp "$ALIASES" "$REPO_ROOT/dot-config/shell/bot-tab.py" "$ODD/"
for sh in bash zsh; do
    command -v "$sh" >/dev/null 2>&1 || continue
    out="$(env -i PATH="/usr/bin:/bin:/opt/homebrew/bin" HOME="$H" PYTHONDONTWRITEBYTECODE=1 \
        "$sh" "$(shell_opts "$sh")" -c 'source "$1" && bot; echo "rc=$?"' _ "$ODD/aliases.sh" 2>&1)"
    check "$sh: an odd checkout path works" $'bob\nsteve\nrc=0' "$out"
done

# zsh completion function (needs compsys; checked by definition, not by a live completion).
if command -v zsh >/dev/null 2>&1; then
    out="$(env -i PATH="/usr/bin:/bin" HOME="$H" zsh -f -c \
        'autoload -Uz compinit && compinit -D -u; source "$1"; print -r -- ${_comps[bot]:-none}' _ "$ALIASES" 2>&1)"
    check "zsh: completion is registered when compsys is loaded" "_bot" "$out"
    out="$(env -i PATH="/usr/bin:/bin" HOME="$H" zsh -f -c \
        'autoload -Uz compinit && compinit -D -u; source "$1"; compadd() { shift; print -r -- "$*"; }; CURRENT=2; _bot' _ "$ALIASES" 2>&1)"
    check "zsh: completion offers only valid bot names" "bob steve" "$out"
    mkdir -p "$TMP/emptybots"
    out="$(env -i PATH="/usr/bin:/bin" HOME="$H" PI_BOTS_DIR="$TMP/emptybots" zsh -f -c \
        'source "$1"; _bot_names; echo "rc=$?"' _ "$ALIASES" 2>&1)"
    check "zsh: no bots, completion is quiet (no nomatch error)" "rc=0" "$out"
fi

# --- scripts/reconcile-pi-bots-trust.mjs ------------------------------------------
if ! command -v node >/dev/null 2>&1; then
    echo "skip trust reconciler (node is not installed)"
else
    PKG="$TMP/pkg/node_modules/@earendil-works/pi-coding-agent"
    mkdir -p "$PKG/dist" "$TMP/pibin"
    echo '{"name": "@earendil-works/pi-coding-agent"}' >"$PKG/package.json"
    # Stand-in for Pi's store: same nearest-ancestor rule and canonical keys.
    cat >"$PKG/dist/index.js" <<'EOF'
import { existsSync, readFileSync, writeFileSync, realpathSync, mkdirSync } from "node:fs";
import { dirname, join } from "node:path";
export function getAgentDir() { return process.env.PI_CODING_AGENT_DIR; }
export class ProjectTrustStore {
  constructor(dir) { this.path = join(dir, "trust.json"); }
  read() { return existsSync(this.path) ? JSON.parse(readFileSync(this.path, "utf8")) : {}; }
  getEntry(cwd) {
    const data = this.read();
    let dir = realpathSync(cwd);
    while (true) {
      if (data[dir] === true || data[dir] === false) return { path: dir, decision: data[dir] };
      if (dirname(dir) === dir) return null;
      dir = dirname(dir);
    }
  }
  set(cwd, decision) {
    const data = this.read(); data[realpathSync(cwd)] = decision;
    mkdirSync(dirname(this.path), { recursive: true });
    writeFileSync(this.path, JSON.stringify(data));
  }
}
EOF
    printf '#!/bin/sh\n' >"$PKG/dist/cli.js"; chmod +x "$PKG/dist/cli.js"
    ln -s "$PKG/dist/cli.js" "$TMP/pibin/pi"
    AG="$TMP/agent"
    trust() { env -i PATH="$TMP/pibin:/usr/bin:/bin:$(dirname "$(command -v node)")" HOME="$H" PI_CODING_AGENT_DIR="$AG" "$@" node "$TRUST" "$MODE" 2>&1; echo "rc=$?"; }
    real_bots="$(cd "$BOTS" && pwd -P)"

    MODE=--check; out="$(trust)"
    contains "trust: check reports the missing decision" "MISSING" "$out"
    contains "trust: check exits 1 on drift" "rc=1" "$out"
    check "trust: check writes nothing" "absent" "$([[ -e "$AG/trust.json" ]] && echo present || echo absent)"

    MODE=--apply; out="$(trust)"
    contains "trust: apply trusts the bots' parent" "Trusted $real_bots" "$out"
    contains "trust: apply exits 0" "rc=0" "$out"
    check "trust: the decision names the bots' parent" "true" \
        "$(node -e 'const d=JSON.parse(require("fs").readFileSync(process.argv[1]));console.log(d[process.argv[2]])' "$AG/trust.json" "$real_bots")"

    MODE=--check; out="$(trust)"
    contains "trust: check passes once applied" "OK   Pi trusts $real_bots" "$out"
    contains "trust: check exits 0 once applied" "rc=0" "$out"

    # A saved "do not trust" for the directory is Bryan's: left alone.
    echo "{\"$real_bots\": false}" >"$AG/trust.json"
    MODE=--apply; out="$(trust)"
    contains "trust: a saved refusal is reported" "do not trust" "$out"
    check "trust: a saved refusal is kept" "false" \
        "$(node -e 'const d=JSON.parse(require("fs").readFileSync(process.argv[1]));console.log(d[process.argv[2]])' "$AG/trust.json" "$real_bots")"

    # A refusal on a parent is not this directory's own: apply trusts the bots' parent.
    echo "{\"$(dirname "$real_bots")\": false}" >"$AG/trust.json"
    MODE=--check; out="$(trust)"
    contains "trust: an inherited refusal is drift" "inherits" "$out"
    MODE=--apply; out="$(trust)"
    contains "trust: an inherited refusal is overridden for the bots only" "Trusted $real_bots" "$out"
    contains "trust: overriding a parent's refusal says so" "overriding \"do not trust\" saved for $(dirname "$real_bots")" "$out"

    # Trust inherited from a parent already covers it.
    echo "{\"$H\": true}" >"$AG/trust.json"
    MODE=--check; out="$(trust)"
    contains "trust: trust through a parent passes" "through $H" "$out"

    # Real hosts reach the bots through a symlink (~/code/pi-bots -> repos/pi-bots); Pi keys
    # trust by the real path, so the script must compare and save real paths.
    ln -s "$H/code/pi-bots" "$TMP/linked"
    echo "{\"$real_bots\": false}" >"$AG/trust.json"
    MODE=--apply; out="$(trust PI_BOTS_DIR="$TMP/linked/bots")"
    contains "trust: through a symlink, a saved refusal is still found and kept" "do not trust" "$out"
    check "trust: through a symlink, the refusal is not overwritten" "{\"$real_bots\": false}" "$(cat "$AG/trust.json")"
    echo '{}' >"$AG/trust.json"
    out="$(trust PI_BOTS_DIR="$TMP/linked/bots")"
    contains "trust: through a symlink, the real path is trusted" "Trusted $real_bots" "$out"
    check "trust: through a symlink, the saved key is the real path" "true" \
        "$(node -e 'const d=JSON.parse(require("fs").readFileSync(process.argv[1]));console.log(d[process.argv[2]])' "$AG/trust.json" "$real_bots")"
    MODE=--check; out="$(trust PI_BOTS_DIR="$TMP/linked/bots")"
    contains "trust: through a symlink, check passes once applied" "OK   Pi trusts $real_bots" "$out"

    MODE=--apply; out="$(trust PI_BOTS_DIR="$TMP/none")"
    contains "trust: no bot directories, skipped" "Skipped (no bot directories" "$out"
    out="$(env -i PATH="/usr/bin:/bin:$(dirname "$(command -v node)")" HOME="$H" PI_CODING_AGENT_DIR="$AG" node "$TRUST" --apply 2>&1)"
    if command -v pi >/dev/null 2>&1 && [[ "$(dirname "$(command -v node)")" == "$(dirname "$(command -v pi)")" ]]; then
        echo "skip trust: no-Pi case (pi shares node's directory here)"
    else
        contains "trust: no Pi, skipped" "Skipped (Pi is not installed)" "$out"
    fi
    out="$(node "$TRUST" --nope 2>&1; echo "rc=$?")"
    contains "trust: a bad mode is a usage error" "rc=2" "$out"
fi

echo
echo "$((TESTS - FAILURES))/$TESTS passed"
[[ $FAILURES -eq 0 ]]
