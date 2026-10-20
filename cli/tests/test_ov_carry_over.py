"""The ov-carry-over job, its storage key, the re-index script and the
blog-scraper skill.

The job's shell runs for real here, against a fake rclone
(fixtures/fake_rclone.py) that maps both buckets onto folders under tmp_path.
That proves what the script does with what rclone gives it: which trees it
copies, where, which keys it leaves alone, and which exit code each defect
gets. It does not prove rclone's own filter or marker behavior, which the
flag assertions below and restore-s3's tests cover.
"""

import hashlib
import importlib.util
import os
import re
import subprocess
import sys
import textwrap
from collections.abc import Iterator
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
APPS = REPO_ROOT / "deployments" / "applications"
JOB = APPS / "services" / "ov-carry-over.hcl"
SCRIPT = REPO_ROOT / "scripts" / "ov_carry_over.py"
SKILL = APPS / "services" / "hermes" / "skills" / "productivity" / "blog-scraper" / "SKILL.md"
FAKE_RCLONE = Path(__file__).resolve().parent / "fixtures" / "fake_rclone.py"
RESOURCES = "lab/user/jasper/resources"
SCRAPER_URI = "viking://user/jasper/resources/blog-scraper/"
BLOGS_URI = "viking://user/jasper/resources/blogs/"

# The 26 keys blogs/ and blog-scraper/ both hold in the old bucket, relative to
# each tree ("" is the tree's own marker), from its listing on 2026-10-20.
SHARED_KEYS = (
    "",
    ".abstract.md",
    ".overview.md",
    "addyosmani/",
    "addyosmani/.abstract.md",
    "addyosmani/.overview.md",
    "anthropic/",
    "anthropic/.abstract.md",
    "anthropic/.overview.md",
    "deepmind/",
    "deepmind/.abstract.md",
    "deepmind/.overview.md",
    "deepmind/gemini-4-argon.md/",
    "deepmind/gemini-4-argon.md/.abstract.md",
    "deepmind/gemini-4-argon.md/.overview.md",
    "mistral/",
    "mistral/.abstract.md",
    "mistral/.overview.md",
    "ollama/",
    "ollama/.abstract.md",
    "ollama/.overview.md",
    "openai/",
    "spotify/",
    "spotify/.abstract.md",
    "spotify/.overview.md",
    "uber/",
)

# Keys only one tree holds. A sidecar under blog-scraper/ names its own URIs,
# as the real ones do.
OWN_KEYS = {
    "blogs": (
        "addyosmani/intent-debt.md/.overview.md",
        "addyosmani/intent-debt.md/The_Intent_Debt/The_Intent_Debt.md",
        "addyosmani/unfetched.md/",
        "deepmind/gemini-4-argon.md/Gemini_4_Argon/Gemini_4_Argon.md",
        "openai/scaling-storage.md/Scaling_Storage.md",
    ),
    "blog-scraper": (
        "addyosmani/agent-loops.md/Agent_Loops.md",
        "deepmind/gemini-4-argon.md/Gemini_4_Argon-_our_next_era/part_1.md",
        "ollama/new-model.md/.abstract.md",
        "ollama/new-model.md/.overview.md",
        "ollama/new-model.md/Body/Body_1.md",
        "nvidia/.overview.md",
        "nvidia/post.md/Post.md",
        "spotify/hero.md/hero.webp",
        "uber/.abstract.md",
        "uber/.overview.md",
        "empty/",
    ),
    "clips": (
        ".abstract.md",
        "heron-clip/.abstract.md",
        "heron-clip/.overview.md",
        "heron-clip/heron.md",
        "heron-clip/heron-photo.png",
        "empty-clip/",
    ),
    "leo": (".overview.md", "2026-10-01/digest.md"),
    "projects": ("rituals/README.md",),
    "handoffs": ("h.md",),
}


def _content(tree: str, key: str) -> bytes:
    folder, _, name = key.rpartition("/")
    if tree == "blog-scraper" and name in (".abstract.md", ".overview.md"):
        return f"### [child]({SCRAPER_URI}{folder}/child)\n".encode()
    return f"{tree} {key}\n".encode()


