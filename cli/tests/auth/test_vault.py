"""The Vault calls, and the refusal to put a password on the wire in clear."""

import json

import pytest

from localstack_cli.auth import vault
from localstack_cli.auth.vault import (
    EDGE_VAULT_ADDR,
    InsecureAddressError,
    VaultError,
    guard_address,
    identity_policies,
    is_plaintext_to_the_network,
)
from tests.fixtures.cluster import FakeCluster


@pytest.mark.parametrize(
    ("addr", "plaintext"),
    [
        ("http://192.168.2.30:8200", True),
        ("http://vault.lab.orangecluster.nl", True),
        ("http://10.0.0.1:8200", True),
        ("https://vault.lab.orangecluster.nl", False),
        ("https://192.168.2.30:8200", False),
        ("http://127.0.0.1:8200", False),
        ("http://localhost:8200", False),
        ("http://[::1]:8200", False),
    ],
)
def test_which_addresses_would_leak_a_password(addr: str, plaintext: bool) -> None:
    """Loopback over http is fine, nothing leaves the host. The cluster's own
    listener sets `tls_disable: true`, so the non-loopback case is live."""
    assert is_plaintext_to_the_network(addr) is plaintext


def test_a_plaintext_address_is_refused_and_names_the_edge() -> None:
    with pytest.raises(InsecureAddressError) as caught:
        guard_address("http://192.168.2.30:8200", insecure=False)
    assert EDGE_VAULT_ADDR in str(caught.value)


def test_insecure_proceeds_but_is_loud() -> None:
    """A guard that can be bypassed silently is decoration."""
    warning = guard_address("http://192.168.2.30:8200", insecure=True)
    assert warning is not None
    assert "unencrypted" in warning


def test_a_tls_address_needs_no_warning() -> None:
    assert guard_address(EDGE_VAULT_ADDR, insecure=False) is None


def test_login_returns_the_auth_block(cluster_addr: str) -> None:
    auth = vault.login_userpass(cluster_addr, "operator", "hunter2")
    assert auth["client_token"] == "hvs.session-token"
    assert auth["entity_id"] == "351f302a"


def test_login_sends_the_password_in_the_body(cluster_addr: str, cluster: FakeCluster) -> None:
    vault.login_userpass(cluster_addr, "operator", "hunter2")
    sent = cluster.requests_for("/v1/auth/userpass/login/operator")
    assert [item.method for item in sent] == ["POST"]
    assert sent[0].json() == {"password": "hunter2"}


def test_a_login_with_no_token_in_the_reply_is_an_error(
    cluster_addr: str, cluster: FakeCluster
) -> None:
    cluster.routes["/v1/auth/userpass/login/operator"] = (200, b'{"auth":{}}')
    with pytest.raises(VaultError, match="returned no token"):
        vault.login_userpass(cluster_addr, "operator", "hunter2")


def test_a_404_on_the_login_path_names_the_path(cluster_addr: str, cluster: FakeCluster) -> None:
    """Reads as a wrong username or a wrong address, which is what it is."""
    cluster.routes["/v1/auth/userpass/login/operator"] = (404, b'{"errors":[]}')
    with pytest.raises(VaultError, match="auth/userpass/login/operator"):
        vault.login_userpass(cluster_addr, "operator", "hunter2")


def test_an_error_body_is_quoted_back(cluster_addr: str, cluster: FakeCluster) -> None:
    """A bare status code sends the reader to the wrong layer."""
    cluster.routes["/v1/auth/token/lookup-self"] = (
        403,
        json.dumps({"errors": ["permission denied"]}).encode(),
    )
    with pytest.raises(VaultError, match="permission denied"):
        vault.lookup_self(cluster_addr, "a-token")


def test_calls_carry_the_vault_token_header(cluster_addr: str, cluster: FakeCluster) -> None:
    """Without the header every authenticated call would 403 against the real
    Vault, so a fake that ignores it would hide the bug."""
    vault.lookup_self(cluster_addr, "a-token")
    assert cluster.requests_for("/v1/auth/token/lookup-self")[0].token == "a-token"


def test_lookup_self_returns_the_data_block(cluster_addr: str) -> None:
    assert vault.lookup_self(cluster_addr, "a-token")["entity_id"] == "351f302a"


def test_renew_self_returns_the_auth_block(cluster_addr: str) -> None:
    assert vault.renew_self(cluster_addr, "a-token")["lease_duration"] == 2764800


def test_revoke_self_tolerates_an_empty_204(cluster_addr: str, cluster: FakeCluster) -> None:
    """Vault answers 204 with no body, and a JSON parse of nothing would
    turn a successful revoke into an error."""
    vault.revoke_self(cluster_addr, "a-token")
    assert cluster.requests_for("/v1/auth/token/revoke-self")[0].method == "POST"


def test_an_unreachable_vault_says_so(closed_addr: str) -> None:
    with pytest.raises(VaultError, match="cannot reach Vault"):
        vault.lookup_self(closed_addr, "a-token")


def test_identity_policies_includes_what_a_group_grants() -> None:
    """The trap this function exists for.

    F11 binds `developer` through an identity group, so it lands in
    `identity_policies` while `policies` holds only `default`. Reporting
    `policies` alone tells a developer they have no grants when they do.
    """
    lookup = {"policies": ["default"], "identity_policies": ["developer"]}
    assert identity_policies(lookup) == ["default", "developer"]


def test_identity_policies_survives_a_lookup_missing_either_key() -> None:
    assert identity_policies({}) == []
    assert identity_policies({"policies": ["default"]}) == ["default"]


