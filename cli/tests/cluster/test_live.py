"""The read commands against the real cluster.

Marked `cluster` and excluded from the default run:

    uv run --project cli pytest -m cluster

Over the HTTPS edge, which answers from the LAN and the tailnet and survives
the firewall change that closes the plaintext ports.
"""

import os

import pytest

from localstack_cli.api import consul, grants, haproxy, nomad, vault
from localstack_cli.api.errors import ClusterError

pytestmark = pytest.mark.cluster

EDGE_VAULT = "https://vault.lab.orangecluster.nl"
EDGE_NOMAD = "https://nomad.lab.orangecluster.nl"
EDGE_CONSUL = "https://consul.lab.orangecluster.nl"


def nomad_token() -> str:
    token = os.environ.get("NOMAD_TOKEN")
    if not token:
        pytest.skip("no NOMAD_TOKEN in the environment")
    return token


def vault_token() -> str:
    token = os.environ.get("VAULT_TOKEN")
    if not token:
        pytest.skip("no VAULT_TOKEN in the environment")
    return token


def test_vault_health_needs_no_token() -> None:
    assert vault.health(EDGE_VAULT, timeout=10).initialized


def test_consul_health_reads_tokenless() -> None:
    assert consul.list_checks(EDGE_CONSUL, timeout=10)


def test_the_routing_table_parses_from_the_job_api() -> None:
    """Not from `deployments/`: that file is an unrendered Terraform input."""
    templates = nomad.job_templates(EDGE_NOMAD, nomad_token(), "haproxy", timeout=10)
    config = next(t for t in templates if t.dest_path == "local/haproxy.cfg")

    routes = haproxy.parse_routes(config.text)

    assert len(routes) >= 10
    assert {"vault", "nomad", "consul", "s3"} <= {route.name for route in routes}


def test_no_live_credential_reaches_a_parsed_route() -> None:
    """The running jobspec carries the real basic-auth password."""
    templates = nomad.job_templates(EDGE_NOMAD, nomad_token(), "haproxy", timeout=10)
    config = next(t for t in templates if t.dest_path == "local/haproxy.cfg")
    assert "insecure-password" in config.text, "the fixture premise has changed"

    rendered = repr(haproxy.parse_routes(config.text))

    assert "insecure-password" not in rendered


def test_the_workload_policy_renders_for_a_real_job() -> None:
    text = vault.read_policy(EDGE_VAULT, vault_token(), "nomad-workloads", timeout=10)

    resolved = grants.render(text, {"nomad_namespace": "default", "nomad_job_id": "memex"})

    assert resolved
    assert grants.accessor(text) is not None
    assert all(not grant.unresolved for grant in resolved)


def test_a_jobs_referenced_secret_paths_resolve() -> None:
    from localstack_cli.api import secrets

    templates = nomad.job_templates(EDGE_NOMAD, nomad_token(), "memex", timeout=10)
    found = secrets.references([(t.task, t.text) for t in templates])
    if not found:
        pytest.skip("memex references no Vault paths")

    for reference in found:
        state = vault.metadata_exists(
            EDGE_VAULT, vault_token(), secrets.kv2_metadata_path(reference.path), timeout=10
        )
        assert state in {"present", "missing", "denied"}


def test_a_denied_read_is_reported_not_raised_as_something_else() -> None:
    """A token with no grants must produce a typed denial, not a crash."""
    with pytest.raises(ClusterError):
        vault.read_policy(EDGE_VAULT, "not-a-real-token", "nomad-workloads", timeout=10)


def test_consul_is_in_the_catalog_but_carries_no_health_check() -> None:
    """Row 8. The one fact the catalog fix rests on.

    It is a fact about how Consul registers itself, not about this repo, so
    a future Consul that adds a self-check makes the fix pointless. This
    goes red then, instead of the fix quietly doing nothing.
    """
    catalog = consul.list_services(EDGE_CONSUL, timeout=10)
    checks = consul.list_checks(EDGE_CONSUL, timeout=10)

    assert "consul" in catalog
    assert [c for c in checks if c.service == "consul"] == []


def test_the_minio_service_still_carries_the_s3_tag() -> None:
    """The tag the `s3` route resolves on, and its uniqueness.

    If this goes red the `s3` row reverts to `unresolved`, which is the
    honest answer, but it should be a known change rather than a mystery.
    """
    catalog = consul.list_services(EDGE_CONSUL, timeout=10)

    assert "s3" in catalog.get("minio", [])
    assert [name for name, tags in catalog.items() if "s3" in tags] == ["minio"]


def test_every_live_route_name_has_at_most_one_tag_carrier() -> None:
    """The tag rung is unambiguous for every route the edge actually serves.

    A tag carried by two services resolves nothing by design, so this going
    red means a row silently stopped resolving. Better to say so here.
    """
    templates = nomad.job_templates(EDGE_NOMAD, nomad_token(), "haproxy", timeout=10)
    config = next(t for t in templates if t.dest_path == "local/haproxy.cfg")
    routes = haproxy.parse_routes(config.text)
    catalog = consul.list_services(EDGE_CONSUL, timeout=10)

    ambiguous = {
        route.name: [name for name, tags in catalog.items() if route.name in tags]
        for route in routes
    }

    assert {name: c for name, c in ambiguous.items() if len(c) > 1} == {}
    assert ambiguous["s3"] == ["minio"]


def test_s3_resolves_to_minio_against_the_real_cluster() -> None:
    """The whole point of the ticket, end to end."""
    from localstack_cli.api import services

    templates = nomad.job_templates(EDGE_NOMAD, nomad_token(), "haproxy", timeout=10)
    config = next(t for t in templates if t.dest_path == "local/haproxy.cfg")
    routes = haproxy.parse_routes(config.text)
    jobs = nomad.job_statuses(EDGE_NOMAD, nomad_token(), timeout=10)
    checks = consul.list_checks(EDGE_CONSUL, timeout=10)
    catalog = consul.list_services(EDGE_CONSUL, timeout=10)

    rows = {r.name: r for r in services.join(routes, jobs, checks, {}, catalog=catalog)}

    assert rows["s3"].job_source is services.JobSource.CONSUL_TAG
    assert rows["s3"].job == "minio"