def _put(root: Path, tree: str, key: str) -> None:
    path = root / tree / key
    if key == "" or key.endswith("/"):
        path.mkdir(parents=True, exist_ok=True)
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(_content(tree, key))


def old_keys() -> set[str]:
    """The fixture's keys relative to the resources folder, as the script reads them."""
    keys = {f"{tree}/{key}" for tree in ("blogs", "blog-scraper") for key in SHARED_KEYS}
    keys |= {f"{tree}/{key}" for tree, own in OWN_KEYS.items() for key in own}
    return keys


@pytest.fixture
def s3(tmp_path: Path) -> Path:
    """Both buckets as folders: the old one filled, the new one empty."""
    root = tmp_path / "s3"
    old = root / "openviking" / RESOURCES
    for tree in ("blogs", "blog-scraper"):
        for key in SHARED_KEYS:
            _put(old, tree, key)
    for tree, own in OWN_KEYS.items():
        for key in own:
            _put(old, tree, key)
    (root / "openviking" / "lab" / "user" / "jasper" / "memories").mkdir(parents=True)
    (root / "openviking" / "lab" / "user" / "jasper" / "memories" / "m.md").write_text("m\n")
    (root / "openviking-v2").mkdir()
    return root


def new(s3: Path) -> Path:
    return s3 / "openviking-v2" / RESOURCES


def old(s3: Path) -> Path:
    return s3 / "openviking" / RESOURCES


@pytest.fixture(scope="module")
def job_script() -> str:
    text = JOB.read_text()
    match = re.search(r"args = \[<<-EOT\n(.*?)\n\s*EOT\n", text, re.S)
    assert match, "ov-carry-over.hcl has no `args = [<<-EOT` script"
    script = textwrap.dedent(match.group(1))
    assert "${" not in script, "the script holds a template token, which templatefile would eat"
    return script


def run_job(tmp_path: Path, s3: Path, script: str, **env: str) -> subprocess.CompletedProcess[str]:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir(exist_ok=True)
    rclone = bin_dir / "rclone"
    rclone.write_text(f'#!/bin/sh\nexec "{sys.executable}" "{FAKE_RCLONE}" "$@"\n')
    rclone.chmod(0o755)
    (tmp_path / "work").mkdir(exist_ok=True)
    (tmp_path / "job.sh").write_text(script)
    return subprocess.run(
        ["sh", str(tmp_path / "job.sh")],
        env={
            "PATH": f"{bin_dir}:{os.environ['PATH']}",
            "FAKE_S3": str(s3),
            "TMPDIR": str(tmp_path / "work"),
            **env,
        },
        capture_output=True,
        text=True,
        check=False,
    )


def tree_of(root: Path) -> dict[str, bytes]:
    return {p.relative_to(root).as_posix(): p.read_bytes() for p in root.rglob("*") if p.is_file()}


def test_job_copies_only_the_four_trees(tmp_path: Path, s3: Path, job_script: str) -> None:
    assert 'trees="blogs clips leo blog-scraper"' in job_script, (
        "blogs must copy before blog-scraper"
    )
    writes = [
        line for line in job_script.splitlines() if re.match(r'\s*rclone copy .* "\$new', line)
    ]
    assert len(writes) == 2
    for line in writes:
        assert "--ignore-existing" in line, f"a copy into the new bucket overwrites: {line}"
    first = [line for line in writes if '"$old/$t/"' in line]
    assert first and "--create-empty-src-dirs --s3-directory-markers" in first[0]

    widened = job_script.replace(
        'trees="blogs clips leo blog-scraper"', 'trees="blogs clips leo blog-scraper projects"'
    )
    refused = run_job(tmp_path, s3, widened)
    assert refused.returncode == 5, refused.stdout + refused.stderr
    assert not new(s3).exists(), "the job copied before refusing a tree"

    done = run_job(tmp_path, s3, job_script)
    assert done.returncode == 0, done.stdout + done.stderr

    assert {p.name for p in new(s3).iterdir()} == {"blogs", "clips", "leo"}
    assert not (s3 / "openviking-v2" / "lab" / "user" / "jasper" / "memories").exists()
    copied = tree_of(new(s3))
    for key, body in tree_of(old(s3) / "blog-scraper").items():
        if not key.endswith((".abstract.md", ".overview.md")):
            assert copied[f"blogs/{key}"] == body
    for tree in ("clips", "leo"):
        assert {k: v for k, v in copied.items() if k.startswith(f"{tree}/")} == {
            f"{tree}/{k}": v for k, v in tree_of(old(s3) / tree).items()
        }


