"""Fetch live Nomad/Consul state and compute tile status.

Thin glue over this app's own read functions (`dash_app.nomad_client`,
`dash_app.consul_client`, copied down from `cli` per Requirement 2) plus
this app's `status.compute_tile_states`. No health-rule logic lives here --
see `status.py`'s module docstring for why, and for why this never fetches
HAProxy's own routing config.
"""

from __future__ import annotations

from dash_app.config import Config
from dash_app.consul_client import list_checks, list_services
from dash_app.nomad_client import job_service_names, job_statuses, list_nodes
from dash_app.status import TileState, compute_tile_states
from dash_app.tiles import Tile


def fetch_tile_states(config: Config, tiles: list[Tile]) -> list[TileState]:
    """Live per-tile status. Raises on a network/auth failure."""
    token = config.read_nomad_token()
    jobs = job_statuses(config.nomad_addr, token)
    nodes = list_nodes(config.nomad_addr, token)
    checks = list_checks(config.consul_addr)
    catalog = list_services(config.consul_addr)

    job_names = {job.name for job in jobs}
    service_names = {
        tile.job: job_service_names(config.nomad_addr, token, tile.job)
        for tile in tiles
        if tile.job in job_names
    }

    return compute_tile_states(tiles, jobs, nodes, checks, catalog, service_names)
