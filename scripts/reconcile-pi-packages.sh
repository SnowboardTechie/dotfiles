#!/usr/bin/env bash
# reconcile-pi-packages.sh — install the third-party Pi packages this repo pins.
#
# Each package below gives Pi something it lacks, for whichever model Pi runs
# (Claude through pi-claude-code, Codex, local Ollama), so none of it leans on
# one provider's own tools:
#   - pi-web-access: `web_search`, `fetch_content`, `get_search_content` and
#     `source_check`. Pi has no web tools, and curl to search engines gets bot
#     challenges. Keyless search goes through Exa's public MCP endpoint; keys
#     for other providers go in machine-local ~/.pi/agent/web-search.json.
#   - @deathbeam/pi-hashline: replaces `read`, `edit` and `grep` with versions
#     that tag each line with a short content hash. Edits name lines by those
#     anchors instead of retyping old text, and anchors from a stale read are
#     rejected. Its `grep` needs `rg`.
#
# Versions are exact: Pi doesn't auto-update an exact npm pin, so an upgrade is
# a reviewed change here. Another version of a listed package is replaced.

set -euo pipefail

usage() {
    cat <<'EOF'
Usage: reconcile-pi-packages.sh (--check | --apply)

  --check   Report whether each pinned Pi package is installed.
            Never mutates the filesystem.
  --apply   Install each pinned package, removing other versions of it.
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

# npm name and exact version, one per line.
PACKAGES=(
    "pi-web-access@0.48.0"
    "@deathbeam/pi-hashline@0.0.16"
)
SETTINGS="$HOME/.pi/agent/settings.json"

echo "Pi packages ($MODE)"

if ! command -v pi >/dev/null 2>&1; then
    echo "  Skipped (pi is not installed)"
    exit 0
fi

for pinned in "${PACKAGES[@]}"; do
    name="${pinned%@*}"
    want="npm:$pinned"

    # Every configured source of this package, one per line.
    installed="$(python3 - "$SETTINGS" "$name" <<'PY'
import json, re, sys
try:
    d = json.load(open(sys.argv[1]))
except FileNotFoundError:
    d = {}
name = sys.argv[2]
for p in d.get("packages") or []:
    src = p if isinstance(p, str) else (p.get("source") or "")
    if re.fullmatch(r"npm:" + re.escape(name) + r"(@[^@/]*)?", src):
        print(src)
PY
)"

    if [[ "$installed" == "$want" ]]; then
        echo "  ok: package $want"
        continue
    fi

    while IFS= read -r other; do
        [[ -z "$other" || "$other" == "$want" ]] && continue
        if [[ "$MODE" == "apply" ]]; then
            command pi remove "$other"
            echo "  Removed $other"
        else
            echo "  WOULD REMOVE $other"
        fi
    done <<<"$installed"

    if grep -qxF "$want" <<<"$installed"; then
        echo "  ok: package $want"
    elif [[ "$MODE" == "apply" ]]; then
        command pi install "$want"
        echo "  Installed $want"
    else
        echo "  MISSING package $want"
    fi
done

if [[ " ${PACKAGES[*]} " == *" @deathbeam/pi-hashline@"* ]] && ! command -v rg >/dev/null 2>&1; then
    echo "  WARNING: rg (ripgrep) is not installed; pi-hashline's grep tool needs it"
fi

exit 0