def test_blog_scraper_sidecars_are_rewritten_once(
    tmp_path: Path, s3: Path, job_script: str
) -> None:
    regenerated = new(s3) / "blogs" / "uber" / ".overview.md"
    regenerated.parent.mkdir(parents=True)
    regenerated.write_text("regenerated by the new instance\n")

    done = run_job(tmp_path, s3, job_script)
    assert done.returncode == 0, done.stdout + done.stderr

    scraper_sidecars = {
        k: v
        for k, v in tree_of(old(s3) / "blog-scraper").items()
        if k.endswith((".abstract.md", ".overview.md"))
    }
    shared = {k for k in SHARED_KEYS if k.endswith(".md")}
    for key, body in scraper_sidecars.items():
        landed = (new(s3) / "blogs" / key).read_bytes()
        if key in shared:
            assert landed == (old(s3) / "blogs" / key).read_bytes(), f"{key} lost the blogs version"
        elif key == "uber/.overview.md":
            assert landed == b"regenerated by the new instance\n", "the rewrite overwrote a key"
        else:
            assert SCRAPER_URI.encode() in body
            assert landed == body.replace(SCRAPER_URI.encode(), BLOGS_URI.encode())


REGENERATED = tuple((f"blogs/{k}", "regenerated\n") for k in SHARED_KEYS if k.endswith(".md")) + (
    ("clips/heron-clip/.overview.md", "regenerated\n"),
)

# Each case: the exit code, the fake rclone's misbehavior, and keys already in
# the new bucket. The first is no defect: sidecars the re-index or a live save
# rewrote, the shared ones among them, are not a hash mismatch.
DEFECTS: dict[str, tuple[int, dict[str, str], tuple[tuple[str, str], ...]]] = {
    "sidecars were regenerated": (0, {}, REGENERATED),
    "a file differs from the old one": (2, {}, (("clips/heron-clip/heron.md", "edited\n"),)),
    "a sidecar is missing": (6, {"FAKE_RCLONE_LOSE": "clips/heron-clip/.abstract.md"}, ()),
    "blogs/ names blog-scraper/": (
        7,
        {},
        (("blogs/nvidia/.overview.md", f"### [post.md]({SCRAPER_URI}nvidia/post.md)\n"),),
    ),
    "an empty directory is missing": (3, {"FAKE_RCLONE_NO_EMPTY_DIRS": "1"}, ()),
}


@pytest.mark.parametrize("defect", DEFECTS)
def test_job_checks_fail_on_each_defect(
    tmp_path: Path, s3: Path, job_script: str, defect: str
) -> None:
    failures = [code for code, _, _ in DEFECTS.values() if code]
    assert len(set(failures)) == len(failures), "two defects share an exit code"
    code, env, seeded = DEFECTS[defect]
    for key, body in seeded:
        path = new(s3) / key
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(body)
    done = run_job(tmp_path, s3, job_script, **env)
    assert done.returncode == code, done.stdout + done.stderr


def _statements(policy: str) -> list[tuple[str, str]]:
    return re.findall(
        r'Effect\s*=\s*"Allow"\s*\n\s*Action\s*=\s*([^\n]+)\n\s*Resource\s*=\s*([^\n]+)', policy
    )


