"""The lab-auth action and the Vault roles it logs in to stay locked down.

The action is public, so anyone can call it. What a caller gets is decided by
the `jwt-github` roles in deployments/infrastructure/machine_roles.tf, one per
entry in `var.vault_ci_callers`. Terraform renders those roles offline here, so
the assertions read the claims Vault would be handed, not the source text.
"""

import base64
import json
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

import pytest
import yaml

# cli/tests/<this file> -> repo root is two up.
REPO_ROOT = Path(__file__).resolve().parents[2]
INFRA = REPO_ROOT / "deployments" / "infrastructure"
ACTION = REPO_ROOT / ".github" / "actions" / "lab-auth" / "action.yml"
WORKFLOWS = REPO_ROOT / ".github" / "workflows"
CHECK_WORKFLOW = WORKFLOWS / "lab-auth-check.yaml"

MOUNT = "jwt-github"
ROLE_HEADER = 'resource "vault_jwt_auth_backend_role" "github_ci" {'
VARIABLE_HEADER = 'variable "vault_ci_callers" {'
OV_SYNC_POLICY_HEADER = 'resource "vault_policy" "ci_ov_sync" {'
CLAIMS = ("repository", "ref", "environment", "workflow_ref")
LEGACY_CLIENT_ID = "T4Y1pq366F11CNTRL-kcbC29ubym11CNTRL"
IMMUTABLE_CLIENT_ID = "T4Y1pq366F11CNTRL-kysCUqvnvH11CNTRL"
APPLICATIONS = REPO_ROOT / "deployments" / "applications"


def _block(text: str, header: str) -> str:
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


