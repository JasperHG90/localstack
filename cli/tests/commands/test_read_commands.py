"""The four read commands end to end, over respx.

No live cluster and no real session: the session is replaced with a stub, so
what is under test is the command's own behavior rather than D2's login.
"""

import json
from pathlib import Path
from typing import Any

import httpx
import pytest
import respx
from typer.testing import CliRunner

from localstack_cli.main import app
from tests.fixtures.haproxy_cfg import FAKE_PASSWORD, LIVE_SHAPE
from tests.fixtures.policies import THREE_BLOCK

FIXTURES = Path(__file__).parent.parent / "fixtures" / "capture"
VAULT = "https://vault.test.invalid"
NOMAD = "https://nomad.test.invalid"
CONSUL = "https://consul.test.invalid"

runner = CliRunner()

# One path that exists, one that does not, and one the token cannot see.
SECRET_TEMPLATE = "".join(
    f'{{{{ with secret "secret/data/default/hermes/{name}" }}}}{{{{ end }}}}'
    for name in ("here", "gone", "hidden")
)


def payload(name: str) -> Any:
    return json.loads((FIXTURES / f"{name}.json").read_text())


class _Credential:
    def __init__(self, token: str) -> None:
        self.token = token


class _Session:
    def credential(self, service: str) -> Any:
        return _Credential(f"a-{service}-token")


@pytest.fixture(autouse=True)
def session(monkeypatch: pytest.MonkeyPatch) -> None:
    """A stub session, so these tests exercise D3 and not D2's login."""
    for module in ("status", "service", "secret", "vault"):
        monkeypatch.setattr(f"localstack_cli.commands.{module}.require_session", lambda: _Session())
        monkeypatch.setattr(f"localstack_cli.commands.{module}.refreshed_session", lambda s: s)
    monkeypatch.setenv("VAULT_ADDR", VAULT)
    monkeypatch.setenv("NOMAD_ADDR", NOMAD)
    monkeypatch.setenv("CONSUL_HTTP_ADDR", CONSUL)


def mock_cluster() -> None:
    respx.get(f"{VAULT}/v1/sys/health").mock(
        return_value=httpx.Response(
            200, json={"initialized": True, "sealed": False, "version": "9.9.9"}
        )
    )
    respx.get(f"{NOMAD}/v1/nodes").mock(return_value=httpx.Response(200, json=payload("nodes")))
    respx.get(f"{NOMAD}/v1/jobs/statuses").mock(
        return_value=httpx.Response(200, json=payload("jobs_statuses"))
    )
    respx.get(f"{CONSUL}/v1/health/state/any").mock(
        return_value=httpx.Response(200, json=payload("consul_health"))
    )
    respx.get(f"{CONSUL}/v1/catalog/services").mock(
        return_value=httpx.Response(200, json=payload("consul_catalog"))
    )


# An eleventh route matching no job, no catalog name and no tag. Appended to
# this module's own copy rather than to the shared `LIVE_SHAPE`, which
# `test_haproxy.py` pins at exactly ten routes by name.
ORPHAN_ROUTE = """
    acl is_orphan     hdr(host) -i orphan.lab.example
    use_backend orphan     if is_orphan

backend orphan
    server orphan1 10.0.0.99:1234 check
"""

EDGE_WITH_AN_ORPHAN = LIVE_SHAPE + ORPHAN_ROUTE


def mock_edge_job(config: str | None = None) -> None:
    """The haproxy job, carrying the routing table AND a credential."""
    respx.get(f"{NOMAD}/v1/job/haproxy").mock(
        return_value=httpx.Response(
            200,
            json={
                "TaskGroups": [
                    {
                        "Tasks": [
                            {
                                "Name": "haproxy",
                                "Templates": [
                                    {
                                        "DestPath": "local/haproxy.cfg",
                                        "EmbeddedTmpl": config or LIVE_SHAPE,
                                    }
                                ],
                            }
                        ]
                    }
                ]
            },
        )
    )


# -- status ------------------------------------------------------------------


