"""The OpenViking config guard refuses the rerank settings ov-ext 0.8.0 dropped.

ov-ext 0.8.0 stops startup when OV_RETRIEVAL_RERANK_MAX_CALLS or
OV_RETRIEVAL_RERANK_FINAL is set, so the guard catches them before a deploy.
"""

import importlib.util
import types
from pathlib import Path

import pytest

# cli/tests/<this file> -> repo root is two up.
REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "check_openviking_config.py"
JOBSPEC = REPO_ROOT / "deployments" / "applications" / "services" / "openviking.hcl"


@pytest.fixture
def guard() -> types.ModuleType:
    spec = importlib.util.spec_from_file_location("check_openviking_config", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_the_committed_jobspec_passes(guard: types.ModuleType) -> None:
    assert guard.jobspec_failures(JOBSPEC.read_text()) == []


@pytest.mark.parametrize("name", ["OV_RETRIEVAL_RERANK_MAX_CALLS", "OV_RETRIEVAL_RERANK_FINAL"])
def test_a_removed_rerank_setting_fails(guard: types.ModuleType, name: str) -> None:
    text = JOBSPEC.read_text().replace("env {", f'env {{\n        {name} = "1"', 1)
    failures = guard.jobspec_failures(text)
    assert any(name in failure for failure in failures)


def test_a_commented_removed_setting_passes(guard: types.ModuleType) -> None:
    text = JOBSPEC.read_text().replace(
        "env {", 'env {\n        # OV_RETRIEVAL_RERANK_FINAL = "true"', 1
    )
    assert guard.jobspec_failures(text) == []
