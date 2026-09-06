import json
from pathlib import Path

import pytest

from dash_app.tiles import Group, Tile, TileConfigError, load_tiles

GRAFANA = {
    "key": "grafana",
    "name": "grafana",
    "desc": "dashboards & metrics",
    "color": "#f2762e",
    "icon": "<svg></svg>",
    "jobs": [{"name": "grafana", "node": "test-node"}],
    "fe": {"url": "https://grafana.lab.orangecluster.nl"},
}

CONNECT = {
    "protocol": "PostgreSQL wire protocol",
    "address": "firebat:5432",
    "auth": "Short-lived credentials from Vault.",
    "example": "psql -h firebat -p 5432 -U <user> -d <database>",
}

POSTGRES = {
    "key": "postgres",
    "name": "postgres",
    "desc": "primary database",
    "color": "#336791",
    "icon": "<svg></svg>",
    "jobs": [{"name": "postgres", "node": "test-node"}],
    "connect": CONNECT,
}

VALID_CONFIG = [
    {"key": "telemetry", "title": "Telemetry", "hint": "metrics", "tiles": [GRAFANA]},
    {"key": "storage", "title": "Storage", "hint": "databases", "tiles": [POSTGRES]},
]


def _write(tmp_path: Path, content: str) -> Path:
    path = tmp_path / "tiles.json"
    path.write_text(content)
    return path


def _groups(tmp_path: Path, raw: object) -> list[Group]:
    return load_tiles(_write(tmp_path, json.dumps(raw)))


def test_loads_ordered_groups_in_file_order(tmp_path: Path) -> None:
    groups = _groups(tmp_path, VALID_CONFIG)

    assert [g.key for g in groups] == ["telemetry", "storage"]
    assert [g.title for g in groups] == ["Telemetry", "Storage"]
    assert groups[0].hint == "metrics"
    assert [t.key for t in groups[0].tiles] == ["grafana"]

    # The order is the file's, not any sort the loader might apply: reversing
    # the file reverses the result.
    reversed_groups = _groups(tmp_path, list(reversed(VALID_CONFIG)))
    assert [g.key for g in reversed_groups] == ["storage", "telemetry"]


def test_keeps_tile_order_within_a_group(tmp_path: Path) -> None:
    both = [{"key": "mixed", "title": "Mixed", "tiles": [POSTGRES, GRAFANA]}]

    assert [t.key for t in _groups(tmp_path, both)[0].tiles] == ["postgres", "grafana"]

    swapped = [{"key": "mixed", "title": "Mixed", "tiles": [GRAFANA, POSTGRES]}]
    assert [t.key for t in _groups(tmp_path, swapped)[0].tiles] == ["grafana", "postgres"]


def test_a_frontend_tile_carries_its_url_and_no_connect(tmp_path: Path) -> None:
    tile = _groups(tmp_path, VALID_CONFIG)[0].tiles[0]

    assert tile.fe is not None
    assert tile.fe.url == "https://grafana.lab.orangecluster.nl"
    assert tile.fe.label == "open"
    assert tile.connect is None


def test_a_frontend_tile_may_name_its_button_label(tmp_path: Path) -> None:
    labelled = dict(GRAFANA, fe={"url": "https://x.example", "label": "open registry-ui"})
    config = [{"key": "g", "title": "G", "tiles": [labelled]}]

    fe = _groups(tmp_path, config)[0].tiles[0].fe
    assert fe is not None
    assert fe.label == "open registry-ui"


def test_a_backend_tile_carries_its_connect_and_no_fe(tmp_path: Path) -> None:
    tile = _groups(tmp_path, VALID_CONFIG)[1].tiles[0]

    assert tile.fe is None
    assert tile.connect is not None
    assert tile.connect.protocol == "PostgreSQL wire protocol"


def test_accepts_a_tile_with_both_fe_and_connect(tmp_path: Path) -> None:
    """The case TODO.md asks for: a service with a UI *and* an API."""
    both = dict(POSTGRES, fe={"url": "https://openviking.lab.orangecluster.nl"})
    config = [{"key": "agentic", "title": "Agentic", "tiles": [both]}]

    tile = _groups(tmp_path, config)[0].tiles[0]

    assert tile.fe is not None
    assert tile.connect is not None


def test_rejects_a_tile_with_neither_fe_nor_connect(tmp_path: Path) -> None:
    naked = {k: v for k, v in POSTGRES.items() if k != "connect"}
    config = [{"key": "storage", "title": "Storage", "tiles": [naked]}]

    with pytest.raises(TileConfigError, match="'fe' or 'connect'"):
        _groups(tmp_path, config)