def test_carry_over_key_cannot_change_the_old_bucket() -> None:
    storage = (APPS / "storage.tf").read_text()
    policy = re.search(
        r'resource "aws_iam_user_policy" "seaweedfs_carry_over" \{(.*?)\n\}', storage, re.S
    )
    assert policy, 'storage.tf has no resource "aws_iam_user_policy" "seaweedfs_carry_over"'
    assert "Deny" not in policy.group(1)
    write = re.search(r"seaweedfs_write_actions\s*=\s*(\[[^\]]*\])", storage)
    assert write
    granted: dict[str, set[str]] = {}
    for action, resource in _statements(policy.group(1)):
        if action.strip() == "local.seaweedfs_write_actions":
            action = write.group(1)
        buckets = set(re.findall(r'aws_s3_bucket\.seaweedfs\["([^"]+)"\]', resource))
        assert len(buckets) == 1, resource
        granted.setdefault(buckets.pop(), set()).update(re.findall(r'"(s3:[^"]+)"', action))
    assert set(granted) == {"openviking", "openviking-v2"}
    assert {"s3:GetObject", "s3:ListBucket"} <= granted["openviking"]
    assert granted["openviking"] <= {"s3:GetBucketLocation", "s3:GetObject", "s3:ListBucket"}
    assert "s3:*" in granted["openviking-v2"]
    assert storage.count("aws_iam_user.seaweedfs_carry_over.name") == 2, "a second policy"

    secrets = (APPS / "secrets.tf").read_text()
    assert re.search(
        r'"ov_carry_over_seaweedfs_credentials" \{[^}]*name\s*=\s*"default/ov-carry-over/seaweedfs"'
        r"[^}]*aws_iam_access_key\.seaweedfs_carry_over\.id",
        secrets,
        re.S,
    )
    services = (APPS / "services.tf").read_text()
    assert re.search(
        r'"ov_carry_over" \{.*?services/ov-carry-over\.hcl.*?'
        r"vault_kv_secret_v2\.ov_carry_over_seaweedfs_credentials\.path",
        services,
        re.S,
    )


