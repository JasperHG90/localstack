"""Shared rendering: tables, `--json`, and the two footers.

`--json` serializes the command's own dataclass rather than a hand-built
dict. A hand-built dict is how the JSON and the table drift apart, and then
one of them is lying.

Two footers appear more than once, so they live here rather than being
retyped:

- Consul's catalog is silently ACL-filtered. The brokered `deploy` token
  sees 2 services of 25, no token sees all 25, and neither path errors. A
  confident table built on the short list is false and nothing on screen
  reveals it, so every view carrying Consul data says so.
- `vault grants` renders policy TEXT. Vault resolves those templates per
  request against the calling entity; this resolves them from arguments.
"""

import dataclasses
import enum
import json
import sys
from typing import Any

from rich.console import Console
from rich.table import Table

CONSUL_FILTER_FOOTER = (
    "Consul data is read with no token, so it shows everything the agent's own "
    "default identity can see. Consul filters this list by ACL silently and "
    "never errors when it is short, so a token here would narrow the view "
    "rather than widen it."
)

GRANTS_FOOTER = (
    "Rendered from policy text, not an authorization decision. Vault resolves "
    "these templates per request against the calling entity."
)


def _plain(value: Any) -> Any:
    """Dataclasses to dicts, enums to their values, recursively."""
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return {key: _plain(item) for key, item in dataclasses.asdict(value).items()}
    if isinstance(value, enum.Enum):
        return value.value
    if isinstance(value, list | tuple):
        return [_plain(item) for item in value]
    if isinstance(value, dict):
        return {key: _plain(item) for key, item in value.items()}
    return value


def emit_json(payload: Any) -> None:
    """The command's own dataclass, as JSON, on stdout."""
    json.dump(_plain(payload), sys.stdout, indent=2, sort_keys=True, default=str)
    sys.stdout.write("\n")


def console() -> Console:
    # Explicit width so output does not change shape with the terminal, which
    # would make it useless to diff and unpleasant to paste into an issue.
    return Console(width=120)


def table(title: str, columns: list[str], rows: list[list[str]], footer: str = "") -> None:
    """One table on stdout, with an optional footer beneath it."""
    built = Table(title=title, title_justify="left", header_style="bold")
    for column in columns:
        built.add_column(column, overflow="fold")
    for row in rows:
        built.add_row(*row)

    out = console()
    out.print(built)
    if footer:
        out.print(f"[dim]{footer}[/dim]")
