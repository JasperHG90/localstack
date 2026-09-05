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


AGENT_TILE = {
    "key": "hermes",
    "name": "hermes",
    "desc": "telegram agent",
    "color": "#a68a1f",
    "icon": "<svg></svg>",
    "category": "agents",
    "job": "hermes",
    "node": "test-node",
    "connect": {
        "protocol": "Telegram bot",
        "address": "test-node:8642",
        "auth": "Message the bot directly in Telegram.",
        "example": "Open your Hermes chat in Telegram.",
    },
}


def test_loads_an_agent_tile_with_its_connect_block(tmp_path: Path) -> None:
    path = _write(tmp_path, json.dumps([AGENT_TILE]))

    agent = load_tiles(path)[0]

    assert agent.category == "agents"
    assert agent.url is None
    assert agent.connect is not None
    assert agent.connect.address == "test-node:8642"


def test_rejects_an_agent_tile_missing_connect(tmp_path: Path) -> None:
    broken = {k: v for k, v in AGENT_TILE.items() if k != "connect"}
    path = _write(tmp_path, json.dumps([broken]))

    with pytest.raises(TileConfigError, match="'hermes' is missing its 'connect' block"):
        load_tiles(path)


def test_rejects_an_unknown_category(tmp_path: Path) -> None:
    broken = {**AGENT_TILE, "category": "agent"}
    path = _write(tmp_path, json.dumps([broken]))

    with pytest.raises(TileConfigError, match="category"):
        load_tiles(path)


SHIPPED_TILES = Path(__file__).resolve().parents[2] / "tiles.json"


def test_the_shipped_tile_config_parses() -> None:
    tiles = load_tiles(SHIPPED_TILES)

    assert tiles
    agents = [t for t in tiles if t.category == "agents"]
    assert {t.key for t in agents} >= {"hermes", "memex"}
    assert all(t.connect is not None for t in agents)


def test_the_shipped_registry_tile_documents_podman_and_kit() -> None:
    registry = next(t for t in load_tiles(SHIPPED_TILES) if t.key == "registry")

    assert registry.connect is not None
    example = registry.connect.example
    assert "podman login" in example
    assert "kit login" in example


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
