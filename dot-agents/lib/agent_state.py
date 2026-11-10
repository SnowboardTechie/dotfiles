"""Where a skill keeps resumable state inside a repository's trunk.

Skills such as issue-work, issue-create and pr-self-review keep per-item state
(plans, progress, drafts, review evidence) beside the repository, ignored by
Git. The place is ``{trunk}/.agent-work/<skill>/<key>/``; it used to be
``{trunk}/.hermes/<skill>/<key>/``, when Hermes was the primary harness.

Rules, in order:

1. If ``.agent-work/<skill>/<key>`` exists, use it.
2. Else if the legacy ``.hermes/<skill>/<key>`` exists, resume it in place.
   It is never moved: recorded files (``progress.md``,
   ``context-validation.json``) hold absolute paths into it.
3. Else the item is new: use ``.agent-work/<skill>/<key>``.

Without a key, the skill's own directory is resolved the same way, except a
new one is always ``.agent-work/<skill>``; ``roots`` lists both so callers
that scan (issue-create's drafts, the type-ID cache) can read legacy entries.

CLI (prints JSON, creates nothing unless ``--create``)::

    python3 ~/code/dotfiles/dot-agents/lib/agent_state.py dir \
        --trunk "$TRUNK_ROOT" --skill issue-work --key bryan-dotfiles-workspace-34
    python3 ~/code/dotfiles/dot-agents/lib/agent_state.py roots \
        --trunk "$TRUNK_ROOT" --skill issue-create

Import from a skill script with:

    sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "lib"))
    import agent_state
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import List, Optional

STATE_DIR = ".agent-work"
LEGACY_STATE_DIR = ".hermes"
_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]*")


def _check_name(label: str, value: str) -> str:
    if not _NAME.fullmatch(value) or value in {".", ".."}:
        raise ValueError(f"{label} must be one plain path segment: {value!r}")
    return value


def roots(trunk: Path, skill: str) -> List[Path]:
    """The skill's state roots, current first, then legacy. Exist or not."""
    _check_name("skill", skill)
    base = Path(trunk).expanduser().resolve()
    return [base / STATE_DIR / skill, base / LEGACY_STATE_DIR / skill]


def resolve(trunk: Path, skill: str, key: Optional[str] = None) -> dict:
    """Pick the state directory for one item (or the skill root without a key)."""
    current_root, legacy_root = roots(trunk, skill)
    if key is not None:
        _check_name("key", key)
        current, legacy = current_root / key, legacy_root / key
    else:
        current, legacy = current_root, legacy_root
    if current.is_dir():
        chosen, is_legacy = current, False
    elif key is not None and legacy.is_dir():
        chosen, is_legacy = legacy, True
    else:
        chosen, is_legacy = current, False
    return {
        "path": str(chosen),
        "exists": chosen.is_dir(),
        "legacy": is_legacy,
        "roots": [str(current_root), str(legacy_root)],
    }


def is_state_path(trunk: Path, skill: str, path: Path) -> bool:
    """True when ``path`` is a per-item child of either of the skill's roots."""
    target = Path(path).expanduser().resolve()
    for root in roots(trunk, skill):
        try:
            relative = target.relative_to(root.resolve())
        except ValueError:
            continue
        if relative.parts:
            return True
    return False


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    sub = parser.add_subparsers(dest="command", required=True)
    one = sub.add_parser("dir", help="state directory for one item")
    one.add_argument("--trunk", type=Path, required=True)
    one.add_argument("--skill", required=True)
    one.add_argument("--key")
    one.add_argument("--create", action="store_true", help="mkdir -p the chosen path")
    both = sub.add_parser("roots", help="current and legacy roots for scanning")
    both.add_argument("--trunk", type=Path, required=True)
    both.add_argument("--skill", required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "roots":
            result: object = [str(p) for p in roots(args.trunk, args.skill)]
        else:
            result = resolve(args.trunk, args.skill, args.key)
            if args.create:
                Path(result["path"]).mkdir(parents=True, exist_ok=True)
                result["exists"] = True
    except ValueError as exc:
        print(json.dumps({"ok": False, "error": str(exc)}))
        return 2
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
