"""The dash backend: serves the live status endpoint only.

`create_app` takes its config and tiles as arguments rather than reading
the environment itself, so tests can build a real Starlette app against
fake data without an env var in sight. `main()` is the only place that
reads the environment and starts a server.

The frontend's static files are served by a separate task
(`deployments/applications/services/dash/frontend/`) -- this app no longer
mounts them; see `dash.hcl` for the two-task split.
"""

from __future__ import annotations

import os
from datetime import UTC, datetime
from typing import Any

from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Route

from dash_app.config import Config
from dash_app.live import fetch_tile_states
from dash_app.status import GroupState, TileState, unknown_states
from dash_app.tiles import Group, load_tiles


def _tile_json(state: TileState) -> dict[str, Any]:
    """Everything the page renders for one tile.

    `status`, `node` and `counts` are the tile-level, folded values the
    card foot, badge, border and summary counts all read; `jobs` carries
    the per-job breakdown the panel lists. Dropping any of them renders a
    page with no badges, and no gate in this repo would catch it.
    """
    tile = state.tile
    body: dict[str, Any] = {
        "key": tile.key,
        "name": tile.name,
        "desc": tile.desc,
        "color": tile.color,
        "icon": tile.icon,
        "status": state.status,
        "node": state.node,
        "counts": state.counts,
        "jobs": [
            {
                "name": job.job.name,
                "node": job.job.node,
                "status": job.status,
                "counts": job.counts,
            }
            for job in state.jobs
        ],
    }
    if tile.fe is not None:
        body["fe"] = {"url": tile.fe.url, "label": tile.fe.label}
    if tile.connect is not None:
        body["connect"] = {
            "protocol": tile.connect.protocol,
            "address": tile.connect.address,
            "auth": tile.connect.auth,
            "example": tile.connect.example,
        }
    return body


def _group_json(state: GroupState) -> dict[str, Any]:
    return {
        "key": state.group.key,
        "title": state.group.title,
        "hint": state.group.hint,
        "tiles": [_tile_json(tile) for tile in state.tiles],
    }


def create_app(config: Config, groups: list[Group]) -> Starlette:
    async def status_endpoint(request: Any) -> JSONResponse:  # noqa: ARG001
        try:
            states = fetch_tile_states(config, groups)
            error = None
        except Exception as err:  # noqa: BLE001
            # A fetch failure reads as "nothing is known yet", the same
            # honest-uncertainty stance cli's own TUI panels take, rather
            # than a 500 that takes the whole page down with it. The page
            # skeleton still renders: same groups, same tiles, no status.
            states = unknown_states(groups)
            error = str(err)

        payload: dict[str, Any] = {
            "groups": [_group_json(state) for state in states],
            "generated_at": datetime.now(UTC).isoformat(),
        }
        if error is not None:
            payload["error"] = error
        return JSONResponse(payload)

    routes = [
        Route("/api/status", status_endpoint),
    ]
    return Starlette(routes=routes)


def main() -> None:
    import uvicorn

    config = Config.from_env()
    groups = load_tiles(config.tiles_path)
    app = create_app(config, groups)
    port = int(os.environ.get("PORT", "8001"))
    uvicorn.run(app, host="0.0.0.0", port=port)  # noqa: S104


if __name__ == "__main__":
    main()
