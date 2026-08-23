import json
from pathlib import Path
from typing import Any

import pytest
from starlette.testclient import TestClient

import dash_app.live as live
import dash_app.status as status
from dash_app.config import Config
from dash_app.main import create_app
from dash_app.tiles import load_tiles

BACKEND_TILES = [
    {
        "key": "postgres",
        "name": "postgres",
        "desc": "primary database",
        "color": "#336791",
        "icon": "<svg></svg>",
        "category": "backend",
        "job": "postgres",
        "node": "firebat",
        "connect": {
            "protocol": "PostgreSQL wire protocol",
            "address": "firebat:5432",
            "auth": "Short-lived credentials from Vault's database secrets engine.",
            "example": "psql -h firebat -p 5432 -U <vault-issued-user> -d <database>",
        },
    },
    {
        "key": "redis",
        "name": "redis",
        "desc": "cache",
        "color": "#a41e11",
        "icon": "<svg></svg>",
        "category": "backend",
        "job": "redis",
        "node": "radxa-dragon-q6a",
        "connect": {
            "protocol": "RESP (Redis protocol)",
            "address": "radxa-dragon-q6a:6379",
            "auth": "Short-lived credentials from Vault's Redis secrets engine.",
            "example": "redis-cli -h radxa-dragon-q6a -p 6379 -a <vault-issued-password>",
        },
    },
]

DASHBOARD_TILE = {
    "key": "grafana",
    "name": "grafana",
    "desc": "dashboards & metrics",
    "color": "#f2762e",
    "icon": "<svg></svg>",
    "category": "dashboard",
    "job": "grafana",
    "node": "ubuntu",
    "url": "https://grafana.lab.orangecluster.nl",
}


def _config(tmp_path: Path) -> Config:
    token_file = tmp_path / "nomad-token"
    token_file.write_text("fake-token")
    return Config(
        nomad_addr="http://nomad.invalid",
        consul_addr="http://consul.invalid",
        nomad_token_file=token_file,
        tiles_path=tmp_path / "tiles.json",
    )


def _write_tiles(tmp_path: Path, entries: list[dict[str, Any]]) -> Path:
    path = tmp_path / "tiles.json"
    path.write_text(json.dumps(entries))
    return path


def test_status_endpoint_calls_judge_all_and_join(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    tiles_path = _write_tiles(tmp_path, [DASHBOARD_TILE])
    tiles = load_tiles(tiles_path)
    config = _config(tmp_path)

    calls = {"judge_all": 0, "join": 0}
    real_judge_all = status.judge_all
    real_join = status.join

    def spy_judge_all(*args: Any, **kwargs: Any) -> Any:
        calls["judge_all"] += 1
        return real_judge_all(*args, **kwargs)

    def spy_join(*args: Any, **kwargs: Any) -> Any:
        calls["join"] += 1
        return real_join(*args, **kwargs)

    monkeypatch.setattr(status, "judge_all", spy_judge_all)
    monkeypatch.setattr(status, "join", spy_join)
    monkeypatch.setattr(live, "job_statuses", lambda *a, **k: [])
    monkeypatch.setattr(live, "list_nodes", lambda *a, **k: [])
    monkeypatch.setattr(live, "list_checks", lambda *a, **k: [])
    monkeypatch.setattr(live, "list_services", lambda *a, **k: {})
    monkeypatch.setattr(live, "job_service_names", lambda *a, **k: [])

    app = create_app(config, tiles)
    client = TestClient(app)

    response = client.get("/api/status")

    assert response.status_code == 200
    assert calls["judge_all"] == 1
    assert calls["join"] == 1


def test_connect_info_never_carries_a_credential_value(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    tiles_path = _write_tiles(tmp_path, BACKEND_TILES)
    tiles = load_tiles(tiles_path)
    config = _config(tmp_path)

    monkeypatch.setattr(live, "job_statuses", lambda *a, **k: [])
    monkeypatch.setattr(live, "list_nodes", lambda *a, **k: [])
    monkeypatch.setattr(live, "list_checks", lambda *a, **k: [])
    monkeypatch.setattr(live, "list_services", lambda *a, **k: {})
    monkeypatch.setattr(live, "job_service_names", lambda *a, **k: [])

    app = create_app(config, tiles)
    client = TestClient(app)

    response = client.get("/api/status")
    body = response.json()

    backend_tiles = [t for t in body["tiles"] if t["category"] == "backend"]
    assert len(backend_tiles) == 2
    for tile, fixture in zip(backend_tiles, BACKEND_TILES, strict=True):
        assert tile["connect"] == fixture["connect"]
        # No key anywhere in the response carries anything shaped like a
        # rendered secret -- only the four config-sourced strings above.
        assert set(tile["connect"].keys()) == {"protocol", "address", "auth", "example"}


def test_a_fetch_failure_returns_unknown_tiles_not_a_500(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    tiles_path = _write_tiles(tmp_path, [DASHBOARD_TILE])
    tiles = load_tiles(tiles_path)
    config = _config(tmp_path)

    def boom(*args: Any, **kwargs: Any) -> Any:
        raise ConnectionError("nomad unreachable")

    monkeypatch.setattr(live, "job_statuses", boom)

    app = create_app(config, tiles)
    client = TestClient(app)

    response = client.get("/api/status")

    assert response.status_code == 200
    body = response.json()
    assert body["tiles"][0]["status"] == "unknown"
    assert "error" in body
