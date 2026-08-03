"""`localstack deps`: the HashiCorp CLIs at the versions this cluster runs.

The versions come from `bootstrap/inventory/group_vars/all.yml`, the same
file the apt pin and the Ansible install task read. The command carries no
copy of them, and it fails rather than guess when it cannot find that file.

Three modes, in one command because they answer one question:

    localstack deps                 report what is installed against the pin
    localstack deps --install       fetch and place what does not match
    localstack deps --with-shims    also write the PATH shims
    localstack deps --remove-shims  take the shims back off

Reporting is the default because installing is the side effect. Someone who
suspects their toolchain runs `deps` to find out, and getting a download for
an answer is not what they asked for.
"""

from pathlib import Path

import typer

from localstack_cli.install import (
    InstallError,
    bin_dir,
    install_tool,
    installed_version,
    shims_dir,
)
from localstack_cli.platforms import PlatformError, current_platform
from localstack_cli.shims import TOKEN_VARS, ShimError, remove_shims, write_shims
from localstack_cli.versions import TOOLS, VersionError, resolve_repo_root, tool_versions

from ._common import fail, warn

app = typer.Typer()


def _report(pinned: dict[str, str], directory: Path) -> bool:
    """Print installed against pinned. True when everything matches.

    R8: drift the command cannot fix is still drift the developer needs to
    see, with both numbers, because silence recreates the skew this command
    exists to remove.
    """
    agreed = True
    for tool in TOOLS:
        found = installed_version(tool, directory=directory)
        want = pinned[tool]
        if found.version == want:
            typer.echo(f"  {tool:<7} {want}  (matches the pin)")
            continue
        agreed = False
        have = found.version or "not installed"
        typer.echo(f"  {tool:<7} {have}  (pinned: {want})")
    return agreed


@app.command()
def deps(
    install: bool = typer.Option(
        False,
        "--install",
        help="Download and install any tool that does not match the pin.",
    ),
    with_shims: bool = typer.Option(
        False,
        "--with-shims",
        help="Also write the nomad, consul and vault PATH shims.",
    ),
    remove_shims_flag: bool = typer.Option(
        False,
        "--remove-shims",
        help="Delete every shim. Leaves the installed binaries alone.",
    ),
    repo_root: Path | None = typer.Option(
        None,
        "--repo-root",
        help="The checkout holding bootstrap/inventory/group_vars/all.yml.",
    ),
) -> None:
    """Install the HashiCorp CLIs at the versions this cluster runs."""
    binaries = bin_dir()
    shims = shims_dir()

    if remove_shims_flag:
        removed = remove_shims(shims)
        if not removed:
            warn(f"no shims to remove in {shims}")
        for path in removed:
            warn(f"removed {path}")
        # Removal is the whole request. Doing an install alongside it would
        # be a side effect nobody asked for.
        return

    try:
        root = resolve_repo_root(explicit=repo_root)
        pinned = tool_versions(root)
        target = current_platform()
    except (VersionError, PlatformError) as error:
        raise fail(str(error)) from error

    warn(f"versions from {root / 'bootstrap/inventory/group_vars/all.yml'}")

    if install:
        for tool in TOOLS:
            found = installed_version(tool, directory=binaries)
            if found.version == pinned[tool]:
                warn(f"  {tool:<7} {pinned[tool]}  already installed")
                continue
            warn(f"  {tool:<7} installing {pinned[tool]} ...")
            try:
                install_tool(tool, pinned[tool], target, directory=binaries)
            except InstallError as error:
                raise fail(str(error)) from error

    agreed = _report(pinned, binaries)

    if with_shims:
        try:
            written = write_shims(sorted(TOKEN_VARS), binaries, shims)
        except ShimError as error:
            raise fail(str(error)) from error
        for path in written:
            warn(f"wrote {path}")
        warn(f"put {shims} before {binaries} on PATH, and both before the system.")
    elif not (shims.is_dir() and any(shims.iterdir())):
        # Q1: shims are opt-in, so their absence has to be stated. The
        # accepted cost of opt-in is hitting "why does `nomad` not see my
        # login" once, and this line is what keeps it to once.
        warn(f"no shims installed in {shims}. A bare nomad, consul or vault")
        warn("will not see a `localstack login` session. Add them with --with-shims.")

    if not agreed:
        # Drift and agreement must not look the same to a script. This holds
        # after `--install` too: an install that ran and left the versions
        # still disagreeing is exactly the case a zero exit would hide.
        raise typer.Exit(1)
