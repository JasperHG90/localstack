"""Fetch a pinned HashiCorp CLI, verify it, and put it under the user's home.

Three rules shape this module.

Verify before unpacking (R3). This CLI exists to handle credentials; putting
an unchecked binary on the developer's PATH would make it the attack it is
meant to prevent. The archive is read into memory, hashed, and compared
against the published `SHA256SUMS` before anything is written to disk.

Write only `$LOCALSTACK_HOME/bin` (R4). No `sudo`, no `/usr/bin`, and never
the shims directory, which `shims.py` owns alone.

Do nothing when there is nothing to do (R2). `deps` gets re-run every time
someone suspects their toolchain, so a re-run that silently refetches wastes
time and hides whether anything was wrong.
"""

import hashlib
import io
import os
import re
import subprocess
import zipfile
from dataclasses import dataclass
from pathlib import Path
from urllib.request import Request, urlopen

RELEASES_BASE = "https://releases.hashicorp.com"
TIMEOUT_SECONDS = 60

LOCALSTACK_HOME_ENV = "LOCALSTACK_HOME"
DEFAULT_HOME = "~/.localstack"

# Every one of these prints `<Tool> vX.Y.Z` on the first line of `version`.
VERSION_PATTERN = re.compile(r"v(\d+\.\d+\.\d+)")


class InstallError(RuntimeError):
    """A download, a checksum, or an install failed."""


def home() -> Path:
    """`$LOCALSTACK_HOME`, or `~/.localstack`.

    One variable with two jobs: it keeps the paths out of the code as
    literals, and it is the seam a test uses to redirect the whole install
    into `tmp_path`.
    """
    return Path(os.environ.get(LOCALSTACK_HOME_ENV) or DEFAULT_HOME).expanduser()


def bin_dir() -> Path:
    """Where the pinned real binaries live. Nothing else writes here."""
    return home() / "bin"


def shims_dir() -> Path:
    """Where the shims live. `shims.py` is the only writer."""
    return home() / "shims"


@dataclass(frozen=True)
class Installed:
    """What is on disk for one tool right now."""

    tool: str
    path: Path
    version: str | None

    @property
    def present(self) -> bool:
        return self.version is not None


def installed_version(tool: str, directory: Path | None = None) -> Installed:
    """Ask the installed binary its own version.

    Reading the binary rather than a state file is the point: a state file
    would keep reporting the version it recorded after someone dropped a
    different build in place, which is the drift R8 exists to report.
    """
    path = (directory or bin_dir()) / tool
    if not path.is_file():
        return Installed(tool=tool, path=path, version=None)
    try:
        result = subprocess.run(
            [str(path), "version"],
            capture_output=True,
            text=True,
            timeout=30,
        )
    except (OSError, subprocess.SubprocessError):
        return Installed(tool=tool, path=path, version=None)

    found = VERSION_PATTERN.search(result.stdout.splitlines()[0] if result.stdout else "")
    return Installed(tool=tool, path=path, version=found.group(1) if found else None)


def _fetch(url: str) -> bytes:
    request = Request(url, method="GET")
    try:
        with urlopen(request, timeout=TIMEOUT_SECONDS) as response:  # noqa: S310
            body: bytes = response.read()
    except OSError as error:
        raise InstallError(f"cannot fetch {url}: {error}") from error
    return body


def published_checksum(base: str | None, tool: str, version: str, archive: str) -> str:
    """The expected sha256 for one archive, from the published SHA256SUMS."""
    base = base or RELEASES_BASE
    url = f"{base}/{tool}/{version}/{tool}_{version}_SHA256SUMS"
    for line in _fetch(url).decode().splitlines():
        digest, _, name = line.partition(" ")
        if name.strip() == archive:
            return digest.strip()
    raise InstallError(f"{url} lists no checksum for {archive}")


def _extract(archive_bytes: bytes, tool: str) -> bytes:
    with zipfile.ZipFile(io.BytesIO(archive_bytes)) as bundle:
        try:
            return bundle.read(tool)
        except KeyError as error:
            raise InstallError(f"the {tool} archive holds no {tool} entry") from error


def install_tool(
    tool: str,
    version: str,
    target: str,
    directory: Path | None = None,
    base: str | None = None,
) -> Path:
    """Download, verify, unpack and place one binary. Returns its path.

    Nothing touches the filesystem until the checksum matches, so a mismatch
    cannot leave a partial file behind.

    `base` defaults to `RELEASES_BASE` at CALL time, not at import time. A
    default argument would freeze the value into the signature, and then a
    test redirecting the module attribute would still reach the real host,
    which is how an offline suite quietly starts using the network.
    """
    from localstack_cli.platforms import artifact_name

    base = base or RELEASES_BASE
    archive = artifact_name(tool, version, target)
    expected = published_checksum(base, tool, version, archive)
    archive_bytes = _fetch(f"{base}/{tool}/{version}/{archive}")

    actual = hashlib.sha256(archive_bytes).hexdigest()
    if actual != expected:
        raise InstallError(
            f"checksum mismatch for {archive}: published {expected}, downloaded {actual}. "
            "Nothing was installed."
        )

    binary = _extract(archive_bytes, tool)
    into = directory or bin_dir()
    into.mkdir(parents=True, exist_ok=True)
    destination = into / tool

    # Write beside the target and rename, so a crash mid-write cannot leave a
    # half-written binary on PATH. `os.replace` is atomic within a filesystem.
    staged = into / f".{tool}.incoming"
    staged.write_bytes(binary)
    staged.chmod(0o755)
    os.replace(staged, destination)
    return destination
