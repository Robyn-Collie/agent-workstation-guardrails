import json
import subprocess
from pathlib import Path

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


def test_no_false_positives_on_this_repo():
    assert main(["--root", str(REPO_ROOT), "--tracked"]) == 0
