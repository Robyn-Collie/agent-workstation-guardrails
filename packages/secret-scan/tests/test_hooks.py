"""End-to-end: the repo's real git hooks, in a throwaway repo, with a fake secret."""

import subprocess
from pathlib import Path

import pytest
from fakes import FAKE_SECRETS

HOOKS = Path(__file__).resolve().parents[3] / ".githooks"
AWS = FAKE_SECRETS["aws-access-key-id"]


def git(repo: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=repo, check=check, capture_output=True, text=True)


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    """A repo using this project's hooks, with one clean commit and a bare remote."""
    work = tmp_path / "work"
    remote = tmp_path / "remote.git"
    subprocess.run(["git", "init", "-q", "--bare", str(remote)], check=True)
    subprocess.run(["git", "init", "-q", "-b", "main", str(work)], check=True)
    git(work, "config", "user.name", "Test")
    git(work, "config", "user.email", "test@example.invalid")
    git(work, "config", "core.hooksPath", str(HOOKS))
    git(work, "remote", "add", "origin", str(remote))
    (work / "README.md").write_text("hello\n")
    git(work, "add", "README.md")
    git(work, "commit", "-q", "-m", "initial")
    return work


def test_pre_commit_blocks_a_staged_secret(repo: Path):
    (repo / "settings.py").write_text(f"KEY = '{AWS}'\n")
    git(repo, "add", "settings.py")
    result = git(repo, "commit", "-m", "add settings", check=False)
    assert result.returncode != 0
    output = result.stdout + result.stderr  # git sends hook output to stderr for commits
    assert "aws-access-key-id" in output
    assert AWS not in output  # the report never echoes the secret
    assert git(repo, "rev-list", "--count", "HEAD").stdout.strip() == "1"  # nothing committed


def test_pre_commit_allows_a_clean_commit(repo: Path):
    (repo / "app.py").write_text("print('hello')\n")
    git(repo, "add", "app.py")
    assert git(repo, "commit", "-m", "add app", check=False).returncode == 0


def test_pre_push_blocks_a_secret_deleted_in_a_later_commit(repo: Path):
    # Skip the pre-commit hook, then "fix" it in the next commit. The final tree is clean,
    # but the secret is still in history, and pushing would publish it.
    (repo / "settings.py").write_text(f"KEY = '{AWS}'\n")
    git(repo, "add", "settings.py")
    git(repo, "commit", "-q", "--no-verify", "-m", "add settings")
    (repo / "settings.py").write_text("import os\nKEY = os.environ['KEY']\n")
    git(repo, "commit", "-q", "-am", "read key from env")

    result = git(repo, "push", "origin", "main", check=False)
    assert result.returncode != 0
    assert "settings.py (commit " in result.stdout + result.stderr
    assert git(repo, "ls-remote", "origin").stdout == ""  # nothing reached the remote


def test_pre_push_allows_clean_commits(repo: Path):
    assert git(repo, "push", "-q", "origin", "main", check=False).returncode == 0
    (repo / "app.py").write_text("print('hello')\n")
    git(repo, "add", "app.py")
    git(repo, "commit", "-q", "-m", "add app")
    assert git(repo, "push", "-q", "origin", "main", check=False).returncode == 0
