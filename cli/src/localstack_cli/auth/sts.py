"""S3 credentials for a SeaweedFS role, traded for a Vault identity token.

Two hops, the same as the openviking-sync action's: the session's Vault token
reads `identity/oidc/token/<role>`, and SeaweedFS's STS swaps that for the role
of the same name. Vault's ACL decides which roles a login may mint, and the
role's trust policy decides what the token gets.

DurationSeconds is sent on purpose. SeaweedFS ignores the identity token's
expiry when it sets the session length and would otherwise grant its
configured default, an hour. 900 is the shortest it accepts.
"""

import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import dataclass

from localstack_cli.auth import vault

DEFAULT_ENDPOINT = "https://s3.lab.orangecluster.nl"
DURATION_SECONDS = 900
TIMEOUT_SECONDS = 10


class StsError(RuntimeError):
    """Minting or swapping failed, with a message naming the step and why."""


@dataclass(frozen=True)
class S3Credentials:
    access_key_id: str
    secret_access_key: str
    session_token: str
    expiration: str

    def exports(self) -> dict[str, str]:
        return {
            "AWS_ACCESS_KEY_ID": self.access_key_id,
            "AWS_SECRET_ACCESS_KEY": self.secret_access_key,
            "AWS_SESSION_TOKEN": self.session_token,
        }


def s3_credentials(
    vault_addr: str, vault_token: str, role: str, endpoint: str, session_name: str
) -> S3Credentials:
    """Mint the role's identity token and swap it at STS for S3 credentials."""
    try:
        reply = vault.read_creds(vault_addr, vault_token, f"identity/oidc/token/{role}")
    except vault.VaultError as error:
        raise StsError(str(error)) from error
    token = reply.get("data", {}).get("token")
    if not token:
        raise StsError(f"Vault returned no token for identity/oidc/token/{role}")
    return _assume_role(endpoint, role, token, session_name)


def _assume_role(endpoint: str, role: str, token: str, session_name: str) -> S3Credentials:
    form = urllib.parse.urlencode(
        {
            "Action": "AssumeRoleWithWebIdentity",
            "Version": "2011-06-15",
            "RoleArn": f"arn:aws:iam::role/{role}",
            "RoleSessionName": session_name,
            "WebIdentityToken": token,
            "DurationSeconds": str(DURATION_SECONDS),
        }
    ).encode()
    request = urllib.request.Request(endpoint.rstrip("/") + "/", data=form, method="POST")
    request.add_header("Content-Type", "application/x-www-form-urlencoded")
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
            raw = response.read()
    except urllib.error.HTTPError as error:
        detail = error.read().decode(errors="replace").strip()
        raise StsError(f"SeaweedFS STS refused role {role} ({error.code}): {detail}") from error
    except OSError as error:
        raise StsError(f"cannot reach SeaweedFS STS at {endpoint}: {error}") from error

    try:
        root = ET.fromstring(raw)
    except ET.ParseError as error:
        raise StsError("SeaweedFS STS returned a body that is not XML") from error
    found = {el.tag.rsplit("}", 1)[-1]: (el.text or "") for el in root.iter()}
    fields = ("AccessKeyId", "SecretAccessKey", "SessionToken", "Expiration")
    missing = [f for f in fields if not found.get(f)]
    if missing:
        raise StsError(f"SeaweedFS STS returned no {', '.join(missing)}")
    return S3Credentials(*(found[f] for f in fields))