@pytest.fixture(scope="module")
def carry() -> Iterator[ModuleType]:
    """The script as a module. dataclass needs it in sys.modules while it loads."""
    spec = importlib.util.spec_from_file_location("ov_carry_over", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    try:
        spec.loader.exec_module(module)
        yield module
    finally:
        del sys.modules[spec.name]


def test_reindex_plan_and_image_rows(carry: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    base = "viking://user/jasper/resources"
    # Of the directories both trees hold, only these have files on both sides.
    merged = ["blogs/deepmind/gemini-4-argon.md", "blogs/addyosmani", "blogs/deepmind", "blogs"]
    want = [("regenerate", f"{base}/{d}") for d in merged]
    want += [("vectors", f"{base}/{tree}") for tree in ("clips", "blogs", "leo")]
    want.append(("image-rows", ""))
    assert [(s.action, s.uri) for s in carry.plan(old_keys())] == want

    calls: list[tuple[str, ...]] = []

    class Recorder:
        def reindex(self, uri: str, mode: str, recursive: bool) -> dict[str, int]:
            calls.append((mode, uri, str(recursive)))
            return {"failed_records": 0}

    monkeypatch.setattr(carry, "copy_image_rows", lambda command, keys: calls.append(("rows",)))
    carry.run(Recorder(), ["psql"], old_keys())
    assert calls == [
        *[("semantic_and_vectors", f"{base}/{d}", "False") for d in merged],
        *[("vectors_only", f"{base}/{t}", "True") for t in ("clips", "blogs", "leo")],
        ("rows",),
    ]

    assert carry.image_keys(old_keys()) == [
        "blog-scraper/spotify/hero.md/hero.webp",
        "clips/heron-clip/heron-photo.png",
    ]
    old_uri = "/user/jasper/resources/blog-scraper/spotify/hero.md/hero.webp"
    new_uri = "/user/jasper/resources/blogs/spotify/hero.md/hero.webp"
    new_id = hashlib.md5(f"lab:viking:/{new_uri}".encode()).hexdigest()
    old_id = hashlib.md5(f"lab:viking:/{old_uri}".encode()).hexdigest()
    sql = carry.image_rows_sql([old_uri], ["level", "vector"])
    assert sql.startswith("INSERT INTO openviking_v2.ov_context (id, uri, ")
    assert "SELECT m.new_id, m.new_uri, " in sql
    assert "FROM openviking.ov_context o" in sql
    assert f"('{old_uri}', '{new_uri}', '{new_id}')" in sql
    assert old_id not in sql and "o.id" not in sql and 'o."id"' not in sql
    assert "ON CONFLICT (id) DO NOTHING" in sql


def _listing(path: Path, keys: set[str]) -> Path:
    path.write_text("".join(f"{RESOURCES}/{k};12;2026-10-20 08:00:00\n" for k in sorted(keys)))
    return path


@pytest.mark.parametrize(
    ("defect", "named"),
    [
        ("missing", "missing clips/heron-clip/heron.md"),
        ("extra-tree", "unexpected top-level entry projects"),
        ("blog-scraper", "blog-scraper/ exists in the new instance"),
        ("count", "leo holds 2 files, the old bucket 1: leo/late.md"),
    ],
)
def test_comparison_names_every_defect(carry: Any, tmp_path: Path, defect: str, named: str) -> None:
    olds = carry.read_listing(_listing(tmp_path / "old.lsf", old_keys()))
    assert olds == old_keys()
    carried = {carry.carried_key(k) for k in olds} - {None}
    new_keys = set(carried) | {"blogs/addyosmani/late-post.md/Late.md"}

    def compare(keys: set[str]) -> tuple[list[str], list[str]]:
        listed = carry.read_listing(_listing(tmp_path / "new.lsf", keys))
        files = {
            t: {k for k in listed if k.startswith(f"{t}/") and carry.is_file(k)}
            for t in ("clips", "blogs", "leo")
        }
        top = {k.split("/", 1)[0] for k in listed}
        result: tuple[list[str], list[str]] = carry.compare(olds, files, top, set())
        return result

    assert compare(new_keys | {".map.md"}) == ([], ["blogs/addyosmani/late-post.md/Late.md"])

    broken = {
        "missing": new_keys - {"clips/heron-clip/heron.md"},
        "extra-tree": new_keys | {"projects/rituals/README.md"},
        "blog-scraper": new_keys | {"blog-scraper/openai/new.md/New.md"},
        "count": new_keys | {"leo/late.md"},
    }[defect]
    problems, _ = compare(broken)
    assert any(named in p for p in problems), problems


def test_blog_scraper_skill_saves_to_blogs() -> None:
    skill = SKILL.read_text()
    assert "resources/blog-scraper" not in skill and "blog-scraper/<" not in skill
    assert 'parent="viking://user/jasper/resources/blogs/{source}/"' in skill
    sources = re.search(r"Source folders: (.*?)\.\s", skill, re.S)
    assert sources, "the skill does not list the source folder for each blog"
    assert set(re.findall(r"`([a-z]+)`", sources.group(1))) == {
        "addyosmani",
        "anthropic",
        "deepmind",
        "mistral",
        "ollama",
        "openai",
        "spotify",
        "uber",
    }


class StubOpenViking:
    """Answers the reads the checks make, in 0.4.17.1's shapes."""

    def __init__(self, files: set[str], overviews: dict[str, str]) -> None:
        self.files = files
        self.overviews = overviews

    def tree(self, uri: str) -> list[dict[str, Any]]:
        tree = uri.rsplit("/", 1)[-1]
        return [
            {"rel_path": k.removeprefix(f"{tree}/"), "isDir": False}
            for k in self.files
            if k.startswith(f"{tree}/")
        ]

    def get(self, path: str, **params: str) -> Any:
        if path == "/api/v1/fs/ls":
            return [{"name": n, "isDir": True} for n in {k.split("/")[0] for k in self.files}]
        assert path == "/api/v1/content/overview"
        return self.overviews[params["uri"].removeprefix("viking://user/jasper/resources/")]


def test_live_checks_read_the_api_shapes(carry: Any) -> None:
    olds = old_keys()
    carried = {carry.carried_key(k) for k in olds if carry.is_file(k)} - {None}
    stub = StubOpenViking(carried, {})
    files = carry.check_files(stub, olds, set())
    assert files["clips"] == {"clips/heron-clip/heron.md", "clips/heron-clip/heron-photo.png"}

    # Each merged overview names one file-holding child from each half. The
    # empty `unfetched.md/` on the blogs side of addyosmani need not appear.
    both = "intent-debt.md and agent-loops.md, Gemini_4_Argon-_our_next_era"
    stub.overviews = {d: both for d in carry.merged_directories(olds)}
    stub.overviews["blogs/"] = "addyosmani deepmind nvidia openai"
    carry.check_overviews(stub, olds)

    stub.overviews["blogs/addyosmani/"] = "only unfetched.md"
    with pytest.raises(carry.CheckFailure, match="addyosmani/ names nothing from blogs"):
        carry.check_overviews(stub, olds)
