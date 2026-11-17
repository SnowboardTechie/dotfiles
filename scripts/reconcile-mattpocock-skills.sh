#!/usr/bin/env bash
# reconcile-mattpocock-skills.sh — load Matt Pocock's promoted skills in Pi,
# Claude Code and OpenCode from one checkout.
#
# Keeps a plain git checkout of https://github.com/mattpocock/skills at the
# commit pinned in dot-agents/skill-sources/mattpocock-skills.json (the only place
# the pin lives) in ~/.local/share/mattpocock-skills, shared by every harness.
# His promoted skills are the directories with a SKILL.md directly under the
# checkout's skills/engineering and skills/productivity.
#
#   - Pi: lists those two directories in `skills` of ~/.pi/agent/settings.json
#     (only when `pi` is installed).
#   - Claude Code (~/.claude/skills) and OpenCode (~/.config/opencode/skills):
#     one symlink per promoted skill, named for the skill, pointing at its
#     directory in the checkout. This script owns only links whose target lies
#     in the checkout: it creates missing ones, repoints its own stale ones and
#     removes its own links for skills he no longer promotes. A real
#     directory, a file or a link pointing anywhere else is reported and kept.
#     RECONCILE_OPENCODE_SKILLS=0 creates no OpenCode links and removes this
#     script's existing ones, as scripts/reconcile-agent-skills.sh does.
#
# Why not `pi install git:...` or his Claude Code plugin: a Pi package
# also loads his unpromoted skills (in-progress/, misc/), and the plugin
# namespaces every skill and moves its own pin. Here the source record holds the one
# pin, which the pi-bots scheduled job mattpocock-skill-watch advances.
#
# In Pi his copy of a name wins once no copy of that name is in
# ~/.agents/skills or ~/.pi/agent/skills: started from `~` (or a non-Git
# directory under it) Pi reads ~/.agents/skills as project skills, which beat
# these settings. So both modes warn about any such copy; neither removes it.
#
# Earlier versions kept the checkout in ~/.pi/agent/upstreams/mattpocock-skills.
# --apply moves a clean one from there, or removes it when a checkout already
# exists at the new place and every commit of the old one is on its origin, and
# replaces its two Pi settings entries with the new ones.
#
# The checkout is never discarded or reset: local modifications, or a checkout
# of some other repository, stop --apply with a report.

set -euo pipefail

usage() {
    cat <<'EOF'
Usage: reconcile-mattpocock-skills.sh (--check | --apply)

  --check   Report the pin, the checkout, the Pi settings entries and every
            Claude Code and OpenCode link --apply would create, repoint or
            remove. Never mutates the filesystem or uses the network.
  --apply   Clone or move the checkout to the pin, set the Pi entries and
            reconcile the Claude Code and OpenCode links.

  RECONCILE_OPENCODE_SKILLS=0 creates no OpenCode links and removes this
            script's existing ones.
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
SOURCE_RECORD="$SCRIPT_DIR/../dot-agents/skill-sources/mattpocock-skills.json"
SETTINGS="$HOME/.pi/agent/settings.json"
CHECKOUT="$HOME/.local/share/mattpocock-skills"
OLD_CHECKOUT="$HOME/.pi/agent/upstreams/mattpocock-skills"
SKILL_DIRS=("$CHECKOUT/skills/engineering" "$CHECKOUT/skills/productivity")
OLD_SKILL_DIRS=("$OLD_CHECKOUT/skills/engineering" "$OLD_CHECKOUT/skills/productivity")
CLAUDE_DEST="$HOME/.claude/skills"
OPENCODE_DEST="$HOME/.config/opencode/skills"

echo "Matt Pocock's skills ($MODE)"

for tool in git python3; do
    if ! command -v "$tool" >/dev/null 2>&1; then
        echo "  Skipped ($tool is not installed)"
        exit 0
    fi
done
HAVE_PI=1
command -v pi >/dev/null 2>&1 || HAVE_PI=0

read_source_record() { # <key>
    python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))[sys.argv[2]])' "$SOURCE_RECORD" "$1"
}
SKILL_SOURCE_URL="$(read_source_record upstream)"
PIN="$(read_source_record commit)"
if [[ ! "$PIN" =~ ^[0-9a-f]{40}$ ]]; then
    echo "  ERROR: pinned commit in $SOURCE_RECORD is not a full SHA: $PIN" >&2
    exit 1
fi
echo "  pin: $PIN"

same_repo() { # <url> <url>
    local a="${1%/}" b="${2%/}"
    [[ "${a%.git}" == "${b%.git}" ]]
}

