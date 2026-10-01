import io
import json
import subprocess
from pathlib import Path

import pytest
from fakes import FAKE_SECRETS

from secret_scan.cli import main

AWS = FAKE_SECRETS["aws-access-key-id"]
REPO_ROOT = Path(__file__).resolve().parents[3]


def test_clean_directory_exits_0(tmp_path: Path, capsys):
    (tmp_path / "app.py").write_text("print('hello')\n")
    assert main(["--root", str(tmp_path)]) == 0
    assert "no secrets found in 1 file(s)" in capsys.readouterr().err


def test_secret_exits_1_and_skips_node_modules(tmp_path: Path, capsys):
    (tmp_path / "config.env").write_text(f"KEY={AWS}\n")
    (tmp_path / "node_modules").mkdir()
    (tmp_path / "node_modules" / "vendored.js").write_text(f"k='{AWS}'\n")
    assert main(["--root", str(tmp_path), "--json"]) == 1
    report = json.loads(capsys.readouterr().out)
    assert [f["path"] for f in report["findings"]] == ["config.env"]


def test_staged_scans_the_index_not_the_working_tree(git_repo: Path):
    secret_file = git_repo / "settings.py"
    secret_file.write_text(f"KEY = '{AWS}'\n")
    subprocess.run(["git", "add", "settings.py"], cwd=git_repo, check=True)
    secret_file.write_text("KEY = os.environ['KEY']\n")  # fixed on disk, but not re-staged
    assert main(["--root", str(git_repo), "--staged"]) == 1


def test_staged_with_nothing_staged_is_clean(git_repo: Path):
    (git_repo / "untracked.py").write_text(f"KEY = '{AWS}'\n")
    assert main(["--root", str(git_repo), "--staged"]) == 0


def test_git_failure_exits_2(tmp_path: Path):
    assert main(["--root", str(tmp_path), "--tracked"]) == 2


def test_allowlist_file_at_root_is_used(tmp_path: Path):
    (tmp_path / "fixtures").mkdir()
    (tmp_path / "fixtures" / "keys.txt").write_text(AWS)
    (tmp_path / ".secret-scan-allowlist").write_text("fixtures/*\n")
    assert main(["--root", str(tmp_path)]) == 0


@pytest.mark.repo_scan
def test_no_false_positives_on_this_repo():
    assert main(["--root", str(REPO_ROOT), "--tracked"]) == 0


def _commit(repo: Path, name: str, text: str, message: str) -> str:
    (repo / name).write_text(text)
    subprocess.run(["git", "add", name], cwd=repo, check=True)
    subprocess.run(
        ["git", "-c", "user.name=T", "-c", "user.email=t@example.invalid", "commit", "-q", "-m", message],
        cwd=repo,
        check=True,
    )
    return subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo, check=True, capture_output=True, text=True).stdout.strip()


ZERO = "0" * 40


def test_pre_push_scans_only_the_commits_being_pushed(git_repo: Path, capsys):
    old = _commit(git_repo, "old.py", f"KEY = '{AWS}'\n", "already on the remote")
    new = _commit(git_repo, "new.py", "print('hi')\n", "being pushed")
    stdin = io.StringIO(f"refs/heads/main {new} refs/heads/main {old}\n")
    assert main(["--root", str(git_repo), "--pre-push"], stdin=stdin) == 0
    assert "in 1 file(s)" in capsys.readouterr().err


def test_pre_push_new_branch_scans_history_and_names_the_commit(git_repo: Path, capsys):
    bad = _commit(git_repo, "settings.py", f"KEY = '{AWS}'\n", "add key")
    head = _commit(git_repo, "settings.py", "KEY = None\n", "remove key")
    stdin = io.StringIO(f"refs/heads/main {head} refs/heads/main {ZERO}\n")
    assert main(["--root", str(git_repo), "--pre-push"], stdin=stdin) == 1
    assert f"settings.py (commit {bad[:8]})" in capsys.readouterr().out


def test_pre_push_branch_deletion_sends_nothing(git_repo: Path):
    _commit(git_repo, "settings.py", f"KEY = '{AWS}'\n", "add key")
    stdin = io.StringIO(f"(delete) {ZERO} refs/heads/old {ZERO}\n")
    assert main(["--root", str(git_repo), "--pre-push"], stdin=stdin) == 0


def test_pre_push_allowlist_still_matches_the_bare_path(git_repo: Path):
    (git_repo / ".secret-scan-allowlist").write_text("fixtures/*\n")
    (git_repo / "fixtures").mkdir()
    head = _commit(git_repo, "fixtures/keys.txt", AWS, "fixture")
    stdin = io.StringIO(f"refs/heads/main {head} refs/heads/main {ZERO}\n")
    assert main(["--root", str(git_repo), "--pre-push"], stdin=stdin) == 0