@respx.mock
def test_status_renders_every_source() -> None:
    mock_cluster()

    result = runner.invoke(app, ["status"])

    assert result.exit_code == 0, result.output
    for source in ("vault", "nodes", "jobs", "consul"):
        assert source in result.stdout


def _last_request_header(path: str, header: str) -> str:
    """The named header on the last request to `path`, from respx's global
    call log.

    Deliberately NOT `respx.get(path)` a second time: re-registering an
    already-mocked route resets its response to the unconfigured default
    (200, empty body), silently breaking whatever mocked it first.
    """
    calls = [call for call in respx.calls if call.request.url.path == path]
    assert calls, f"no request was made to {path!r}"
    return str(calls[-1].request.headers[header])


@respx.mock
def test_status_uses_the_manage_credential_for_nodes_and_jobs() -> None:
    """`deploy` excludes `list-jobs`/`node:read`; only `manage` grants them."""
    mock_cluster()

    result = runner.invoke(app, ["status"])

    assert result.exit_code == 0, result.output
    assert _last_request_header("/v1/nodes", "X-Nomad-Token") == "a-nomad_manage-token"
    assert _last_request_header("/v1/jobs/statuses", "X-Nomad-Token") == "a-nomad_manage-token"


@respx.mock
def test_status_exits_non_zero_when_one_source_fails() -> None:
    """Three green panels from a swallowed timeout is the failure guarded."""
    mock_cluster()
    respx.get(f"{CONSUL}/v1/health/state/any").mock(side_effect=httpx.ConnectError("refused"))

    result = runner.invoke(app, ["status"])

    assert result.exit_code == 1
    assert "unsealed" in result.stdout
    assert "ERROR" in result.stdout


@respx.mock
def test_status_says_consul_is_acl_filtered() -> None:
    """A confident table built on a short list is false, and nothing shows it."""
    mock_cluster()

    result = runner.invoke(app, ["status"])

    assert "read with no token" in result.stdout


@respx.mock
def test_status_json_is_parseable() -> None:
    mock_cluster()

    result = runner.invoke(app, ["status", "--json"])

    assert json.loads(result.stdout)["vault"]["value"]["sealed"] is False


# -- service -----------------------------------------------------------------


@respx.mock
def test_service_uses_the_manage_credential_for_job_statuses() -> None:
    """`deploy` excludes `list-jobs`; only `manage` grants it."""
    mock_cluster()
    mock_edge_job()
    respx.get(url__regex=rf"{NOMAD}/v1/job/(?!haproxy)").mock(
        return_value=httpx.Response(200, json={"TaskGroups": []})
    )

    result = runner.invoke(app, ["service"])

    assert result.exit_code == 0, result.output
    assert _last_request_header("/v1/jobs/statuses", "X-Nomad-Token") == "a-nomad_manage-token"


@respx.mock
def test_service_renders_the_join() -> None:
    mock_cluster()
    mock_edge_job()
    respx.get(url__regex=rf"{NOMAD}/v1/job/(?!haproxy)").mock(
        return_value=httpx.Response(200, json={"TaskGroups": []})
    )

    result = runner.invoke(app, ["service"])

    assert result.exit_code == 0, result.output
    assert "s3" in result.stdout
    # `s3` resolves by tag now, so the unresolved case needs its own route.
    assert "consul-tag" in result.stdout


@respx.mock
def test_service_never_prints_the_jobspec_credential() -> None:
    """The running haproxy job carries a live password in its template."""
    mock_cluster()
    mock_edge_job()
    respx.get(url__regex=rf"{NOMAD}/v1/job/(?!haproxy)").mock(
        return_value=httpx.Response(200, json={"TaskGroups": []})
    )

    for argv in (["service"], ["service", "--json"]):
        result = runner.invoke(app, argv)
        assert FAKE_PASSWORD not in result.output
        assert "insecure-password" not in result.output