# Inspect a checkout without writing to it (no index refresh, no fetch).
# Prints: absent | foreign | dirty <head> | clean <head>
inspect() { # <dir>
    local dir="$1" top origin head
    if [[ ! -e "$dir" && ! -L "$dir" ]]; then
        echo "absent"; return
    fi
    top="$(git -C "$dir" rev-parse --show-toplevel 2>/dev/null || true)"
    if [[ -z "$top" || "$(cd "$top" && pwd -P)" != "$(cd "$dir" && pwd -P)" ]]; then
        echo "foreign"; return
    fi
    origin="$(git -C "$dir" config --get remote.origin.url 2>/dev/null || true)"
    if ! same_repo "$origin" "$SKILL_SOURCE_URL"; then
        echo "foreign"; return
    fi
    head="$(git -C "$dir" rev-parse --verify --quiet HEAD 2>/dev/null || true)"
    if [[ -n "$(git --no-optional-locks -C "$dir" status --porcelain --untracked-files=all 2>/dev/null)" ]]; then
        echo "dirty ${head:-none}"; return
    fi
    echo "clean ${head:-none}"
}

# 0 when every commit reachable from the checkout's HEAD is on a fetched
# ref of origin (his repository), so removing the checkout loses nothing origin lacks.
head_is_on_origin() { # <dir>
    [[ -n "$(git -C "$1" for-each-ref --contains HEAD refs/remotes/origin 2>/dev/null)" ]]
}

describe() { # <label> <dir> <state>
    local label="$1" dir="$2" state="$3"
    case "$state" in
        absent) echo "  $label: missing ($dir)" ;;
        foreign) echo "  $label: $dir is not a checkout of $SKILL_SOURCE_URL" ;;
        dirty*) echo "  $label: ${state#dirty }, with local modifications ($dir)" ;;
        clean*)
            if [[ "${state#clean }" == "$PIN" ]]; then
                echo "  ok: $label at the pin ($dir)"
            else
                echo "  $label: ${state#clean } (not the pin) ($dir)"
            fi
            ;;
    esac
}

NEW_STATE="$(inspect "$CHECKOUT")"
OLD_STATE="$(inspect "$OLD_CHECKOUT")"
describe "checkout" "$CHECKOUT" "$NEW_STATE"
if [[ "$OLD_STATE" != "absent" ]]; then
    describe "old Pi-only checkout" "$OLD_CHECKOUT" "$OLD_STATE"
fi

# --- Pi settings -------------------------------------------------------------

# Print "missing <dir>" for absent new entries and "old <dir>" for present old ones.
settings_drift() {
    python3 - "$SETTINGS" "${SKILL_DIRS[@]}" "${OLD_SKILL_DIRS[@]}" <<'PY'
import json, sys
path, new_eng, new_prod, old_eng, old_prod = sys.argv[1:]
try:
    skills = json.load(open(path)).get("skills") or []
except FileNotFoundError:
    skills = []
for w in (new_eng, new_prod):
    if w not in skills:
        print("missing", w)
for o in (old_eng, old_prod):
    if o in skills:
        print("old", o)
PY
}

# Replace the old entries in place with the new ones, add any still missing,
# and leave every other key and entry as found.
write_settings() {
    python3 - "$SETTINGS" "${SKILL_DIRS[@]}" "${OLD_SKILL_DIRS[@]}" <<'PY'
import json, os, sys
path, new_eng, new_prod, old_eng, old_prod = sys.argv[1:]
os.makedirs(os.path.dirname(path), exist_ok=True)
try:
    settings = json.load(open(path))
except FileNotFoundError:
    settings = {}
replace = {old_eng: new_eng, old_prod: new_prod}
out = []
for entry in settings.get("skills") or []:
    entry = replace.get(entry, entry)
    if entry not in out:
        out.append(entry)
for w in (new_eng, new_prod):
    if w not in out:
        out.append(w)
settings["skills"] = out
tmp = path + ".tmp"
with open(tmp, "w") as f:
    json.dump(settings, f, indent=2)
    f.write("\n")
os.replace(tmp, path)
PY
}

report_settings() {
    local drift line
    if [[ $HAVE_PI -eq 0 ]]; then
        echo "  Pi: skipped (pi is not installed)"
        return 0
    fi
    drift="$(settings_drift)"
    for dir in "${SKILL_DIRS[@]}"; do
        if grep -qxF "missing $dir" <<<"$drift"; then
            echo "  MISSING Pi settings entry $dir"
        else
            echo "  ok: Pi settings entry $dir"
        fi
    done
    while IFS= read -r line; do
        [[ "$line" == old\ * ]] && echo "  OLD Pi settings entry ${line#old } (would be replaced)"
    done <<<"$drift"
    return 0
}

