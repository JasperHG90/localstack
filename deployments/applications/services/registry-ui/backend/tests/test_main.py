"""The route and its config.

These moved out of dash's suite when this service was split out, and were
briefly lost in the move: `main.py` and `config.py` shipped one revision
with no coverage at all, which took the credential guardrail's only scorer
with them. That is what this file exists to prevent recurring.
"""

from __future__ import annotations

import base64
import json
from pathlib import Path

import pytest
from starlette.testclient import TestClient

from registry_ui.config import Config, ConfigError
from registry_ui.main import create_app

PASSWORD = "shibboleth"


def _config(tmp_path: Path, credential: str | None = None) -> Config:
    credential_file = tmp_path / "registry.json"
    if credential is None:
        credential = json.dumps({"username": "push", "password": PASSWORD})
    credential_file.write_text(credential)
    return Config(
        registry_addr="http://registry.invalid",
        registry_credential_file=credential_file,
        registry_db_path=tmp_path / "registry.db",
    )


def test_from_env_names_every_missing_variable_at_once(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in ("REGISTRY_ADDR", "REGISTRY_CREDENTIAL_FILE", "REGISTRY_DB_PATH"):
        monkeypatch.delenv(name, raising=False)
    with pytest.raises(ConfigError) as caught:
        Config.from_env()
    message = str(caught.value)
    assert "REGISTRY_ADDR" in message
    assert "REGISTRY_CREDENTIAL_FILE" in message
    assert "REGISTRY_DB_PATH" in message


def test_a_credential_that_has_not_rendered_reads_as_absent(tmp_path: Path) -> None:
    """An unrendered Vault template must not raise, the same stance dash takes."""
    missing = Config(
        registry_addr="http://registry.invalid",
        registry_credential_file=tmp_path / "never-written.json",
        registry_db_path=tmp_path / "registry.db",
    )
    assert missing.read_registry_credential() is None
    # the half-rendered shapes a consul-template restart can leave behind
    assert _config(tmp_path, credential="").read_registry_credential() is None
    assert _config(tmp_path, credential="{{ with secret }}").read_registry_credential() is None
    assert _config(tmp_path, credential='{"username":"push"}').read_registry_credential() is None


def test_an_unrendered_credential_answers_200_and_creates_no_database(tmp_path: Path) -> None:
    config = _config(tmp_path, credential="")
    app = create_app(config)

    with TestClient(app) as http:
        response = http.get("/api/registry")

    assert response.status_code == 200
    body = response.json()
    assert body["models"] == []
    assert body["error"] == "registry credential not rendered yet"
    assert not config.registry_db_path.exists(), "no store is built without a credential"


def test_an_unreachable_registry_returns_an_error_payload_not_a_500(tmp_path: Path) -> None:
    app = create_app(_config(tmp_path))

    with TestClient(app) as http:
        response = http.get("/api/registry")

    assert response.status_code == 200
    body = response.json()
    assert body["models"] == []
    assert body["images"] == []
    assert body["error"], "the failure is reported rather than swallowed"


def test_the_payload_never_carries_the_registry_credential(tmp_path: Path) -> None:
    """Guardrail. The positive control proves the credential is really there."""
    config = _config(tmp_path)
    assert config.read_registry_credential() == ("push", PASSWORD)

    app = create_app(config)
    with TestClient(app) as http:
        raw = http.get("/api/registry").text

    assert PASSWORD not in raw
    # the wire form too: grepping the plaintext alone would miss a leaked
    # Authorization header, which is what the client actually sends.
    assert base64.b64encode(f"push:{PASSWORD}".encode()).decode() not in raw


def test_the_static_page_carries_no_credential_and_no_secret_path() -> None:
    """The frontend is a separate task, so assert on the file the browser gets."""
    index = (Path(__file__).resolve().parents[2] / "frontend" / "index.html").read_text()
    assert PASSWORD not in index
    assert "REGISTRY_CREDENTIAL_FILE" not in index
    assert "/secrets/" not in index


def test_the_route_answers_on_the_bare_path_only(tmp_path: Path) -> None:
    """oauth2-proxy matches the upstream path exactly; a nested path is not ours."""
    app = create_app(_config(tmp_path))

    with TestClient(app) as http:
        assert http.get("/api/registry").status_code == 200
        assert http.get("/api/registry/nested").status_code == 404
        assert http.get("/api/status").status_code == 404, "this service serves one route"


def test_the_refresh_flag_is_accepted_on_the_same_path(tmp_path: Path) -> None:
    """A query string still matches an exact path-scoped upstream."""
    app = create_app(_config(tmp_path))

    with TestClient(app) as http:
        assert http.get("/api/registry?refresh=1").status_code == 200
