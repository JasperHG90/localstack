"""Vault seal state, the one read that needs no token."""

import json
from pathlib import Path

import httpx
import pytest
import respx

from localstack_cli.api.errors import Timeout, Unreachable
from localstack_cli.api.vault import seal_status

FIXTURES = Path(__file__).parent / "fixtures" / "capture"
ADDRESS = "https://vault.test.invalid"
SEAL = f"{ADDRESS}/v1/sys/seal-status"


def payload() -> dict[str, object]:
    loaded: dict[str, object] = json.loads((FIXTURES / "seal_status.json").read_text())
    return loaded


@respx.mock
def test_an_unsealed_vault_parses() -> None:
    respx.get(SEAL).mock(return_value=httpx.Response(200, json=payload()))

    status = seal_status(ADDRESS)

    assert not status.sealed
    assert status.threshold == 3
    assert status.shares == 5
    assert status.summary == "unsealed"


@respx.mock
def test_no_token_header_is_sent() -> None:
    """This read needs none, and it is what still works when the session dies."""
    route = respx.get(SEAL).mock(return_value=httpx.Response(200, json=payload()))

    seal_status(ADDRESS)

    assert "X-Vault-Token" not in route.calls.last.request.headers


@respx.mock
def test_a_sealed_vault_says_how_far_the_unseal_got() -> None:
    """The common real outage here. The root justfile has a recipe for it."""
    respx.get(SEAL).mock(
        return_value=httpx.Response(200, json={**payload(), "sealed": True, "progress": 1})
    )

    status = seal_status(ADDRESS)

    assert status.sealed
    assert status.summary == "SEALED  1/3 keys entered"


@respx.mock
def test_an_unreachable_vault_names_the_address() -> None:
    respx.get(SEAL).mock(side_effect=httpx.ConnectError("refused"))

    with pytest.raises(Unreachable) as caught:
        seal_status(ADDRESS)

    assert ADDRESS in str(caught.value)


@respx.mock
def test_a_slow_vault_times_out() -> None:
    respx.get(SEAL).mock(side_effect=httpx.ReadTimeout("slow"))

    with pytest.raises(Timeout):
        seal_status(ADDRESS, timeout=0.01)