@respx.mock
def test_service_json_is_parseable() -> None:
    mock_cluster()
    # The orphan config, so `unresolved` is still exercised somewhere: `s3`
    # resolves by tag now and was this suite's only unresolved row.
    mock_edge_job(EDGE_WITH_AN_ORPHAN)
    respx.get(url__regex=rf"{NOMAD}/v1/job/(?!haproxy)").mock(
        return_value=httpx.Response(200, json={"TaskGroups": []})
    )

    result = runner.invoke(app, ["service", "--json"])

    rows = json.loads(result.stdout)
    assert {row["job_source"] for row in rows} >= {
        "job-id",
        "consul-tag",
        "no-route",
        "unresolved",
    }


@respx.mock
def test_service_open_prints_the_url_before_opening(monkeypatch: pytest.MonkeyPatch) -> None:
    """The browser launch is the part most likely to fail in a devcontainer."""
    mock_cluster()
    mock_edge_job()
    respx.get(url__regex=rf"{NOMAD}/v1/job/(?!haproxy)").mock(
        return_value=httpx.Response(200, json={"TaskGroups": []})
    )

    def explode(url: str, *args: Any, **kwargs: Any) -> bool:
        raise RuntimeError("no browser here")

    monkeypatch.setattr("webbrowser.open", explode)

    result = runner.invoke(app, ["service", "memex", "--open"])

    assert result.exit_code == 0, result.output
    assert "https://memex.lab.example" in result.stdout


@respx.mock
def test_service_brokers_no_token_for_the_consul_ui() -> None:
    """An explicit token REPLACES the agent default and shrinks the UI."""
    source = (
        Path(__file__).resolve().parents[2] / "src" / "localstack_cli" / "commands" / "service.py"
    ).read_text()

    assert "clipboard" not in source.lower()
    assert "OSC" not in source


# -- secret ------------------------------------------------------------------


def mock_job_with_secrets() -> None:
    respx.get(f"{NOMAD}/v1/job/hermes").mock(
        return_value=httpx.Response(
            200,
            json={
                "TaskGroups": [
                    {
                        "Tasks": [
                            {
                                "Name": "hermes",
                                "Templates": [
                                    {
                                        "DestPath": "secrets/env",
                                        "EmbeddedTmpl": SECRET_TEMPLATE,
                                    }
                                ],
                            }
                        ]
                    }
                ]
            },
        )
    )
    respx.get(f"{VAULT}/v1/secret/metadata/default/hermes/here").mock(
        return_value=httpx.Response(200, json={"data": {"current_version": 1}})
    )
    respx.get(f"{VAULT}/v1/secret/metadata/default/hermes/gone").mock(
        return_value=httpx.Response(404, json={"errors": []})
    )
    respx.get(f"{VAULT}/v1/secret/metadata/default/hermes/hidden").mock(
        return_value=httpx.Response(403, text="permission denied")
    )


@respx.mock
def test_secret_still_uses_the_deploy_credential() -> None:
    """Regression guard: `secret` only needs `read-job`, which `deploy`
    already grants, so it must not widen to `manage`."""
    mock_job_with_secrets()

    result = runner.invoke(app, ["secret", "hermes"])

    assert result.exit_code == 0, result.output
    assert _last_request_header("/v1/job/hermes", "X-Nomad-Token") == "a-nomad-token"


@respx.mock
def test_secret_reports_present_missing_and_denied_separately() -> None:
    """Folding denied into missing sends someone to write an existing secret."""
    mock_job_with_secrets()

    result = runner.invoke(app, ["secret", "hermes"])

    assert result.exit_code == 0, result.output
    assert "present" in result.stdout
    assert "missing" in result.stdout
    assert "denied" in result.stdout


@respx.mock
def test_secret_never_requests_the_data_endpoint() -> None:
    mock_job_with_secrets()
    data = respx.get(url__regex=rf"{VAULT}/v1/secret/data/").mock(
        return_value=httpx.Response(200, json={"data": {"data": {"password": "leaked"}}})
    )

    result = runner.invoke(app, ["secret", "hermes"])

    assert data.call_count == 0
    assert "leaked" not in result.output


@respx.mock
def test_secret_json_is_parseable() -> None:
    mock_job_with_secrets()

    result = runner.invoke(app, ["secret", "hermes", "--json"])

    states = {row["state"] for row in json.loads(result.stdout)}
    assert states == {"present", "missing", "denied"}


