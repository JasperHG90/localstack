"""Tile config: the groups of services shown on the landing page.

One JSON file names every group and every tile. Array order is display
order, for the group headers and for the tiles inside each group, so
rearranging the page is editing that file and nothing else.

A tile is one SERVICE, not one endpoint. It may carry a browser UI
(`fe`), instructions for reaching it without a browser (`connect`), or
both, and it names every Nomad job behind it so a service split across
two jobs still reports one status.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

DEFAULT_FE_LABEL = "open"


class TileConfigError(ValueError):
    """The tile config file is missing, malformed, or names an invalid tile."""


@dataclass(frozen=True)
class ConnectInfo:
    """How to work with a service without a browser. Never a credential value.

    Covers both directions: how to CALL a service (postgres, the registry)
    and how to be picked up BY one (prometheus scrapes only what tags
    itself), because both are things a browser cannot do for you.
    """

    protocol: str
    address: str
    auth: str
    example: str


@dataclass(frozen=True)
class FrontEnd:
    """A service's browser UI, and the label on the button that opens it."""

    url: str
    label: str = DEFAULT_FE_LABEL


@dataclass(frozen=True)
class JobRef:
    """One Nomad job behind a tile, and the node its jobspec constrains it to.

    `name` is a Consul service name rather than a Nomad job for an agent
    endpoint (Vault, Nomad, Consul), which `status.compute_tile_states`
    resolves on its own rung. `node` is a deployment-time fact, so it is
    config like everything else here rather than fetched per request.
    """

    name: str
    node: str


@dataclass(frozen=True)
class Tile:
    """One card on the landing page."""

    key: str
    name: str
    desc: str
    color: str
    icon: str
    jobs: list[JobRef]
    fe: FrontEnd | None = None
    connect: ConnectInfo | None = None


@dataclass(frozen=True)
class Group:
    """One headed section of the page, and the tiles under it, in order."""

    key: str
    title: str
    hint: str
    tiles: list[Tile]


def _require(obj: dict[str, Any], field: str, where: str) -> Any:
    value = obj.get(field)
    if value in (None, ""):
        raise TileConfigError(f"{where} is missing required field {field!r}")
    return value


def _parse_connect(raw: Any, tile_key: str) -> ConnectInfo:
    where = f"tile {tile_key!r} 'connect'"
    if not isinstance(raw, dict):
        raise TileConfigError(f"tile {tile_key!r} has a 'connect' that is not an object")
    return ConnectInfo(
        protocol=_require(raw, "protocol", where),
        address=_require(raw, "address", where),
        auth=_require(raw, "auth", where),
        example=_require(raw, "example", where),
    )


def _parse_fe(raw: Any, tile_key: str) -> FrontEnd:
    where = f"tile {tile_key!r} 'fe'"
    if not isinstance(raw, dict):
        raise TileConfigError(f"tile {tile_key!r} has an 'fe' that is not an object")
    return FrontEnd(
        url=_require(raw, "url", where),
        label=raw.get("label") or DEFAULT_FE_LABEL,
    )


def _parse_jobs(raw: Any, tile_key: str) -> list[JobRef]:
    if not isinstance(raw, list) or not raw:
        raise TileConfigError(f"tile {tile_key!r} needs a non-empty 'jobs' array")
    jobs = []
    for entry in raw:
        if not isinstance(entry, dict):
            raise TileConfigError(f"tile {tile_key!r} has a 'jobs' entry that is not an object")
        where = f"tile {tile_key!r} job"
        jobs.append(
            JobRef(name=_require(entry, "name", where), node=_require(entry, "node", where))
        )
    return jobs


def _parse_tile(raw: dict[str, Any]) -> Tile:
    key = raw.get("key")
    if not key:
        raise TileConfigError("a tile is missing its required 'key' field")

    where = f"tile {key!r}"
    name = _require(raw, "name", where)
    desc = _require(raw, "desc", where)
    color = _require(raw, "color", where)
    icon = _require(raw, "icon", where)
    jobs = _parse_jobs(raw.get("jobs"), key)

    fe = _parse_fe(raw["fe"], key) if raw.get("fe") is not None else None
    connect = _parse_connect(raw["connect"], key) if raw.get("connect") is not None else None
    if fe is None and connect is None:
        raise TileConfigError(f"tile {key!r} needs an 'fe' or 'connect' block, or both")

    return Tile(
        key=key,
        name=name,
        desc=desc,
        color=color,
        icon=icon,
        jobs=jobs,
        fe=fe,
        connect=connect,
    )


def _parse_group(raw: Any, seen_tiles: set[str]) -> Group:
    if not isinstance(raw, dict):
        raise TileConfigError("a group entry is not an object")

    key = raw.get("key")
    if not key:
        raise TileConfigError("a group is missing its required 'key' field")

    title = _require(raw, "title", f"group {key!r}")
    tiles_raw = raw.get("tiles")
    if not isinstance(tiles_raw, list) or not tiles_raw:
        raise TileConfigError(f"group {key!r} needs a non-empty 'tiles' array")

    tiles = []
    for item in tiles_raw:
        if not isinstance(item, dict):
            raise TileConfigError(f"group {key!r} contains a tile entry that is not an object")
        tile = _parse_tile(item)
        if tile.key in seen_tiles:
            raise TileConfigError(f"duplicate tile key {tile.key!r}")
        seen_tiles.add(tile.key)
        tiles.append(tile)

    return Group(key=key, title=title, hint=raw.get("hint") or "", tiles=tiles)


def load_tiles(path: Path) -> list[Group]:
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
        raise TileConfigError(f"{path} must be a JSON array of groups")

    groups = []
    seen_groups: set[str] = set()
    seen_tiles: set[str] = set()
    for item in raw:
        group = _parse_group(item, seen_tiles)
        if group.key in seen_groups:
            raise TileConfigError(f"duplicate group key {group.key!r}")
        seen_groups.add(group.key)
        groups.append(group)
    return groups
