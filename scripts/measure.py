#!/usr/bin/env python3
"""Time the inner loop: repeated runs, median and spread, exit codes checked.

Standard library only. Run from the repo root:

    python3 scripts/measure.py              # all scenarios, default repeats
    python3 scripts/measure.py --runs 3     # quicker, noisier

Every run must exit 0 (or the scenario's expected code); otherwise the script stops, so a
failing check can never be reported as a fast one. Results print as a Markdown table plus
the environment they were measured in.
"""

from __future__ import annotations

import argparse
import os
import platform
import statistics
import subprocess
import sys
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional

ROOT = Path(__file__).resolve().parents[1]
NX = str(ROOT / "node_modules" / ".bin" / "nx")
PROBE = ROOT / "packages" / "secret-scan" / "secret_scan" / "_measure_probe.py"
ALL_CHECKS = [NX, "run-many", "-t", "lint", "typecheck", "test"]


def sh(cmd: list[str]) -> int:
    return subprocess.run(cmd, cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode


def nx_reset() -> None:
    sh([NX, "reset"])


def change_python_file() -> None:
    # Nx hashes file contents, so the change must be new content, not just a new mtime.
    PROBE.write_text(f"# measurement probe {uuid.uuid4()}\n")


def remove_probe() -> None:
    PROBE.unlink(missing_ok=True)


@dataclass
class Scenario:
    name: str
    command: list[str]
    runs: int
    before_each: Optional[Callable[[], None]] = None
    after_all: Optional[Callable[[], None]] = None
    expect_exit: int = 0
    warmup: bool = True
    times: list[float] = field(default_factory=list)


def scenarios(runs: int) -> list[Scenario]:
    scan = [sys.executable, "-m", "secret_scan", "--root", "../.."]
    return [
        Scenario("All checks, cold (cache cleared before each run)", ALL_CHECKS, runs, before_each=nx_reset, warmup=False),
        Scenario("All checks, fully cached", ALL_CHECKS, runs * 2),
        Scenario(
            "All checks, one Python file changed",
            ALL_CHECKS,
            runs,
            before_each=change_python_file,
            after_all=remove_probe,
        ),
        Scenario("secret-scan, every tracked file", [*scan, "--tracked"], runs * 2),
        Scenario("secret-scan, staged files (pre-commit)", [*scan, "--staged"], runs * 2),
        Scenario(
            "guardrail-check on this repo",
            ["node", "apps/guardrail-check/dist/cli.js", "."],
            runs * 2,
            expect_exit=1,  # 3 checks fail until Epic 2 adds the devcontainer, hooks and AGENTS.md
        ),
    ]


def run(scenario: Scenario) -> None:
    cwd = ROOT / "packages" / "secret-scan" if "secret_scan" in scenario.command else ROOT
    if scenario.warmup:
        subprocess.run(scenario.command, cwd=cwd, capture_output=True)
    try:
        for _ in range(scenario.runs):
            if scenario.before_each:
                scenario.before_each()
            start = time.perf_counter()
            code = subprocess.run(scenario.command, cwd=cwd, capture_output=True).returncode
            elapsed = time.perf_counter() - start
            if code != scenario.expect_exit:
                sys.exit(f"[FAIL] {scenario.name}: exit {code}, expected {scenario.expect_exit}")
            scenario.times.append(elapsed)
    finally:
        if scenario.after_all:
            scenario.after_all()


def environment() -> str:
    node = subprocess.run(["node", "--version"], capture_output=True, text=True).stdout.strip()
    nx = subprocess.run([NX, "--version"], cwd=ROOT, capture_output=True, text=True).stdout
    nx_local = next((line.split("v")[-1] for line in nx.splitlines() if "Local" in line), "?")
    return (
        f"{platform.system()} {platform.machine()}, {os.cpu_count()} CPUs, "
        f"Python {platform.python_version()}, Node {node}, Nx {nx_local}, "
        f"NX_DAEMON={os.environ.get('NX_DAEMON', 'default')}"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--runs", type=int, default=5, help="runs per scenario (cached ones get double)")
    args = parser.parse_args()

    results = scenarios(args.runs)
    for scenario in results:
        print(f"... {scenario.name}", file=sys.stderr)
        run(scenario)

    print("| Scenario | Runs | Median (s) | Min (s) | Max (s) |")
    print("|---|---:|---:|---:|---:|")
    for s in results:
        print(f"| {s.name} | {len(s.times)} | {statistics.median(s.times):.2f} | {min(s.times):.2f} | {max(s.times):.2f} |")
    print(f"\nEnvironment: {environment()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