# -- vault grants ------------------------------------------------------------


@respx.mock
def test_vault_grants_resolves_the_template() -> None:
    respx.get(f"{VAULT}/v1/sys/policies/acl/nomad-workloads").mock(
        return_value=httpx.Response(200, json={"data": {"policy": THREE_BLOCK}})
    )

    result = runner.invoke(app, ["vault", "grants", "memex"])

    assert result.exit_code == 0, result.output
    assert "secret/data/default/memex" in result.stdout


@respx.mock
def test_vault_grants_says_it_is_not_an_authorization_decision() -> None:
    respx.get(f"{VAULT}/v1/sys/policies/acl/nomad-workloads").mock(
        return_value=httpx.Response(200, json={"data": {"policy": THREE_BLOCK}})
    )

    result = runner.invoke(app, ["vault", "grants", "memex"])

    assert "not an authorization decision" in result.stdout


@respx.mock
def test_vault_grants_json_is_parseable() -> None:
    respx.get(f"{VAULT}/v1/sys/policies/acl/nomad-workloads").mock(
        return_value=httpx.Response(200, json={"data": {"policy": THREE_BLOCK}})
    )

    result = runner.invoke(app, ["vault", "grants", "memex", "--json"])

    grants = json.loads(result.stdout)
    assert grants[0]["resolved_path"] == "secret/data/default/memex/*"


# -- the failure path --------------------------------------------------------


@respx.mock
def test_a_missing_grant_does_not_tell_you_to_log_in() -> None:
    """Logging in again changes nothing when the policy is the problem."""
    respx.get(f"{VAULT}/v1/sys/policies/acl/nomad-workloads").mock(
        return_value=httpx.Response(403, text=VAULT_DENIED)
    )
    respx.get(f"{VAULT}/v1/auth/token/lookup-self").mock(
        return_value=httpx.Response(200, json={"data": {}})
    )

    result = runner.invoke(app, ["vault", "grants", "memex"])

    assert result.exit_code == 1
    assert "sys/policies/acl" in result.output
    assert "Run `localstack login`" not in result.output


# Vault's real 403 body for a bad token, copied from the live cluster on
# 2026-08-03. An earlier version of these rows used Consul's phrasing, which
# Vault never sends, so they greened on a fiction.
VAULT_BAD_TOKEN = '{"errors":["2 errors occurred:\n\t* permission denied\n\t* invalid token\n\n"]}'
VAULT_DENIED = '{"errors":["1 error occurred:\n\t* permission denied\n\n"]}'


@respx.mock
def test_a_dead_session_does_tell_you_to_log_in() -> None:
    """Vault's own wording for a bad token, not a made-up one."""
    respx.get(f"{VAULT}/v1/sys/policies/acl/nomad-workloads").mock(
        return_value=httpx.Response(403, text=VAULT_BAD_TOKEN)
    )

    result = runner.invoke(app, ["vault", "grants", "memex"])

    assert result.exit_code == 1
    assert "localstack login" in result.output


@respx.mock
def test_a_dead_token_that_looks_like_a_policy_gap_still_says_log_in() -> None:
    """The blocker this row exists for.

    Vault answers 403 with a body that names no capability, so the fetch
    layer classifies it as a policy gap. The probe then finds the token does
    not authenticate, and the probe has to win: telling someone their policy
    is short when their session is dead is the same circle, reversed.
    """
    respx.get(f"{VAULT}/v1/sys/policies/acl/nomad-workloads").mock(
        return_value=httpx.Response(403, text=VAULT_DENIED)
    )
    respx.get(f"{VAULT}/v1/auth/token/lookup-self").mock(
        return_value=httpx.Response(403, text=VAULT_BAD_TOKEN)
    )

    result = runner.invoke(app, ["vault", "grants", "memex"])

    assert result.exit_code == 1
    assert "does not authenticate" in result.output
    assert "localstack login" in result.output
    assert "will not change it" not in result.output


