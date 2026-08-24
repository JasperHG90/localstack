"""Tile config: the list of services shown on the landing page.

One JSON file names every tile. Adding or removing a service from the
homepage is editing that file; nothing else on this page changes.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

Category = Literal["dashboard", "backend"]


class TileConfigError(ValueError):
    """The tile config file is missing, malformed, or names an invalid tile."""


@dataclass(frozen=True)
class ConnectInfo:
    """How to connect to a backend-row service. Never a credential value."""

    protocol: str
    address: str
    auth: str
    example: str


@dataclass(frozen=True)
class Tile:
    """One card on the landing page.

    `node` is the node the tile's job is constrained to in its own Nomad
    jobspec -- a deployment-time fact, not something computed live, so it
    is config like everything else here rather than fetched per request.
    """

    key: str
    name: str
    desc: str
    color: str
    icon: str
    category: Category
    job: str
    node: str
    url: str | None = None
    connect: ConnectInfo | None = None


def _require(obj: dict[str, Any], field: str, tile_key: str) -> Any:
    value = obj.get(field)
    if value in (None, ""):
        raise TileConfigError(f"tile {tile_key!r} is missing required field {field!r}")
    return value


def _parse_connect(raw: Any, tile_key: str) -> ConnectInfo:
    if not isinstance(raw, dict):
        raise TileConfigError(f"backend tile {tile_key!r} is missing its 'connect' block")
    return ConnectInfo(
        protocol=_require(raw, "protocol", tile_key),
        address=_require(raw, "address", tile_key),
        auth=_require(raw, "auth", tile_key),
        example=_require(raw, "example", tile_key),
    )


def _parse_tile(raw: dict[str, Any]) -> Tile:
    key = raw.get("key")
    if not key:
        raise TileConfigError("a tile is missing its required 'key' field")

    name = _require(raw, "name", key)
    desc = _require(raw, "desc", key)
    color = _require(raw, "color", key)
    icon = _require(raw, "icon", key)
    category = _require(raw, "category", key)
    job = _require(raw, "job", key)
    node = _require(raw, "node", key)

    if category not in ("dashboard", "backend"):
        raise TileConfigError(f"tile {key!r} has invalid category {category!r}")

    url: str | None = None
    connect: ConnectInfo | None = None
    if category == "dashboard":
        url = _require(raw, "url", key)
    else:
        connect = _parse_connect(raw.get("connect"), key)

    return Tile(
        key=key,
        name=name,
        desc=desc,
        color=color,
        icon=icon,
        category=category,
        job=job,
        node=node,
        url=url,
        connect=connect,
    )


def load_tiles(path: Path) -> list[Tile]:
    """Read and validate the tile config file. Raises TileConfigError."""
    try:
        text = path.read_text()
    except OSError as error:
        raise TileConfigError(f"cannot read tile config at {path}: {error}") from error

    try:
        raw = json.loads(text)
    except json.JSONDecodeError as error:
        raise TileConfigError(f"{path} is not valid JSON: {error}") from error

    if not isinstance(raw, list):
        raise TileConfigError(f"{path} must be a JSON array of tiles")

    tiles = []
    for item in raw:
        if not isinstance(item, dict):
            raise TileConfigError(f"{path} contains a tile entry that is not an object")
        tiles.append(_parse_tile(item))
    return tiles
