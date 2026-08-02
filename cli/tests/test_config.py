import pytest

from localstack_cli.config import Config, ConfigError

ADDRS = {
    "VAULT_ADDR": "https://vault.example.invalid",
    "NOMAD_ADDR": "https://nomad.example.invalid",
    "CONSUL_HTTP_ADDR": "https://consul.example.invalid",
}


def test_reads_all_three_addresses(monkeypatch: pytest.MonkeyPatch) -> None:
    for name, value in ADDRS.items():
        monkeypatch.setenv(name, value)
    config = Config.from_env()
    assert config.vault_addr == ADDRS["VAULT_ADDR"]
    assert config.nomad_addr == ADDRS["NOMAD_ADDR"]
    assert config.consul_addr == ADDRS["CONSUL_HTTP_ADDR"]


@pytest.mark.parametrize("missing", sorted(ADDRS))
def test_names_the_missing_variable(monkeypatch: pytest.MonkeyPatch, missing: str) -> None:
    for name, value in ADDRS.items():
        monkeypatch.setenv(name, value)
    monkeypatch.delenv(missing)
    with pytest.raises(ConfigError) as excinfo:
        Config.from_env()
    assert missing in str(excinfo.value)


def test_reports_every_missing_variable_at_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """One re-run should reveal all three, not the first of three."""
    for name in ADDRS:
        monkeypatch.delenv(name, raising=False)
    with pytest.raises(ConfigError) as excinfo:
        Config.from_env()
    message = str(excinfo.value)
    for name in ADDRS:
        assert name in message


def test_empty_string_counts_as_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    """An exported-but-empty var is a likelier mistake than an unset one."""
    for name, value in ADDRS.items():
        monkeypatch.setenv(name, value)
    monkeypatch.setenv("VAULT_ADDR", "")
    with pytest.raises(ConfigError):
        Config.from_env()
