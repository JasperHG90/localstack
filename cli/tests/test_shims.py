"""The shims are executed, not just read.

Every row here runs the shim as a real process against a fixture binary, so
what is scored is the behavior a developer gets rather than the text of a
template.

Two setup rules, and both are load-bearing. `LOCALSTACK_HOME` points into
`tmp_path`, so nothing reads or writes the developer's real `~/.localstack`.
And the ambient token variables are deleted: this devcontainer exports
`NOMAD_TOKEN`, `VAULT_TOKEN` and `CONSUL_TOKEN` live, so a test that leaves
one in place cannot tell a token the shim injected from one the shell had.
"""

import os
import subprocess
from pathlib import Path

import pytest

from localstack_cli.shims import TOKEN_VARS, ShimError, remove_shims, render, write_shims

TOOLS = sorted(TOKEN_VARS)
AMBIENT = ("NOMAD_TOKEN", "VAULT_TOKEN", "CONSUL_HTTP_TOKEN", "CONSUL_TOKEN")

# Records the variable it was called with, plus one line per call, so a run
# can be checked for both the injected token and the absence of recursion.
COUNTER = """#!/bin/sh
echo "call" >> "{log}"
echo "{variable}=${{{variable}-<unset>}}"
"""

# Stands in for `localstack token <tool>` on PATH.
BROKER = """#!/bin/sh
{body}
"""


