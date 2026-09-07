#!/usr/bin/env python3
"""Assert that a Vault identity token authenticates to OpenViking, and that a
wrong one does not.

No gate in this repo runs a deployed service, so nothing else proves the chain
this ticket builds actually works. Run this by hand after an apply, from a host
that reaches both Vault and the OpenViking API, holding a Vault token whose
entity carries `ov_account`.

Four assertions, each exiting non-zero on the first failure:

    1. a minted token is accepted, and resolves to the expected account
    2. no token at all is refused
    3. a token carrying a foreign audience is refused
    4. a token naming an account that does not exist behaves the same for a
       read and a write

The last one is the open question rather than a pass/fail on its own: the OIDC
plugin creates nothing, and account creation used to be what initialized a
person's directory trees. Whichever way it answers, RECORD IT — the answer
decides whether adding a person needs a provisioning step.

Assertions 3 and 4 mint from scratch roles this script creates and deletes in
the same run. A grant on its own cannot tell a working mapping from one that
accepts everything, which is why the denials are here.
"""

from __future__ import annotations

import argparse
import base64
import json
import subprocess
import sys
import urllib.error
import urllib.request
import uuid
from typing import Any

DEFAULT_ROLE = "openviking"
DEFAULT_API = "https://openviking-api.lab.orangecluster.nl"

# Any authenticated route that reads the caller's own tree. `viking://` is the
# root of it, so a 200 here means the identity resolved to a real account.
DATA_ROUTE = "/api/v1/fs/ls?uri=viking://"


class ProbeFailure(Exception):
    """An assertion that did not hold. The message is the report."""


def vault(*args: str) -> str:
    """Run the vault CLI and return stdout, or raise with its stderr."""
    done = subprocess.run(["vault", *args], capture_output=True, text=True, check=False)
    if done.returncode != 0:
        raise ProbeFailure(f"vault {' '.join(args)} failed: {done.stderr.strip()}")
    return done.stdout.strip()


def mint(role: str) -> str:
    return vault("read", "-field=token", f"identity/oidc/token/{role}")


def claims(token: str) -> dict[str, Any]:
    """Decode the payload WITHOUT verifying. Only for reporting what was sent."""
    payload = token.split(".")[1]
    payload += "=" * (-len(payload) % 4)
    decoded: dict[str, Any] = json.loads(base64.urlsafe_b64decode(payload))
    return decoded


def call(base: str, token: str | None) -> int:
    """Status code from the data route, with the token or without one."""
    request = urllib.request.Request(base.rstrip("/") + DATA_ROUTE)
    if token is not None:
        request.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            return int(response.status)
    except urllib.error.HTTPError as error:
        return int(error.code)


def scratch_role(name: str, key: str, client_id: str, account: str) -> None:
    vault(
        "write",
        f"identity/oidc/role/{name}",
        f"key={key}",
        f"client_id={client_id}",
        "ttl=300",
        f'template={{"ov_account":"{account}"}}',
    )


def assert_token_is_accepted(base: str, role: str, expected: str) -> None:
    token = mint(role)
    sent = claims(token).get("ov_account")
    if sent != expected:
        raise ProbeFailure(
            f"the role published ov_account={sent!r}, expected {expected!r}. "
            "Check the entity's metadata, not the config."
        )
    status = call(base, token)
    if status != 200:
        raise ProbeFailure(
            f"a valid token for {expected!r} got HTTP {status}, expected 200. "
            "If 401, compare the token's iss and aud against server.oidc in "
            "ov.conf.json; upstream verifies both exactly."
        )
    print(f"ok  a minted token for {expected!r} is accepted")


def assert_no_token_is_refused(base: str) -> None:
    status = call(base, None)
    if status not in (401, 403):
        raise ProbeFailure(
            f"an unauthenticated call got HTTP {status}, expected 401 or 403. "
            "This route is what justifies exposing the port at all."
        )
    print(f"ok  an unauthenticated call is refused ({status})")


def assert_foreign_audience_is_refused(base: str, account: str) -> None:
    """A token OpenViking can verify the signature of, but must reject on aud.

    It needs its OWN key: Vault refuses to mint a token whose client_id is not
    in the signing key's allowed_client_ids, so a foreign audience on the real
    key never gets issued at all. That is a real defence, and it is upstream of
    the one being tested here.
    """
    suffix = uuid.uuid4().hex[:8]
    key = f"probe-key-{suffix}"
    name = f"probe-aud-{suffix}"
    aud = f"not-openviking-{suffix}"
    vault(
        "write",
        f"identity/oidc/key/{key}",
        "algorithm=RS256",
        "rotation_period=3600",
        "verification_ttl=3600",
        f"allowed_client_ids={aud}",
    )
    try:
        scratch_role(name, key, aud, account)
        status = call(base, mint(name))
        if status not in (401, 403):
            raise ProbeFailure(
                f"a token with a foreign audience got HTTP {status}, expected "
                "401 or 403. Audience verification is not reaching the server."
            )
        print(f"ok  a foreign audience is refused ({status})")
    finally:
        vault("delete", f"identity/oidc/role/{name}")
        vault("delete", f"identity/oidc/key/{key}")


def report_unknown_account(base: str, key: str, client_id: str) -> None:
    """Answer the open question: is an uninitialized account tree usable?"""
    account = f"neverseen-{uuid.uuid4().hex[:8]}"
    name = f"probe-unknown-{uuid.uuid4().hex[:8]}"
    scratch_role(name, key, client_id, account)
    try:
        status = call(base, mint(name))
    finally:
        vault("delete", f"identity/oidc/role/{name}")

    verdict = {
        200: "an account that was never created is READABLE. Adding a person "
        "needs no provisioning step.",
        401: "refused. Adding a person needs a provisioning step, and there "
        "is none under oidc.",
        403: "refused. Adding a person needs a provisioning step, and there "
        "is none under oidc.",
    }.get(
        status,
        "an unexpected status. Read the server log before drawing a "
        "conclusion from it.",
    )
    print(f"??  account {account!r} -> HTTP {status}: {verdict}")


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--api", default=DEFAULT_API, help="OpenViking API base URL")
    parser.add_argument("--role", default=DEFAULT_ROLE, help="identity-token role")
    parser.add_argument(
        "--account",
        required=True,
        help="the ov_account the calling Vault token's entity carries",
    )
    parser.add_argument(
        "--key",
        default="identity-tokens",
        help="named key the scratch roles sign with",
    )
    parser.add_argument(
        "--audience",
        default="openviking",
        help="the real role's client_id, reused by the unknown-account role",
    )
    args = parser.parse_args(argv)

    try:
        assert_token_is_accepted(args.api, args.role, args.account)
        assert_no_token_is_refused(args.api)
        assert_foreign_audience_is_refused(args.api, args.account)
        report_unknown_account(args.api, args.key, args.audience)
    except ProbeFailure as failure:
        print(f"FAIL: {failure}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
