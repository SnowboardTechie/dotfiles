#!/usr/bin/env bash
# reconcile-agent-skills.sh — link the curated personal agent-skill pool
# (dot-agents/skills/) into each tool's skills directory.
#
# The *_SKILLS arrays below are the single canonical curation source.
# dot-agents/README.md documents the rationale; it does not duplicate the lists.
#
# Ownership rules (extracted unchanged from setup-platform-configs.sh):
#   - create or refresh links for curated pool skills
#   - prune only symlinks that resolve into the pool and are no longer curated
#   - preserve real directories, regular files, foreign and broken symlinks
#
# Requires only Bash plus the utilities the legacy setup script already used
# (perl for path resolution). No Stow, no network, no elevation.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

usage() {
    cat <<'EOF'
Usage: reconcile-agent-skills.sh (--check | --apply)

  --check   Report the per-tool operations that --apply would perform.
            Never mutates the filesystem.
  --apply   Create/refresh curated skill links and prune stale pool-owned
            links. Never touches real files, real directories, or symlinks
            that do not resolve into this repository's skill pool.
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
    if [[ $# -gt 0 ]]; then
        echo "ERROR: expected exactly one of --check or --apply, got: $*" >&2
    fi
    usage >&2
    exit 2
fi

resolve_path() {
    perl -MCwd -le 'print Cwd::abs_path($ARGV[0])' "$1"
}

# Retired pool skills. Their source directories no longer exist, so links to
# them are dangling — and `Cwd::abs_path` returns EMPTY for a dangling link whose
# *parent* component is also missing, which would classify them as "foreign" and
# preserve them forever. Match the raw `readlink` target instead: it needs no
# filesystem to resolve, so the outcome is the same on every platform.
#
# This is an exact allowlist of two historical targets, never a pattern. Every
# other broken or foreign link is still preserved untouched.
RETIRED_POOL_TARGETS=(agent-workspace git-master)

is_legacy_pool_link() { # <link-path> -> 0 when it names a retired pool skill
    local raw legacy
    raw="$(readlink "$1" 2>/dev/null || true)"
    [[ -n "$raw" ]] || return 1
    for legacy in "${RETIRED_POOL_TARGETS[@]}"; do
        if [[ "$raw" == "$SKILLS_SRC/$legacy" ]]; then
            return 0
        fi
    done
    return 1
}

SKILLS_SRC="$(resolve_path "$REPO_ROOT/dot-agents/skills")"

if [[ -z "$SKILLS_SRC" || ! -d "$SKILLS_SRC" ]]; then
    echo "ERROR: skill pool not found at $REPO_ROOT/dot-agents/skills" >&2
    exit 1
fi

# Common core shared by Claude, OpenCode, and Pi: dev/PR, PKM, and workflow learning.
COMMON_SKILLS=(ship worktrunk update-pr-description pr-self-review code-review
    vault-pkm vault-capture skill-retrospective obsidian)

# Planning and delivery cores adapted from an upstream suite (see
# dot-agents/upstreams/mattpocock-skills.json). Curated for the three runtimes
# Bryan actually plans and implements on. `guided-learning` is Hermes-only until
# real use earns wider distribution; Pi stays lean but receives `code-review`
# through COMMON_SKILLS because its shared `pr-self-review` workflow requires it.
ADAPTED_CORES=(grilling wayfinder tdd diagnosing-bugs codebase-architecture)

PI_SKILLS=("${COMMON_SKILLS[@]}")

CLAUDE_SKILLS=("${COMMON_SKILLS[@]}"
    manual-merge issue-create issue-plan issue-work loop-issue sync-hold-branch
    adr-and-spec-coach conforming-tech-specs sprint-deliverable-update weekly-planning
    catalog-review dependency-review dependency-triage
    voice-bryan find-skills
    "${ADAPTED_CORES[@]}")

OPENCODE_SKILLS=("${COMMON_SKILLS[@]}"
    manual-merge issue-create issue-plan issue-work loop-issue
    adr-and-spec-coach conforming-tech-specs
    voice-bryan gamedev
    "${ADAPTED_CORES[@]}")

# Hermes keeps its bundled/local obsidian and vault-pkm implementations. Personal
# skills live in a dedicated category so the shared pool remains canonical while
# Hermes's curator and bundled-skill lifecycle stay separate.
HERMES_SKILLS=(
    ship worktrunk update-pr-description pr-self-review code-review multiagent-pr-review
    manual-merge issue-create issue-plan issue-work loop-issue
    coding-agent-handoff-supervision
    vault-capture skill-retrospective adr-and-spec-coach voice-bryan
    dx-target dx-preview conforming-tech-specs
    catalog-review dependency-review dependency-triage sprint-deliverable-update
    "${ADAPTED_CORES[@]}"
    guided-learning
)

# Print an operation line. Operations mutate only under --apply; check mode
# reports the identical plan with a "would" prefix.
op() {
    local verb="$1" detail="$2"
    if [[ "$MODE" == "check" ]]; then
        echo "  would $verb: $detail"
    else
        echo "  $verb: $detail"
    fi
}

# Reconcile one tool's skills directory against its curated list.
# Check and apply share every decision; apply additionally executes the
# owned operations (rm/mkdir/ln) that check only reports.
reconcile_tool() {
    local label="$1" dest="$2" legacy_dest="$3"; shift 3
    local wanted=("$@")
    local existing name tgt w keep fresh=0
    local n_create=0 n_refresh=0 n_ok=0 n_prune=0 n_foreign=0 n_collide=0 n_untouched=0 n_missing=0

    echo ""
    echo "$label ($dest):"

    # Replace known whole-directory layouts from before the per-skill pool.
    # A foreign destination symlink may be independently managed.
    if [[ -L "$dest" ]]; then
        tgt="$(resolve_path "$dest")"
        if [[ "$tgt" == "$SKILLS_SRC" || ( -n "$legacy_dest" && "$tgt" == "$legacy_dest" ) ]]; then
            op "replace legacy whole-directory link with a directory" "$dest"
            if [[ "$MODE" == "apply" ]]; then
                rm "$dest"
            fi
            fresh=1
        else
            echo "  WARNING: destination is a foreign symlink; skipping $label"
            return 0
        fi
    elif [[ -e "$dest" && ! -d "$dest" ]]; then
        echo "  WARNING: destination exists and is not a directory; skipping $label"
        return 0
    elif [[ ! -e "$dest" ]]; then
        fresh=1
    fi

    if [[ "$MODE" == "apply" ]]; then
        mkdir -p "$dest"
    fi

    # Scan pass: prune stale pool-owned links, report foreign links that are
    # preserved, count unmanaged real entries. Skipped when the destination
    # does not exist yet (or is a legacy link that check mode leaves in place).
    if [[ $fresh -eq 0 || "$MODE" == "apply" ]]; then
        for existing in "$dest"/*; do
            if [[ ! -e "$existing" && ! -L "$existing" ]]; then
                continue
            fi
            name="$(basename "$existing")"
            keep=0
            for w in "${wanted[@]}"; do
                if [[ "$w" == "$name" ]]; then keep=1; break; fi
            done
            if [[ -L "$existing" ]]; then
                tgt="$(resolve_path "$existing")"
                case "$tgt" in
                    "$SKILLS_SRC"/*)
                        if [[ $keep -eq 0 ]]; then
                            op "prune stale pool link" "$name"
                            if [[ "$MODE" == "apply" ]]; then
                                rm "$existing"
                            fi
                            n_prune=$((n_prune + 1))
                        fi
                        ;;
                    *)
                        if [[ $keep -eq 0 ]] && is_legacy_pool_link "$existing"; then
                            # A dangling link to a retired pool skill. Resolution
                            # cannot see through it, so the raw target decides.
                            op "prune retired pool link" "$name"
                            if [[ "$MODE" == "apply" ]]; then
                                rm "$existing"
                            fi
                            n_prune=$((n_prune + 1))
                        elif [[ $keep -eq 0 ]]; then
                            # Foreign or broken symlink (e.g. Omarchy package skills):
                            # never touched. Curated-name collisions are reported in
                            # the link pass instead.
                            echo "  preserved (foreign symlink): $name"
                            n_foreign=$((n_foreign + 1))
                        fi
                        ;;
                esac
            else
                # Real directory or file: never touched. Curated-name
                # collisions are reported in the link pass instead.
                if [[ $keep -eq 0 ]]; then
                    n_untouched=$((n_untouched + 1))
                fi
            fi
        done
    fi

    # Link pass: create or refresh curated links owned by the pool.
    for name in "${wanted[@]}"; do
        if [[ ! -d "$SKILLS_SRC/$name" ]]; then
            echo "  WARNING: skill '$name' not in pool, skipping"
            n_missing=$((n_missing + 1))
            continue
        fi
        if [[ $fresh -eq 1 && "$MODE" == "check" ]]; then
            op "create link" "$name"
            n_create=$((n_create + 1))
            continue
        fi
        if [[ -L "$dest/$name" ]]; then
            tgt="$(resolve_path "$dest/$name")"
            if [[ "$tgt" == "$SKILLS_SRC/$name" ]]; then
                n_ok=$((n_ok + 1))
            else
                case "$tgt" in
                    "$SKILLS_SRC"/*)
                        op "refresh pool link" "$name"
                        if [[ "$MODE" == "apply" ]]; then
                            ln -sfn "$SKILLS_SRC/$name" "$dest/$name"
                        fi
                        n_refresh=$((n_refresh + 1))
                        ;;
                    *)
                        echo "  WARNING: $label/$name is a foreign symlink; preserved, not linked"
                        n_collide=$((n_collide + 1))
                        ;;
                esac
            fi
        elif [[ -e "$dest/$name" ]]; then
            echo "  WARNING: $label/$name exists and is not a symlink; preserved, not linked"
            n_collide=$((n_collide + 1))
        else
            op "create link" "$name"
            if [[ "$MODE" == "apply" ]]; then
                ln -sfn "$SKILLS_SRC/$name" "$dest/$name"
            fi
            n_create=$((n_create + 1))
        fi
    done

    echo "  summary: $n_create create, $n_refresh refresh, $n_ok ok, $n_prune prune," \
        "$n_foreign foreign preserved, $n_collide collisions preserved," \
        "$n_untouched unmanaged untouched, $n_missing missing"
    return 0
}

echo "Reconciling agent skills ($MODE) from $SKILLS_SRC"

reconcile_tool "Claude"   "$HOME/.claude/skills"          "$REPO_ROOT/dot-claude/skills"          "${CLAUDE_SKILLS[@]}"
reconcile_tool "OpenCode" "$HOME/.config/opencode/skills" "$REPO_ROOT/dot-config/opencode/skills" "${OPENCODE_SKILLS[@]}"
reconcile_tool "Pi"       "$HOME/.pi/agent/skills"        ""                                      "${PI_SKILLS[@]}"
reconcile_tool "Hermes"   "$HOME/.hermes/skills/personal" ""                                      "${HERMES_SKILLS[@]}"

echo ""
if [[ "$MODE" == "check" ]]; then
    echo "Check complete — no changes were made."
else
    echo "Apply complete."
fi
