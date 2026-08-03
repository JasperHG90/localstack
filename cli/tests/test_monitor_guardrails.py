"""The boundaries this ticket must not cross, as tests.

Each one fails green if it is written carelessly, which is why they check the
package path exists first: a grep over a directory that is not there returns
no match, and no-match is the pass condition.
"""

import ast
import re
from pathlib import Path

PACKAGE = Path(__file__).resolve().parents[1] / "src" / "localstack_cli"
API = PACKAGE / "api"
TUI = PACKAGE / "tui"


def test_the_paths_this_file_greps_actually_exist() -> None:
    """Without this every check below passes on an empty search."""
    assert PACKAGE.is_dir()
    assert API.is_dir()
    assert TUI.is_dir()


def imports_of(directory: Path) -> set[str]:
    """Every module imported anywhere under `directory`."""
    found: set[str] = set()
    for path in sorted(directory.rglob("*.py")):
        for node in ast.walk(ast.parse(path.read_text())):
            if isinstance(node, ast.Import):
                found.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                found.add(node.module.split(".")[0])
    return found


def test_there_is_one_fetch_layer() -> None:
    """Two would mean two places deciding what a 403 means."""
    assert "httpx" not in imports_of(TUI)
    assert not list(PACKAGE.rglob("cluster_api.py"))


def test_the_tui_reads_through_the_api_package() -> None:
    sources = " ".join(path.read_text() for path in TUI.rglob("*.py"))

    assert "from localstack_cli.api" in sources


def test_the_api_layer_imports_no_renderer() -> None:
    """D3's contract: dataclasses out, so more than one front end can use it."""
    imported = imports_of(API)

    assert "textual" not in imported
    assert "typer" not in imported
    assert "rich" not in imported


def test_no_cluster_address_is_hardcoded_in_the_panel() -> None:
    """Addresses come from `config.py`. The plaintext ports are closing.

    Scoped to what this ticket owns: the fetch layer, the panel, and the
    command. Two places elsewhere in the package hold an address on purpose
    and must keep it. `auth/vault.py` names the TLS edge so `login` can
    refuse a plaintext address before it prompts for a password, and the
    break-glass runbook names all three routes because it exists for the case
    where the configured one is broken. Widening this check to the whole
    package would demand breaking both.
    """
    pattern = re.compile(r"192\.168\.\d+\.\d+|:4646|:8200|:8500|lab\.orangecluster\.nl")
    owned = [*API.rglob("*.py"), *TUI.rglob("*.py"), PACKAGE / "commands" / "monitor.py"]
    offenders = [
        f"{path.relative_to(PACKAGE)}:{number}"
        for path in sorted(owned)
        for number, line in enumerate(path.read_text().splitlines(), start=1)
        if pattern.search(line)
    ]

    assert offenders == []


def test_there_is_no_second_auth_path() -> None:
    """Auth comes entirely from the session `login` brokered."""
    pattern = re.compile(r"userpass|auth/token|session\.json|VAULT_TOKEN")
    offenders = [
        f"{path.relative_to(PACKAGE)}:{number}"
        for path in sorted((API, TUI))
        for source in path.rglob("*.py")
        for number, line in enumerate(source.read_text().splitlines(), start=1)
        if pattern.search(line)
    ]

    assert offenders == []


def test_no_token_value_appears_in_a_fixture_or_baseline() -> None:
    """Snapshot fixtures are scrubbed, and the baselines render no token."""
    pattern = re.compile(r"hvs\.|hvo_|hvb\.")
    searched = [
        *(Path(__file__).parent / "fixtures" / "capture").glob("*.json"),
        *(Path(__file__).parent / "__snapshots__").rglob("*"),
    ]
    offenders = [
        str(path)
        for path in searched
        if path.is_file() and pattern.search(path.read_text(errors="ignore"))
    ]

    assert offenders == []


def test_the_grafana_boundary_holds() -> None:
    """No metrics, no charts, no history, no logs, no alerting, no writes."""
    sources = " ".join(path.read_text() for path in PACKAGE.rglob("*.py"))
    forbidden = ("prometheus_client", "promql", "PromQL", "Sparkline", "plotext")

    assert [word for word in forbidden if word in sources] == []


def test_the_panel_never_writes_to_the_cluster() -> None:
    """Read-only: the TUI issues GETs and nothing else."""
    sources = " ".join(path.read_text() for path in (*API.rglob("*.py"), *TUI.rglob("*.py")))

    for verb in (".post(", ".put(", ".delete(", ".patch("):
        assert verb not in sources
