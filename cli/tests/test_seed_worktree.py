"""scripts/seed_worktree.sh gives a linked worktree the gitignored gate inputs.

`loopctl ticket land` stamps a temporary worktree, and `just pre_commit` fails
there unless the SSH key and the tfvars terraform validate reads are present.
"""

import subprocess
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "seed_worktree.sh"
TFVARS = [
    "deployments/infrastructure/vars/prod.tfvars",
    "deployments/applications/vars/prod.tfvars",
]


def git(cwd: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@t", *args],
        cwd=cwd,
        check=True,
        capture_output=True,
    )


@pytest.fixture
def primary(tmp_path: Path) -> Path:
    """A repo whose gitignored key and tfvars exist only in the primary checkout."""
    repo = tmp_path / "primary"
    repo.mkdir()
    git(repo, "init", "-q", "-b", "main")
    (repo / ".gitignore").write_text(".ssh\nprod.tfvars\n")
    for f in TFVARS:
        (repo / f).parent.mkdir(parents=True)
        (repo / f).with_suffix(".tfvars.example").write_text("example\n")
        (repo / f).write_text(f"real {f}\n")
    (repo / ".ssh").mkdir()
    (repo / ".ssh" / "id_rsa").write_text("key\n")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "init")
    return repo


def seed(cwd: Path) -> None:
    subprocess.run(["bash", str(SCRIPT)], cwd=cwd, check=True, capture_output=True)


def test_a_linked_worktree_gets_the_key_and_tfvars(primary: Path) -> None:
    wt = primary.parent / "wt"
    git(primary, "worktree", "add", "-q", str(wt))
    assert not (wt / ".ssh").exists()

    seed(wt)

    assert (wt / ".ssh").is_symlink()
    assert (wt / ".ssh").resolve() == (primary / ".ssh").resolve()
    for f in TFVARS:
        assert not (wt / f).is_symlink()
        assert (wt / f).read_text() == f"real {f}\n"


def test_an_existing_file_in_the_worktree_is_kept(primary: Path) -> None:
    wt = primary.parent / "wt"
    git(primary, "worktree", "add", "-q", str(wt))
    (wt / TFVARS[0]).write_text("worktree's own\n")

    seed(wt)

    assert (wt / TFVARS[0]).read_text() == "worktree's own\n"


def files(repo: Path) -> list[Path]:
    return sorted(p.relative_to(repo) for p in repo.rglob("*") if ".git" not in p.parts)


def test_the_primary_checkout_is_left_alone(primary: Path) -> None:
    before = files(primary)

    seed(primary)

    assert files(primary) == before
