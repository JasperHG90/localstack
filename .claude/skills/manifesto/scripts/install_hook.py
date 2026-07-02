#!/usr/bin/env python3
"""install_hook.py — wire the manifesto `Stop` hook into a project's settings.

Self-contained, pure stdlib, tool-agnostic. The hook command points at this
script's sibling `manifesto_hook.py`, resolved by absolute path AT INSTALL TIME
(`Path(__file__).resolve()`), so it is correct no matter where the skill was
installed or how it got there.

Because a skill can later be relocated (re-install, moved checkout), `--validate`
re-points an existing entry at the current absolute path; the `manifesto` skill's
sync mode calls it every run so the hook self-heals.

Settings file: `<root>/.claude/settings.json` (root = $CLAUDE_PROJECT_DIR, else
--root, else cwd). Our entry is recognized by the command containing
"manifesto_hook.py", so install/validate/uninstall are all idempotent.

Usage:
  install_hook.py              Install or update the Stop hook (idempotent).
  install_hook.py --validate   Repair the path if drifted; exit 1 if not installed.
  install_hook.py --uninstall  Remove the manifesto Stop hook.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

MARKER = "manifesto_hook.py"


def _script_command() -> str:
    script = Path(__file__).resolve().parent / "manifesto_hook.py"
    return f'python3 "{script}"'


def _root(arg_root: str | None) -> Path:
    return Path(arg_root or os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd())


def _settings_path(root: Path) -> Path:
    return root / ".claude" / "settings.json"


def _load(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except json.JSONDecodeError as exc:
        print(f"error: {path} is not valid JSON: {exc}", file=sys.stderr)
        raise SystemExit(2) from exc


def _save(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )


def _stop_groups(settings: dict) -> list:
    return settings.setdefault("hooks", {}).setdefault("Stop", [])


def _strip_marker(groups: list) -> bool:
    """Remove every hook whose command mentions the marker. Returns True if any removed."""
    removed = False
    for group in groups:
        hooks = group.get("hooks", []) if isinstance(group, dict) else []
        kept = [h for h in hooks if MARKER not in str(h.get("command", ""))]
        if len(kept) != len(hooks):
            removed = True
            group["hooks"] = kept
    # Drop now-empty groups.
    groups[:] = [g for g in groups if isinstance(g, dict) and g.get("hooks")]
    return removed


def _find_command(groups: list) -> str | None:
    for group in groups:
        for hook in group.get("hooks", []) if isinstance(group, dict) else []:
            cmd = str(hook.get("command", ""))
            if MARKER in cmd:
                return cmd
    return None


def cmd_install(root: Path) -> int:
    path = _settings_path(root)
    settings = _load(path)
    groups = _stop_groups(settings)
    _strip_marker(groups)
    groups.append({"hooks": [{"type": "command", "command": _script_command()}]})
    _save(path, settings)
    print(f"installed Stop hook → {path}\n  command: {_script_command()}")
    return 0


def cmd_validate(root: Path) -> int:
    path = _settings_path(root)
    if not path.exists():
        print("not-installed (no settings.json)")
        return 1
    settings = _load(path)
    groups = _stop_groups(settings)
    current = _find_command(groups)
    want = _script_command()
    if current is None:
        print("not-installed")
        return 1
    if current == want:
        print(f"ok\t{want}")
        return 0
    _strip_marker(groups)
    groups.append({"hooks": [{"type": "command", "command": want}]})
    _save(path, settings)
    print(f"repaired\t{current}\t->\t{want}")
    return 0


def cmd_uninstall(root: Path) -> int:
    path = _settings_path(root)
    if not path.exists():
        print("nothing to uninstall")
        return 0
    settings = _load(path)
    groups = _stop_groups(settings)
    removed = _strip_marker(groups)
    if not groups:
        settings.get("hooks", {}).pop("Stop", None)
    if not settings.get("hooks"):
        settings.pop("hooks", None)
    _save(path, settings)
    print("uninstalled" if removed else "nothing to uninstall")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Install the manifesto Stop hook")
    parser.add_argument(
        "--root",
        default=None,
        help="project root (default: $CLAUDE_PROJECT_DIR or cwd)",
    )
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "--validate",
        action="store_true",
        help="repair path if drifted; exit 1 if absent",
    )
    group.add_argument(
        "--uninstall", action="store_true", help="remove the manifesto Stop hook"
    )
    args = parser.parse_args(argv)

    root = _root(args.root)
    if args.uninstall:
        return cmd_uninstall(root)
    if args.validate:
        return cmd_validate(root)
    return cmd_install(root)


if __name__ == "__main__":
    raise SystemExit(main())
