"""The credential cache: modes, atomicity, round trip and staleness."""

import json
import stat
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from localstack_cli.auth.session import (
    DEFAULT_SKEW,
    SCHEMA_VERSION,
    Credential,
    Session,
    SessionError,
    delete,
    expires_at,
    load,
    save,
    session_path,
)

NOW = datetime(2026, 8, 2, 12, 0, tzinfo=UTC)


def credential(minutes: int, **kwargs: object) -> Credential:
    return Credential(
        token=str(kwargs.pop("token", "a-token")),
        accessor=str(kwargs.pop("accessor", "an-accessor")),
        expires_at=NOW + timedelta(minutes=minutes),
        renewable=bool(kwargs.pop("renewable", True)),
        **kwargs,  # type: ignore[arg-type]
    )


def a_session() -> Session:
    return Session(
        method="userpass",
        vault_addr="https://vault.example",
        username="operator",
        vault=Credential(
            token="vault-token",
            accessor="vault-accessor",
            expires_at=NOW + timedelta(days=32),
            renewable=True,
            entity_id="351f302a",
            policies=("default",),
        ),
        nomad=credential(30, token="nomad-token", accessor="nomad-accessor", lease_id="nl"),
        nomad_manage=credential(
            30, token="nomad-manage-token", accessor="nomad-manage-accessor", lease_id="nml"
        ),
        consul=credential(30, token="consul-token", accessor="consul-accessor", lease_id="cl"),
    )


