"""The version resolver reads `group_vars/all.yml` and nothing else."""

import re
import subprocess
from pathlib import Path

import pytest

from localstack_cli.versions import (
    GROUP_VARS_RELATIVE,
    REPO_ROOT_ENV,
    VersionError,
    resolve_repo_root,
    strip_revision,
    tool_versions,
)

# Not the pinned versions: a literal here would be the second source of truth
# R1 forbids, and row 1's grep would rightly fail on it if it were under
# `cli/src`. These are invented values, so a test that passes proves the
# resolver followed the file rather than a memory of the real pin.
FIXTURE_VERSIONS = {"consul": "9.8.7-1", "vault": "9.8.6-1", "nomad": "9.8.5-1"}


def write_repo(root: Path, versions: dict[str, str]) -> Path:
    """Lay out just enough of a checkout for the resolver to find."""
    group_vars = root / GROUP_VARS_RELATIVE
    group_vars.parent.mkdir(parents=True, exist_ok=True)
    body = "\n".join(f"  {tool}: {value}" for tool, value in versions.items())
    group_vars.write_text(f"hashistack_versions:\n{body}\n  nomad-driver-podman: 0.6.4-1\n")
    return root


def test_versions_follow_the_file(tmp_path: Path) -> None:
    root = write_repo(tmp_path / "repo", FIXTURE_VERSIONS)

    assert tool_versions(root) == {"consul": "9.8.7", "vault": "9.8.6", "nomad": "9.8.5"}


def test_editing_the_file_moves_the_resolved_version(tmp_path: Path) -> None:
    root = write_repo(tmp_path / "repo", FIXTURE_VERSIONS)
    assert tool_versions(root)["nomad"] == "9.8.5"

    write_repo(root, {**FIXTURE_VERSIONS, "nomad": "9.9.9-1"})

    assert tool_versions(root)["nomad"] == "9.9.9"


def test_the_driver_plugin_is_not_a_cli(tmp_path: Path) -> None:
    """`nomad-driver-podman` is pinned in the same file but has no CLI."""
    root = write_repo(tmp_path / "repo", FIXTURE_VERSIONS)

    assert "nomad-driver-podman" not in tool_versions(root)


@pytest.mark.parametrize(
    ("declared", "expected"),
    [("2.0.4-1", "2.0.4"), ("2.0.4", "2.0.4"), ("1.10.0-3", "1.10.0")],
)
def test_strip_revision(declared: str, expected: str) -> None:
    assert strip_revision(declared) == expected


def test_a_missing_tool_is_named(tmp_path: Path) -> None:
    root = write_repo(tmp_path / "repo", {"consul": "9.8.7-1", "vault": "9.8.6-1"})

    with pytest.raises(VersionError, match="nomad"):
        tool_versions(root)


