"""The openviking-sync action mirrors a repo's folders into its own ov-sync prefix.

`sync.py` runs against a real git repository under `tmp_path`, with a stub
`aws` first on PATH. The stub keeps the bucket as a directory, so a later run
sees what an earlier one wrote, and fails the calls a test names. The workflow
and the SeaweedFS IAM config are read the way GitHub and SeaweedFS read them.
"""

import hashlib
import importlib.util
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
import yaml

from tests.fixtures.seaweedfs_iam import REPO_ROOT, render_iam

SYNC = REPO_ROOT / ".github" / "actions" / "openviking-sync" / "sync.py"
WORKFLOW = REPO_ROOT / ".github" / "workflows" / "openviking-sync.yaml"
BUCKET = "ov-sync"
PREFIX = "JasperHG90/localstack/"
MANIFEST = PREFIX + "_state/manifest.json"

# A stand-in for the three `aws s3api` calls sync.py makes. It appends one
# JSON line per call to $AWS_STUB_LOG, keeps objects under $AWS_STUB_ROOT, and
# fails any call listed in $AWS_STUB_FAIL as "<op> <key>" lines. Writing the
# key in $AWS_STUB_KILL_ON kills its whole process group, as a job timeout
# kills the run.
STUB = """#!{python}
import json, os, shutil, sys
from pathlib import Path

argv = sys.argv[1:]
op = argv[argv.index("s3api") + 1]
opt = {{argv[i]: argv[i + 1] for i in range(len(argv) - 1) if argv[i].startswith("--")}}
key = opt["--key"]
with open(os.environ["AWS_STUB_LOG"], "a") as log:
    log.write(json.dumps({{"op": op, "key": key, "endpoint": opt.get("--endpoint-url")}}) + "\\n")
if f"{{op}} {{key}}" in os.environ.get("AWS_STUB_FAIL", "").splitlines():
    print(f"An error occurred (InternalError) when calling {{op}}", file=sys.stderr)
    sys.exit(254)
obj = Path(os.environ["AWS_STUB_ROOT"]) / opt["--bucket"] / key
if op == "get-object":
    if not obj.is_file():
        print("An error occurred (NoSuchKey) when calling the GetObject operation: "
              "The specified key does not exist.", file=sys.stderr)
        sys.exit(254)
    shutil.copyfile(obj, argv[-1])
elif op == "put-object":
    obj.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(opt["--body"], obj)
    if os.environ.get("AWS_STUB_KILL_ON") == key:
        os.killpg(0, 9)
elif op == "delete-object":
    obj.unlink(missing_ok=True)
print("{{}}")
"""


class Lab:
    """A git repository, the stub bucket, and the log of every aws call."""

    def __init__(self, tmp_path: Path) -> None:
        self.repo = tmp_path / "repo"
        self.root = tmp_path / "s3"
        self.log = tmp_path / "aws.log"
        bin_dir = tmp_path / "bin"
        bin_dir.mkdir()
        stub = bin_dir / "aws"
        stub.write_text(STUB.format(python=sys.executable))
        stub.chmod(0o755)
        self.env = {
            **os.environ,
            "PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}",
            "AWS_STUB_LOG": str(self.log),
            "AWS_STUB_ROOT": str(self.root),
        }
        self.repo.mkdir()
        self.git("init", "-q")
        self.git("config", "user.email", "test@example.com")
        self.git("config", "user.name", "test")
        self.write("docs/a.md", "a\n")
        self.write("docs/b.md", "b\n")
        self.write(".okf/index.md", "index\n")
        self.write("other/x.md", "outside the synced folders\n")
        self.commit("docs", ".okf", "other")

    def git(self, *args: str) -> None:
        subprocess.run(["git", *args], cwd=self.repo, check=True, capture_output=True)

    def write(self, path: str, text: str) -> None:
        target = self.repo / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text)

    def commit(self, *new: str) -> None:
        self.git("add", "-u")
        if new:
            self.git("add", *new)
        self.git("commit", "-q", "-m", "change")

    def sync(
        self, fail: tuple[str, ...] = (), kill_on: str = ""
    ) -> subprocess.CompletedProcess[str]:
        self.log.unlink(missing_ok=True)
        self.log.touch()
        return subprocess.run(
            [
                sys.executable,
                str(SYNC),
                "--bucket",
                BUCKET,
                "--prefix",
                PREFIX.rstrip("/"),
                "--endpoint",
                "https://s3.example.test",
                "--folders",
                "docs .okf",
            ],
            cwd=self.repo,
            env={**self.env, "AWS_STUB_FAIL": "\n".join(fail), "AWS_STUB_KILL_ON": kill_on},
            capture_output=True,
            text=True,
            # Its own process group, so a stub kill stops the run and every
            # upload still in flight, and nothing else.
            start_new_session=True,
        )

    def calls(self, op: str) -> list[str]:
        rows = [json.loads(line) for line in self.log.read_text().splitlines()]
        return sorted(r["key"] for r in rows if r["op"] == op)

    def objects(self) -> set[str]:
        bucket = self.root / BUCKET
        return {p.relative_to(bucket).as_posix() for p in bucket.rglob("*") if p.is_file()}

    def manifest(self) -> dict[str, str]:
        data: dict[str, str] = json.loads((self.root / BUCKET / MANIFEST).read_text())
        return data

    def sha(self, path: str) -> str:
        return hashlib.sha256((self.repo / path).read_bytes()).hexdigest()


