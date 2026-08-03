"""`localstack secret <service>`: which Vault paths a job wants, and are they there.

The question is "why will this job not render its template", so the answer
has to include the paths that are NOT there. A table of only the paths that
resolve turns a broken job into an empty, healthy-looking view.

Three states, never two. `denied` is not `missing`: telling someone their
secret does not exist when they simply cannot see it sends them to write one
that is already there.

No value is ever read. Existence comes from `secret/metadata/`, which carries
versions and timestamps and no `data` field at all.
"""

import typer

from localstack_cli.api import nomad, secrets, vault
from localstack_cli.api.errors import ClusterError
from localstack_cli.commands._common import fail, refreshed_session, require_session
from localstack_cli.commands._session import explain
from localstack_cli.commands.render import emit_json, table
from localstack_cli.config import Config, ConfigError

app = typer.Typer()


@app.command()
def secret(
    service: str = typer.Argument(..., help="The Nomad job to inspect."),
    as_json: bool = typer.Option(False, "--json", help="Emit the result as JSON."),
) -> None:
    """List the Vault paths a job's templates reference, and whether they exist."""
    try:
        config = Config.from_env()
    except ConfigError as error:
        raise fail(str(error)) from error

    session = refreshed_session(require_session())
    nomad_entry = session.credential("nomad")
    vault_entry = session.credential("vault")
    vault_token = vault_entry.token if vault_entry else None

    try:
        templates = nomad.job_templates(
            config.nomad_addr, nomad_entry.token if nomad_entry else None, service
        )
    except ClusterError as error:
        raise explain(
            error,
            config.vault_addr,
            vault_token,
            nomad_addr=config.nomad_addr,
            nomad_token=nomad_entry.token if nomad_entry else None,
        ) from error

    # Only the extracted path strings cross this line. A jobspec template can
    # carry a rendered credential, so the text stays inside the extractor.
    found = secrets.references([(t.task, t.text) for t in templates])
    if not found:
        raise fail(f"{service} references no Vault paths.")

    resolved = []
    for reference in found:
        if reference.state is secrets.State.UNKNOWN:
            resolved.append(reference)
            continue
        metadata = secrets.kv2_metadata_path(reference.path)
        if vault_token is None:
            raise fail("no Vault token in the session. Run `localstack login`.")
        state = vault.metadata_exists(config.vault_addr, vault_token, metadata)
        resolved.append(
            secrets.SecretRef(path=reference.path, task=reference.task, state=secrets.State(state))
        )

    if as_json:
        emit_json(resolved)
        return

    table(
        f"vault paths referenced by {service}",
        ["path", "task", "state"],
        [[r.path, r.task, r.state.value] for r in resolved],
    )
