"""Rendering a templated policy without becoming Vault."""

import re
from pathlib import Path

from localstack_cli.api.grants import accessor, render, variables
from tests.fixtures.policies import ACCESSOR, SIX_BLOCK, THREE_BLOCK, WITH_UNKNOWN_VARIABLE

VALUES = {"nomad_namespace": "default", "nomad_job_id": "memex"}


def test_the_accessor_is_discovered_not_assumed() -> None:
    """It is derived at bootstrap and differs per rebuild."""
    assert accessor(THREE_BLOCK) == ACCESSOR


def test_a_policy_without_a_template_has_no_accessor() -> None:
    assert accessor('path "secret/data/x" {\n  capabilities = ["read"]\n}') is None


def test_the_variables_are_read_off_the_text() -> None:
    assert variables(THREE_BLOCK) == {"nomad_namespace", "nomad_job_id"}


def test_the_three_block_policy_resolves() -> None:
    grants = render(THREE_BLOCK, VALUES)

    assert len(grants) == 3
    assert grants[0].resolved_path == "secret/data/default/memex/*"
    assert grants[0].capabilities == ["read"]
    assert not any(grant.unresolved for grant in grants)


def test_the_six_block_policy_resolves_too() -> None:
    """The policy has changed block count once and will again."""
    grants = render(SIX_BLOCK, VALUES)

    assert len(grants) == 6
    assert grants[3].resolved_path == "secret/metadata/*"
    assert grants[4].capabilities == ["read", "create", "update"]


def test_the_raw_line_is_kept_beside_the_resolved_one() -> None:
    """Both columns, so a reader can see what was substituted."""
    grant = render(THREE_BLOCK, VALUES)[0]

    assert ACCESSOR in grant.raw_path
    assert "{{" in grant.raw_path
    assert "{{" not in grant.resolved_path


def test_an_unfillable_variable_stays_visible_and_is_flagged() -> None:
    """Blanking it would produce a resolved-looking path that is wrong."""
    grants = render(WITH_UNKNOWN_VARIABLE, VALUES)

    assert len(grants) == 1
    assert grants[0].unresolved
    assert "nomad_region" in grants[0].resolved_path
    assert "{{" in grants[0].resolved_path


def test_the_namespace_is_substituted_independently() -> None:
    grants = render(THREE_BLOCK, {"nomad_namespace": "staging", "nomad_job_id": "memex"})

    assert grants[0].resolved_path.startswith("secret/data/staging/memex/")


def test_no_path_count_appears_in_the_source() -> None:
    """Code that counts blocks breaks the next time the policy moves."""
    source = (
        Path(__file__).resolve().parents[2] / "src" / "localstack_cli" / "api" / "grants.py"
    ).read_text()
    code = [
        line
        for line in source.splitlines()
        if line.strip() and not line.strip().startswith("#") and '"""' not in line
    ]

    assert not any(re.search(r"==\s*[36]\b|len\(.*\)\s*[=<>]=?\s*[36]\b", line) for line in code)


def test_the_accessor_literal_is_absent_from_the_whole_package() -> None:
    """It differs per rebuild, so a constant would break on the next one."""
    package = Path(__file__).resolve().parents[2] / "src" / "localstack_cli"
    offenders = [
        str(path.relative_to(package))
        for path in package.rglob("*.py")
        if "auth_jwt_649fd6cc" in path.read_text()
    ]

    assert offenders == []


def test_a_comment_block_is_not_mistaken_for_a_path() -> None:
    """The live policy ends with a long comment; it must not become a row."""
    assert len(render(THREE_BLOCK, VALUES)) == 3


def test_the_unresolved_flag_survives_serialization() -> None:
    """As a property it vanished from `asdict`, so `--json` carried no mark."""
    from dataclasses import asdict

    resolved = render(WITH_UNKNOWN_VARIABLE, VALUES)[0]
    clean = render(THREE_BLOCK, VALUES)[0]

    assert asdict(resolved)["unresolved"] is True
    assert asdict(clean)["unresolved"] is False
