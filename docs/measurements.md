# Measurements

Every speed claim in the README points here. Numbers come from `scripts/measure.py`, which repeats each
command, reports the median and range, and stops if any run exits with an unexpected code (so a failing
check can never be recorded as a fast one). Reproduce them with:

```sh
python3 scripts/measure.py --runs 5
```

## 2026-09-29: inner loop baseline (Story 1.5)

**Environment:** Linux x86_64 cloud container, 4 CPUs (Intel Xeon 2.8 GHz), 15 GB RAM, Python 3.11.15,
Node 22.22.2, Nx 23.2.1, local cache only (no Nx Cloud). The repo had 2 projects and 50 tracked files.
Wall-clock time, measured from outside the process.

### With the Nx daemon (the default)

| Scenario                                         | Runs | Median (s) | Min (s) | Max (s) |
| ------------------------------------------------ | ---: | ---------: | ------: | ------: |
| All checks, cold (cache cleared before each run) |    5 |       6.36 |    6.20 |    6.96 |
| All checks, fully cached                         |   10 |       0.91 |    0.85 |    1.00 |
| All checks, one Python file changed              |    5 |       2.94 |    2.84 |    3.24 |
| secret-scan, every tracked file                  |   10 |       0.16 |    0.15 |    0.30 |
| secret-scan, staged files (nothing staged)       |   10 |       0.08 |    0.07 |    0.09 |
| guardrail-check on this repo                     |   10 |       0.09 |    0.08 |    0.11 |

### Without the daemon (`NX_DAEMON=false`)

| Scenario                                         | Runs | Median (s) | Min (s) | Max (s) |
| ------------------------------------------------ | ---: | ---------: | ------: | ------: |
| All checks, cold (cache cleared before each run) |    5 |       6.55 |    6.09 |    6.90 |
| All checks, fully cached                         |   10 |       3.30 |    3.20 |    3.45 |
| All checks, one Python file changed              |    5 |       4.63 |    4.57 |    4.71 |
| secret-scan, every tracked file                  |   10 |       0.17 |    0.14 |    0.22 |
| secret-scan, staged files (nothing staged)       |   10 |       0.08 |    0.07 |    0.11 |
| guardrail-check on this repo                     |   10 |       0.09 |    0.08 |    0.11 |

"All checks" is `nx run-many -t lint typecheck test`: lint, typecheck, build and test for
`guardrail-check`, and pytest for `secret-scan` (5 tasks).

### What the numbers say

- **The cache cuts a full check from 6.4 s to 0.9 s** (about 7× faster) when nothing changed.
- **Changing one Python file costs 2.9 s**, not 6.4 s: the four TypeScript tasks replay from cache
  and only `secret-scan:test` reruns.
- **The Nx daemon is worth about 2.4 s on every cached run.** Without it, each command rebuilds the
  project graph (measured separately: `nx show projects` takes 1.25 s without the daemon). Cold runs
  barely change, because `nx reset` also stops the daemon.
- **The scanner is cheap enough for every commit.** Scanning all 50 tracked files takes 0.16 s. The
  staged-files run above had nothing staged, so it measures startup and the `git diff` call only;
  real pre-commit hook times are recorded in Story 2.4.
- **A cache input has a price.** `secret-scan:test` declares the pytest version as a cache input, and
  checking it costs about 0.2 s per run (`python3 -m pytest --version`: 203 to 209 ms over 3 runs).
  The Python version check costs under 0.01 s.

### Limits

- One machine, one day, a tiny repo. These are a baseline to compare later changes against, not a
  benchmark of Nx.
- Earlier single-run numbers in `docs/notes/story-1.1-nx-workspace.md` (2.2 s cold, 56 ms cached) are
  Nx's own "Run duration", which excludes Nx's startup and project graph time. The wall-clock numbers
  here are what a developer actually waits for.
- The daemon hung once in this container during Story 1.1; it worked in every run here.

## 2026-09-29: egress firewall load time (Story 2.2)

**Environment:** GitHub-hosted `ubuntu-latest` runner, measured by the firewall script itself
(`date +%s%N` at start and end) and printed to the container log. One run each, so treat these as a
rough size, not a median.

| Firewall version                                   | Load time | Run                                                                                                  |
| -------------------------------------------------- | --------- | ---------------------------------------------------------------------------------------------------- |
| 9 hosts looked up                                  | 166 ms    | [36601883071](https://github.com/Robyn-Collie/agent-workstation-guardrails/actions/runs/36601883071) |
| 9 hosts looked up, plus GitHub's ranges (80 CIDRs) | 417 ms    | [36602350548](https://github.com/Robyn-Collie/agent-workstation-guardrails/actions/runs/36602350548) |

It runs once per container start, before any tool, so it adds to startup, not to the inner loop.

## 2026-09-30: baked-secret check time (Story 2.3)

`check-no-baked-secret.sh` on the devcontainer image (about 600 MB saved) and its running container.
One run each.

| Where                              | Version                                 | Time                                                                                                            |
| ---------------------------------- | --------------------------------------- | --------------------------------------------------------------------------------------------------------------- |
| Build container (4 CPUs)           | `tar` lists and extracts every layer    | 203 s                                                                                                           |
| Build container (4 CPUs)           | Search raw layers, decompress if needed | 51 s                                                                                                            |
| GitHub-hosted `ubuntu-latest` (CI) | Search raw layers, decompress if needed | 28 s ([run 36753700515](https://github.com/Robyn-Collie/agent-workstation-guardrails/actions/runs/36753700515)) |

In the build container, `docker save` alone took 19 s and `docker export` 18 s, so most of the time
left is copying the image, not searching it. It runs in CI, not on every commit.
