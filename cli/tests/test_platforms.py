"""`deps` runs on the developer's machine, so it resolves its own platform."""

import pytest

from localstack_cli.platforms import PlatformError, artifact_name, current_platform


@pytest.mark.parametrize(
    ("system", "machine", "expected"),
    [
        ("Linux", "aarch64", "linux_arm64"),
        ("Linux", "arm64", "linux_arm64"),
        ("Linux", "x86_64", "linux_amd64"),
        ("Linux", "amd64", "linux_amd64"),
        ("Darwin", "arm64", "darwin_arm64"),
        ("Darwin", "x86_64", "darwin_amd64"),
    ],
)
def test_platform_is_resolved(
    monkeypatch: pytest.MonkeyPatch, system: str, machine: str, expected: str
) -> None:
    monkeypatch.setattr("platform.system", lambda: system)
    monkeypatch.setattr("platform.machine", lambda: machine)

    assert current_platform() == expected


@pytest.mark.parametrize(
    ("system", "machine"),
    [("Windows", "AMD64"), ("Linux", "riscv64"), ("Plan9", "x86_64")],
)
def test_an_unsupported_platform_is_named(
    monkeypatch: pytest.MonkeyPatch, system: str, machine: str
) -> None:
    monkeypatch.setattr("platform.system", lambda: system)
    monkeypatch.setattr("platform.machine", lambda: machine)

    with pytest.raises(PlatformError, match=system.lower()):
        current_platform()


def test_artifact_name_matches_the_published_archive() -> None:
    """The shape confirmed against `releases.hashicorp.com` on 2026-08-03."""
    assert artifact_name("nomad", "9.8.5", "linux_arm64") == "nomad_9.8.5_linux_arm64.zip"