def test_session_path_follows_xdg_config_home(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", "/somewhere/cfg")
    assert session_path() == Path("/somewhere/cfg/localstack/session.json")


def test_session_path_falls_back_to_dot_config(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
    assert session_path() == Path.home() / ".config" / "localstack" / "session.json"


def test_the_cache_is_never_inside_the_repo(monkeypatch: pytest.MonkeyPatch) -> None:
    """Loop worktrees live under `.loop/worktrees/`, and a token written there
    would not be gitignored."""
    monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
    assert ".loop" not in str(session_path())


def test_round_trip_preserves_every_field(tmp_path: Path) -> None:
    path = tmp_path / "cfg" / "session.json"
    original = a_session()
    save(original, path)
    assert load(path) == original


def test_the_file_is_0600_in_a_0700_directory(tmp_path: Path) -> None:
    path = tmp_path / "cfg" / "session.json"
    save(a_session(), path)
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    assert stat.S_IMODE(path.parent.stat().st_mode) == 0o700


def test_the_directory_mode_is_enforced_even_when_it_already_exists(tmp_path: Path) -> None:
    """`mkdir` is subject to umask and an existing directory keeps its own
    mode, so the permissive case is the one worth testing."""
    directory = tmp_path / "cfg"
    directory.mkdir(mode=0o755)
    save(a_session(), directory / "session.json")
    assert stat.S_IMODE(directory.stat().st_mode) == 0o700


def test_the_write_leaves_no_temp_file_behind(tmp_path: Path) -> None:
    path = tmp_path / "cfg" / "session.json"
    save(a_session(), path)
    assert [p.name for p in path.parent.iterdir()] == ["session.json"]


def test_a_missing_cache_is_none_not_an_error(tmp_path: Path) -> None:
    """Nobody having logged in is an ordinary state, not a failure."""
    assert load(tmp_path / "absent.json") is None


def test_corrupt_json_reports_the_path_and_does_not_crash(tmp_path: Path) -> None:
    path = tmp_path / "session.json"
    path.write_text("{not json")
    with pytest.raises(SessionError, match="not valid JSON"):
        load(path)


def test_a_wrong_schema_version_says_how_to_recover(tmp_path: Path) -> None:
    path = tmp_path / "session.json"
    path.write_text(json.dumps({"version": 99, "vault": {}}))
    with pytest.raises(SessionError, match="localstack logout"):
        load(path)


def test_a_missing_vault_entry_is_an_error(tmp_path: Path) -> None:
    path = tmp_path / "session.json"
    path.write_text(json.dumps({"version": SCHEMA_VERSION, "vault": None}))
    with pytest.raises(SessionError, match="no vault credential"):
        load(path)


def test_a_malformed_entry_names_which_one(tmp_path: Path) -> None:
    path = tmp_path / "session.json"
    path.write_text(
        json.dumps({"version": SCHEMA_VERSION, "vault": {"token": "t"}}),
    )
    with pytest.raises(SessionError, match="`vault` is malformed"):
        load(path)


@pytest.mark.parametrize(
    ("minutes_left", "expected"),
    [
        (30, False),
        (6, False),
        (5, True),  # exactly at the skew boundary: already treated as gone
        (4, True),
        (0, True),
        (-10, True),
    ],
)
def test_is_stale_at_the_skew_boundary(minutes_left: int, expected: bool) -> None:
    assert credential(minutes_left).is_stale(NOW, DEFAULT_SKEW) is expected


def test_seconds_left_never_goes_negative() -> None:
    """An expired credential is zero seconds from useful, not minus six
    hundred, and a negative would read as a very long life somewhere."""
    assert credential(-10).seconds_left(NOW) == 0


def test_expires_at_is_absolute_and_computed_from_the_lease() -> None:
    assert expires_at(1800, NOW) == NOW + timedelta(seconds=1800)


def test_credential_lookup_by_service_name() -> None:
    session = a_session()
    assert session.credential("nomad") is session.nomad
    assert session.credential("nomad_manage") is session.nomad_manage
    assert session.credential("consul") is session.consul
    assert session.credential("vault") is session.vault
    assert session.credential("postgres") is None


def test_the_three_expiries_are_independent(tmp_path: Path) -> None:
    """One shared expiry would be wrong for at least two of the three: the
    brokered pair cap at an hour and the Vault token lasts weeks."""
    path = tmp_path / "session.json"
    save(a_session(), path)
    loaded = load(path)
    assert loaded is not None
    assert loaded.nomad is not None and loaded.consul is not None
    assert loaded.vault.expires_at != loaded.nomad.expires_at
    assert loaded.vault.expires_at > loaded.nomad.expires_at


def test_delete_reports_whether_there_was_anything(tmp_path: Path) -> None:
    path = tmp_path / "session.json"
    save(a_session(), path)
    assert delete(path) is True
    assert delete(path) is False


def test_save_sets_the_mode_at_creation_not_afterwards(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The headline security property, constrained rather than assumed.

    Opening 0644 and chmod-ing to 0600 afterwards leaves a window in which
    the whole session file is world readable, and the FINAL mode is 0600
    either way. Only the creation call tells them apart.
    """
    import os

    modes: list[int] = []
    real_open = os.open

    def recording_open(path: object, flags: int, mode: int = 0o777) -> int:
        modes.append(mode)
        return real_open(path, flags, mode)  # type: ignore[arg-type]

    monkeypatch.setattr(os, "open", recording_open)
    save(a_session(), tmp_path / "cfg" / "session.json")
    assert modes == [0o600], f"session file created with {[oct(m) for m in modes]}"


def test_a_crash_before_the_rename_leaves_the_old_session_intact(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Atomicity, exercised rather than asserted."""
    import os

    path = tmp_path / "cfg" / "session.json"
    save(a_session(), path)
    original = path.read_text()

    def boom(source: object, target: object) -> None:
        raise OSError("simulated crash before rename")

    monkeypatch.setattr(os, "replace", boom)
    with pytest.raises(OSError, match="simulated crash"):
        save(a_session(), path)

    assert path.read_text() == original
    assert [p.name for p in path.parent.iterdir()] == ["session.json"]


def test_a_leftover_temp_file_does_not_block_a_later_save(tmp_path: Path) -> None:
    """The hand-rolled `.<name>.<pid>` temp name collided.

    A temp file left behind by a SIGKILLed run blocked every later write with
    FileExistsError once that pid was recycled, which is a CLI that cannot log
    in until someone finds the file. `mkstemp` picks a name nothing holds.
    """
    import os

    path = tmp_path / "session.json"
    (tmp_path / f".session.json.{os.getpid()}").write_text("stale")
    save(a_session(), path)
    assert load(path) is not None
