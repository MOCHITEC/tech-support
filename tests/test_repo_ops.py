"""GitRepoOps: クローン上でブランチを作りファイルを積んで push する。

ローカルの bare リポジトリを remote に見立てて実際の git 操作を検証する。
"""
import subprocess

import pytest

from app.agents.repo_ops import GitRepoOps


def _git(cwd, *args):
    return subprocess.run(
        ["git", "-C", str(cwd), *args], capture_output=True, text=True, check=True
    )


@pytest.fixture
def remote_and_clone(tmp_path):
    """main ブランチを持つ bare remote と、その作業クローンを用意する。"""
    remote = tmp_path / "remote.git"
    subprocess.run(["git", "init", "--bare", "-b", "main", str(remote)], check=True)

    seed = tmp_path / "seed"
    subprocess.run(["git", "clone", str(remote), str(seed)], check=True)
    (seed / "app").mkdir()
    (seed / "app" / "services.py").write_text("# original\n", encoding="utf-8")
    _git(seed, "add", ".")
    _git(seed, "-c", "user.email=s@x", "-c", "user.name=s", "commit", "-m", "init")
    _git(seed, "push", "origin", "main")

    clone = tmp_path / "clone"
    subprocess.run(["git", "clone", str(remote), str(clone)], check=True)
    return remote, clone


def test_commit_and_push_creates_branch_with_files(remote_and_clone):
    remote, clone = remote_and_clone
    ops = GitRepoOps(clone)

    ops.commit_and_push(
        branch="agent/ticket-7-fix",
        files={"app/services.py": "# fixed\n", "tests/test_repro_ticket_7.py": "x"},
        message="fix: ticket #7",
    )

    branches = _git(remote, "branch", "--list").stdout
    assert "agent/ticket-7-fix" in branches
    pushed = _git(remote, "show", "agent/ticket-7-fix:app/services.py").stdout
    assert pushed == "# fixed\n"


def test_branches_start_from_base_each_time(remote_and_clone):
    remote, clone = remote_and_clone
    ops = GitRepoOps(clone)

    ops.commit_and_push(branch="b1", files={"app/a.py": "1"}, message="m1")
    ops.commit_and_push(branch="b2", files={"app/b.py": "2"}, message="m2")

    # b2 は main から分岐するので b1 の変更を含まない。
    files = _git(remote, "ls-tree", "-r", "--name-only", "b2").stdout
    assert "app/b.py" in files
    assert "app/a.py" not in files
