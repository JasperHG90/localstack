"""`localstack deps` end to end, against a local release server.

Every test redirects `LOCALSTACK_HOME` into `tmp_path`, so nothing here
reads or writes the developer's real `~/.localstack`.
"""

import threading
from collections.abc import Iterator
from pathlib import Path

import pytest
from typer.testing import CliRunner

from localstack_cli.install import RELEASES_BASE
from localstack_cli.main import app
from localstack_cli.versions import GROUP_VARS_RELATIVE, REPO_ROOT_ENV, TOOLS
from tests.fixtures.releases import Handler, ReleaseServer, build_archive, fake_binary, publish

PINNED = {"consul": "9.8.7", "vault": "9.8.6", "nomad": "9.8.5"}
TARGET = "linux_arm64"

runner = CliRunner()


@pytest.fixture
def releases() -> Iterator[ReleaseServer]:
    server = ReleaseServer(("127.0.0.1", 0), Handler)
    server.files = {}
    server.requests = []
    for tool, version in PINNED.items():
        publish(
            server.files,
            tool,
            version,
            TARGET,
            build_archive(tool, fake_binary(tool, version)),
        )
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield server
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


@pytest.fixture
def repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A checkout stub plus a redirected home, with the platform fixed."""
    root = tmp_path / "repo"
    group_vars = root / GROUP_VARS_RELATIVE
    group_vars.parent.mkdir(parents=True)
    body = "\n".join(f"  {tool}: {version}-1" for tool, version in PINNED.items())
    group_vars.write_text(f"hashistack_versions:\n{body}\n")

    monkeypatch.setenv(REPO_ROOT_ENV, str(root))
    monkeypatch.setenv("LOCALSTACK_HOME", str(tmp_path / "home"))
    monkeypatch.setattr("platform.system", lambda: "Linux")
    monkeypatch.setattr("platform.machine", lambda: "aarch64")
    return root


@pytest.fixture
def local_releases(releases: ReleaseServer, monkeypatch: pytest.MonkeyPatch) -> ReleaseServer:
    """Point the installer at the local server instead of the real host."""
    host, port = releases.server_address[0], releases.server_address[1]
    monkeypatch.setattr("localstack_cli.install.RELEASES_BASE", f"http://{host!s}:{port}")
    return releases


def test_the_default_run_installs_nothing(
    tmp_path: Path, repo: Path, local_releases: ReleaseServer
) -> None:
    """Reporting is the default; installing is the side effect."""
    result = runner.invoke(app, ["deps"])

    assert not (tmp_path / "home" / "bin").exists()
    assert local_releases.requests == []
    assert "not installed" in result.output


def test_drift_exits_non_zero_and_names_both_versions(
    tmp_path: Path, repo: Path, local_releases: ReleaseServer
) -> None:
    binaries = tmp_path / "home" / "bin"
    binaries.mkdir(parents=True)
    stale = binaries / "nomad"
    stale.write_text(fake_binary("nomad", "0.0.1"))
    stale.chmod(0o755)

    result = runner.invoke(app, ["deps"])

    assert result.exit_code == 1
    assert "0.0.1" in result.output
    assert PINNED["nomad"] in result.output


def test_install_places_every_tool(
    tmp_path: Path, repo: Path, local_releases: ReleaseServer
) -> None:
    result = runner.invoke(app, ["deps", "--install"])

    assert result.exit_code == 0, result.output
    binaries = tmp_path / "home" / "bin"
    assert sorted(path.name for path in binaries.iterdir()) == sorted(TOOLS)
    assert "matches the pin" in result.output


def test_a_second_run_downloads_nothing(
    tmp_path: Path, repo: Path, local_releases: ReleaseServer
) -> None:
    """R2: this command gets re-run every time someone suspects their tools."""
    runner.invoke(app, ["deps", "--install"])
    local_releases.requests.clear()

    result = runner.invoke(app, ["deps", "--install"])

    assert result.exit_code == 0, result.output
    assert local_releases.requests == []
    assert result.output.count("already installed") == len(TOOLS)


def test_a_checksum_mismatch_fails_and_installs_nothing(
    tmp_path: Path, repo: Path, releases: ReleaseServer, monkeypatch: pytest.MonkeyPatch
) -> None:
    releases.files.clear()
    for tool, version in PINNED.items():
        publish(
            releases.files,
            tool,
            version,
            TARGET,
            build_archive(tool, fake_binary(tool, version)),
            checksum="0" * 64,
        )
    host, port = releases.server_address[0], releases.server_address[1]
    monkeypatch.setattr("localstack_cli.install.RELEASES_BASE", f"http://{host!s}:{port}")

    result = runner.invoke(app, ["deps", "--install"])

    assert result.exit_code == 1
    assert "checksum mismatch" in result.output
    binaries = tmp_path / "home" / "bin"
    assert not binaries.exists() or list(binaries.iterdir()) == []


def test_shims_are_not_written_without_the_flag(
    tmp_path: Path, repo: Path, local_releases: ReleaseServer
) -> None:
    """Q1: shadowing a binary is a change to the machine, so it is asked for."""
    result = runner.invoke(app, ["deps", "--install"])

    assert not (tmp_path / "home" / "shims").exists()
    assert "--with-shims" in result.output


def test_with_shims_writes_three_and_remove_shims_takes_them_back(
    tmp_path: Path, repo: Path, local_releases: ReleaseServer
) -> None:
    runner.invoke(app, ["deps", "--install"])
    binaries = tmp_path / "home" / "bin"
    before = {path.name: path.read_bytes() for path in binaries.iterdir()}

    written = runner.invoke(app, ["deps", "--with-shims"])
    shims = tmp_path / "home" / "shims"

    assert written.exit_code == 0, written.output
    assert sorted(path.name for path in shims.iterdir()) == sorted(TOOLS)

    removed = runner.invoke(app, ["deps", "--remove-shims"])

    assert removed.exit_code == 0, removed.output
    assert list(shims.iterdir()) == []
    for tool in TOOLS:
        assert tool in removed.output
    assert {path.name: path.read_bytes() for path in binaries.iterdir()} == before


def test_with_shims_refuses_over_missing_binaries(repo: Path) -> None:
    result = runner.invoke(app, ["deps", "--with-shims"])

    assert result.exit_code == 1
    assert "not installed" in result.output


def test_a_missing_repo_root_fails_loudly(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """R1a: never a built-in version list."""
    nowhere = tmp_path / "nowhere"
    nowhere.mkdir()
    monkeypatch.delenv(REPO_ROOT_ENV, raising=False)
    monkeypatch.setenv("LOCALSTACK_HOME", str(tmp_path / "home"))
    monkeypatch.setenv("LOCALSTACK_REPO_ROOT", str(nowhere))

    result = runner.invoke(app, ["deps"])

    assert result.exit_code == 1
    assert GROUP_VARS_RELATIVE in result.output


def test_the_repo_root_flag_is_honoured(
    tmp_path: Path, repo: Path, local_releases: ReleaseServer, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv(REPO_ROOT_ENV, raising=False)

    result = runner.invoke(app, ["deps", "--repo-root", str(repo)])

    assert PINNED["nomad"] in result.output


def test_the_report_goes_to_stdout(
    tmp_path: Path, repo: Path, local_releases: ReleaseServer
) -> None:
    """`localstack deps > report.txt` must not produce an empty file.

    Diagnostics belong on stderr; the report a developer asked for is the
    command's answer and belongs on stdout.
    """
    result = CliRunner().invoke(app, ["deps"])

    assert "not installed" in result.stdout


def test_an_install_that_does_not_settle_still_exits_non_zero(
    tmp_path: Path, repo: Path, releases: ReleaseServer, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An install that ran and left drift behind must not read as success."""
    releases.files.clear()
    for tool, version in PINNED.items():
        # The archive installs, but the binary answers with a different
        # version, so the run finishes with the pin still unmet.
        publish(
            releases.files,
            tool,
            version,
            TARGET,
            build_archive(tool, fake_binary(tool, "0.0.1")),
        )
    host, port = releases.server_address[0], releases.server_address[1]
    monkeypatch.setattr("localstack_cli.install.RELEASES_BASE", f"http://{host!s}:{port}")

    result = runner.invoke(app, ["deps", "--install"])

    assert result.exit_code == 1
    assert "0.0.1" in result.output


def test_the_command_is_registered_lazily() -> None:
    """D2's convention: no group, no eager import."""
    result = runner.invoke(app, ["--help"])

    assert "deps" in result.output


def test_the_real_release_host_is_the_default() -> None:
    """The local server is a test seam, not the shipped default."""
    assert RELEASES_BASE == "https://releases.hashicorp.com"
