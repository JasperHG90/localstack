#!/usr/bin/env python3
"""manifesto_hook.py — Claude Code `Stop` hook that nudges when MANIFESTO.md drifts.

Self-contained, pure stdlib, and FAILS OPEN: any error, a missing lock, or a
missing manifesto results in a silent exit 0 so the hook can never block a turn.

On stop it reads `.manifesto/lock.json`, hashes the tracked files, and — if any
changed since the last `manifesto_state.py write` — surfaces a one-time, per-session
reminder to reconcile the manifesto via the skill's `sync` mode. The reminder is
debounced with a `.manifesto/.hook-seen-<session_id>` sentinel so it fires at most
once per session rather than after every turn.

Whole-file hashing is a deliberately cheap, language-agnostic *advisory* signal.
The authoritative symbol-anchor check lives in `manifesto_state.py verify`; an
occasional reminder triggered by a cosmetic edit is acceptable at this cadence.
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
from pathlib import Path
from typing import NoReturn


def _silent_exit() -> NoReturn:
    raise SystemExit(0)


def _sha256(path: Path) -> str | None:
    try:
        h = hashlib.sha256()
        with path.open("rb") as fh:
            for block in iter(lambda: fh.read(65536), b""):
                h.update(block)
        return h.hexdigest()
    except OSError:
        return None


def _project_root(event: dict) -> Path:
    for candidate in (
        os.environ.get("CLAUDE_PROJECT_DIR"),
        event.get("cwd"),
        os.getcwd(),
    ):
        if candidate:
            return Path(candidate)
    return Path.cwd()


def main() -> None:
    try:
        raw = sys.stdin.read()
        event = json.loads(raw) if raw.strip() else {}
    except Exception:
        _silent_exit()

    root = _project_root(event)
    lock_path = root / ".manifesto" / "lock.json"
    if not lock_path.exists():
        _silent_exit()

    try:
        lock = json.loads(lock_path.read_text(encoding="utf-8"))
        tracked = lock.get("tracked_files", {})
    except Exception:
        _silent_exit()
    if not tracked:
        _silent_exit()

    changed: list[str] = []
    for rel, recorded in tracked.items():
        current = _sha256(root / rel)
        if current is None or current != recorded:
            changed.append(rel)
    if not changed:
        _silent_exit()

    # Debounce: at most one reminder per session.
    session_id = str(event.get("session_id") or "nosession")
    sentinel = root / ".manifesto" / f".hook-seen-{session_id}"
    if sentinel.exists():
        _silent_exit()
    try:
        sentinel.parent.mkdir(parents=True, exist_ok=True)
        sentinel.write_text("seen\n", encoding="utf-8")
    except OSError:
        pass  # best-effort; still emit once

    preview = ", ".join(sorted(changed)[:5])
    if len(changed) > 5:
        preview += f", +{len(changed) - 5} more"
    message = (
        f"MANIFESTO.md may be out of date: {len(changed)} tracked file(s) changed "
        f"since the last sync ({preview}). Consider running the `manifesto` skill in "
        f"sync mode to reconcile the architecture/design doc with the code."
    )

    # For a Stop event, `systemMessage` is the only supported way to surface text
    # (additionalContext is rejected by the Stop schema). It is shown to the user,
    # who can then ask to run sync.
    print(json.dumps({"systemMessage": message}))
    raise SystemExit(0)


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception:
        raise SystemExit(0)
