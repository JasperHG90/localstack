"""Which release archive this machine needs.

Plural so it cannot be mistaken for the stdlib `platform` module it imports.

The devcontainer is `linux_arm64` and the cluster spans both architectures,
but `deps` installs onto the developer's machine, which may be a Mac. So this
resolves rather than assumes.
"""

import platform

# HashiCorp publishes one archive per OS and architecture, named with its own
# vocabulary. `uname` reports several spellings for the same architecture.
SYSTEMS = {"linux": "linux", "darwin": "darwin"}
MACHINES = {
    "aarch64": "arm64",
    "arm64": "arm64",
    "x86_64": "amd64",
    "amd64": "amd64",
}


class PlatformError(RuntimeError):
    """This machine has no published HashiCorp archive."""


def current_platform() -> str:
    """The `<os>_<arch>` fragment of the release artifact name."""
    system = platform.system().lower()
    machine = platform.machine().lower()

    if system not in SYSTEMS:
        raise PlatformError(
            f"no HashiCorp release archives for {system}. Supported: {', '.join(sorted(SYSTEMS))}."
        )
    if machine not in MACHINES:
        raise PlatformError(
            f"unsupported architecture {machine} on {system}. "
            f"Supported: {', '.join(sorted(MACHINES))}."
        )
    return f"{SYSTEMS[system]}_{MACHINES[machine]}"


def artifact_name(tool: str, version: str, target: str) -> str:
    """The published archive filename, e.g. `nomad_1.2.3_linux_arm64.zip`."""
    return f"{tool}_{version}_{target}.zip"
