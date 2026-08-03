"""What version of each HashiCorp CLI this cluster runs.

The answer lives in `bootstrap/inventory/group_vars/all.yml`, which the apt
pin and the Ansible install task already read. This module reads the same
file. It does not carry a copy of the numbers: a second list is how the
developer's toolchain and the cluster drift apart while both look pinned.

Finding that file is the awkward part. It is a repo file, and an installed
console script runs from anywhere, so the path cannot be assumed. Hence the
four-step search in `resolve_repo_root`, and hence the failure when all four
miss: a built-in fallback list would be exactly the second source of truth
this module exists to prevent, and it would fail silently.
"""

import os
from pathlib import Path

import yaml

GROUP_VARS_RELATIVE = "bootstrap/inventory/group_vars/all.yml"
REPO_ROOT_ENV = "LOCALSTACK_REPO_ROOT"
VERSIONS_KEY = "hashistack_versions"

# The three tools with a CLI a developer runs. `nomad-driver-podman` is
# pinned in the same file but is a server plugin, so it is deliberately not
# here.
TOOLS = ("consul", "nomad", "vault")


class VersionError(RuntimeError):
    """The repo root, the file, or a version inside it could not be found."""


def strip_revision(declared: str) -> str:
    """`X.Y.Z-1` to `X.Y.Z`.

    The example is deliberately not a real version. A literal here would read
    as a carried pin, and the check that enforces R1 is a grep.

    The file carries a Debian package revision because apt needs one. The
    upstream release artifacts do not. This is the only place that transform
    happens; written twice is how it diverges.
    """
    return declared.split("-", 1)[0]


def _candidates(start: Path) -> list[Path]:
    """`start` and every directory above it."""
    start = start.resolve()
    return [start, *start.parents]


def resolve_repo_root(
    explicit: Path | None = None,
    walk_from: Path | None = None,
) -> Path:
    """Locate the checkout holding `group_vars/all.yml`. First hit wins.

    1. `explicit`, from `deps --repo-root`.
    2. `LOCALSTACK_REPO_ROOT`.
    3. A walk up from the working directory.
    4. A walk up from `walk_from`, this module's own location by default.

    Step 4 is what makes an editable install work from any directory. It is
    also why `walk_from` is a parameter: inside a checkout the module always
    sits under the repo root, so step 4 always succeeds and the failure
    branch is unreachable. Unsetting the overrides cannot force it, because
    unsetting them is what hands control to the walk. A test passes a
    `tmp_path` instead.
    """
    if explicit is not None:
        root = Path(explicit).expanduser()
        if not (root / GROUP_VARS_RELATIVE).is_file():
            raise VersionError(f"--repo-root {root} does not hold {GROUP_VARS_RELATIVE}")
        return root

    from_env = os.environ.get(REPO_ROOT_ENV)
    if from_env:
        root = Path(from_env).expanduser()
        if not (root / GROUP_VARS_RELATIVE).is_file():
            raise VersionError(f"{REPO_ROOT_ENV}={root} does not hold {GROUP_VARS_RELATIVE}")
        return root

    searched: list[Path] = []
    for start in (Path.cwd(), walk_from or Path(__file__).parent):
        for candidate in _candidates(start):
            if (candidate / GROUP_VARS_RELATIVE).is_file():
                return candidate
            searched.append(candidate)

    raise VersionError(
        f"cannot find {GROUP_VARS_RELATIVE}. Searched: "
        + ", ".join(str(path) for path in searched)
        + f". Point at the checkout with --repo-root PATH or {REPO_ROOT_ENV}. "
        "There is no built-in version list: the versions come from the repo "
        "or the command fails."
    )


def tool_versions(repo_root: Path) -> dict[str, str]:
    """The upstream version of each tool in `TOOLS`, revision stripped."""
    group_vars = repo_root / GROUP_VARS_RELATIVE
    parsed = yaml.safe_load(group_vars.read_text())
    declared = (parsed or {}).get(VERSIONS_KEY)
    if not isinstance(declared, dict):
        raise VersionError(f"{group_vars} declares no {VERSIONS_KEY} mapping")

    missing = [tool for tool in TOOLS if not declared.get(tool)]
    if missing:
        raise VersionError(f"{group_vars} declares no version for: {', '.join(missing)}")

    return {tool: strip_revision(str(declared[tool])) for tool in TOOLS}