@respx.mock
def test_a_denied_job_list_names_list_jobs_not_login() -> None:
    """The live shape under a brokered `deploy` token.

    `read-job` is granted, so the single-job read works; `list-jobs` is not,
    so the job list is refused. That combination proves the token
    authenticates and the policy is short, which is the opposite of a dead
    session.
    """
    mock_cluster()
    mock_edge_job()
    respx.get(url__regex=rf"{NOMAD}/v1/job/(?!haproxy)").mock(
        return_value=httpx.Response(200, json={"TaskGroups": []})
    )
    respx.get(f"{NOMAD}/v1/jobs/statuses").mock(
        return_value=httpx.Response(403, text="Permission denied")
    )

    result = runner.invoke(app, ["service"])

    assert result.exit_code == 1
    assert "list-jobs" in result.output
    assert "the session is live" in result.output
    assert "Run `localstack login`" not in result.output


# -- the command surface -----------------------------------------------------


@pytest.mark.parametrize("cut", ["jobs", "mounts", "policies", "kv", "services"])
def test_no_native_cli_mirror_was_added(cut: str) -> None:
    """The operator cut seven mirror commands. None may come back.

    Checked against the REGISTERED names, not the help prose: `jobs` appears
    in a perfectly good help sentence and would fail a substring match.
    """
    from localstack_cli._lazy import LAZY_SUBCOMMANDS

    assert cut not in LAZY_SUBCOMMANDS


def test_the_four_commands_are_registered() -> None:
    result = runner.invoke(app, ["--help"])

    for name in ("status", "service", "secret", "vault"):
        assert name in result.stdout


def test_vault_has_exactly_one_subcommand() -> None:
    result = runner.invoke(app, ["vault", "--help"])

    assert "grants" in result.stdout
    for cut in ("mounts", "policies", "kv"):
        assert cut not in result.stdout


@respx.mock
def test_a_denied_nomad_read_probes_a_known_job_before_blaming_the_session() -> None:
    """Requirement 13's Nomad probe, and it only runs after a 403.

    A 403 on the read while a single known job still reads proves the token
    authenticates and simply lacks the capability.
    """
    mock_cluster()
    haproxy_route = respx.get(f"{NOMAD}/v1/job/haproxy")
    haproxy_route.mock(
        side_effect=[
            httpx.Response(403, text="Permission denied"),
            httpx.Response(200, json={"TaskGroups": []}),
        ]
    )

    result = runner.invoke(app, ["service"])

    assert result.exit_code == 1
    assert "the session is live" in result.output
    assert "Run `localstack login`" not in result.output
    # Two calls: the real read, then the probe. Never on the success path.
    assert haproxy_route.call_count == 2


@respx.mock
def test_the_probe_does_not_run_when_the_read_succeeds() -> None:
    """The diagnostic calls are for the 403 path only."""
    mock_cluster()
    edge = respx.get(f"{NOMAD}/v1/job/haproxy").mock(
        return_value=httpx.Response(
            200,
            json={
                "TaskGroups": [
                    {
                        "Tasks": [
                            {
                                "Name": "haproxy",
                                "Templates": [
                                    {"DestPath": "local/haproxy.cfg", "EmbeddedTmpl": LIVE_SHAPE}
                                ],
                            }
                        ]
                    }
                ]
            },
        )
    )
    respx.get(url__regex=rf"{NOMAD}/v1/job/(?!haproxy)").mock(
        return_value=httpx.Response(200, json={"TaskGroups": []})
    )
    lookup = respx.get(f"{VAULT}/v1/auth/token/lookup-self").mock(
        return_value=httpx.Response(200, json={"data": {}})
    )

    result = runner.invoke(app, ["service"])

    assert result.exit_code == 0
    assert edge.call_count == 1
    assert lookup.call_count == 0


@respx.mock
def test_a_nomad_denial_is_never_reported_as_a_dead_session() -> None:
    """The over-correction the last review caught.

    Nomad's dead-token case is classified upstream by its body. So a failed
    probe here is almost always a second policy gap, and reading it as "your
    session is dead" is the same wrong turn, reversed again. It must produce
    the neutral message instead.
    """
    mock_cluster()
    respx.get(url__regex=rf"{NOMAD}/v1/job/").mock(
        return_value=httpx.Response(403, text="Permission denied")
    )

    result = runner.invoke(app, ["secret", "hermes"])

    assert result.exit_code == 1
    assert "does not authenticate" not in result.output
    assert "Run `localstack login`" not in result.output
    assert "read-job" in result.output


