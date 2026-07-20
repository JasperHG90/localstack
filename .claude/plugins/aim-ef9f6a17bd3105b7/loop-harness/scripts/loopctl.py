#!/usr/bin/env python3
"""``loopctl`` launcher: ``python3 .../scripts/loopctl.py <subcommand>``.

Stdlib only; bootstraps ``sys.path`` to the plugin's ``src/`` so consumers
need no install step. The SessionStart hook prints this script's path into
the agent's context.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

try:  # the harness needs 3.11+ (StrEnum, dt.UTC); the SYSTEM python3 may be older
    from loop_harness.cli import main
except (ImportError, AttributeError) as exc:  # fail open, but LOUDLY: silence looks like gating
    print(
        f"loop-harness failed to load under python {sys.version.split()[0]} "
        f"(3.11+ required): {exc}; the loop is NOT active",
        file=sys.stderr,
    )
    raise SystemExit(0) from None

if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
