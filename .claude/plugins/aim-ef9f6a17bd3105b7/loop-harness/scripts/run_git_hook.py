#!/usr/bin/env python3
"""Git ``pre-commit`` shim: ``python3 .../scripts/run_git_hook.py``.

A git hook runs with no ``${CLAUDE_PLUGIN_ROOT}``; the managed
``.git/hooks/pre-commit`` invokes this script by its baked-in absolute path.
Stdlib only, so the system ``python3`` suffices. Bootstraps ``sys.path`` to
the plugin's ``src/`` and dispatches to the backstop entry.

Fail direction: an import failure (a moved/reinstalled plugin, or a system
``python3`` older than 3.11) exits 0 LOUDLY — a broken import allows the
commit with a stderr note, so the backstop never wedges commits over a
harness defect.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

try:  # the harness needs 3.11+ (StrEnum, dt.UTC); the SYSTEM python3 may be older
    from loop_harness.githook import pre_commit
except (ImportError, AttributeError) as exc:  # fail open, but LOUDLY: silence looks like gating
    print(
        f"loop-harness failed to load under python {sys.version.split()[0]} "
        f"(3.11+ required): {exc}; the git commit backstop is NOT active",
        file=sys.stderr,
    )
    raise SystemExit(0) from None

if __name__ == "__main__":
    raise SystemExit(pre_commit())