# --- Claude Code and OpenCode links -----------------------------------------

# Print "<group>/<name>" for every promoted skill at the pin in <repo>, or
# nothing when that repository lacks the pinned commit.
promoted_at_pin() { # <repo>
    git -C "$1" cat-file -e "$PIN^{commit}" 2>/dev/null || return 0
    git -C "$1" ls-tree -r --name-only "$PIN" -- skills/engineering skills/productivity |
        sed -nE 's#^skills/(engineering|productivity)/([^/]+)/SKILL\.md$#\1/\2#p'
}

# A link is this script's when its raw target lies in the checkout, at the
# current place or the old one. The raw target is read, not resolved, so a
# link left dangling by a dropped skill is still recognised.
is_own_link() { # <path>
    local raw
    [[ -L "$1" ]] || return 1
    raw="$(readlink "$1")"
    [[ "$raw" == "$CHECKOUT/skills/"* || "$raw" == "$OLD_CHECKOUT/skills/"* ]]
}

op() { # <verb> <detail>
    if [[ "$MODE" == "check" ]]; then
        echo "  would $1: $2"
    else
        echo "  $1: $2"
    fi
}

# Reconcile one harness directory against the promoted list (one
# "<group>/<name>" per line; empty to remove every own link).
reconcile_links() { # <label> <dest> <promoted>
    local label="$1" dest="$2" promoted="$3"
    local entry group name want path raw
    local n_create=0 n_repoint=0 n_ok=0 n_remove=0 n_kept=0

    echo ""
    echo "  $label ($dest):"
    if [[ -e "$dest" && ! -d "$dest" ]]; then
        echo "    WARNING: $dest exists and is not a directory; skipping $label"
        return 0
    fi
    if [[ "$MODE" == "apply" && -n "$promoted" ]]; then
        mkdir -p "$dest"
    fi

    # Remove own links for names no longer promoted.
    if [[ -d "$dest" ]]; then
        for path in "$dest"/*; do
            is_own_link "$path" || continue
            name="${path##*/}"
            if ! grep -qE "^(engineering|productivity)/${name//./\\.}\$" <<<"$promoted"; then
                op "remove" "$label/$name (no longer promoted)"
                [[ "$MODE" == "apply" ]] && rm "$path"
                n_remove=$((n_remove + 1))
            fi
        done
    fi

    while IFS= read -r entry; do
        [[ -n "$entry" ]] || continue
        group="${entry%%/*}"; name="${entry#*/}"
        want="$CHECKOUT/skills/$group/$name"
        path="$dest/$name"
        if [[ -L "$path" ]]; then
            raw="$(readlink "$path")"
            if [[ "$raw" == "$want" ]]; then
                n_ok=$((n_ok + 1))
            elif is_own_link "$path"; then
                op "repoint" "$label/$name -> $want"
                [[ "$MODE" == "apply" ]] && ln -sfn "$want" "$path"
                n_repoint=$((n_repoint + 1))
            else
                echo "    WARNING: $path is a link to $raw; kept, not linked to his $name"
                n_kept=$((n_kept + 1))
            fi
        elif [[ -e "$path" ]]; then
            echo "    WARNING: $path exists and is not a link; kept, not linked to his $name"
            n_kept=$((n_kept + 1))
        else
            op "create" "$label/$name -> $want"
            [[ "$MODE" == "apply" ]] && ln -s "$want" "$path"
            n_create=$((n_create + 1))
        fi
    done <<<"$promoted"

    echo "    summary: $n_create create, $n_repoint repoint, $n_ok ok, $n_remove remove, $n_kept kept"
    return 0
}

reconcile_all_links() { # <promoted>
    reconcile_links "Claude Code" "$CLAUDE_DEST" "$1"
    if [[ "${RECONCILE_OPENCODE_SKILLS:-1}" == "0" ]]; then
        reconcile_links "OpenCode" "$OPENCODE_DEST" ""
    else
        reconcile_links "OpenCode" "$OPENCODE_DEST" "$1"
    fi
}

# Warn about a local copy of one of his promoted names, which can win over his
# in Pi. Names come from the checkout; without one there is nothing to compare.
warn_shadowing() { # <promoted>
    local entry name dest
    while IFS= read -r entry; do
        [[ -n "$entry" ]] || continue
        name="${entry#*/}"
        for dest in "$HOME/.agents/skills" "$HOME/.pi/agent/skills"; do
            if [[ -e "$dest/$name" || -L "$dest/$name" ]]; then
                echo "  WARNING: $dest/$name shares a name with his $name and can win over it in Pi"
            fi
        done
    done <<<"$1"
}

# --- check ---------------------------------------------------------------------

