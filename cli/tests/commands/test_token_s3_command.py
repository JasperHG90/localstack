"""`localstack token s3 ROLE`: Vault token in, three S3 exports out.

FakeCluster plays both Vault and SeaweedFS's STS, which answers on `/`. The
role is an argument: Vault's ACL decides which identity tokens the login may
mint, and SeaweedFS's trust policy decides what each one gets.
"""

import json
import urllib.parse
from datetime import UTC, datetime, timedelta

import pytest
from typer.testing import CliRunner, Result

from localstack_cli.auth.session import Credential, Session, save, session_path
from localstack_cli.main import app
from tests.fixtures.cluster import FakeCluster

runner = CliRunner()

TOKEN_PATH = "/v1/identity/oidc/token/local-ov-sync"
STS_REPLY = b"""<AssumeRoleWithWebIdentityResponse xmlns="https://sts.amazonaws.com/doc/2011-06-15/">
<AssumeRoleWithWebIdentityResult><Credentials>
<AccessKeyId>AKID</AccessKeyId><SecretAccessKey>SECRET</SecretAccessKey>
<SessionToken>SESSION</SessionToken><Expiration>2026-11-27T18:15:00Z</Expiration>
</Credentials></AssumeRoleWithWebIdentityResult></AssumeRoleWithWebIdentityResponse>"""


@pytest.fixture
def logged_in(cluster_addr: str) -> Session:
    now = datetime.now(UTC)
    session = Session(
        method="userpass",
        vault_addr=cluster_addr,
        username="operator",
        vault=Credential(
            "hvs.vault",
            "vault-acc",
            now + timedelta(days=30),
            True,
            entity_id="351f302a",
            policies=("default",),
        ),
        nomad=Credential("nomad-tok", "nomad-acc", now + timedelta(minutes=25), True),
        nomad_manage=Credential(
            "nomad-manage-tok", "nomad-manage-acc", now + timedelta(minutes=25), True
        ),
        consul=Credential("consul-tok", "consul-acc", now + timedelta(minutes=25), True),
    )
    save(session, session_path())
    return session


@pytest.fixture
def healthy(cluster: FakeCluster) -> FakeCluster:
    cluster.routes[TOKEN_PATH] = (200, json.dumps({"data": {"token": "the.jwt.token"}}).encode())
    cluster.routes["/"] = (200, STS_REPLY)
    return cluster


def _invoke(cluster_addr: str) -> Result:
    return runner.invoke(app, ["token", "s3", "local-ov-sync", "--endpoint", cluster_addr])


def test_success_prints_only_three_export_lines(
    logged_in: Session, healthy: FakeCluster, cluster_addr: str
) -> None:
    result = _invoke(cluster_addr)
    assert result.exit_code == 0, result.stderr
    assert result.stdout == (
        "export AWS_ACCESS_KEY_ID=AKID\n"
        "export AWS_SECRET_ACCESS_KEY=SECRET\n"
        "export AWS_SESSION_TOKEN=SESSION\n"
    )
    assert "2026-11-27T18:15:00Z" in result.stderr


def test_success_mints_with_the_session_token_and_asks_sts_for_900_seconds(
    logged_in: Session, healthy: FakeCluster, cluster_addr: str
) -> None:
    _invoke(cluster_addr)
    [mint] = healthy.requests_for(TOKEN_PATH)
    assert mint.token == "hvs.vault"
    [sts] = healthy.requests_for("/")
    form = dict(urllib.parse.parse_qsl(sts.body.decode()))
    assert form["Action"] == "AssumeRoleWithWebIdentity"
    assert form["RoleArn"] == "arn:aws:iam::role/local-ov-sync"
    assert form["WebIdentityToken"] == "the.jwt.token"
    assert form["DurationSeconds"] == "900"


def test_vault_refusal_prints_nothing_and_exits_nonzero(
    logged_in: Session, healthy: FakeCluster, cluster_addr: str
) -> None:
    healthy.routes[TOKEN_PATH] = (403, b'{"errors":["permission denied"]}')
    result = _invoke(cluster_addr)
    assert result.exit_code != 0
    assert result.stdout == ""
    assert "local-ov-sync" in result.stderr
    assert healthy.requests_for("/") == []


def test_sts_refusal_prints_nothing_and_exits_nonzero(
    logged_in: Session, healthy: FakeCluster, cluster_addr: str
) -> None:
    healthy.routes["/"] = (403, b"<Error><Code>AccessDenied</Code></Error>")
    result = _invoke(cluster_addr)
    assert result.exit_code != 0
    assert result.stdout == ""
    assert "AccessDenied" in result.stderr


def test_success_works_for_any_role_name(
    logged_in: Session, healthy: FakeCluster, cluster_addr: str
) -> None:
    healthy.routes["/v1/identity/oidc/token/ci-other"] = healthy.routes[TOKEN_PATH]
    result = runner.invoke(app, ["token", "s3", "ci-other", "--endpoint", cluster_addr])
    assert result.exit_code == 0, result.stderr
    [sts] = healthy.requests_for("/")
    assert dict(urllib.parse.parse_qsl(sts.body.decode()))["RoleArn"] == (
        "arn:aws:iam::role/ci-other"
    )


def test_s3_without_a_role_is_refused_with_nothing_on_stdout(logged_in: Session) -> None:
    result = runner.invoke(app, ["token", "s3"])
    assert result.exit_code != 0
    assert result.stdout == ""
