"""The uv and prek caches are shared with the loop-harness devcontainer.

Docker shares a named volume only when both containers name it the same, so a
rename on this side silently gives this container its own empty cache.
"""

import json
import re
from pathlib import Path

import pytest

from localstack_cli.versions import resolve_repo_root

SHARED = {
    "UV_CACHE_DIR": "source=loop-harness-uv-cache,target=/home/vscode/.cache/uv,type=volume",
    "PREK_HOME": "source=loop-harness-prek-cache,target=/home/vscode/.cache/prek,type=volume",
}


def devcontainer() -> Path:
    return resolve_repo_root() / ".devcontainer"


def mounts() -> list[str]:
    config = json.loads((devcontainer() / "devcontainer.json").read_text())
    return list(config["mounts"])


@pytest.mark.parametrize(("variable", "mount"), SHARED.items())
def test_the_cache_is_the_loop_harness_volume(variable: str, mount: str) -> None:
    assert mount in mounts()

    target = re.search(r"target=([^,]+)", mount)
    assert target is not None
    # Set in the Dockerfile or in devcontainer.json's containerEnv; either way
    # the tool must point at the mounted volume, or it fills its own cache.
    dockerfile = (devcontainer() / "Dockerfile").read_text()
    env = json.loads((devcontainer() / "devcontainer.json").read_text()).get("containerEnv", {})
    assert f"ENV {variable}={target.group(1)}\n" in dockerfile or env.get(variable) == target.group(
        1
    ), f"{variable} does not point at {target.group(1)}"


def test_claude_state_is_not_shared() -> None:
    assert "source=localstack-claude,target=/home/vscode/.claude,type=volume" in mounts()
    assert not any(m.startswith("source=loop-harness-claude,") for m in mounts())


def test_the_cli_venv_is_a_volume() -> None:
    """The workspace is bind-mounted from macOS, and so would be its venv."""
    assert any(
        m.endswith("target=${containerWorkspaceFolder}/cli/.venv,type=volume") for m in mounts()
    )


def test_setup_replaces_a_leftover_pre_commit_hook() -> None:
    """Without --overwrite prek keeps the old hook as .legacy and still runs it,
    and that hook fails once pre-commit is gone from the image."""
    justfile = (resolve_repo_root() / "justfile").read_text()

    assert "prek install --overwrite" in justfile
    assert "just setup" in (devcontainer() / "bootstrap.sh").read_text()


def test_ovsync_is_installed_at_the_pinned_tag() -> None:
    dockerfile = (devcontainer() / "Dockerfile").read_text()

    assert (
        'RUN uv tool install ov-sync --from "git+https://github.com/JasperHG90/'
        'openviking_extensions@ov-sync-v0.3.0#subdirectory=packages/ov-sync"\n'
    ) in dockerfile


def test_openviking_credentials_are_read_only() -> None:
    """The directory, not ovcli.conf: ovx --bind replaces the file by rename,
    and a file bind would keep showing the old one."""
    assert (
        "source=${localEnv:HOME}/.openviking,target=/home/vscode/.openviking,type=bind,readonly"
        in mounts()
    )


def test_ovx_stays_writable() -> None:
    """ovx -L --no-bind stores its token in ~/.ovx from inside the container."""
    assert "source=${localEnv:HOME}/.ovx,target=/home/vscode/.ovx,type=bind" in mounts()