def test_rejects_a_tile_with_an_empty_jobs_list(tmp_path: Path) -> None:
    config = [{"key": "storage", "title": "Storage", "tiles": [dict(POSTGRES, jobs=[])]}]

    with pytest.raises(TileConfigError, match="jobs"):
        _groups(tmp_path, config)


def test_rejects_a_job_missing_its_node(tmp_path: Path) -> None:
    config = [
        {
            "key": "storage",
            "title": "Storage",
            "tiles": [dict(POSTGRES, jobs=[{"name": "postgres"}])],
        }
    ]

    with pytest.raises(TileConfigError, match="node"):
        _groups(tmp_path, config)


def test_rejects_a_duplicate_group_key(tmp_path: Path) -> None:
    config = [
        {"key": "storage", "title": "Storage", "tiles": [POSTGRES]},
        {"key": "storage", "title": "Storage Again", "tiles": [GRAFANA]},
    ]

    with pytest.raises(TileConfigError, match="duplicate group key 'storage'"):
        _groups(tmp_path, config)


def test_rejects_a_duplicate_tile_key_across_groups(tmp_path: Path) -> None:
    config = [
        {"key": "storage", "title": "Storage", "tiles": [POSTGRES]},
        {"key": "telemetry", "title": "Telemetry", "tiles": [POSTGRES]},
    ]

    with pytest.raises(TileConfigError, match="duplicate tile key 'postgres'"):
        _groups(tmp_path, config)


def test_rejects_a_group_missing_its_title(tmp_path: Path) -> None:
    with pytest.raises(TileConfigError, match="title"):
        _groups(tmp_path, [{"key": "storage", "tiles": [POSTGRES]}])


def test_rejects_a_group_with_no_tiles(tmp_path: Path) -> None:
    with pytest.raises(TileConfigError, match="tiles"):
        _groups(tmp_path, [{"key": "storage", "title": "Storage", "tiles": []}])


def test_rejects_a_tile_missing_its_name(tmp_path: Path) -> None:
    nameless = {k: v for k, v in GRAFANA.items() if k != "name"}
    config = [{"key": "telemetry", "title": "Telemetry", "tiles": [nameless]}]

    with pytest.raises(TileConfigError, match="name"):
        _groups(tmp_path, config)


def test_rejects_a_connect_block_missing_a_field(tmp_path: Path) -> None:
    connect = dict(CONNECT)
    del connect["example"]
    config = [{"key": "storage", "title": "Storage", "tiles": [dict(POSTGRES, connect=connect)]}]

    with pytest.raises(TileConfigError, match="example"):
        _groups(tmp_path, config)


def test_rejects_a_frontend_block_missing_its_url(tmp_path: Path) -> None:
    config = [{"key": "telemetry", "title": "Telemetry", "tiles": [dict(GRAFANA, fe={})]}]

    with pytest.raises(TileConfigError, match="url"):
        _groups(tmp_path, config)


def test_rejects_syntactically_invalid_json(tmp_path: Path) -> None:
    path = _write(tmp_path, "[{,}]")

    with pytest.raises(TileConfigError):
        load_tiles(path)


SHIPPED_TILES = Path(__file__).resolve().parents[2] / "tiles.json"

EXPECTED_GROUPS = ["platform", "storage", "telemetry", "events", "agentic", "artifacts"]

EXPECTED_TILES = {
    "platform": ["nomad", "consul", "vault"],
    "storage": ["postgres", "redis", "minio"],
    "telemetry": ["grafana", "phoenix", "tempo", "prometheus", "alerting"],
    "events": ["nats"],
    "agentic": ["bifrost", "hermes", "openviking"],
    "artifacts": ["registry"],
}


def test_the_shipped_config_parses_into_the_six_expected_groups() -> None:
    """Pins the whole set: a typo that drops a service fails here, not in a browser."""
    groups = load_tiles(SHIPPED_TILES)

    assert [g.key for g in groups] == EXPECTED_GROUPS
    assert {g.key: [t.key for t in g.tiles] for g in groups} == EXPECTED_TILES


def test_every_shipped_tile_has_a_frontend_or_connect_block() -> None:
    for group in load_tiles(SHIPPED_TILES):
        for tile in group.tiles:
            assert tile.fe is not None or tile.connect is not None, tile.key


def test_the_shipped_config_has_no_memex_openviking_api_or_registry_ui_tile() -> None:
    keys = {t.key for g in load_tiles(SHIPPED_TILES) for t in g.tiles}

    assert "memex" not in keys
    assert "openviking-api" not in keys
    assert "registry-ui" not in keys


