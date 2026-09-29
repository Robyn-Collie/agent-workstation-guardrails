# Story 1.5: Measure the loop

Notes for explaining this story in a review or interview. Results: [docs/measurements.md](../measurements.md).

## Why write a script instead of using hyperfine

`hyperfine` (the benchmarking tool the brief suggested) isn't installed in the build container, and a
script in the repo lets anyone rerun exactly the same scenarios with one command. `scripts/measure.py`
is standard-library Python: it repeats each command, takes the median (less sensitive to one slow run
than the average), and reports min and max so the spread is visible.

## Three decisions that make the numbers trustworthy

1. **Exit codes are checked on every run.** A task that fails fast looks like a fast task. The script
   stops if any run exits unexpectedly. (This is the lesson from the typecheck bug fixed in #22.)
2. **"Cold" really is cold.** `nx reset` runs before every cold run, clearing the cache and stopping
   the daemon.
3. **"One file changed" changes content, not just the timestamp.** Nx fingerprints file contents, so
   the script writes a new random comment into a probe file inside `secret-scan`, then deletes it.

## The surprise

Fully cached runs took 3.3 s without the Nx daemon but 0.9 s with it. The daemon is a background
process that keeps the project graph in memory; without it, every command rebuilds the graph from
scratch (1.25 s on its own here). That's a real finding to bring to a DevEx conversation: on a large
monorepo, the daemon's health is part of the inner loop.

## Interview line

"I don't say the cache makes it faster; I say a fully cached check went from 6.4 seconds to 0.9 on this
machine, median of 10 runs, and here's the script."
