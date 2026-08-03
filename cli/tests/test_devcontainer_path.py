"""The devcontainer's PATH is part of this feature, so it is asserted here.

The shims only work if their directory comes first. Get the order wrong and
every other check still reads green while a bare `nomad` runs whatever apt
left behind, which is the exact skew `deps` exists to remove.
"""

import re
from pathlib import Path

from localstack_cli.install import DEFAULT_HOME
from localstack_cli.versions import resolve_repo_root

PATH_LINE = re.compile(r'^ENV PATH="(?P<value>.*)"$', re.MULTILINE)


def devcontainer() -> Path:
    return resolve_repo_root() / ".devcontainer"


def test_shims_come_before_binaries_and_both_before_the_system() -> None:
    dockerfile = (devcontainer() / "Dockerfile").read_text()
    found = PATH_LINE.search(dockerfile)
    assert found is not None, "the Dockerfile sets no ENV PATH"

    entries = found.group("value").split(":")
    home = DEFAULT_HOME.replace("~", "$HOME")
    shims = entries.index(f"{home}/shims")
    binaries = entries.index(f"{home}/bin")

    assert shims < binaries
    assert binaries < entries.index("$PATH")


def test_the_devcontainer_never_names_the_consul_token_file() -> None:
    """D2 R12: the file outranks the variable, and nothing writes it.

    Exporting it would break `consul` outright on the next container rebuild
    rather than do nothing.
    """
    offenders = [
        path.name
        for path in sorted(devcontainer().iterdir())
        if path.is_file() and "CONSUL_HTTP_TOKEN_FILE" in path.read_text(errors="ignore")
    ]

    assert offenders == []


def test_the_container_asks_for_the_shims() -> None:
    """Q1: opt-in on a laptop, passed at build here."""
    bootstrap = (devcontainer() / "bootstrap.sh").read_text()

    assert "localstack deps --install --with-shims" in bootstrap