if [[ "$MODE" == "check" ]]; then
    case "$NEW_STATE:$OLD_STATE" in
        absent:clean*) echo "  would move $OLD_CHECKOUT to $CHECKOUT" ;;
        clean*:clean*)
            if head_is_on_origin "$OLD_CHECKOUT"; then
                echo "  would remove $OLD_CHECKOUT (every commit of it is on its origin)"
            else
                echo "  would stop: $OLD_CHECKOUT has commits its origin lacks"
            fi
            ;;
        *:dirty*|*:foreign) echo "  would stop: $OLD_CHECKOUT needs attention first" ;;
    esac
    report_settings
    source_repo=""
    [[ "$NEW_STATE" == clean* || "$NEW_STATE" == dirty* ]] && source_repo="$CHECKOUT"
    [[ -z "$source_repo" && ( "$OLD_STATE" == clean* || "$OLD_STATE" == dirty* ) ]] && source_repo="$OLD_CHECKOUT"
    promoted=""
    [[ -n "$source_repo" ]] && promoted="$(promoted_at_pin "$source_repo")"
    if [[ -z "$promoted" ]]; then
        echo "  links: the promoted list is unknown until a checkout holds the pin"
    else
        echo "  promoted at the pin: $(grep -c . <<<"$promoted")"
        warn_shadowing "$promoted"
        reconcile_all_links "$promoted"
    fi
    exit 0
fi

# --- apply ---------------------------------------------------------------------

stop() {
    echo "  STOPPED: $*" >&2
    exit 1
}

case "$OLD_STATE" in
    foreign) stop "move $OLD_CHECKOUT aside; it is not a checkout of $SKILL_SOURCE_URL" ;;
    dirty*) stop "$OLD_CHECKOUT has local modifications; nothing was moved or discarded. Inspect them with: git -C '$OLD_CHECKOUT' status" ;;
esac
case "$NEW_STATE" in
    foreign) stop "move $CHECKOUT aside; it is not a checkout of $SKILL_SOURCE_URL" ;;
    dirty*) stop "$CHECKOUT has local modifications; nothing was discarded. Inspect them with: git -C '$CHECKOUT' status" ;;
esac

if [[ "$OLD_STATE" == clean* ]]; then
    if [[ "$NEW_STATE" == "absent" ]]; then
        mkdir -p "${CHECKOUT%/*}"
        mv "$OLD_CHECKOUT" "$CHECKOUT"
        echo "  Moved $OLD_CHECKOUT to $CHECKOUT"
        NEW_STATE="$OLD_STATE"
    elif head_is_on_origin "$OLD_CHECKOUT"; then
        rm -rf "$OLD_CHECKOUT"
        echo "  Removed $OLD_CHECKOUT (a clean copy; every commit of it is on its origin)"
    else
        stop "$OLD_CHECKOUT has commits its origin lacks, and $CHECKOUT exists too; nothing was removed"
    fi
    rmdir "${OLD_CHECKOUT%/*}" 2>/dev/null || true
fi

case "$NEW_STATE" in
    absent)
        mkdir -p "${CHECKOUT%/*}"
        tmp="$CHECKOUT.partial.$$"
        trap 'rm -rf "$tmp"' EXIT
        git clone --quiet --no-checkout "$SKILL_SOURCE_URL" "$tmp"
        git -C "$tmp" -c advice.detachedHead=false checkout --quiet --detach "$PIN"
        mv "$tmp" "$CHECKOUT"
        trap - EXIT
        echo "  Cloned $SKILL_SOURCE_URL at $PIN"
        ;;
    clean*)
        head="${NEW_STATE#clean }"
        if [[ "$head" != "$PIN" ]]; then
            if ! git -C "$CHECKOUT" cat-file -e "$PIN^{commit}" 2>/dev/null; then
                git -C "$CHECKOUT" fetch --quiet origin
            fi
            git -C "$CHECKOUT" -c advice.detachedHead=false checkout --quiet --detach "$PIN"
            echo "  Moved checkout $head -> $PIN"
        fi
        ;;
esac

if [[ $HAVE_PI -eq 0 ]]; then
    echo "  Pi: skipped (pi is not installed)"
elif [[ -n "$(settings_drift)" ]]; then
    write_settings
    echo "  Set Pi settings entries for skills/engineering and skills/productivity"
else
    echo "  ok: Pi settings entries present"
fi

promoted="$(promoted_at_pin "$CHECKOUT")"
if [[ -z "$promoted" ]]; then
    stop "no promoted skill found in $CHECKOUT at $PIN"
fi
reconcile_all_links "$promoted"
echo ""
warn_shadowing "$promoted"

exit 0
