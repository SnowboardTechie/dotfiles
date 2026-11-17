#!/usr/bin/env bash
# reconcile-pi-pstack.sh — keep pstack's own Pi agent directory, ~/.pi/pstack.
#
# Unattended builds run Pi with PI_CODING_AGENT_DIR=~/.pi/pstack. pstack stays
# out of ~/.pi/agent on purpose: 66 of the port's 67 skills are model-invocable,
# so installing it there would load them into every Pi session and bot. This
# reconciler never touches ~/.pi/agent. It makes the pstack directory hold:
#   - settings.json: the pi-claude-code package and the pstack port
#     (git:github.com/michael-denyer/pstack-claude@<commit>, the commit read
#     from dot-agents/upstreams/pstack-claude.json; another pin of the port is
#     removed), defaultProvider claude-code, defaultModel claude-opus-5-5.
#     Packages go through `pi install`/`pi remove` with PI_CODING_AGENT_DIR set.
#   - pstack-models.md: a link to dot-agents/pstack-forgejo/pstack-models.md.
#   - auth.json (mode 600) with the opencode-go key as a `!cat` command that
#     reads ~/.secrets/opencode-api-key. Created only when absent; an existing
#     one is never rewritten or printed, only reported when it lacks the entry.
#   - AGENTS.md: a link to dot-pi/agent/AGENTS.md.
# Any other file in the directory is left alone, and so is a foreign file or
# link where one of the links above belongs (reported).
# PI_PSTACK_DIR overrides the directory (tests). Skips without pi or claude.

set -euo pipefail

usage() {
    cat <<'EOF'
Usage: reconcile-pi-pstack.sh (--check | --apply)

  --check   Report what the pstack Pi agent directory lacks. Never mutates
            the filesystem.
  --apply   Install the packages, set the defaults, link the model sheet and
            AGENTS.md, and create auth.json when it is absent.
EOF
}

MODE=""
if [[ $# -eq 1 ]]; then
    case "$1" in
        --check) MODE="check" ;;
        --apply) MODE="apply" ;;
        -h|--help) usage; exit 0 ;;
    esac
fi
if [[ -z "$MODE" ]]; then
    usage >&2
    exit 2
fi

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LEDGER="$REPO_ROOT/dot-agents/upstreams/pstack-claude.json"
SHEET_REL="dot-agents/pstack-forgejo/pstack-models.md"
INSTRUCTIONS_REL="dot-pi/agent/AGENTS.md"
DIR="${PI_PSTACK_DIR:-$HOME/.pi/pstack}"
SETTINGS="$DIR/settings.json"
AUTH="$DIR/auth.json"
CLAUDE_CODE="https://github.com/earendil-works/pi-claude-code"
PSTACK_REPO="git:github.com/michael-denyer/pstack-claude"
PROVIDER="claude-code"
MODEL="claude-opus-5-5"

echo "Pi pstack directory ($MODE) for $DIR"

if ! command -v pi >/dev/null 2>&1; then
    echo "  Skipped (pi is not installed)"
    exit 0
fi
if ! command -v claude >/dev/null 2>&1; then
    echo "  Skipped (the claude CLI is not installed; the claude-code provider needs it)"
    exit 0
fi

commit="$(python3 - "$LEDGER" <<'PY'
import json, re, sys
c = json.load(open(sys.argv[1])).get("commit") or ""
print(c if re.fullmatch(r"[0-9a-f]{40}", c) else "")
PY
)"
if [[ -z "$commit" ]]; then
    echo "  ERROR: no full commit in $LEDGER" >&2
    exit 1
fi
PSTACK="$PSTACK_REPO@$commit"

pi_here() { PI_CODING_AGENT_DIR="$DIR" command pi "$@"; }

# Configured package sources matching a regex, one per line.
sources_matching() {
    python3 - "$SETTINGS" "$1" <<'PY'
import json, re, sys
try:
    d = json.load(open(sys.argv[1]))
except FileNotFoundError:
    d = {}
for p in d.get("packages") or []:
    src = p if isinstance(p, str) else (p.get("source") or "")
    if re.fullmatch(sys.argv[2], src):
        print(src)
PY
}

# ensure_package <wanted source> <regex for any version of it>
ensure_package() {
    local want="$1" installed other
    installed="$(sources_matching "$2")"
    if [[ "$installed" == "$want" ]]; then
        echo "  ok: package $want"
        return
    fi
    while IFS= read -r other; do
        [[ -z "$other" || "$other" == "$want" ]] && continue
        if [[ "$MODE" == "apply" ]]; then
            pi_here remove "$other"
            echo "  Removed $other"
        else
            echo "  WOULD REMOVE $other"
        fi
    done <<<"$installed"
    if grep -qxF "$want" <<<"$installed"; then
        echo "  ok: package $want"
    elif [[ "$MODE" == "apply" ]]; then
        mkdir -p "$DIR"
        pi_here install "$want"
        echo "  Installed $want"
    else
        echo "  MISSING package $want"
    fi
}