@pytest.fixture
def layout(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("LOCALSTACK_HOME", str(tmp_path / "home"))
    for name in AMBIENT:
        monkeypatch.delenv(name, raising=False)
    return tmp_path


def make_binaries(root: Path, log: Path) -> Path:
    """A counter script per tool, standing in for the pinned binaries."""
    binaries = root / "home" / "bin"
    binaries.mkdir(parents=True)
    for tool in TOOLS:
        path = binaries / tool
        path.write_text(COUNTER.format(log=log, variable=TOKEN_VARS[tool]))
        path.chmod(0o755)
    return binaries


def make_broker(root: Path, body: str) -> Path:
    """A directory holding a fake `localstack`, to be put on PATH."""
    directory = root / "broker"
    directory.mkdir(exist_ok=True)
    path = directory / "localstack"
    path.write_text(BROKER.format(body=body))
    path.chmod(0o755)
    return directory


def run_shim(
    tool: str, shims: Path, binaries: Path, broker: Path
) -> subprocess.CompletedProcess[str]:
    """Run the shim with PATH ordered shims, bin, broker, then the system.

    The ordering is the point of row 8: a shim that resolves its tool through
    PATH re-finds itself, and it only does so on a correctly configured
    machine, so a test that forgets this ordering passes a broken shim.
    """
    environment = dict(os.environ)
    for name in AMBIENT:
        environment.pop(name, None)
    environment["PATH"] = os.pathsep.join(
        [str(shims), str(binaries), str(broker), "/usr/bin", "/bin"]
    )
    return subprocess.run(
        [tool, "version"],
        capture_output=True,
        text=True,
        timeout=30,
        env=environment,
    )


def test_the_template_never_names_the_consul_token_file() -> None:
    """D2 R12: exporting it would break `consul` outright."""
    bodies = "".join(render(tool, Path("/anywhere") / tool) for tool in TOOLS)

    assert "CONSUL_HTTP_TOKEN_FILE" not in bodies


def test_each_shim_names_its_own_variable() -> None:
    for tool, variable in TOKEN_VARS.items():
        body = render(tool, Path("/anywhere") / tool)
        assert f'exec env {variable}="$T"' in body


def test_the_binary_path_is_an_absolute_literal(layout: Path) -> None:
    """R7: nothing unexpanded, nothing resolved through PATH."""
    body = render("nomad", layout / "home" / "bin" / "nomad")

    assert f'REAL="{layout}/home/bin/nomad"' in body
    assert "$HOME" not in body
    assert "$LOCALSTACK_HOME" not in body


def test_a_shim_is_refused_over_a_missing_binary(layout: Path) -> None:
    """A shim pointing nowhere is a dead command."""
    with pytest.raises(ShimError, match="not installed"):
        write_shims(TOOLS, layout / "home" / "bin", layout / "home" / "shims")


def test_with_shims_writes_exactly_three_files(layout: Path) -> None:
    binaries = make_binaries(layout, layout / "calls.log")
    shims = layout / "home" / "shims"

    write_shims(TOOLS, binaries, shims)

    assert sorted(path.name for path in shims.iterdir()) == TOOLS
    for path in shims.iterdir():
        assert path.stat().st_mode & 0o777 == 0o755


def test_removal_clears_the_shims_and_leaves_the_binaries(layout: Path) -> None:
    """Row 9: reversal must not take the real tooling with it."""
    binaries = make_binaries(layout, layout / "calls.log")
    shims = layout / "home" / "shims"
    write_shims(TOOLS, binaries, shims)
    before = {path.name: (path.read_bytes(), path.stat().st_mode) for path in binaries.iterdir()}

    removed = remove_shims(shims)

    assert sorted(path.name for path in removed) == TOOLS
    assert list(shims.iterdir()) == []
    after = {path.name: (path.read_bytes(), path.stat().st_mode) for path in binaries.iterdir()}
    assert after == before
    for path in binaries.iterdir():
        assert path.stat().st_mode & 0o111


def test_removing_nothing_is_not_an_error(layout: Path) -> None:
    assert remove_shims(layout / "home" / "shims") == []


@pytest.mark.parametrize("tool", TOOLS)
def test_the_shim_injects_the_token_and_calls_the_pinned_binary_once(
    layout: Path, tool: str
) -> None:
    """Row 8: exactly one call, at the pinned absolute path, no recursion."""
    log = layout / "calls.log"
    binaries = make_binaries(layout, log)
    shims = layout / "home" / "shims"
    write_shims(TOOLS, binaries, shims)
    broker = make_broker(layout, 'echo "s.token-for-$2"')

    result = run_shim(tool, shims, binaries, broker)

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == f"{TOKEN_VARS[tool]}=s.token-for-{tool}"
    assert log.read_text().count("call") == 1


@pytest.mark.parametrize("tool", TOOLS)
def test_the_shim_falls_through_when_the_broker_fails(layout: Path, tool: str) -> None:
    """Row 7, first case: a CLI bug must not become a dead command."""
    log = layout / "calls.log"
    binaries = make_binaries(layout, log)
    shims = layout / "home" / "shims"
    write_shims(TOOLS, binaries, shims)
    broker = make_broker(layout, 'echo "no session" >&2; exit 1')

    result = run_shim(tool, shims, binaries, broker)

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == f"{TOKEN_VARS[tool]}=<unset>"
    assert log.read_text().count("call") == 1


@pytest.mark.parametrize("tool", TOOLS)
def test_the_shim_falls_through_on_an_empty_token(layout: Path, tool: str) -> None:
    """Row 7, second case: unset, never set to the empty string.

    An empty export clears a token the developer already had, which looks
    like success and is worse than an outright failure.
    """
    log = layout / "calls.log"
    binaries = make_binaries(layout, log)
    shims = layout / "home" / "shims"
    write_shims(TOOLS, binaries, shims)
    broker = make_broker(layout, "exit 0")

    result = run_shim(tool, shims, binaries, broker)

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == f"{TOKEN_VARS[tool]}=<unset>"
    assert log.read_text().count("call") == 1


@pytest.mark.parametrize("tool", TOOLS)
def test_an_ambient_token_survives_a_broker_that_gives_nothing(layout: Path, tool: str) -> None:
    """The reason empty must not be exported, stated as a run."""
    log = layout / "calls.log"
    binaries = make_binaries(layout, log)
    shims = layout / "home" / "shims"
    write_shims(TOOLS, binaries, shims)
    broker = make_broker(layout, "exit 0")

    environment = dict(os.environ)
    for name in AMBIENT:
        environment.pop(name, None)
    environment[TOKEN_VARS[tool]] = "s.already-had-one"
    environment["PATH"] = os.pathsep.join(
        [str(shims), str(binaries), str(broker), "/usr/bin", "/bin"]
    )
    result = subprocess.run(
        [tool, "version"], capture_output=True, text=True, timeout=30, env=environment
    )

    assert result.stdout.strip() == f"{TOKEN_VARS[tool]}=s.already-had-one"


def test_the_shim_does_not_reach_a_system_binary(layout: Path) -> None:
    """Row 8's second failure: a shim over `/usr/bin` undoes the pin.

    The pinned binary is the only thing the shim may run, so pointing the
    shims directory at a home with no `bin` entry must fail rather than fall
    back to whatever apt left on the machine.
    """
    binaries = make_binaries(layout, layout / "calls.log")
    body = render("nomad", binaries / "nomad")
    # The shebang is `/usr/bin/env`, which is how the script starts at all.
    # What must not appear is a system path as the exec target, or any
    # attempt to find the tool through PATH.
    after_shebang = body.split("\n", 1)[1]

    code = [
        line for line in after_shebang.splitlines() if line.strip() and not line.startswith("#")
    ]

    assert not any("/usr/bin" in line or "/usr/local/bin" in line for line in code)
    assert not any("command -v" in line or "which " in line for line in code)
    # The one exec target is the pinned binary, named in full.
    assert f'REAL="{binaries / "nomad"}"' in code
