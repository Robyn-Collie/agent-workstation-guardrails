"""Command line: `python -m secret_scan [--staged | --tracked | --pre-push] [paths...]`.

Exit codes: 0 clean, 1 secrets found, 2 usage or git error.
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Iterator, Optional, Sequence, TextIO

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


def commits_to_push(root: Path, stdin: TextIO) -> list[str]:
    """Commits a push would send, from the lines git gives a pre-push hook on stdin.

    Each line is `<local ref> <local sha> <remote ref> <remote sha>`. A sha of all zeros
    means "doesn't exist": a deleted branch sends nothing, and a new branch sends every
    commit that no remote branch has yet.
    """
    commits: list[str] = []
    for line in stdin:
        parts = line.split()
        if len(parts) != 4:
            continue
        local, remote = parts[1], parts[3]
        if set(local) == {"0"}:
            continue
        if set(remote) == {"0"}:
            spec = [local, "--not", "--remotes"]
        else:
            spec = [f"{remote}..{local}"]
        for sha in git(root, "rev-list", *spec).decode().split():
            if sha not in commits:
                commits.append(sha)
    return commits


def pushed(root: Path, commits: Sequence[str]) -> Iterator[tuple[str, bytes, str]]:
    """Each file each commit added or changed, as it was in that commit.

    Scanning every commit, not just the last, matters: a secret committed and then
    deleted in a later commit is still in the history that gets pushed.
    """
    for sha in commits:
        names = git(root, "diff-tree", "--root", "--no-commit-id", "-r", "--name-only", "--diff-filter=ACMR", "-z", sha)
        for name in filter(None, names.decode().split("\0")):
            yield name, git(root, "show", f"{sha}:{name}"), sha


def main(argv: Optional[Sequence[str]] = None, stdin: Optional[TextIO] = None) -> int:
    parser = argparse.ArgumentParser(prog="secret-scan", description="Find secrets before they leave the machine.")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--staged", action="store_true", help="scan files staged for commit")
    mode.add_argument("--tracked", action="store_true", help="scan every file git tracks")
    mode.add_argument(
        "--pre-push",
        action="store_true",
        help="scan every commit about to be pushed (reads git's pre-push lines from stdin)",
    )
    parser.add_argument("--root", default=".", help="repository root (default: current directory)")
    parser.add_argument("--allowlist", help=f"allowlist file (default: <root>/{DEFAULT_FILE})")
    parser.add_argument("--json", action="store_true", help="print findings as JSON")
    parser.add_argument("paths", nargs="*", help="files or directories to scan (default: root)")
    args = parser.parse_args(argv)

    root = Path(args.root).resolve()
    allowlist = Allowlist.load(Path(args.allowlist) if args.allowlist else root / DEFAULT_FILE)
    try:
        if args.pre_push:
            sources: Iterator[tuple[str, bytes, Optional[str]]] = pushed(root, commits_to_push(root, stdin or sys.stdin))
        else:
            if args.staged:
                files = staged(root)
            elif args.tracked:
                files = tracked(root)
            else:
                files = walk(root, args.paths or ["."])
            sources = ((path, data, None) for path, data in files)
        findings = []
        scanned = 0
        for path, data, commit in sources:
            text = decode(data)
            if text is None:
                continue
            scanned += 1
            for finding in scan_text(path, text, allowlist):
                # Path stays bare for the allowlist; the commit is added only for the report.
                if commit:
                    finding = dataclasses.replace(finding, path=f"{path} (commit {commit[:8]})")
                findings.append(finding)
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