@pytest.fixture
def lab(tmp_path: Path) -> Lab:
    return Lab(tmp_path)


def test_uploads_only_changed_tracked_files(lab: Lab) -> None:
    lab.write("docs/untracked.md", "never added to git\n")
    first = lab.sync()
    assert first.returncode == 0, first.stderr
    assert lab.calls("put-object") == sorted(
        [PREFIX + "docs/a.md", PREFIX + "docs/b.md", PREFIX + ".okf/index.md", MANIFEST]
    )

    lab.write("docs/a.md", "a, changed\n")
    lab.write("docs/c.md", "c is new\n")
    lab.commit("docs/c.md")
    second = lab.sync()
    assert second.returncode == 0, second.stderr
    assert lab.calls("put-object") == sorted([PREFIX + "docs/a.md", PREFIX + "docs/c.md", MANIFEST])
    assert (lab.root / BUCKET / PREFIX / "docs/a.md").read_text() == "a, changed\n"
    assert lab.manifest() == {
        p: lab.sha(p) for p in ("docs/a.md", "docs/b.md", "docs/c.md", ".okf/index.md")
    }
    assert all(key.startswith(PREFIX) for key in lab.objects())


def test_deletes_removed_files(lab: Lab) -> None:
    assert lab.sync().returncode == 0
    lab.git("rm", "-q", "docs/b.md")
    lab.commit()
    run = lab.sync()
    assert run.returncode == 0, run.stderr
    assert lab.calls("delete-object") == [PREFIX + "docs/b.md"]
    assert PREFIX + "docs/b.md" not in lab.objects()
    assert PREFIX + "docs/a.md" in lab.objects()
    assert lab.manifest() == {p: lab.sha(p) for p in ("docs/a.md", ".okf/index.md")}


def test_no_change_run_is_a_no_op(lab: Lab) -> None:
    first = lab.sync()
    assert first.returncode == 0, first.stderr
    assert lab.calls("get-object") == [MANIFEST]

    second = lab.sync()
    assert second.returncode == 0, second.stderr
    assert lab.calls("put-object") == []
    assert lab.calls("delete-object") == []


def test_unreadable_manifest_stops_the_run(lab: Lab) -> None:
    # Read as empty, it would re-upload everything and forget the old
    # entries, so files deleted later would stay in the bucket for good.
    assert lab.sync().returncode == 0
    run = lab.sync(fail=(f"get-object {MANIFEST}",))
    assert run.returncode != 0
    assert lab.calls("put-object") == []
    assert lab.calls("delete-object") == []


def test_failure_writes_only_what_happened(lab: Lab) -> None:
    lab.write(".okf/gone.md", "removed below\n")
    lab.commit(".okf/gone.md")
    assert lab.sync().returncode == 0
    old_a = lab.sha("docs/a.md")
    lab.write("docs/a.md", "a, changed\n")
    lab.write("docs/c.md", "c is new\n")
    lab.git("rm", "-q", "docs/b.md", ".okf/gone.md")
    lab.commit("docs/c.md")

    failed = lab.sync(fail=(f"put-object {PREFIX}docs/a.md", f"delete-object {PREFIX}.okf/gone.md"))
    assert failed.returncode != 0
    manifest = lab.manifest()
    assert manifest["docs/a.md"] == old_a, "a failed upload's new hash was recorded"
    assert ".okf/gone.md" in manifest, "a failed delete's entry was dropped"
    assert "docs/b.md" not in manifest
    assert manifest["docs/c.md"] == lab.sha("docs/c.md")

    # docs/c.md went up in the failed run. Removing it now must still remove
    # its object, which only works if the failed run recorded it.
    lab.git("rm", "-q", "docs/c.md")
    lab.commit()
    retry = lab.sync()
    assert retry.returncode == 0, retry.stderr
    assert {PREFIX + "docs/c.md", PREFIX + ".okf/gone.md", PREFIX + "docs/b.md"}.isdisjoint(
        lab.objects()
    )
    assert lab.manifest() == {p: lab.sha(p) for p in ("docs/a.md", ".okf/index.md")}


