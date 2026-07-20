"""Loop kill switch, operator notification, and handoff records.

``.loop/HALT`` engaged means the loop must not act; the commit gate is
bypassed (the operator is in control). Notifications are best-effort:
their absence must never break the loop.
"""

from __future__ import annotations

import argparse
import contextlib
import datetime as dt
import json
import subprocess
from pathlib import Path

HALT_FILE = Path(".loop") / "HALT"
HANDOFF_FILE = Path(".loop") / "handoff.log"


def engaged(repo: Path) -> str | None:
    """The halt reason, or ``None`` when the loop may act."""
    path = repo / HALT_FILE
    if not path.exists():
        return None
    try:
        return path.read_text(encoding="utf-8").strip() or "halted"
    except OSError:
        return "halted (unreadable HALT file)"  # fail closed for the LOOP


def engage(repo: Path, reason: str) -> None:
    """Engage the kill switch with a reason the operator can read."""
    path = repo / HALT_FILE
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(reason + "\n", encoding="utf-8")


def clear(repo: Path) -> None:
    """Clear the kill switch; the loop may act again."""
    (repo / HALT_FILE).unlink(missing_ok=True)


def notify(message: str, *, title: str = "loop harness") -> None:
    """Best-effort macOS desktop notification; never raises."""
    with contextlib.suppress(Exception):
        script = f"display notification {json.dumps(message)} with title {json.dumps(title)}"
        subprocess.run(
            ["osascript", "-e", script],
            check=False,
            capture_output=True,
            timeout=5,
        )


def handoff(repo: Path, text: str, *, now: dt.datetime | None = None) -> None:
    """Append a one-line handoff record for the operator."""
    at = now if now is not None else dt.datetime.now(dt.UTC)
    path = repo / HANDOFF_FILE
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(f"{at.isoformat()}\t{text}\n")


def main(argv: list[str] | None = None) -> int:
    """CLI: engage, clear, or show the kill switch."""
    parser = argparse.ArgumentParser(description="loop kill switch")
    sub = parser.add_subparsers(dest="cmd", required=True)
    eng = sub.add_parser("engage")
    eng.add_argument("reason", nargs="?", default="manual halt")
    sub.add_parser("clear")
    sub.add_parser("status")
    args = parser.parse_args(argv)
    repo = Path.cwd()
    if args.cmd == "engage":
        engage(repo, str(args.reason))
        print(f"HALT engaged: {args.reason}")
        return 0
    if args.cmd == "clear":
        clear(repo)
        print("HALT cleared")
        return 0
    reason = engaged(repo)
    print(f"HALT: {'ENGAGED - ' + reason if reason else 'clear'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
