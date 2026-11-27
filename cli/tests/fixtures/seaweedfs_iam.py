"""Render SeaweedFS's IAM config the way the job does, offline.

Terraform evaluates `local.seaweedfs_iam` (deployments/infrastructure/services.tf)
and the seaweedfs jobspec template with the Vault resource paths swapped for
literals and a stand-in signing key. The result is the JSON SeaweedFS loads.
"""

import json
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

import pytest

# cli/tests/fixtures/<this file> -> repo root is three up.
REPO_ROOT = Path(__file__).resolve().parents[3]
INFRA = REPO_ROOT / "deployments" / "infrastructure"
JOBSPEC = INFRA / "services" / "seaweedfs.hcl"
STS_SECRET = "secret/data/default/seaweedfs/sts"
SIGNING_KEY = "c3RhbmQtaW4="
CALLERS_HEADER = 'variable "vault_ci_callers" {'
OPERATOR_ENTITY_ID = "operator-entity-id"


def block(text: str, header: str) -> str:
    """The block opened by `header`, found by brace depth."""
    start = text.find(header)
    if start == -1:
        pytest.fail(f"no `{header}` block; the check cannot run")
    depth = 0
    for i in range(start, len(text)):
        depth += {"{": 1, "}": -1}.get(text[i], 0)
        if depth == 0 and text[i] == "}":
            return text[start : i + 1]
    pytest.fail(f"`{header}` block never closes")


def render_iam(workdir: Path) -> dict[str, Any]:
    terraform = shutil.which("terraform")
    if terraform is None:
        pytest.fail("terraform is not on PATH; this test renders the config with it")
    services = (INFRA / "services.tf").read_text()
    locals_block = re.search(r"^locals \{\n  seaweedfs_keyless_jobs.*?^\}\n", services, re.M | re.S)
    job = re.search(r'^resource "nomad_job" "seaweedfs" \{\n(.*?)^\}\n', services, re.M | re.S)
    if not locals_block or not job:
        pytest.fail("services.tf has no seaweedfs_keyless_jobs locals or no nomad_job.seaweedfs")
    sts_name = re.search(
        r'resource "vault_kv_secret_v2" "seaweedfs_sts" \{[^}]*name\s*=\s*"([^"]+)"',
        (INFRA / "secrets.tf").read_text(),
    )
    assert sts_name and f"secret/data/{sts_name.group(1)}" == STS_SECRET, (
        "the STS signing key is not written to default/seaweedfs/sts"
    )
    # nomad_job.seaweedfs's own templatefile call, with its resource
    # references swapped for the paths they resolve to.
    call = (
        job.group(1)
        .replace("vault_kv_secret_v2.seaweedfs_sts.path", f'"{STS_SECRET}"')
        .replace("vault_kv_secret_v2.seaweedfs_admin.path", '"secret/data/default/seaweedfs/admin"')
        .replace(
            "vault_kv_secret_v2.seaweedfs_webhook.path", '"secret/data/default/seaweedfs/webhook"'
        )
        .replace("jobspec = templatefile(", "rendered = templatefile(", 1)
    )
    if "vault_kv_secret_v2." in call:
        pytest.fail("nomad_job.seaweedfs passes a resource reference this test does not resolve")
    callers = block((INFRA / "variables.tf").read_text(), CALLERS_HEADER)
    # The operator entity's id exists only after apply.
    locals_text = locals_block.group(0).replace(
        "vault_identity_entity.operator.id", f'"{OPERATOR_ENTITY_ID}"'
    )
    (workdir / "services").mkdir()
    shutil.copy(JOBSPEC, workdir / "services" / "seaweedfs.hcl")
    (workdir / "main.tf").write_text(callers + "\n" + locals_text + "\nlocals {\n" + call + "}\n")
    # jsonencode makes the console print one JSON string literal.
    printed = subprocess.run(
        [terraform, "console"],
        input="jsonencode(local.rendered)\n",
        cwd=workdir,
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    jobspec = json.loads(json.loads(printed))
    template = re.search(
        r"data\s*=\s*<<-EOH\n\s*(\{\{ with secret[^\n]*)\n\s*EOH\n"
        r'\s*destination\s*=\s*"secrets/iam\.json"',
        jobspec,
        re.S,
    )
    if not template:
        pytest.fail("seaweedfs.hcl renders no template with destination secrets/iam.json")
    body = template.group(1)
    opener = f'{{{{ with secret "{STS_SECRET}" }}}}'
    assert body.startswith(opener), (
        "the IAM config does not read its signing key from default/seaweedfs/sts"
    )
    body = body.removeprefix(opener).removesuffix("{{ end }}")
    config: dict[str, Any] = json.loads(body.replace("{{ .Data.data.signing_key }}", SIGNING_KEY))
    return config
