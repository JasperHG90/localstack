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
from dash_app.status import TileState
from dash_app.tiles import Tile, load_tiles


def _tile_json(state: TileState) -> dict[str, Any]:
    tile = state.tile
    body: dict[str, Any] = {
        "key": tile.key,
        "name": tile.name,
        "desc": tile.desc,
        "color": tile.color,
        "icon": tile.icon,
        "category": tile.category,
        "node": tile.node,
        "status": state.status,
        "counts": state.counts,
    }
    if tile.category == "dashboard":
        body["url"] = tile.url
    else:
        assert tile.connect is not None  # enforced by tiles.load_tiles
        body["connect"] = {
            "protocol": tile.connect.protocol,
            "address": tile.connect.address,
            "auth": tile.connect.auth,
            "example": tile.connect.example,
        }
    return body


def create_app(config: Config, tiles: list[Tile]) -> Starlette:
    async def status_endpoint(request: Any) -> JSONResponse:  # noqa: ARG001
        try:
            states = fetch_tile_states(config, tiles)
            error = None
        except Exception as err:  # noqa: BLE001
            # A fetch failure reads as "nothing is known yet", the same
            # honest-uncertainty stance cli's own TUI panels take, rather
            # than a 500 that takes the whole page down with it.
            states = [
                TileState(tile=tile, status="unknown", counts="", checks="") for tile in tiles
            ]
            error = str(err)

        payload: dict[str, Any] = {
            "tiles": [_tile_json(state) for state in states],
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
    tiles = load_tiles(config.tiles_path)
    app = create_app(config, tiles)
    port = int(os.environ.get("PORT", "8001"))
    uvicorn.run(app, host="0.0.0.0", port=port)  # noqa: S104


if __name__ == "__main__":
    main()
