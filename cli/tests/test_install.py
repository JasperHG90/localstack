"""Nothing lands on PATH that was not verified first."""

import threading
from collections.abc import Iterator
from pathlib import Path

import pytest

from localstack_cli.install import (
    InstallError,
    bin_dir,
    home,
    install_tool,
    installed_version,
    published_checksum,
    shims_dir,
)
from tests.fixtures.releases import Handler, ReleaseServer, build_archive, fake_binary, publish

TOOL = "nomad"
VERSION = "9.8.5"
TARGET = "linux_arm64"


@pytest.fixture
def releases() -> Iterator[ReleaseServer]:
    server = ReleaseServer(("127.0.0.1", 0), Handler)
    server.files = {}
    server.requests = []
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield server
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


@pytest.fixture
def base(releases: ReleaseServer) -> str:
    host, port = releases.server_address[0], releases.server_address[1]
    return f"http://{host!s}:{port}"


def test_home_follows_the_environment(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LOCALSTACK_HOME", str(tmp_path / "elsewhere"))

    assert home() == tmp_path / "elsewhere"
    assert bin_dir() == tmp_path / "elsewhere" / "bin"
    assert shims_dir() == tmp_path / "elsewhere" / "shims"


def test_binaries_and_shims_are_different_directories(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Share one and `--with-shims` overwrites the pinned binary."""
    monkeypatch.setenv("LOCALSTACK_HOME", str(tmp_path))

    assert bin_dir() != shims_dir()


def test_a_verified_download_is_installed_and_executable(
    tmp_path: Path, releases: ReleaseServer, base: str
) -> None:
    archive = build_archive(TOOL, fake_binary(TOOL, VERSION))
    publish(releases.files, TOOL, VERSION, TARGET, archive)
    into = tmp_path / "bin"

    path = install_tool(TOOL, VERSION, TARGET, directory=into, base=base)

    assert path == into / TOOL
    assert path.stat().st_mode & 0o111
    assert installed_version(TOOL, directory=into).version == VERSION


def test_a_checksum_mismatch_installs_nothing(
    tmp_path: Path, releases: ReleaseServer, base: str
) -> None:
    archive = build_archive(TOOL, fake_binary(TOOL, VERSION))
    publish(releases.files, TOOL, VERSION, TARGET, archive, checksum="0" * 64)
    into = tmp_path / "bin"

    with pytest.raises(InstallError, match="checksum mismatch"):
        install_tool(TOOL, VERSION, TARGET, directory=into, base=base)

    # Not just "the binary is absent": a partial or staged file left behind is
    # the same supply-chain hole one rename away.
    assert not into.exists() or list(into.iterdir()) == []


def test_an_unpublished_checksum_is_refused(releases: ReleaseServer, base: str) -> None:
    releases.files[f"/{TOOL}/{VERSION}/{TOOL}_{VERSION}_SHA256SUMS"] = b"abc  other.zip\n"

    with pytest.raises(InstallError, match="no checksum"):
        published_checksum(base, TOOL, VERSION, f"{TOOL}_{VERSION}_{TARGET}.zip")


def test_an_unreachable_release_server_is_reported(tmp_path: Path) -> None:
    with pytest.raises(InstallError, match="cannot fetch"):
        install_tool(TOOL, VERSION, TARGET, directory=tmp_path, base="http://127.0.0.1:1")


def test_an_archive_without_the_binary_is_refused(
    tmp_path: Path, releases: ReleaseServer, base: str
) -> None:
    archive = build_archive("something-else", "#!/bin/sh\n")
    publish(releases.files, TOOL, VERSION, TARGET, archive)

    with pytest.raises(InstallError, match="holds no nomad entry"):
        install_tool(TOOL, VERSION, TARGET, directory=tmp_path, base=base)


def test_the_checksum_is_read_before_the_archive_is_fetched(
    tmp_path: Path, releases: ReleaseServer, base: str
) -> None:
    """R3: verify before unpacking, which means fetch the sums first."""
    archive = build_archive(TOOL, fake_binary(TOOL, VERSION))
    publish(releases.files, TOOL, VERSION, TARGET, archive)

    install_tool(TOOL, VERSION, TARGET, directory=tmp_path, base=base)

    assert releases.requests[0].endswith("SHA256SUMS")


def test_installing_over_a_wrong_version_replaces_it(
    tmp_path: Path, releases: ReleaseServer, base: str
) -> None:
    into = tmp_path / "bin"
    into.mkdir()
    stale = into / TOOL
    stale.write_text(fake_binary(TOOL, "0.0.1"))
    stale.chmod(0o755)
    publish(releases.files, TOOL, VERSION, TARGET, build_archive(TOOL, fake_binary(TOOL, VERSION)))

    install_tool(TOOL, VERSION, TARGET, directory=into, base=base)

    assert installed_version(TOOL, directory=into).version == VERSION
    assert list(into.iterdir()) == [into / TOOL]


def test_a_missing_binary_reports_no_version(tmp_path: Path) -> None:
    found = installed_version(TOOL, directory=tmp_path)

    assert not found.present
    assert found.version is None


def test_an_unrunnable_binary_reports_no_version(tmp_path: Path) -> None:
    """A file that is not executable must read as absent, not crash `deps`."""
    (tmp_path / TOOL).write_text("not a binary")

    assert installed_version(TOOL, directory=tmp_path).version is None
