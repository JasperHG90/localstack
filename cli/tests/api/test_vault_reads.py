"""Vault's policy read, its existence check, and the live-session probe."""

import httpx
import pytest
import respx

from localstack_cli.api.errors import MissingCapability
from localstack_cli.api.vault import health, metadata_exists, read_policy, token_is_live
from tests.fixtures.policies import THREE_BLOCK

ADDRESS = "https://vault.test.invalid"
TOKEN = "a-vault-token"
LOOKUP = f"{ADDRESS}/v1/auth/token/lookup-self"
POLICY = f"{ADDRESS}/v1/sys/policies/acl/nomad-workloads"
METADATA = f"{ADDRESS}/v1/secret/metadata/default/hermes/github"
DATA = f"{ADDRESS}/v1/secret/data/default/hermes/github"


@respx.mock
def test_health_needs_no_token() -> None:
    route = respx.get(f"{ADDRESS}/v1/sys/health").mock(
        return_value=httpx.Response(
            200, json={"initialized": True, "sealed": False, "version": "9.9.9"}
        )
    )

    result = health(ADDRESS)

    assert result.initialized and not result.sealed
    assert "X-Vault-Token" not in route.calls.last.request.headers


@respx.mock
def test_the_policy_text_is_fetched_not_embedded() -> None:
    respx.get(POLICY).mock(return_value=httpx.Response(200, json={"data": {"policy": THREE_BLOCK}}))

    assert read_policy(ADDRESS, TOKEN, "nomad-workloads") == THREE_BLOCK


@respx.mock
def test_a_denied_policy_read_names_the_grant() -> None:
    respx.get(POLICY).mock(return_value=httpx.Response(403, text="permission denied"))

    with pytest.raises(MissingCapability) as caught:
        read_policy(ADDRESS, TOKEN, "nomad-workloads")

    assert "sys/policies/acl" in caught.value.capability


@respx.mock
def test_a_present_path_reads_present() -> None:
    respx.get(METADATA).mock(
        return_value=httpx.Response(200, json={"data": {"current_version": 1, "versions": {}}})
    )

    assert metadata_exists(ADDRESS, TOKEN, "secret/metadata/default/hermes/github") == "present"


@respx.mock
def test_an_absent_path_reads_missing() -> None:
    respx.get(METADATA).mock(return_value=httpx.Response(404, json={"errors": []}))

    assert metadata_exists(ADDRESS, TOKEN, "secret/metadata/default/hermes/github") == "missing"


@respx.mock
def test_a_denied_path_is_a_third_state_never_missing() -> None:
    """Saying "missing" would send someone to write a secret already there."""
    respx.get(METADATA).mock(return_value=httpx.Response(403, text="permission denied"))

    assert metadata_exists(ADDRESS, TOKEN, "secret/metadata/default/hermes/github") == "denied"


@respx.mock
def test_the_existence_check_never_touches_the_data_endpoint() -> None:
    """Reading the value is neither needed nor safe to render."""
    respx.get(METADATA).mock(return_value=httpx.Response(200, json={"data": {}}))
    data = respx.get(DATA).mock(return_value=httpx.Response(200, json={"data": {"data": {}}}))

    metadata_exists(ADDRESS, TOKEN, "secret/metadata/default/hermes/github")

    assert data.call_count == 0


@respx.mock
def test_a_live_session_reports_live() -> None:
    respx.get(LOOKUP).mock(return_value=httpx.Response(200, json={"data": {}}))

    assert token_is_live(ADDRESS, TOKEN)


@respx.mock
def test_a_dead_session_reports_dead() -> None:
    """This is what separates "log in again" from "you lack the grant"."""
    respx.get(LOOKUP).mock(return_value=httpx.Response(403, text="permission denied"))

    assert not token_is_live(ADDRESS, TOKEN)