def _console(workdir: Path, expression: str) -> Any:
    terraform = shutil.which("terraform")
    if terraform is None:
        pytest.fail("terraform is not on PATH; this test renders the roles with it")
    printed = subprocess.run(
        [terraform, "console"],
        input=f"jsonencode({expression})\n",
        cwd=workdir,
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    return json.loads(json.loads(printed))


@pytest.fixture(scope="module")
def rendered(tmp_path_factory: pytest.TempPathFactory) -> dict[str, Any]:
    """The default caller list and the role body Terraform builds for each entry."""
    variable = _block((INFRA / "variables.tf").read_text(), VARIABLE_HEADER)
    role = _block((INFRA / "machine_roles.tf").read_text(), ROLE_HEADER)
    body = role[len(ROLE_HEADER) : -1]
    if not re.search(r"^\s*for_each\s*=\s*var\.vault_ci_callers\s*$", body, re.M):
        pytest.fail("vault_jwt_auth_backend_role.github_ci is not one role per vault_ci_callers")
    body = re.sub(r"^\s*for_each\s*=.*$", "", body, flags=re.M)
    body = body.replace("vault_jwt_auth_backend.github.path", f'"{MOUNT}"')
    body = body.replace("each.key", "key").replace("each.value", "value")
    # The ov-sync policy's own name expression, so the role sees the name
    # Terraform would hand it.
    policy = _block((INFRA / "machine_roles.tf").read_text(), OV_SYNC_POLICY_HEADER)
    policy_name = re.search(r'^\s*name\s*=\s*("[^"\n]*")', policy, re.M)
    if not policy_name:
        pytest.fail("vault_policy.ci_ov_sync has no literal name")
    body = body.replace(
        "vault_policy.ci_ov_sync[key].name", policy_name.group(1).replace("each.key", "key")
    )
    workdir = tmp_path_factory.mktemp("lab-auth")
    (workdir / "main.tf").write_text(
        variable
        + "\nlocals {\n  roles = { for key, value in var.vault_ci_callers : key => {"
        + body
        + "} }\n}\n"
    )
    return {
        "callers": _console(workdir, "var.vault_ci_callers"),
        "roles": _console(workdir, "local.roles"),
    }


def _workflow_jobs_using_lab_auth() -> list[tuple[Path, dict[Any, Any], dict[str, Any]]]:
    found = []
    for path in sorted(WORKFLOWS.glob("*.y*ml")):
        workflow = yaml.safe_load(path.read_text())
        for job in (workflow.get("jobs") or {}).values():
            uses = [step.get("uses", "") for step in job.get("steps") or []]
            if any(".github/actions/lab-auth" in u for u in uses):
                found.append((path, workflow, job))
    return found


def _triggers(workflow: dict[Any, Any]) -> set[str]:
    # PyYAML reads the bare key `on` as the boolean True.
    on = workflow.get("on", workflow.get(True))
    if isinstance(on, str):
        return {on}
    return set(on or [])


def test_caller_roles_bind_all_four_claims(rendered: dict[str, Any]) -> None:
    other_roles = [
        path.name
        for path in INFRA.glob("*.tf")
        for header in re.findall(
            r'^resource "vault_jwt_auth_backend_role" "[^"]+" \{', path.read_text(), re.M
        )
        if header != ROLE_HEADER
        and re.search(
            rf'backend\s*=\s*("{MOUNT}"|vault_jwt_auth_backend\.github\.path)',
            _block(path.read_text(), header),
        )
    ]
    assert other_roles == [], f"a jwt-github role outside github_ci: {other_roles}"
    assert rendered["roles"], "no caller role rendered"
    for name, role in rendered["roles"].items():
        caller = rendered["callers"][name]
        assert role["backend"] == MOUNT
        assert role["role_name"] == name
        assert role["role_type"] == "jwt"
        assert role["bound_audiences"] == ["vault.io"], name
        assert role["bound_claims_type"] == "string", f"{name} matches claims by glob"
        assert set(CLAIMS) <= set(role["bound_claims"]), f"{name} drops a claim"
        workflow_ref = (
            f"{caller['repository']}/.github/workflows/{caller['workflow']}@{caller['ref']}"
        )
        assert role["bound_claims"] == {
            "repository": caller["repository"],
            "ref": caller["ref"],
            "environment": caller["environment"],
            "workflow_ref": workflow_ref,
        }
        ov_sync = [f"ci-ov-sync-{name}"] if caller["ov_sync"] else []
        assert role["token_policies"] == ["default", *ov_sync], name
        # 0 would fall back to the mount's default, which is Vault's 32 days.
        assert 0 < role["token_ttl"] < 3600, f"{name} token_ttl is not minutes"
        assert 0 < role["token_max_ttl"] < 3600, f"{name} token_max_ttl is not minutes"


def test_workflows_using_lab_auth_are_guarded() -> None:
    found = _workflow_jobs_using_lab_auth()
    assert CHECK_WORKFLOW in [path for path, _, _ in found]
    for path, workflow, job in found:
        triggers = _triggers(workflow)
        assert not triggers & {"pull_request", "pull_request_target"}, path.name
        assert job.get("environment"), f"{path.name} job has no environment"
        assert job.get("timeout-minutes"), f"{path.name} job has no timeout-minutes"
        permissions = job.get("permissions", workflow.get("permissions"))
        assert isinstance(permissions, dict), f"{path.name} has no explicit permissions"
        assert permissions.get("id-token") == "write", path.name


def test_action_shape() -> None:
    text = ACTION.read_text()
    action = yaml.safe_load(text)
    inputs = action["inputs"]
    assert action["runs"]["using"] == "composite"
    assert "secrets." not in text
    assert not [n for n in inputs if re.search(r"secret|key|token|password", n)], inputs
    assert "--accept-routes" not in text
    assert inputs["vault-role"]["required"] is True
    assert inputs["tailscale-client-id"]["default"] == ""
    assert inputs["tailscale-audience"]["default"] == ""
    assert inputs["tags"]["default"] == "tag:ci"

    steps = action["runs"]["steps"]
    join = [s for s in steps if s.get("uses", "").startswith("tailscale/github-action@")]
    assert len(join) == 1
    ref = join[0]["uses"].split("@", 1)[1]
    assert ref == "v4" or (re.fullmatch(r"[0-9a-f]{40}", ref) and f"@{ref} # v4" in text), join[0][
        "uses"
    ]
    with_ = join[0]["with"]
    assert with_.get("args", "") == ""
    assert {k: v for k, v in with_.items() if k != "args"} == {
        "oauth-client-id": "${{ steps.tailscale-identity.outputs.client-id }}",
        "audience": "${{ steps.tailscale-identity.outputs.audience }}",
        "tags": "${{ inputs.tags }}",
    }

    assert steps.index(_identity_step()) < steps.index(join[0])
    login = next(s for s in steps if s.get("id") == "login")
    script = login["run"]
    assert re.findall(r"audience=([^\"'&\s]+)", script) == ["vault.io"]
    assert login["env"]["VAULT_MOUNT"] == "${{ inputs.vault-mount }}"
    assert login["env"]["VAULT_ROLE"] == "${{ inputs.vault-role }}"
    assert "/v1/auth/${VAULT_MOUNT}/login" in script
    mask = script.find('echo "::add-mask::$token"')
    assert mask != -1, "the Vault token is not masked"
    exports = [
        script.find('echo "VAULT_TOKEN=$token" >> "$GITHUB_ENV"'),
        script.find('echo "VAULT_ADDR=$VAULT_ADDR" >> "$GITHUB_ENV"'),
        script.find('echo "vault-token=$token" >> "$GITHUB_OUTPUT"'),
    ]
    assert -1 not in exports, "VAULT_ADDR or VAULT_TOKEN is not exported"
    assert mask < min(exports), "the token is exported before it is masked"
    assert (
        action["outputs"]["vault-token"]["value"]
        == f"${{{{ steps.{login['id']}.outputs.vault-token }}}}"
    )
    assert action["outputs"]["vault-addr"]["value"] == "${{ inputs.vault-addr }}"


def test_default_callers(rendered: dict[str, Any]) -> None:
    assert list(rendered["callers"].values()) == [
        {
            "repository": "JasperHG90/localstack",
            "ref": "refs/heads/main",
            "environment": "lab",
            "workflow": "lab-auth-check.yaml",
            "ov_sync": False,
        },
        {
            "repository": "JasperHG90/localstack",
            "ref": "refs/heads/main",
            "environment": "lab",
            "workflow": "openviking-sync.yaml",
            "ov_sync": True,
        },
        {
            "repository": "JasperHG90/loop-engineering-harness",
            "ref": "refs/heads/main",
            "environment": "lab",
            "workflow": "openviking-sync.yaml",
            "ov_sync": True,
        },
    ]


def test_check_workflow_logs_in_with_its_caller_role(rendered: dict[str, Any]) -> None:
    (_, _, job), *_ = [f for f in _workflow_jobs_using_lab_auth() if f[0] == CHECK_WORKFLOW]
    step = next(s for s in job["steps"] if ".github/actions/lab-auth" in s.get("uses", ""))
    assert step["with"]["vault-role"] in rendered["callers"]


def _stub(bin_dir: Path, name: str, body: str) -> None:
    path = bin_dir / name
    path.write_text(f"#!/bin/sh\n{body}\n")
    path.chmod(0o755)


def test_check_step_survives_errexit(tmp_path: Path) -> None:
    """GitHub runs `shell: bash` as `bash -e -o pipefail`. A closed port's
    expected 124 from `timeout` must reach the step's `case`, not end it."""
    if shutil.which("jq") is None:
        pytest.fail("jq is not on PATH; the check cannot run")
    job = yaml.safe_load(CHECK_WORKFLOW.read_text())["jobs"]["check"]
    step = next(s for s in job["steps"] if s.get("name", "").startswith("Check the token"))
    script = tmp_path / "step.sh"
    script.write_text(step["run"])
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    _stub(bin_dir, "curl", "printf 200")
    _stub(bin_dir, "timeout", "exit 124")
    peers = {"Peer": {"a": {"HostName": "firebat", "TailscaleIPs": ["100.64.0.9"]}}}
    _stub(bin_dir, "tailscale", f"echo '{json.dumps(peers)}'")

    result = subprocess.run(
        ["bash", "--noprofile", "--norc", "-e", "-o", "pipefail", str(script)],
        capture_output=True,
        text=True,
        check=False,
        env={
            "PATH": f"{bin_dir}:/usr/bin:/bin:/usr/local/bin",
            "VAULT_ADDR": "https://vault.example",
            "VAULT_TOKEN": "t",
        },
    )

    assert result.stdout.count("timed out") == 5, result.stdout + result.stderr
    assert "OVERALL=PASS" in result.stdout
    assert result.returncode == 0


def test_login_fails_on_missing_oidc_value(tmp_path: Path) -> None:
    """An OIDC response with no `value` fails at the OIDC step, not later as a
    Vault refusal of the literal string null."""
    action = yaml.safe_load(ACTION.read_text())
    step = next(s for s in action["runs"]["steps"] if s.get("id") == "login")
    script = tmp_path / "login.sh"
    script.write_text(step["run"])
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    vault_called = tmp_path / "vault-called"
    _stub(
        bin_dir,
        "curl",
        f'case "$*" in *"/login"*) touch {vault_called}; cat >/dev/null ;; esac\necho "{{}}"',
    )

    result = subprocess.run(
        ["bash", "--noprofile", "--norc", "-e", "-o", "pipefail", str(script)],
        capture_output=True,
        text=True,
        check=False,
        env={
            "PATH": f"{bin_dir}:/usr/bin:/bin:/usr/local/bin",
            "ACTIONS_ID_TOKEN_REQUEST_URL": "https://oidc.example/token?x=1",
            "ACTIONS_ID_TOKEN_REQUEST_TOKEN": "t",
            "VAULT_ADDR": "https://vault.example",
            "VAULT_MOUNT": MOUNT,
            "VAULT_ROLE": "some-role",
            "GITHUB_ENV": str(tmp_path / "env"),
            "GITHUB_OUTPUT": str(tmp_path / "out"),
        },
    )

    assert result.returncode != 0
    assert not vault_called.exists()
    assert "::add-mask::null" not in result.stdout
    assert re.search(r"::error::.*OIDC token", result.stdout), result.stdout + result.stderr


def _identity_step() -> dict[str, Any]:
    action = yaml.safe_load(ACTION.read_text())
    return next(s for s in action["runs"]["steps"] if s.get("id") == "tailscale-identity")


def _jwt(sub: str) -> str:
    def part(claims: dict[str, str]) -> str:
        raw = base64.urlsafe_b64encode(json.dumps(claims).encode()).decode()
        return raw.rstrip("=")

    return f"{part({'alg': 'RS256'})}.{part({'sub': sub})}.sig"


def _run_identity_step(
    tmp_path: Path, sub: str, client_id: str = "", audience: str = ""
) -> tuple[subprocess.CompletedProcess[str], dict[str, str], bool]:
    script = tmp_path / "identity.sh"
    script.write_text(_identity_step()["run"])
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    called = tmp_path / "curl-called"
    _stub(bin_dir, "curl", f"touch {called}\necho '{json.dumps({'value': _jwt(sub)})}'")
    output = tmp_path / "out"
    result = subprocess.run(
        ["bash", "--noprofile", "--norc", "-e", "-o", "pipefail", str(script)],
        capture_output=True,
        text=True,
        check=False,
        env={
            "PATH": f"{bin_dir}:/usr/bin:/bin:/usr/local/bin",
            "ACTIONS_ID_TOKEN_REQUEST_URL": "https://oidc.example/token?x=1",
            "ACTIONS_ID_TOKEN_REQUEST_TOKEN": "t",
            "CLIENT_ID": client_id,
            "AUDIENCE": audience,
            "GITHUB_OUTPUT": str(output),
        },
    )
    outputs = dict(
        line.split("=", 1) for line in (output.read_text().splitlines() if output.exists() else [])
    )
    return result, outputs, called.exists()


@pytest.mark.parametrize(
    ("sub", "client_id"),
    [
        (
            "repo:JasperHG90@8079803/loop-engineering-harness@1405517573:environment:lab",
            IMMUTABLE_CLIENT_ID,
        ),
        ("repo:JasperHG90/localstack:environment:lab", LEGACY_CLIENT_ID),
    ],
)
def test_action_picks_credential_by_subject(tmp_path: Path, sub: str, client_id: str) -> None:
    if shutil.which("jq") is None:
        pytest.fail("jq is not on PATH; the check cannot run")
    result, outputs, _ = _run_identity_step(tmp_path, sub)

    assert result.returncode == 0, result.stdout + result.stderr
    assert outputs == {"client-id": client_id, "audience": f"api.tailscale.com/{client_id}"}
    assert "audience=vault.io" not in _identity_step()["run"]


@pytest.mark.parametrize(
    "sub",
    [
        "repo:JasperHG90@8079803/loop-engineering-harness@1405517573:environment:lab",
        "repo:JasperHG90/localstack:environment:lab",
    ],
)
def test_explicit_tailscale_inputs_override(tmp_path: Path, sub: str) -> None:
    result, outputs, called = _run_identity_step(
        tmp_path, sub, client_id="explicit-client", audience="explicit-audience"
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert outputs == {"client-id": "explicit-client", "audience": "explicit-audience"}
    assert not called, "the step fetched a token although both inputs were given"


def test_loop_engineering_harness_caller(rendered: dict[str, Any]) -> None:
    name = "loop-engineering-harness-openviking-sync"
    assert rendered["callers"][name]["ov_sync"] is True
    assert rendered["roles"][name]["bound_claims"] == {
        "repository": "JasperHG90/loop-engineering-harness",
        "ref": "refs/heads/main",
        "environment": "lab",
        "workflow_ref": (
            "JasperHG90/loop-engineering-harness/.github/workflows/"
            "openviking-sync.yaml@refs/heads/main"
        ),
    }


def test_ov_sync_prefix_map() -> None:
    text = (APPLICATIONS / "services.tf").read_text()
    block = re.search(r"prefixes\s*=\s*jsonencode\(\{(.*?)\}\)", text, re.S)
    assert block, "no prefixes map in deployments/applications/services.tf"
    pairs = dict(re.findall(r'"([^"]+)"\s*=\s*"([^"]+)"', block.group(1)))
    assert pairs == {
        "JasperHG90/localstack/": "viking://user/jasper/resources/projects/localstack/",
        "JasperHG90/loop-engineering-harness/": (
            "viking://user/jasper/resources/projects/loop-engineering-harness/"
        ),
        "JasperHG90/local/": "viking://user/jasper/resources/local/",
    }
