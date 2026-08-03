"""Two shapes of the `nomad-workloads` policy.

`THREE_BLOCK` is what live Vault serves today, captured 2026-08-03.
`SIX_BLOCK` is the pre-F9 form. Neither is "the live one" for testing
purposes: the point is that the renderer works against both, because this
policy has already changed block count once and will again.

The accessor here is made up. The real one is derived at bootstrap from
`vault auth list` and differs per rebuild, so a fixture carrying it would
teach the wrong lesson.

The paths are assembled rather than written out because a rendered one runs
past 170 characters, which is unreadable in a diff and trips the line-length
gate.
"""

ACCESSOR = "auth_jwt_deadbeef"


def var(key: str) -> str:
    """One `{{identity.entity.aliases.<accessor>.metadata.<key>}}` reference."""
    return "{{identity.entity.aliases." + ACCESSOR + ".metadata." + key + "}}"


NAMESPACE = var("nomad_namespace")
JOB_ID = var("nomad_job_id")
REGION = var("nomad_region")


def block(path: str, capabilities: str) -> str:
    return f'path "{path}" {{\n  capabilities = [{capabilities}]\n}}\n'


THREE_BLOCK = "\n".join(
    [
        block(f"secret/data/{NAMESPACE}/{JOB_ID}/*", '"read"'),
        block(f"secret/data/{NAMESPACE}/{JOB_ID}", '"read"'),
        block(f"secret/metadata/{NAMESPACE}/*", '"list"'),
        "# A trailing comment block, as the live policy carries.\n",
    ]
)

SIX_BLOCK = "\n".join(
    [
        THREE_BLOCK,
        block("secret/metadata/*", '"list"'),
        block("bootstrap/data/*", '"read", "create", "update"'),
        block("bootstrap/metadata/*", '"list"'),
    ]
)

# A future variable this command cannot fill from its arguments.
WITH_UNKNOWN_VARIABLE = block(f"secret/data/{NAMESPACE}/{REGION}/*", '"read"')
