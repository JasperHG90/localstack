import json
from pathlib import Path

import pytest

from dash_app.tiles import TileConfigError, load_tiles

VALID_CONFIG = [
    {
        "key": "grafana",
        "name": "grafana",
        "desc": "dashboards & metrics",
        "color": "#f2762e",
        "icon": "<svg></svg>",
        "category": "dashboard",
        "job": "grafana",
        "node": "test-node",
        "url": "https://grafana.lab.orangecluster.nl",
    },
    {
        "key": "postgres",
        "name": "postgres",
        "desc": "primary database",
        "color": "#336791",
        "icon": "<svg></svg>",
        "category": "backend",
        "job": "postgres",
        "node": "test-node",
        "connect": {
            "protocol": "PostgreSQL wire protocol",
            "address": "firebat:5432",
            "auth": "Short-lived credentials from Vault.",
            "example": "psql -h firebat -p 5432 -U <user> -d <database>",
        },
    },
]


def _write(tmp_path: Path, content: str) -> Path:
    path = tmp_path / "tiles.json"
    path.write_text(content)
    return path


def test_loads_a_valid_mixed_config(tmp_path: Path) -> None:
    path = _write(tmp_path, json.dumps(VALID_CONFIG))

    tiles = load_tiles(path)

    assert len(tiles) == 2
    dashboard = next(t for t in tiles if t.key == "grafana")
    assert dashboard.category == "dashboard"
    assert dashboard.url == "https://grafana.lab.orangecluster.nl"
    assert dashboard.connect is None

    backend = next(t for t in tiles if t.key == "postgres")
    assert backend.category == "backend"
    assert backend.url is None
    assert backend.connect is not None
    assert backend.connect.protocol == "PostgreSQL wire protocol"
    assert backend.connect.address == "firebat:5432"


def test_rejects_syntactically_invalid_json(tmp_path: Path) -> None:
    path = _write(tmp_path, "[{,}]")

    with pytest.raises(TileConfigError):
        load_tiles(path)


def test_rejects_a_dashboard_tile_missing_url(tmp_path: Path) -> None:
    broken = [
        {
            "key": "grafana",
            "name": "grafana",
            "desc": "dashboards & metrics",
            "color": "#f2762e",
            "icon": "<svg></svg>",
            "category": "dashboard",
            "job": "grafana",
            "node": "test-node",
        },
    ]
    path = _write(tmp_path, json.dumps(broken))

    with pytest.raises(TileConfigError, match="url"):
        load_tiles(path)


def test_rejects_a_backend_tile_missing_connect_field(tmp_path: Path) -> None:
    broken = [
        {
            "key": "postgres",
            "name": "postgres",
            "desc": "primary database",
            "color": "#336791",
            "icon": "<svg></svg>",
            "category": "backend",
            "job": "postgres",
            "node": "test-node",
            "connect": {
                "protocol": "PostgreSQL wire protocol",
                "address": "firebat:5432",
                "auth": "Short-lived credentials from Vault.",
                # "example" missing
            },
        },
    ]
    path = _write(tmp_path, json.dumps(broken))

    with pytest.raises(TileConfigError, match="example"):
        load_tiles(path)


def test_rejects_a_tile_missing_its_name(tmp_path: Path) -> None:
    broken = [
        {
            "key": "grafana",
            "desc": "dashboards & metrics",
            "color": "#f2762e",
            "icon": "<svg></svg>",
            "category": "dashboard",
            "job": "grafana",
            "node": "test-node",
            "url": "https://grafana.lab.orangecluster.nl",
        },
    ]
    path = _write(tmp_path, json.dumps(broken))

    with pytest.raises(TileConfigError, match="name"):
        load_tiles(path)
