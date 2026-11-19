#!/usr/bin/env bash
# reconcile-agent-skills.sh — link the curated skills from the personal skill pool
# (dot-agents/skills/) into each harness's skills directory.
#
# The *_SKILLS arrays below are the single canonical curation source.
# dot-agents/README.md documents the rationale; it does not duplicate the lists.
#
# Ownership rules (extracted unchanged from setup-platform-configs.sh):
#   - create or refresh links for curated skills in the skill pool
#   - prune only symlinks that resolve into the skill pool and are no longer curated
#   - preserve real directories, regular files, foreign and broken symlinks
#
# Requires only Bash plus the utilities the setup entry point already used
# (perl for path resolution). No Stow, no network, no elevation.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

usage() {
    cat <<'EOF'
Usage: reconcile-agent-skills.sh (--check | --apply)

  --check   Report the per-harness operations that --apply would perform.
            Never mutates the filesystem.
  --apply   Create/refresh curated skill links and prune stale skill pool
            links. Never touches real files, real directories, or symlinks
            that do not resolve into this repository's skill pool.

  RECONCILE_OPENCODE_SKILLS=0 retires only OpenCode links into the skill pool
            on machines that no longer run OpenCode; other harnesses are unchanged.
  RECONCILE_HERMES_SKILLS=0 skips Hermes entirely: no links are created or
            pruned in ~/.hermes/skills/personal.
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

# Skills retired from the skill pool. Their source directories no longer exist, so links to
# them are dangling — and `Cwd::abs_path` returns EMPTY for a dangling link whose
# *parent* component is also missing, which would classify them as "foreign" and
# preserve them forever. Match the raw `readlink` target instead: it needs no
# filesystem to resolve, so the outcome is the same on every platform.
#
# This is an exact allowlist of historical targets, never a pattern. Every
# other broken or foreign link is still preserved untouched. `vault-capture`
# was replaced by the backend-neutral `knowledge-capture` router (2026-09-16);
# `apple-notes-pkm` was removed when the personal vault returned to Markdown
# (2026-10-31). The local `code-review` split into `pr-self-review`'s review
# contract and `teammate-pr-review` (2026-11-16). The six skills adapted from
# Matt Pocock's retired the same day in favour of his own (`grilling`,
# `wayfinder`, `tdd`, `diagnosing-bugs`, `codebase-architecture` for his
# `codebase-design` and `improve-codebase-architecture`, `guided-learning` for
# his `teach`). His skills never come from the skill pool:
# scripts/reconcile-mattpocock-skills.sh links them into Claude Code and
# OpenCode and lists them in Pi's settings.
RETIRED_SKILL_POOL_TARGETS=(agent-workspace git-master vault-capture apple-notes-pkm code-review
    grilling wayfinder tdd diagnosing-bugs codebase-architecture guided-learning)

is_retired_skill_pool_link() { # <link-path> -> 0 when it names a skill retired from the skill pool
    local raw legacy
    raw="$(readlink "$1" 2>/dev/null || true)"
    [[ -n "$raw" ]] || return 1
    for legacy in "${RETIRED_SKILL_POOL_TARGETS[@]}"; do
        if [[ "$raw" == "$SKILLS_SRC/$legacy" ]]; then
            return 0
        fi
    done
    return 1
}

SKILLS_SRC="$(resolve_path "$REPO_ROOT/dot-agents/skills")"

# Matt Pocock's checkout, whose per-skill links in the Claude Code and OpenCode
# directories scripts/reconcile-mattpocock-skills.sh owns. They are left alone
# like any foreign link, but counted rather than listed one by one.
MATTPOCOCK_CHECKOUT="$HOME/.local/share/mattpocock-skills"

if [[ -z "$SKILLS_SRC" || ! -d "$SKILLS_SRC" ]]; then
    echo "ERROR: skill pool not found at $REPO_ROOT/dot-agents/skills" >&2
    exit 1
fi

# Common core shared by Claude, OpenCode, Pi, and Codex: dev/PR and PKM.
# PKM: vault-pkm (every Markdown vault, including the personal ~/second-brain)
# and knowledge-capture (the router that decides between the personal vault and a workspace's vault).
# apple-notes-pkm was removed 2026-10-31.
# black-box-verification is a shared verification method (see
# dot-agents/skill-sources/pstack-claude.json), so every harness, Pi included, receives it.
COMMON_SKILLS=(ship worktrunk update-pr-description pr-self-review teammate-pr-review
    vault-pkm knowledge-capture session-handoff
    black-box-verification)

# Claude dropped these on 2026-09-28 (no recorded use); OpenCode, Pi, and Codex keep them.
NON_CLAUDE_COMMON=(skill-retrospective obsidian)

# Matt Pocock's promoted skills (his `grilling`, `wayfinder`, `tdd`,
# `code-review` and the rest) are not in these lists: one checkout of his
# repository serves every harness through scripts/reconcile-mattpocock-skills.sh.
# No skill in the skill pool may share a name with one of his. Reviewing other people's PRs
# is `teammate-pr-review` (in COMMON_SKILLS), which loads his `code-review`.

# Pi is becoming the primary harness (dotfiles-workspace#34), so it grows past
# the common core as each workflow is made to run from Pi.
# next-session: Pi launches the next Pi in a Rex pane.
# draw-it: Pi draws a picture into a Rex pane beside the conversation.
# Delivery skills: a Pi orchestrator runs the issue workflows, the visible
# handoff they delegate through, and the DX planning step issue-plan loads,
# then reviews, publishes and merges (manual-merge).
# Skills for the interactive Pi that were Hermes-only, so no workflow it shares needs a Hermes
# session: dual-model teammate review, DX preview, proven cores, sprint updates,
# and demo prep (technical-demo-preparation, moved from a
# Hermes-local copy on 2026-11-12).
# pre-review-cleanup (Pi and Claude, 2026-11-17): Bryan turns the SGG pre-review
# service's draft into his posted review and records the feedback in the sgg vault. Hermes's own bots and scheduled jobs (bot-planning, bot-reminders,
# yunohost-updates) stay with Hermes until the bot service replaces them.
# server-update-checks (Pi, 2026-11-19): Bryan asks Pi to settle what Steve's
# YunoHost report marked "needs a check"; it reaches the server through
# yunohost-updates' access model, so Pi gets that skill too.
PI_SKILLS=("${COMMON_SKILLS[@]}" "${NON_CLAUDE_COMMON[@]}" next-session
    manual-merge issue-create issue-plan issue-work loop-issue
    coding-agent-handoff-supervision dx-target
    multiagent-pr-review dx-preview proven-cores sprint-deliverable-update
    technical-demo-preparation draw-it pre-review-cleanup
    server-update-checks yunohost-updates)

# Codex uses the supported user scope (~/.agents/skills), not its bundled
# ~/.codex/skills/.system directory. Share the portable coding/planning core;
# leave Hermes-specific orchestration and specialist workflows opt-in.
# Pi reads ~/.agents/skills too, and from `~` a copy there beats Matt Pocock's
# skill of the same name, which is one more reason no skill in the skill pool takes one of
# his names.
CODEX_SKILLS=("${COMMON_SKILLS[@]}" "${NON_CLAUDE_COMMON[@]}"
    manual-merge issue-create issue-plan issue-work loop-issue
    adr-and-spec-coach conforming-tech-specs voice-bryan
    catalog-review dependency-review dependency-triage
    superwhisper-meetings)

CLAUDE_SKILLS=("${COMMON_SKILLS[@]}"
    manual-merge issue-create issue-plan issue-work
    adr-and-spec-coach dx-target conforming-tech-specs proven-cores
    catalog-review dependency-review dependency-triage
    voice-bryan superwhisper-meetings pre-review-cleanup)

OPENCODE_SKILLS=("${COMMON_SKILLS[@]}" "${NON_CLAUDE_COMMON[@]}"
    manual-merge issue-create issue-plan issue-work loop-issue
    adr-and-spec-coach conforming-tech-specs
    voice-bryan gamedev)

# Hermes keeps its bundled/local obsidian and vault-pkm implementations. Personal
# skills live in a dedicated category so the skill pool remains canonical while
# Hermes's curator and bundled-skill lifecycle stay separate. Personal knowledge
# is ~/second-brain, reached through Hermes's own vault-pkm.
# `rex` is Hermes-only: Rex's own `rex skill setup` already covers Claude, Codex,
# OpenCode, and Pi (its skill dir lives in ~/.agents/skills/rex), but not Hermes.
HERMES_SKILLS=(
    ship worktrunk update-pr-description pr-self-review teammate-pr-review multiagent-pr-review
    manual-merge issue-create issue-plan issue-work loop-issue
    coding-agent-handoff-supervision
    knowledge-capture skill-retrospective adr-and-spec-coach voice-bryan
    session-handoff next-session black-box-verification
    dx-target dx-preview conforming-tech-specs proven-cores
    catalog-review dependency-review dependency-triage sprint-deliverable-update
    technical-demo-preparation
    yunohost-updates superwhisper-meetings bot-planning bot-reminders
    rex
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

# Reconcile one harness's skills directory against its curated list.
# Check and apply share every decision; apply additionally executes the
# owned operations (rm/mkdir/ln) that check only reports.
reconcile_tool() {
    local label="$1" dest="$2" legacy_dest="$3"; shift 3
    local wanted=("$@")
    local existing name tgt w keep fresh=0
    local n_create=0 n_refresh=0 n_ok=0 n_prune=0 n_foreign=0 n_collide=0 n_untouched=0 n_missing=0 n_his=0

    echo ""
    echo "$label ($dest):"

    # Replace known whole-directory layouts from before the per-skill links into the skill pool.
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

    # Scan pass: prune stale skill pool links, report foreign links that are
    # preserved, count foreign real entries. Skipped when the destination
    # does not exist yet (or is a legacy link that check mode leaves in place).
    if [[ $fresh -eq 0 || "$MODE" == "apply" ]]; then
        for existing in "$dest"/*; do
            if [[ ! -e "$existing" && ! -L "$existing" ]]; then
                continue
            fi
            name="$(basename "$existing")"
            keep=0
            for w in "${wanted[@]+"${wanted[@]}"}"; do
                if [[ "$w" == "$name" ]]; then keep=1; break; fi
            done
            if [[ -L "$existing" ]]; then
                tgt="$(resolve_path "$existing")"
                case "$tgt" in
                    "$SKILLS_SRC"/*)
                        if [[ $keep -eq 0 ]]; then
                            op "prune stale skill pool link" "$name"
                            if [[ "$MODE" == "apply" ]]; then
                                rm "$existing"
                            fi
                            n_prune=$((n_prune + 1))
                        fi
                        ;;
                    *)
                        if [[ $keep -eq 0 ]] && is_retired_skill_pool_link "$existing"; then
                            # A dangling link to a skill retired from the skill pool. Resolution
                            # cannot see through it, so the raw target decides.
                            op "prune retired skill pool link" "$name"
                            if [[ "$MODE" == "apply" ]]; then
                                rm "$existing"
                            fi
                            n_prune=$((n_prune + 1))
                        elif [[ $keep -eq 0 && "$(readlink "$existing")" == "$MATTPOCOCK_CHECKOUT/skills/"* ]]; then
                            n_his=$((n_his + 1))
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

    # Link pass: create or refresh curated links owned by the skill pool.
    for name in "${wanted[@]+"${wanted[@]}"}"; do
        if [[ ! -d "$SKILLS_SRC/$name" ]]; then
            echo "  WARNING: skill '$name' not in the skill pool, skipping"
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
                        op "refresh skill pool link" "$name"
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
        "$n_untouched foreign real entries untouched, $n_missing missing"
    if [[ $n_his -gt 0 ]]; then
        echo "  $n_his links to Matt Pocock's skills left to scripts/reconcile-mattpocock-skills.sh"
    fi
    return 0
}

echo "Reconciling agent skills ($MODE) from $SKILLS_SRC"

reconcile_tool "Claude"   "$HOME/.claude/skills"          "$REPO_ROOT/dot-claude/skills"          "${CLAUDE_SKILLS[@]}"
if [[ "${RECONCILE_OPENCODE_SKILLS:-1}" == "0" ]]; then
    reconcile_tool "OpenCode" "$HOME/.config/opencode/skills" "$REPO_ROOT/dot-config/opencode/skills"
else
    reconcile_tool "OpenCode" "$HOME/.config/opencode/skills" "$REPO_ROOT/dot-config/opencode/skills" "${OPENCODE_SKILLS[@]}"
fi
reconcile_tool "Codex"    "$HOME/.agents/skills"          ""                                      "${CODEX_SKILLS[@]}"
reconcile_tool "Pi"       "$HOME/.pi/agent/skills"        ""                                      "${PI_SKILLS[@]}"
if [[ "${RECONCILE_HERMES_SKILLS:-1}" == "0" ]]; then
    echo ""
    echo "Hermes: skipped (RECONCILE_HERMES_SKILLS=0)"
else
    reconcile_tool "Hermes"   "$HOME/.hermes/skills/personal" ""                                      "${HERMES_SKILLS[@]}"
fi

echo ""
if [[ "$MODE" == "check" ]]; then
    echo "Check complete — no changes were made."
else
    echo "Apply complete."
fi