def test_killed_run_keeps_its_progress(lab: Lab) -> None:
    spec = importlib.util.spec_from_file_location("sync", SYNC)
    assert spec and spec.loader
    sync = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(sync)
    extra = [f"docs/bulk/{n:03}.md" for n in range(sync.CHECKPOINT + 10)]
    for path in extra:
        lab.write(path, f"{path}\n")
    lab.commit("docs/bulk")
    everything = ["docs/a.md", "docs/b.md", ".okf/index.md", *extra]

    killed = lab.sync(kill_on=MANIFEST)
    assert killed.returncode != 0
    saved = lab.manifest()
    assert len(saved) >= sync.CHECKPOINT, "no progress was saved before the kill"
    assert len(saved) < len(everything), "the run finished; the kill came too late"
    assert all(saved[p] == lab.sha(p) for p in saved)

    retry = lab.sync()
    assert retry.returncode == 0, retry.stderr
    assert lab.calls("put-object") == sorted(
        [PREFIX + p for p in everything if p not in saved] + [MANIFEST]
    )
    assert lab.manifest() == {p: lab.sha(p) for p in everything}


def test_workflow_guard() -> None:
    workflow = yaml.safe_load(WORKFLOW.read_text())
    # PyYAML reads the bare key `on` as the boolean True.
    on = workflow.get("on", workflow.get(True))
    assert not set(on) & {"pull_request", "pull_request_target"}
    assert set(on) == {"push", "workflow_dispatch"}
    assert on["push"]["branches"] == ["main"]
    assert workflow["concurrency"]["group"]
    assert workflow["concurrency"].get("cancel-in-progress", False) is False
    [job] = workflow["jobs"].values()
    assert job["environment"] == "lab"
    assert 0 < job["timeout-minutes"] <= 5
    permissions = job.get("permissions", workflow.get("permissions"))
    assert permissions == {"id-token": "write", "contents": "read"}
    uses = [step.get("uses", "") for step in job["steps"]]
    assert uses.index("./.github/actions/lab-auth") < uses.index(
        "./.github/actions/openviking-sync"
    )
    login = job["steps"][uses.index("./.github/actions/lab-auth")]
    assert login["with"]["vault-role"] == "localstack-openviking-sync"


def test_seaweedfs_ci_policies_are_prefix_scoped(tmp_path: Path) -> None:
    iam = render_iam(tmp_path)
    policies: dict[str, Any] = {p["name"]: p["document"] for p in iam["policies"]}
    ci_roles = [
        r
        for r in iam["roles"]
        if r["trustPolicy"]["Statement"][0]["Principal"] != {"Federated": "nomad"}
    ]
    assert ci_roles, "no CI role rendered"
    for role in ci_roles:
        [statement] = role["trustPolicy"]["Statement"]
        assert statement["Principal"] == {"Federated": "vault"}, role["roleName"]
        assert statement["Action"] == "sts:AssumeRoleWithWebIdentity"
        assert set(statement["Condition"]) == {"StringEquals"}, role["roleName"]
        assert set(statement["Condition"]["StringEquals"]) == {"oidc:ci_repository"}
        repo = statement["Condition"]["StringEquals"]["oidc:ci_repository"]
        assert re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repo), repo
        assert role["attachedPolicies"], role["roleName"]
        for name in role["attachedPolicies"]:
            for s in policies[name]["Statement"]:
                assert s["Effect"] == "Allow"
                assert sorted(s["Action"]) == ["s3:DeleteObject", "s3:GetObject", "s3:PutObject"]
                assert s["Resource"] == [f"arn:aws:s3:::{BUCKET}/{repo}/*"], name


ACTION = REPO_ROOT / ".github" / "actions" / "openviking-sync" / "action.yml"


def test_credential_step_masks_and_keeps_secrets_in_the_step() -> None:
    text = ACTION.read_text()
    steps = yaml.safe_load(text)["runs"]["steps"]
    assert len(steps) == 1
    script = steps[0]["run"]
    assert "secrets." not in text
    assert "GITHUB_ENV" not in script.replace("never to $GITHUB_ENV", "")
    assert "GITHUB_OUTPUT" not in script
    assert 'role="ci-$login_role"' in script
    assert ".data.meta.role" in script
    assert '--role-arn "arn:aws:iam::role/$role"' in script
    for value, first_use in [
        ("$jwt", '--web-identity-token "$jwt"'),
        ("$AWS_ACCESS_KEY_ID", "export AWS_ACCESS_KEY_ID"),
        ("$AWS_SECRET_ACCESS_KEY", "export AWS_ACCESS_KEY_ID AWS_SECRET_ACCESS_KEY"),
        ("$AWS_SESSION_TOKEN", "AWS_SESSION_TOKEN\n"),
    ]:
        mask = script.find(f'echo "::add-mask::{value}"')
        assert mask != -1, f"{value} is not masked"
        assert mask < script.find(first_use), f"{value} is used before it is masked"
