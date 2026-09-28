"""Command line: `python -m secret_scan [--staged | --tracked] [paths...]`.

Exit codes: 0 clean, 1 secrets found, 2 usage or git error.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Iterator, Optional, Sequence

from secret_scan.allowlist import DEFAULT_FILE, Allowlist
from secret_scan.scanner import decode, scan_text

SKIP_DIRS = {".git", "node_modules", ".venv", "dist", ".nx", "__pycache__", ".pytest_cache"}


def git(root: Path, *args: str) -> bytes:
    return subprocess.run(["git", *args], cwd=root, check=True, capture_output=True).stdout


def files_under(start: Path) -> Iterator[Path]:
    if start.is_file():
        yield start
        return
    for directory, subdirs, names in os.walk(start):
        subdirs[:] = sorted(d for d in subdirs if d not in SKIP_DIRS)  # prune in place
        for name in sorted(names):
            yield Path(directory) / name


def walk(root: Path, paths: Sequence[str]) -> Iterator[tuple[str, bytes]]:
    for given in paths:
        for file in files_under((root / given).resolve()):
            shown = file.relative_to(root).as_posix() if file.is_relative_to(root) else str(file)
            yield shown, file.read_bytes()


def tracked(root: Path) -> Iterator[tuple[str, bytes]]:
    for name in git(root, "ls-files", "-z").decode().split("\0"):
        if name and (root / name).is_file():
            yield name, (root / name).read_bytes()


def staged(root: Path) -> Iterator[tuple[str, bytes]]:
    """The content in the index (what will be committed), not the working tree."""
    names = git(root, "diff", "--cached", "--name-only", "--diff-filter=ACMR", "-z").decode().split("\0")
    for name in filter(None, names):
        yield name, git(root, "show", f":{name}")


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(prog="secret-scan", description="Find secrets before they leave the machine.")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--staged", action="store_true", help="scan files staged for commit")
    mode.add_argument("--tracked", action="store_true", help="scan every file git tracks")
    parser.add_argument("--root", default=".", help="repository root (default: current directory)")
    parser.add_argument("--allowlist", help=f"allowlist file (default: <root>/{DEFAULT_FILE})")
    parser.add_argument("--json", action="store_true", help="print findings as JSON")
    parser.add_argument("paths", nargs="*", help="files or directories to scan (default: root)")
    args = parser.parse_args(argv)

    root = Path(args.root).resolve()
    allowlist = Allowlist.load(Path(args.allowlist) if args.allowlist else root / DEFAULT_FILE)
    try:
        if args.staged:
            sources = staged(root)
        elif args.tracked:
            sources = tracked(root)
        else:
            sources = walk(root, args.paths or ["."])
        findings = []
        scanned = 0
        for path, data in sources:
            text = decode(data)
            if text is not None:
                scanned += 1
                findings.extend(scan_text(path, text, allowlist))
    except subprocess.CalledProcessError as error:
        print(f"secret-scan: git failed: {error.stderr.decode().strip()}", file=sys.stderr)
        return 2

    if args.json:
        print(json.dumps({"scanned": scanned, "findings": [f.__dict__ for f in findings]}, indent=2))
    else:
        for finding in findings:
            print(finding)
        verdict = f"{len(findings)} possible secret(s) found" if findings else "no secrets found"
        print(f"secret-scan: {verdict} in {scanned} file(s)", file=sys.stderr)
    return 1 if findings else 0