def test_the_shipped_openviking_tile_carries_both_fe_and_connect() -> None:
    tile = next(t for g in load_tiles(SHIPPED_TILES) for t in g.tiles if t.key == "openviking")

    assert tile.fe is not None
    assert tile.fe.url == "https://openviking.lab.orangecluster.nl"
    assert tile.connect is not None
    assert "openviking-api.lab.orangecluster.nl" in tile.connect.address


def test_the_shipped_registry_tile_names_both_of_its_jobs() -> None:
    tile = next(t for g in load_tiles(SHIPPED_TILES) for t in g.tiles if t.key == "registry")

    assert [(j.name, j.node) for j in tile.jobs] == [
        ("registry", "ubuntu"),
        ("registry-ui", "radxa-dragon-q6a"),
    ]
    assert tile.fe is not None
    assert tile.fe.url == "https://registry-ui.lab.orangecluster.nl"
    assert tile.connect is not None
    assert "podman login" in tile.connect.example
    assert "kit login" in tile.connect.example


def test_the_shipped_prometheus_tile_documents_the_consul_tag() -> None:
    """A service is scraped only if its author tags it, so the tile must say so."""
    tile = next(t for g in load_tiles(SHIPPED_TILES) for t in g.tiles if t.key == "prometheus")

    assert tile.fe is None
    assert tile.connect is not None
    assert "prometheus" in tile.connect.auth
    assert "tag" in tile.connect.auth.lower()
    assert "metrics_path" in tile.connect.auth


def _connect_text(tile: Tile) -> str:
    """Every connect field of a tile, joined. A bot name may sit in any of them."""
    assert tile.connect is not None
    c = tile.connect
    return " ".join([c.protocol, c.address, c.auth, c.example])


def test_the_shipped_telegram_tiles_name_their_bots() -> None:
    tiles = {t.key: t for g in load_tiles(SHIPPED_TILES) for t in g.tiles}

    hermes = _connect_text(tiles["hermes"])
    alerting = _connect_text(tiles["alerting"])

    assert "@OrangeHermes" in hermes
    assert "@OrangeClusterAlertBot" in alerting

    # The two bots are separate and the cards must not blur that. Checked over
    # every connect field, not just address: the hermes card names its bot in
    # three of them, so a narrower check would let the other two drift.
    assert "@OrangeClusterAlertBot" not in hermes
    assert "@OrangeHermes" not in alerting


def test_the_shipped_hermes_tile_keeps_its_lan_only_gateway() -> None:
    """The gateway host and port are the card's only non-Telegram fact."""
    hermes = next(t for g in load_tiles(SHIPPED_TILES) for t in g.tiles if t.key == "hermes")

    assert hermes.connect is not None
    assert "radxa-dragon-q6a:8642" in hermes.connect.address
    assert "LAN-only" in hermes.connect.address


def test_the_shipped_alerting_tile_tracks_grafanas_job() -> None:
    """Grafana is the alert engine, so alerting is down when grafana is."""
    alerting = next(t for g in load_tiles(SHIPPED_TILES) for t in g.tiles if t.key == "alerting")

    assert [(j.name, j.node) for j in alerting.jobs] == [("grafana", "ubuntu")]
    assert alerting.fe is not None
    # Grafana's own alert template links this path (grafana.hcl:378), which is
    # what makes it canonical rather than a guess.
    assert alerting.fe.url == "https://grafana.lab.orangecluster.nl/alerting/list"


def test_the_shipped_alerting_tile_does_not_claim_delivery_on_its_face() -> None:
    """The status dot is grafana's job, and the card face has to say so.

    A card reading "grafana alerts to telegram" beside a green dot asserts a
    delivery nobody checked. docs/monitoring.md documents that exact silent
    failure: alerts fire in the UI and nothing arrives.
    """
    alerting = next(t for g in load_tiles(SHIPPED_TILES) for t in g.tiles if t.key == "alerting")

    assert "unchecked" in alerting.desc


def test_the_shipped_config_carries_no_nomad_template_opener() -> None:
    """`${` and `%{` are jobspec template syntax once dash.hcl splices this file in.

    An expression-shaped `${...}` fails `terraform apply`; `%{ if ... }` parses
    and silently rewrites the deployed text. A bare `$` is safe and ships today.
    """
    raw = SHIPPED_TILES.read_text()

    assert "${" not in raw
    assert "%{" not in raw
