"""Turn a live cluster capture into a committable fixture.

Run by hand when the fixtures need refreshing, never by the test suite:

    NOMAD_TOKEN=... uv run --project cli python cli/tests/fixtures/scrub_capture.py <capture-dir>

Three things come out. Identifiers become stable placeholders, so a
re-capture does not churn every snapshot baseline. Values that move on their
own (indexes, submit times, the seal nonce) are frozen. And anything
token-shaped is dropped outright.

The whole 19-job response is kept. A hand-picked subset would encode a
tidier cluster than the real one, which is the failure the health rules
exist to catch.
"""

import json
import sys
from pathlib import Path
from typing import Any

# Frozen so a re-capture does not rewrite every fixture with new numbers.
FROZEN_INDEX = 1000
FROZEN_SUBMIT_TIME = 1750000000000000000

# Dropped wholesale: large, irrelevant to the panel, and full of host detail.
DROP_KEYS = {"Drivers", "HostVolumes", "Definition", "Output", "Notes"}

# Frozen to a constant rather than placeheld, since they are pure noise.
FROZEN_KEYS = {
    "CreateIndex": FROZEN_INDEX,
    "ModifyIndex": FROZEN_INDEX,
    "SubmitTime": FROZEN_SUBMIT_TIME,
}

# Every key whose value is an opaque identifier gets a stable placeholder
# derived from its position, so the same capture always scrubs identically.
ID_KEYS = {"ID", "NodeID", "FollowupEvalID", "ParentID", "cluster_id", "nonce"}


def looks_like_a_uuid(value: object) -> bool:
    text = str(value)
    return len(text) == 36 and text.count("-") == 4


class Placeholder:
    """Hands out `<kind>-01`, `<kind>-02`, ... consistently per capture."""

    def __init__(self) -> None:
        self.seen: dict[str, str] = {}

    def of(self, kind: str, value: str) -> str:
        if value not in self.seen:
            self.seen[value] = f"{kind}-{len(self.seen) + 1:02d}"
        return self.seen[value]


def scrub(node: Any, names: Placeholder) -> Any:
    if isinstance(node, list):
        return [scrub(item, names) for item in node]
    if not isinstance(node, dict):
        return node

    out: dict[str, Any] = {}
    for key, value in node.items():
        if key in DROP_KEYS:
            continue
        if key in FROZEN_KEYS:
            out[key] = FROZEN_KEYS[key]
            continue
        if key in ID_KEYS and looks_like_a_uuid(value):
            out[key] = names.of("id", str(value))
            continue
        out[key] = scrub(value, names)
    return out


def main() -> int:
    if len(sys.argv) != 2:
        print(__doc__, file=sys.stderr)
        return 2

    source = Path(sys.argv[1])
    target = Path(__file__).parent / "capture"
    target.mkdir(parents=True, exist_ok=True)

    for name in ("jobs_statuses", "nodes", "seal_status", "consul_health", "consul_catalog"):
        payload = json.loads((source / f"{name}.json").read_text())
        scrubbed = scrub(payload, Placeholder())
        text = json.dumps(scrubbed, indent=2, sort_keys=True) + "\n"
        if "hvs." in text or "hvo_" in text:
            raise SystemExit(f"{name}: a token survived scrubbing")
        (target / f"{name}.json").write_text(text)
        print(f"wrote {target / f'{name}.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