@respx.mock
def test_the_probe_does_not_re_issue_the_call_that_just_failed() -> None:
    """A probe against the same resource has its answer decided in advance."""
    mock_cluster()
    hermes = respx.get(f"{NOMAD}/v1/job/hermes").mock(
        return_value=httpx.Response(403, text="Permission denied")
    )
    respx.get(url__regex=rf"{NOMAD}/v1/job/(?!hermes)").mock(
        return_value=httpx.Response(200, json={"TaskGroups": []})
    )

    result = runner.invoke(app, ["secret", "hermes"])

    assert result.exit_code == 1
    assert hermes.call_count == 1
    # The probe went to a different job and succeeded, so this is a policy
    # gap and the message says so.
    assert "the session is live" in result.output


@respx.mock
def test_consul_resolves_from_the_catalog_not_from_health_checks() -> None:
    """The reported defect, through the command.

    Consul registers itself in the catalog but its only check is a node-level
    `serfHealth` with an empty `ServiceName`, so a rung keyed on checks misses
    it and the row falls to `unresolved`.

    This is the red-first row: it goes red against the pre-fix code for the
    right reason (the `job_source` is wrong, nothing raises). The `join()`
    level test cannot, because pre-fix `join()` does not accept a catalog
    argument at all and would only raise `TypeError`.
    """
    mock_cluster()
    mock_edge_job()
    respx.get(url__regex=rf"{NOMAD}/v1/job/(?!haproxy)").mock(
        return_value=httpx.Response(200, json={"TaskGroups": []})
    )

    result = runner.invoke(app, ["service", "--json"])

    rows = {row["name"]: row for row in json.loads(result.stdout)}
    assert rows["consul"]["job_source"] == "consul-name"
    # The two that resolve today must keep resolving.
    assert rows["vault"]["job_source"] == "consul-name"
    assert rows["nomad"]["job_source"] == "consul-name"


@respx.mock
def test_the_table_says_where_an_unresolved_row_points() -> None:
    """Row 5. The dataclass carried the backend and `--json` emitted it, but
    the table dropped it, so the rows with the least resolved information
    showed the least on screen.
    """
    mock_cluster()
    # `s3` used to be this test's subject, but it now resolves by tag, which
    # would leave this passing while exercising no unresolved row at all.
    mock_edge_job(EDGE_WITH_AN_ORPHAN)
    respx.get(url__regex=rf"{NOMAD}/v1/job/(?!haproxy)").mock(
        return_value=httpx.Response(200, json={"TaskGroups": []})
    )

    result = runner.invoke(app, ["service", "--json"])
    rows = {row["name"]: row for row in json.loads(result.stdout)}

    assert rows["orphan"]["job_source"] == "unresolved"
    assert rows["orphan"]["backend"] == "10.0.0.99:1234"

    table = runner.invoke(app, ["service"])
    assert "backend" in table.stdout
    assert "10.0.0.99:1234" in table.stdout.replace(" ", "")


@respx.mock
def test_s3_resolves_to_minio_by_tag() -> None:
    """Row 5. `s3` is MinIO's S3 API port; the job declares the tag."""
    mock_cluster()
    mock_edge_job()
    respx.get(url__regex=rf"{NOMAD}/v1/job/(?!haproxy)").mock(
        return_value=httpx.Response(200, json={"TaskGroups": []})
    )

    result = runner.invoke(app, ["service", "--json"])

    rows = {row["name"]: row for row in json.loads(result.stdout)}
    assert rows["s3"]["job_source"] == "consul-tag"
    assert rows["s3"]["job"] == "minio"
    # The `minio` route is untouched, and the job is neither suppressed nor
    # duplicated by the tag match.
    assert rows["minio"]["job_source"] == "job-id"
    assert len([r for r in json.loads(result.stdout) if r["job"] == "minio"]) == 2