def test_a_malformed_file_names_the_key(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    group_vars = root / GROUP_VARS_RELATIVE
    group_vars.parent.mkdir(parents=True)
    group_vars.write_text("something_else: 1\n")

    with pytest.raises(VersionError, match="hashistack_versions"):
        tool_versions(root)


def test_explicit_root_wins(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    wanted = write_repo(tmp_path / "wanted", FIXTURE_VERSIONS)
    other = write_repo(tmp_path / "other", {**FIXTURE_VERSIONS, "nomad": "0.0.1-1"})
    monkeypatch.setenv(REPO_ROOT_ENV, str(other))

    assert resolve_repo_root(explicit=wanted) == wanted


def test_the_environment_variable_is_used_when_no_flag_is_given(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = write_repo(tmp_path / "repo", FIXTURE_VERSIONS)
    monkeypatch.setenv(REPO_ROOT_ENV, str(root))
    monkeypatch.chdir(tmp_path)

    assert resolve_repo_root(walk_from=tmp_path) == root


def test_the_working_directory_is_walked_up(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = write_repo(tmp_path / "repo", FIXTURE_VERSIONS)
    deep = root / "deployments" / "infrastructure"
    deep.mkdir(parents=True)
    monkeypatch.delenv(REPO_ROOT_ENV, raising=False)
    monkeypatch.chdir(deep)

    # `walk_from` points nowhere useful, so a pass here is the cwd walk.
    assert resolve_repo_root(walk_from=tmp_path / "elsewhere") == root


def test_the_module_location_is_the_last_resort(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = write_repo(tmp_path / "repo", FIXTURE_VERSIONS)
    outside = tmp_path / "outside"
    outside.mkdir()
    monkeypatch.delenv(REPO_ROOT_ENV, raising=False)
    monkeypatch.chdir(outside)

    assert resolve_repo_root(walk_from=root / "cli" / "src" / "localstack_cli") == root


def test_the_default_walk_start_finds_this_checkout(monkeypatch: pytest.MonkeyPatch) -> None:
    """The seam has a real default: the module's own location."""
    monkeypatch.delenv(REPO_ROOT_ENV, raising=False)

    root = resolve_repo_root()

    assert (root / GROUP_VARS_RELATIVE).is_file()


def test_no_root_anywhere_fails_loudly(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """R1a: never a built-in version list, always a message you can act on."""
    nowhere = tmp_path / "nowhere"
    nowhere.mkdir()
    monkeypatch.delenv(REPO_ROOT_ENV, raising=False)
    monkeypatch.chdir(nowhere)

    with pytest.raises(VersionError) as caught:
        resolve_repo_root(walk_from=nowhere)

    message = str(caught.value)
    assert GROUP_VARS_RELATIVE in message
    assert "--repo-root" in message
    assert REPO_ROOT_ENV in message
    assert str(nowhere) in message


def source_lines_matching(pattern: re.Pattern[str]) -> list[str]:
    """Every `cli/src` line matching `pattern`, as `path:line: text`.

    Scoped to `cli/src`. `cli/tests` is where a fixture legitimately writes a
    version down, and a check covering it would fail for doing the right
    thing.
    """
    source = Path(__file__).resolve().parents[1] / "src"
    return [
        f"{path.relative_to(source)}:{number}: {line.strip()}"
        for path in sorted(source.rglob("*.py"))
        for number, line in enumerate(path.read_text().splitlines(), start=1)
        if pattern.search(line)
    ]


def test_source_carries_no_hashistack_version_literal() -> None:
    """Row 1's scorer verbatim: `grep -rnE '2\\.0\\.[0-9]' cli/src`."""
    assert source_lines_matching(re.compile(r"2\.0\.[0-9]")) == []


def test_source_carries_no_currently_pinned_version() -> None:
    """The same rule, against whatever the file declares today.

    Row 1's grep is pinned to the `2.0.x` series the cluster runs now. This
    check reads `group_vars/all.yml` and looks for those exact strings, so it
    keeps working after the pin moves off that series.
    """
    declared = tool_versions(resolve_repo_root())
    pattern = re.compile("|".join(re.escape(value) for value in sorted(set(declared.values()))))

    assert source_lines_matching(pattern) == []


def test_the_repo_file_still_declares_every_tool() -> None:
    """The resolver's contract against the real file, not a fixture.

    This is the test R1 asks for: it goes red when `group_vars/all.yml` stops
    carrying a tool the CLI installs, which is how the CLI and the cluster
    would drift while both look pinned.
    """
    versions = tool_versions(resolve_repo_root())

    assert sorted(versions) == ["consul", "nomad", "vault"]
    for tool, value in versions.items():
        assert re.fullmatch(r"\d+\.\d+\.\d+", value), f"{tool} resolved to {value!r}"


def test_the_ansible_pin_reads_the_same_file() -> None:
    """P3, as a test: nothing else declares `hashistack_versions`.

    A second declaration is how the developer's toolchain and the cluster
    drift apart while both look pinned.
    """
    root = resolve_repo_root()
    found = subprocess.run(
        ["git", "grep", "-l", "hashistack_versions"],
        cwd=root,
        capture_output=True,
        text=True,
        check=True,
    )
    declaring = {
        line
        for line in found.stdout.split()
        if line.endswith(("all.yml", "all.yaml")) and "group_vars" in line
    }

    assert declaring == {GROUP_VARS_RELATIVE}
