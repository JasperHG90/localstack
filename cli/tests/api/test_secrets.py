"""Which Vault paths a job asks for, including the ones that are not there."""

from localstack_cli.api.secrets import State, kv2_metadata_path, references

# The live shape: every reference on this cluster is a static literal today.
LITERAL_TEMPLATE = """
{{ with secret "secret/data/default/hermes/github" }}
GITHUB_TOKEN={{ .Data.data.token }}
{{ end }}
{{ with secret "secret/data/default/hermes/db" }}
DB_PASSWORD={{ .Data.data.password }}
{{ end }}
"""

COMPUTED_TEMPLATE = """
{{ with secret (printf "secret/data/default/%s/creds" (env "NOMAD_JOB_NAME")) }}
KEY={{ .Data.data.key }}
{{ end }}
"""

# A template carrying a rendered credential, as the haproxy job's does.
TEMPLATE_WITH_A_SECRET_IN_IT = """
user admin insecure-password not-a-real-password-0000
{{ with secret "secret/data/default/edge/tls" }}{{ .Data.data.cert }}{{ end }}
"""


def test_literal_paths_are_extracted() -> None:
    found = references([("hermes", LITERAL_TEMPLATE)])

    assert [ref.path for ref in found] == [
        "secret/data/default/hermes/db",
        "secret/data/default/hermes/github",
    ]


def test_the_referencing_task_is_kept() -> None:
    found = references([("hermes", LITERAL_TEMPLATE)])

    assert {ref.task for ref in found} == {"hermes"}


def test_paths_are_deduplicated_across_tasks() -> None:
    """A path used by three tasks is one row, not three."""
    found = references([("one", LITERAL_TEMPLATE), ("two", LITERAL_TEMPLATE)])

    assert len(found) == 2


def test_a_computed_reference_is_kept_and_flagged_unknown() -> None:
    """A shrinking table is a worse lie than an incomplete one."""
    found = references([("hermes", COMPUTED_TEMPLATE)])

    assert len(found) == 1
    assert found[0].state is State.UNKNOWN
    assert "hermes" in found[0].path


def test_a_job_with_no_references_yields_nothing() -> None:
    assert references([("x", "no secrets here")]) == []


def test_only_the_path_crosses_the_boundary() -> None:
    """The surrounding template text can carry a rendered credential."""
    found = references([("edge", TEMPLATE_WITH_A_SECRET_IN_IT)])

    assert [ref.path for ref in found] == ["secret/data/default/edge/tls"]
    for ref in found:
        assert "insecure-password" not in ref.path
        assert "not-a-real-password-0000" not in repr(ref)


def test_the_metadata_path_is_derived_not_guessed() -> None:
    """KV2 splits reads and metadata across two prefixes on one mount."""
    assert (
        kv2_metadata_path("secret/data/default/hermes/github")
        == "secret/metadata/default/hermes/github"
    )


def test_only_the_first_data_segment_is_rewritten() -> None:
    """A path whose own name contains `/data/` must not be mangled twice."""
    assert (
        kv2_metadata_path("secret/data/default/app/data/thing")
        == "secret/metadata/default/app/data/thing"
    )
