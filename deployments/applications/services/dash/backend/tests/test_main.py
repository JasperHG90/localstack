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

POSTGRES = {
    "key": "postgres",
    "name": "postgres",
    "desc": "primary database",
    "color": "#336791",
    "icon": "<svg></svg>",
    "jobs": [{"name": "postgres", "node": "firebat"}],
    "connect": {
        "protocol": "PostgreSQL wire protocol",
        "address": "firebat:5432",
        "auth": "Short-lived credentials from Vault's database secrets engine.",
        "example": "psql -h firebat -p 5432 -U <vault-issued-user> -d <database>",
    },
}

REDIS = {
    "key": "redis",
    "name": "redis",
    "desc": "cache",
    "color": "#a41e11",
    "icon": "<svg></svg>",
    "jobs": [{"name": "redis", "node": "radxa-dragon-q6a"}],
    "connect": {
        "protocol": "RESP (Redis protocol)",
        "address": "radxa-dragon-q6a:6379",
        "auth": "Short-lived credentials from Vault's Redis secrets engine.",
        "example": "redis-cli -h radxa-dragon-q6a -p 6379 -a <vault-issued-password>",
    },
}

GRAFANA = {
    "key": "grafana",
    "name": "grafana",
    "desc": "dashboards & metrics",
    "color": "#f2762e",
    "icon": "<svg></svg>",
    "jobs": [{"name": "grafana", "node": "ubuntu"}],
    "fe": {"url": "https://grafana.lab.orangecluster.nl"},
}

OPENVIKING = {
    "key": "openviking",
    "name": "openviking",
    "desc": "context store",
    "color": "#4fb39a",
    "icon": "<svg></svg>",
    "jobs": [{"name": "openviking", "node": "radxa-dragon-q6a"}],
    "fe": {"url": "https://openviking.lab.orangecluster.nl", "label": "open dashboard"},
    "connect": {
        "protocol": "REST / MCP API",
        "address": "https://openviking-api.lab.orangecluster.nl",
        "auth": "Per-user API key.",
        "example": "curl -H 'X-API-Key: <key>' https://openviking-api.lab.orangecluster.nl",
    },
}

REGISTRY = {
    "key": "registry",
    "name": "registry",
    "desc": "oci images & models",
    "color": "#7a8cd1",
    "icon": "<svg></svg>",
    "jobs": [
        {"name": "registry", "node": "ubuntu"},
        {"name": "registry-ui", "node": "radxa-dragon-q6a"},
    ],
    "fe": {"url": "https://registry-ui.lab.orangecluster.nl", "label": "open registry-ui"},
    "connect": {
        "protocol": "OCI Distribution API over HTTPS",
        "address": "https://registry.lab.orangecluster.nl",
        "auth": "Basic auth (htpasswd).",
        "example": "podman login registry.lab.orangecluster.nl -u push",
    },
}

TELEMETRY = {"key": "telemetry", "title": "Telemetry", "hint": "metrics", "tiles": [GRAFANA]}
STORAGE = {"key": "storage", "title": "Storage", "hint": "data", "tiles": [POSTGRES, REDIS]}


def _config(tmp_path: Path) -> Config:
    token_file = tmp_path / "nomad-token"
    token_file.write_text("fake-token")
    return Config(
        nomad_addr="http://nomad.invalid",
        consul_addr="http://consul.invalid",
        nomad_token_file=token_file,
        tiles_path=tmp_path / "tiles.json",
    )


def _write_tiles(tmp_path: Path, groups: list[dict[str, Any]]) -> Path:
    path = tmp_path / "tiles.json"
    path.write_text(json.dumps(groups))
    return path