ensure_package "$CLAUDE_CODE" "https://github\\.com/earendil-works/pi-claude-code"
ensure_package "$PSTACK" "git:github\\.com/michael-denyer/pstack-claude(@.*)?"

# Default provider and model: this directory exists for pstack, so they are set.
for pair in "defaultProvider=$PROVIDER" "defaultModel=$MODEL"; do
    key="${pair%%=*}"
    want="${pair#*=}"
    current="$(python3 - "$SETTINGS" "$key" <<'PY'
import json, sys
try:
    d = json.load(open(sys.argv[1]))
except FileNotFoundError:
    d = {}
print(d.get(sys.argv[2]) or "")
PY
)"
    if [[ "$current" == "$want" ]]; then
        echo "  ok: $key $want"
    elif [[ "$MODE" == "apply" ]]; then
        mkdir -p "$DIR"
        python3 - "$SETTINGS" "$key" "$want" <<'PY'
import json, os, sys
path, key, value = sys.argv[1:]
try:
    d = json.load(open(path))
except FileNotFoundError:
    d = {}
d[key] = value
tmp = path + ".tmp"
with open(tmp, "w") as f:
    json.dump(d, f, indent=2)
    f.write("\n")
if os.path.exists(path):
    os.chmod(tmp, os.stat(path).st_mode & 0o777)
os.replace(tmp, path)
PY
        echo "  Set $key ${current:-<unset>} -> $want"
    else
        echo "  WOULD SET $key ${current:-<unset>} -> $want"
    fi
done

# ensure_link <path in the directory> <path relative to the repository>
# A link to the same relative path in another checkout of this repository (a
# worktree, or ~/code/dotfiles) is this reconciler's own and is repointed here.
ensure_link() {
    local dest="$1" src="$REPO_ROOT/$2" target
    target="$(readlink "$dest" 2>/dev/null || true)"
    if [[ -L "$dest" && "$target" == "$src" ]]; then
        echo "  ok: $dest"
    elif [[ -L "$dest" && "$target" == /*"/$2" ]]; then
        if [[ "$MODE" == "apply" ]]; then
            ln -sfn "$src" "$dest"
            echo "  Repointed $dest -> $src"
        else
            echo "  WOULD REPOINT $dest from $target"
        fi
    elif [[ -e "$dest" || -L "$dest" ]]; then
        echo "  WARNING: $dest is not managed by this repository, skipping"
    elif [[ "$MODE" == "apply" ]]; then
        mkdir -p "$DIR"
        ln -s "$src" "$dest"
        echo "  Linked $dest"
    else
        echo "  MISSING $dest"
    fi
}

ensure_link "$DIR/pstack-models.md" "$SHEET_REL"
ensure_link "$DIR/AGENTS.md" "$INSTRUCTIONS_REL"

# auth.json: created when absent, never rewritten or printed.
if [[ -e "$AUTH" || -L "$AUTH" ]]; then
    has_entry="$(python3 - "$AUTH" <<'PY' 2>/dev/null || echo unreadable
import json, sys
d = json.load(open(sys.argv[1]))
e = d.get("opencode-go") if isinstance(d, dict) else None
print("yes" if isinstance(e, dict) and e.get("key") else "no")
PY
)"
    case "$has_entry" in
        yes) echo "  ok: $AUTH has an opencode-go key" ;;
        no) echo "  NOTE: $AUTH has no opencode-go entry; add the !cat form from dot-agents/pstack-forgejo/models.md" ;;
        *) echo "  WARNING: $AUTH is not readable JSON; left alone" ;;
    esac
    mode="$(stat -c %a "$AUTH" 2>/dev/null || stat -f %Lp "$AUTH")"
    [[ "$mode" == "600" ]] || echo "  NOTE: $AUTH is mode $mode, not 600"
elif [[ "$MODE" == "apply" ]]; then
    mkdir -p "$DIR"
    (
        umask 077
        cat >"$AUTH" <<'EOF'
{
  "opencode-go": {
    "type": "api_key",
    "key": "!cat \"$HOME/.secrets/opencode-api-key\""
  }
}
EOF
    )
    chmod 600 "$AUTH"
    echo "  Created $AUTH (opencode-go key read from ~/.secrets/opencode-api-key)"
else
    echo "  MISSING $AUTH"
fi

exit 0