# The shape Vault really answers an MFA-enforced login with, measured against
# the Login MFA contract: HTTP 200, a NULL auth block, and the challenge under
# `mfa_requirement`. A fake that returned 401 or an error body would let a
# client pass while the real thing fell through to "returned no token".
# Captured from the live cluster on 2026-09-12, not written from the docs. The
# earlier version of this constant put `mfa_requirement` at the TOP LEVEL with a
# null `auth`, which is what the API contract describes. Vault actually nests it
# inside `auth`, beside an empty `client_token`. The fake matched the docs, so
# every test passed while the real login fell through to "no token".
MFA_CHALLENGE = {
    "request_id": "e9b1f0c2-1111-2222-3333-444455556666",
    "warnings": [
        "A login request was issued that is subject to MFA validation. "
        "Please make sure to validate the login by sending another request "
        "to sys/mfa/validate endpoint."
    ],
    "auth": {
        "client_token": "",
        "accessor": "",
        "entity_id": "",
        "policies": ["default"],
        "mfa_requirement": {
            "mfa_request_id": "d0c9eec7-6921-8d2a-3d8a-b8e1bd2e0e2f",
            # The key is the login enforcement's name, so nothing may key on a
            # fixed one.
            "mfa_constraints": {
                "operator-totp": {
                    "any": [
                        {
                            "type": "totp",
                            "id": "0c7722c7-3976-fe35-24a9-ace1971ef8c4",
                            "uses_passcode": True,
                        }
                    ]
                }
            },
        },
    },
}

MFA_VALIDATED = {
    "auth": {
        "client_token": "hvs.mfa-validated-token",
        "accessor": "vault-accessor",
        "entity_id": "351f302a",
        "policies": ["default", "developer"],
        "identity_policies": ["developer"],
        "lease_duration": 2764800,
        "renewable": True,
    }
}


def _enforce_mfa(cluster: FakeCluster) -> None:
    cluster.routes["/v1/auth/userpass/login/operator"] = (
        200,
        json.dumps(MFA_CHALLENGE).encode(),
    )


def test_an_mfa_challenge_is_not_reported_as_a_failed_login(
    cluster_addr: str, cluster: FakeCluster
) -> None:
    """The whole point of MFARequired. Before it, an enforced mount raised
    "returned no token. Check the username", which blames the wrong layer and
    sends the reader looking for a typo that is not there."""
    _enforce_mfa(cluster)
    with pytest.raises(vault.MFARequired) as caught:
        vault.login_userpass(cluster_addr, "operator", "hunter2")
    assert caught.value.request_id == "d0c9eec7-6921-8d2a-3d8a-b8e1bd2e0e2f"
    assert caught.value.method_ids == ["0c7722c7-3976-fe35-24a9-ace1971ef8c4"]


def test_mfa_required_is_still_a_vault_error(cluster_addr: str, cluster: FakeCluster) -> None:
    """Callers written before Login MFA catch VaultError. They must keep
    catching this, or an enforced mount turns into an AttributeError."""
    _enforce_mfa(cluster)
    with pytest.raises(VaultError):
        vault.login_userpass(cluster_addr, "operator", "hunter2")


def test_a_challenge_naming_no_method_says_so(cluster_addr: str, cluster: FakeCluster) -> None:
    """An enforcement with no reachable method is a config fault, and the
    message has to name the field rather than the password."""
    cluster.routes["/v1/auth/userpass/login/operator"] = (
        200,
        json.dumps({"auth": None, "mfa_requirement": {"mfa_request_id": "x"}}).encode(),
    )
    with pytest.raises(VaultError, match="mfa_method_ids"):
        vault.login_userpass(cluster_addr, "operator", "hunter2")


def test_validate_mfa_returns_the_auth_block(cluster_addr: str, cluster: FakeCluster) -> None:
    cluster.routes["/v1/sys/mfa/validate"] = (200, json.dumps(MFA_VALIDATED).encode())
    auth = vault.validate_mfa(cluster_addr, "req-1", "method-1", "123456")
    assert auth["client_token"] == "hvs.mfa-validated-token"


def test_validate_mfa_sends_the_payload_vault_expects(
    cluster_addr: str, cluster: FakeCluster
) -> None:
    """Keyed by method id, and the passcode in a LIST. Vault rejects a bare
    string, and the failure reads like a wrong code rather than a wrong shape."""
    cluster.routes["/v1/sys/mfa/validate"] = (200, json.dumps(MFA_VALIDATED).encode())
    vault.validate_mfa(cluster_addr, "req-1", "method-1", "123456")
    sent = cluster.requests_for("/v1/sys/mfa/validate")
    assert [item.method for item in sent] == ["POST"]
    assert sent[0].json() == {
        "mfa_request_id": "req-1",
        "mfa_payload": {"method-1": ["123456"]},
    }


def test_a_wrong_passcode_surfaces_vaults_own_words(
    cluster_addr: str, cluster: FakeCluster
) -> None:
    cluster.routes["/v1/sys/mfa/validate"] = (
        400,
        json.dumps({"errors": ["failed to satisfy enforcement userpass-totp"]}).encode(),
    )
    with pytest.raises(VaultError, match="failed to satisfy enforcement"):
        vault.validate_mfa(cluster_addr, "req-1", "method-1", "000000")


def test_an_enforced_entity_with_no_secret_names_enrollment(
    cluster_addr: str, cluster: FakeCluster
) -> None:
    """Applying the enforcement before enrolling anyone lands here, and Vault
    reports it as an empty 200 rather than an error. The old message blamed the
    username, which sent the reader hunting a typo that was not there.
    Measured against the live cluster on 2026-09-12."""
    cluster.routes["/v1/auth/userpass/login/operator"] = (200, b'{"auth":null}')
    with pytest.raises(VaultError, match="no second factor"):
        vault.login_userpass(cluster_addr, "operator", "hunter2")
