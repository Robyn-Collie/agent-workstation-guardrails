import subprocess
from pathlib import Path

from fakes import FAKE_SECRETS

from secret_scan.allowlist import Allowlist
from secret_scan.scanner import decode, redact, scan_text

AWS = FAKE_SECRETS["aws-access-key-id"]


def test_finding_reports_path_and_line_but_not_the_secret():
    [finding] = scan_text("deploy.sh", f"#!/bin/sh\nexport KEY={AWS}\n")
    assert (finding.path, finding.line) == ("deploy.sh", 2)
    assert AWS not in str(finding)
    assert finding.redacted == redact(AWS) == "AKIA... (20 chars)"


def test_inline_pragma_allows_one_line():
    text = f"KEY={AWS}  # secret-scan: allow\nKEY2={AWS}\n"
    assert [f.line for f in scan_text("x", text)] == [2]


def test_allowlist_can_skip_a_whole_file():
    allowlist = Allowlist.parse("# known-safe docs\ndocs/*.md\n")
    assert scan_text("docs/guide/setup.md", AWS, allowlist) == []
    assert len(scan_text("src/setup.md", AWS, allowlist)) == 1


def test_allowlist_can_skip_one_rule_in_a_file():
    allowlist = Allowlist.parse("generic-secret:tests/*\n")
    text = FAKE_SECRETS["generic-secret"] + "\n" + AWS
    assert [f.rule_id for f in scan_text("tests/data.py", text, allowlist)] == ["aws-access-key-id"]


def test_missing_allowlist_file_means_empty(tmp_path: Path):
    assert Allowlist.load(tmp_path / "nope").entries == []


def test_binary_and_oversized_files_are_skipped():
    assert decode(b"\x89PNG\0\0" + AWS.encode()) is None
    assert decode(b"a" * 1_000_001) is None
    assert decode(AWS.encode()) == AWS
