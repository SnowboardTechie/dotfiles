#!/usr/bin/env bash
# reconcile-mattpocock-skills.sh — load Matt Pocock's promoted skills in Pi.
#
# Keeps a plain git checkout of https://github.com/mattpocock/skills at the
# commit pinned in dot-agents/upstreams/mattpocock-skills.json (the only place
# the pin lives), and lists the checkout's skills/engineering and
# skills/productivity directories in `skills` of ~/.pi/agent/settings.json.
#
# Why settings paths and not `pi install git:...`: a package install also loads
# the unpromoted skills (in-progress/, misc/), and the local pool copies win the
# name clashes. Listed in `skills`, exactly the promoted ones load, and his copy
# of a name wins once no copy of that name is in ~/.agents/skills or
# ~/.pi/agent/skills. A copy there can still win: started from `~` (or a non-Git
# directory under it) Pi reads ~/.agents/skills as project skills, which beat
# these settings. So both modes warn about any such copy; neither removes it.
#
# The checkout is never discarded or reset: local modifications, or a checkout
# of some other repository, stop --apply with a report.

set -euo pipefail

usage() {
    cat <<'EOF'
Usage: reconcile-mattpocock-skills.sh (--check | --apply)

  --check   Report the pin, the checkout's commit and the two Pi settings
            entries. Never mutates the filesystem or uses the network.
  --apply   Clone or move the checkout to the pin and add the two entries.
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

SCRIPT_DIR="$(cd "${BASH_SOURCE[0]%/*}" && pwd)"
LEDGER="$SCRIPT_DIR/../dot-agents/upstreams/mattpocock-skills.json"
AGENT_DIR="$HOME/.pi/agent"
SETTINGS="$AGENT_DIR/settings.json"
CHECKOUT="$AGENT_DIR/upstreams/mattpocock-skills"
SKILL_DIRS=("$CHECKOUT/skills/engineering" "$CHECKOUT/skills/productivity")

echo "Matt Pocock's skills in Pi ($MODE)"

for tool in pi git python3; do
    if ! command -v "$tool" >/dev/null 2>&1; then
        echo "  Skipped ($tool is not installed)"
        exit 0
    fi
done

read_ledger() { # <key>
    python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))[sys.argv[2]])' "$LEDGER" "$1"
}
UPSTREAM="$(read_ledger upstream)"
PIN="$(read_ledger commit)"
if [[ ! "$PIN" =~ ^[0-9a-f]{40}$ ]]; then
    echo "  ERROR: pinned commit in $LEDGER is not a full SHA: $PIN" >&2
    exit 1
fi
echo "  pin: $PIN"

same_repo() { # <url> <url>
    local a="${1%/}" b="${2%/}"
    [[ "${a%.git}" == "${b%.git}" ]]
}

# Inspect the checkout without writing to it (no index refresh, no fetch).
# Sets STATE to absent | foreign | dirty | clean, and HEAD_SHA.
inspect_checkout() {
    HEAD_SHA=""
    if [[ ! -e "$CHECKOUT" ]]; then
        STATE="absent"; return
    fi
    local top origin
    top="$(git -C "$CHECKOUT" rev-parse --show-toplevel 2>/dev/null || true)"
    if [[ -z "$top" || "$(cd "$top" && pwd -P)" != "$(cd "$CHECKOUT" && pwd -P)" ]]; then
        STATE="foreign"; return
    fi
    origin="$(git -C "$CHECKOUT" config --get remote.origin.url 2>/dev/null || true)"
    if ! same_repo "$origin" "$UPSTREAM"; then
        STATE="foreign"; return
    fi
    HEAD_SHA="$(git -C "$CHECKOUT" rev-parse --verify --quiet HEAD 2>/dev/null || true)"
    if [[ -n "$(git --no-optional-locks -C "$CHECKOUT" status --porcelain --untracked-files=all 2>/dev/null)" ]]; then
        STATE="dirty"; return
    fi
    STATE="clean"
}

# Print the entries of SKILL_DIRS missing from `skills` in settings.json.
missing_entries() {
    python3 - "$SETTINGS" "${SKILL_DIRS[@]}" <<'PY'
import json, sys
path, *wanted = sys.argv[1:]
try:
    skills = json.load(open(path)).get("skills") or []
except FileNotFoundError:
    skills = []
for w in wanted:
    if w not in skills:
        print(w)
PY
}

add_entries() {
    python3 - "$SETTINGS" "${SKILL_DIRS[@]}" <<'PY'
import json, os, sys
path, *wanted = sys.argv[1:]
os.makedirs(os.path.dirname(path), exist_ok=True)
try:
    settings = json.load(open(path))
except FileNotFoundError:
    settings = {}
skills = settings.setdefault("skills", [])
skills.extend(w for w in wanted if w not in skills)
tmp = path + ".tmp"
with open(tmp, "w") as f:
    json.dump(settings, f, indent=2)
    f.write("\n")
os.replace(tmp, path)
PY
}

inspect_checkout
case "$STATE" in
    absent) echo "  checkout: missing ($CHECKOUT)" ;;
    foreign) echo "  checkout: $CHECKOUT is not a checkout of $UPSTREAM" ;;
    dirty) echo "  checkout: ${HEAD_SHA:-no commit}, with local modifications" ;;
    clean)
        if [[ "$HEAD_SHA" == "$PIN" ]]; then
            echo "  ok: checkout at the pin"
        else
            echo "  checkout: $HEAD_SHA (not the pin)"
        fi
        ;;
esac

# Warn about a local copy of one of his promoted names, which can win over his.
# Names come from the checkout; without one there is nothing to compare.
warn_shadowing() {
    local dir name dest
    [[ -d "$CHECKOUT/skills" ]] || return 0
    for dir in "${SKILL_DIRS[@]}"; do
        for name in "$dir"/*/; do
            name="${name%/}"; name="${name##*/}"
            [[ -f "$dir/$name/SKILL.md" ]] || continue
            for dest in "$HOME/.agents/skills" "$HOME/.pi/agent/skills"; do
                if [[ -e "$dest/$name" ]]; then
                    echo "  WARNING: $dest/$name shares a name with his $name and can win over it in Pi"
                fi
            done
        done
    done
}

if [[ "$MODE" == "check" ]]; then
    warn_shadowing
    missing="$(missing_entries)"
    for dir in "${SKILL_DIRS[@]}"; do
        if grep -qxF "$dir" <<<"$missing"; then
            echo "  MISSING settings entry $dir"
        else
            echo "  ok: settings entry $dir"
        fi
    done
    exit 0
fi

case "$STATE" in
    foreign)
        echo "  STOPPED: move $CHECKOUT aside; it is not a checkout of $UPSTREAM" >&2
        exit 1
        ;;
    dirty)
        echo "  STOPPED: $CHECKOUT has local modifications; nothing was discarded." >&2
        echo "  Inspect them with: git -C '$CHECKOUT' status" >&2
        exit 1
        ;;
    absent)
        mkdir -p "${CHECKOUT%/*}"
        tmp="$CHECKOUT.partial.$$"
        trap 'rm -rf "$tmp"' EXIT
        git clone --quiet --no-checkout "$UPSTREAM" "$tmp"
        git -C "$tmp" -c advice.detachedHead=false checkout --quiet --detach "$PIN"
        mv "$tmp" "$CHECKOUT"
        trap - EXIT
        echo "  Cloned $UPSTREAM at $PIN"
        ;;
    clean)
        if [[ "$HEAD_SHA" != "$PIN" ]]; then
            if ! git -C "$CHECKOUT" cat-file -e "$PIN^{commit}" 2>/dev/null; then
                git -C "$CHECKOUT" fetch --quiet origin
            fi
            git -C "$CHECKOUT" -c advice.detachedHead=false checkout --quiet --detach "$PIN"
            echo "  Moved checkout $HEAD_SHA -> $PIN"
        fi
        ;;
esac

if [[ -n "$(missing_entries)" ]]; then
    add_entries
    echo "  Added settings entries for skills/engineering and skills/productivity"
else
    echo "  ok: settings entries present"
fi

warn_shadowing

exit 0