def _offline(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(live, "job_statuses", lambda *a, **k: [])
    monkeypatch.setattr(live, "list_nodes", lambda *a, **k: [])
    monkeypatch.setattr(live, "list_checks", lambda *a, **k: [])
    monkeypatch.setattr(live, "list_services", lambda *a, **k: {})
    monkeypatch.setattr(live, "job_service_names", lambda *a, **k: [])


def _get(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, groups: list[dict[str, Any]]) -> Any:
    _offline(monkeypatch)
    config = _config(tmp_path)
    app = create_app(config, load_tiles(_write_tiles(tmp_path, groups)))
    return TestClient(app).get("/api/status")


def test_status_endpoint_calls_judge_all_and_join(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
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

    response = _get(tmp_path, monkeypatch, [TELEMETRY])

    assert response.status_code == 200
    assert calls["judge_all"] == 1
    assert calls["join"] == 1


def test_status_payload_carries_groups_in_config_order(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    body = _get(tmp_path, monkeypatch, [TELEMETRY, STORAGE]).json()

    assert "tiles" not in body
    assert [g["key"] for g in body["groups"]] == ["telemetry", "storage"]
    assert [g["title"] for g in body["groups"]] == ["Telemetry", "Storage"]
    assert body["groups"][0]["hint"] == "metrics"
    assert [t["key"] for t in body["groups"][1]["tiles"]] == ["postgres", "redis"]

    # Order is the config's, not a sort: reversing the config reverses the payload.
    reversed_body = _get(tmp_path, monkeypatch, [STORAGE, TELEMETRY]).json()
    assert [g["key"] for g in reversed_body["groups"]] == ["storage", "telemetry"]


def test_every_tile_carries_the_fields_the_page_renders(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The badge, the border and the summary counts all read these three."""
    body = _get(tmp_path, monkeypatch, [TELEMETRY, STORAGE]).json()

    for group in body["groups"]:
        for tile in group["tiles"]:
            assert tile["status"] in {"up", "degraded", "down", "unknown"}
            assert tile["node"]
            assert "counts" in tile
            assert tile["jobs"]


def test_a_tile_with_both_fe_and_connect_emits_both(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    agentic = {"key": "agentic", "title": "Agentic", "tiles": [OPENVIKING]}

    tile = _get(tmp_path, monkeypatch, [agentic]).json()["groups"][0]["tiles"][0]

    assert tile["fe"] == {
        "url": "https://openviking.lab.orangecluster.nl",
        "label": "open dashboard",
    }
    assert tile["connect"]["address"] == "https://openviking-api.lab.orangecluster.nl"


def test_a_tile_with_only_connect_emits_no_fe_key(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    body = _get(tmp_path, monkeypatch, [STORAGE, TELEMETRY]).json()

    postgres = body["groups"][0]["tiles"][0]
    grafana = body["groups"][1]["tiles"][0]

    assert "fe" not in postgres
    assert "connect" in postgres
    # Positive control: the same payload does emit `fe` for a tile that has one.
    assert "fe" in grafana
    assert "connect" not in grafana


def test_each_tile_carries_a_per_job_status_array(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    artifacts = {"key": "artifacts", "title": "Artifacts", "tiles": [REGISTRY]}

    tile = _get(tmp_path, monkeypatch, [artifacts]).json()["groups"][0]["tiles"][0]

    assert [(j["name"], j["node"]) for j in tile["jobs"]] == [
        ("registry", "ubuntu"),
        ("registry-ui", "radxa-dragon-q6a"),
    ]
    assert all(j["status"] in {"up", "degraded", "down", "unknown"} for j in tile["jobs"])


def test_a_two_job_tile_reports_the_folded_status_in_the_payload(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The fold has to reach the JSON, not just `compute_tile_states`."""
    from dash_app.nomad_client import Alloc, Job

    artifacts = {"key": "artifacts", "title": "Artifacts", "tiles": [REGISTRY]}
    jobs = [
        Job(
            name="registry",
            job_type="service",
            status="running",
            stopped=False,
            desired=1,
            allocs=[Alloc(client_status="running", group="registry", node_id="n1")],
        ),
        Job(name="registry-ui", job_type="service", status="dead", stopped=True, desired=0),
    ]

    _offline(monkeypatch)
    monkeypatch.setattr(live, "job_statuses", lambda *a, **k: jobs)
    config = _config(tmp_path)
    app = create_app(config, load_tiles(_write_tiles(tmp_path, [artifacts])))

    tile = TestClient(app).get("/api/status").json()["groups"][0]["tiles"][0]

    assert tile["status"] == "down"
    assert tile["node"] == "radxa-dragon-q6a"
    assert {j["name"]: j["status"] for j in tile["jobs"]} == {
        "registry": "up",
        "registry-ui": "down",
    }


def test_connect_info_never_carries_a_credential_value(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    body = _get(tmp_path, monkeypatch, [STORAGE]).json()

    tiles = body["groups"][0]["tiles"]
    assert len(tiles) == 2
    for tile, fixture in zip(tiles, [POSTGRES, REDIS], strict=True):
        assert tile["connect"] == fixture["connect"]
        # No key anywhere in the response carries anything shaped like a
        # rendered secret -- only the four config-sourced strings above.
        assert set(tile["connect"].keys()) == {"protocol", "address", "auth", "example"}


def test_a_fetch_failure_returns_unknown_tiles_not_a_500(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def boom(*args: Any, **kwargs: Any) -> Any:
        raise ConnectionError("nomad unreachable")

    _offline(monkeypatch)
    monkeypatch.setattr(live, "job_statuses", boom)
    config = _config(tmp_path)
    app = create_app(config, load_tiles(_write_tiles(tmp_path, [TELEMETRY, STORAGE])))

    response = TestClient(app).get("/api/status")

    assert response.status_code == 200
    body = response.json()
    # The page skeleton survives: same groups, same tiles, nothing known.
    assert [g["key"] for g in body["groups"]] == ["telemetry", "storage"]
    assert body["groups"][0]["tiles"][0]["status"] == "unknown"
    assert "error" in body
