from __future__ import annotations

from pathlib import Path

import pytest

from driftwatch.config import Config, ConfigError

REQUIRED = {
    "DRIFTWATCH_EMBARK_URL": "http://embark.test:8000/",
    "DRIFTWATCH_EMBARK_KEY_FILE": "/secrets/embark.key",
    "DRIFTWATCH_EMBEDDING_MODEL": "embedding",
    "DRIFTWATCH_RERANK_MODEL": "reranker",
    "DRIFTWATCH_GOLDSET_PATH": "/local/goldset.jsonl",
    "DRIFTWATCH_RERANK_GOLDSET_PATH": "/local/rerank-goldset.jsonl",
    "DRIFTWATCH_BASELINE_PATH": "/var/lib/driftwatch/baseline.npz",
}


@pytest.fixture(autouse=True)
def clean_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in list(REQUIRED) + [
        "DRIFTWATCH_INTERVAL_SECONDS",
        "DRIFTWATCH_RERANK_POOL",
        "DRIFTWATCH_REQUEST_TIMEOUT",
    ]:
        monkeypatch.delenv(name, raising=False)


def set_required(monkeypatch: pytest.MonkeyPatch) -> None:
    for name, value in REQUIRED.items():
        monkeypatch.setenv(name, value)


def test_every_missing_variable_is_named_at_once(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DRIFTWATCH_EMBARK_URL", "http://embark.test:8000")

    with pytest.raises(ConfigError) as err:
        Config.from_env()

    message = str(err.value)
    assert "DRIFTWATCH_EMBEDDING_MODEL" in message
    assert "DRIFTWATCH_GOLDSET_PATH" in message


def test_the_defaults_are_a_daily_run(monkeypatch: pytest.MonkeyPatch) -> None:
    set_required(monkeypatch)

    config = Config.from_env()

    assert config.interval_seconds == 86400.0
    assert config.rerank_pool == 10
    assert config.request_timeout == 120.0


def test_a_trailing_slash_on_the_url_is_dropped(monkeypatch: pytest.MonkeyPatch) -> None:
    """httpx joins a base_url and a path; two slashes reach embark as a 404."""
    set_required(monkeypatch)

    assert Config.from_env().embark_url == "http://embark.test:8000"


def test_a_non_numeric_interval_names_the_variable(monkeypatch: pytest.MonkeyPatch) -> None:
    set_required(monkeypatch)
    monkeypatch.setenv("DRIFTWATCH_INTERVAL_SECONDS", "daily")

    with pytest.raises(ConfigError, match="DRIFTWATCH_INTERVAL_SECONDS is not a number"):
        Config.from_env()


def test_a_zero_interval_is_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    set_required(monkeypatch)
    monkeypatch.setenv("DRIFTWATCH_INTERVAL_SECONDS", "0")

    with pytest.raises(ConfigError, match="must be positive"):
        Config.from_env()


def test_the_key_is_read_and_stripped(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    set_required(monkeypatch)
    key_file = tmp_path / "embark.key"
    key_file.write_text("  secret\n", encoding="utf-8")
    monkeypatch.setenv("DRIFTWATCH_EMBARK_KEY_FILE", str(key_file))

    assert Config.from_env().read_embark_key() == "secret"


def test_an_empty_key_file_is_refused(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    set_required(monkeypatch)
    key_file = tmp_path / "embark.key"
    key_file.write_text("\n", encoding="utf-8")
    monkeypatch.setenv("DRIFTWATCH_EMBARK_KEY_FILE", str(key_file))

    with pytest.raises(ConfigError, match="is empty"):
        Config.from_env().read_embark_key()
