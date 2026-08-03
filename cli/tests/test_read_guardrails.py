"""The boundaries the read commands must not cross.

Every check asserts its search path exists first. A grep over a directory
that is not there returns no match, and no-match is the pass condition, so a
wrong prefix would pass all of these for the wrong reason.
"""

import ast
import re
from pathlib import Path

PACKAGE = Path(__file__).resolve().parents[1] / "src" / "localstack_cli"
API = PACKAGE / "api"
COMMANDS = PACKAGE / "commands"


def test_the_paths_these_checks_grep_exist() -> None:
    assert PACKAGE.is_dir()
    assert API.is_dir()
    assert COMMANDS.is_dir()


def executable_lines(directory: Path) -> list[str]:
    """Source with comments and docstrings removed.

    These modules explain at length why they do not do the forbidden thing,
    so a grep over raw text flags the prose documenting the decision.
    """
    out: list[str] = []
    for path in sorted(directory.rglob("*.py")):
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            if isinstance(
                node, ast.Module | ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef
            ) and ast.get_docstring(node):
                node.body[0] = ast.Pass()
        out.extend(f"{path.name}: {line}" for line in ast.unparse(tree).splitlines())
    return out


def test_no_subprocess_anywhere() -> None:
    """An `rtk` shim rewrites shelled commands here, so a subprocess's output
    is not guaranteed to be the binary's own. HTTP plus respx is also what
    keeps the default suite offline.

    Scoped to the read path. `install.py` runs `<tool> version` on purpose:
    asking an installed binary its own version is the only honest way to
    detect drift, and a recorded answer would keep claiming the version it
    was told long after someone replaced the file.
    """
    pattern = re.compile(r"subprocess|os\.system|shutil\.which")
    lines = executable_lines(API) + executable_lines(COMMANDS)

    assert [line for line in lines if pattern.search(line)] == []


def test_the_api_layer_imports_no_renderer() -> None:
    """D4's TUI imports `api/` and must not drag in a CLI framework."""
    pattern = re.compile(r"^[a-z_]+\.py: (import|from) (typer|rich)")

    assert [line for line in executable_lines(API) if pattern.search(line)] == []


def test_no_address_host_or_port_in_the_api_layer() -> None:
    """All three addresses come from `config.py`, so a firewall change that
    moves them is not a change to this ticket.
    """
    pattern = re.compile(r"192\.168\.|lab\.orangecluster\.nl|:(4646|8200|8500)")

    assert [line for line in executable_lines(API) if pattern.search(line)] == []


def test_the_api_layer_is_read_only() -> None:
    pattern = re.compile(r"\.(post|put|delete|patch)\(")

    assert [line for line in executable_lines(API) if pattern.search(line)] == []


def test_nothing_requests_the_kv2_data_endpoint() -> None:
    """Existence comes from metadata, which carries no `data` field at all."""
    assert [line for line in executable_lines(API) if "secret/data/" in line] == []


def test_the_repo_tree_is_never_read_for_cluster_state() -> None:
    """`talat-shim` and `talat-consumer` run live with no job file here, so a
    repo-derived answer under-reports by two. The routing table is likewise
    a Terraform `templatefile` input, not what the edge is running.
    """
    pattern = re.compile(r"haproxy\.hcl|deployments/")

    assert [line for line in executable_lines(PACKAGE) if pattern.search(line)] == []


def test_only_one_module_reaches_for_template_text() -> None:
    """A jobspec template can hold a rendered credential, so there is one
    door to it and one place to audit.
    """
    offenders = [
        str(path.relative_to(PACKAGE))
        for path in sorted(PACKAGE.rglob("*.py"))
        if "EmbeddedTmpl" in path.read_text() and path.name != "nomad.py"
    ]

    assert offenders == []
