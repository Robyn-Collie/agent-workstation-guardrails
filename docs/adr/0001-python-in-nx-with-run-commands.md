# ADR 0001: Run the Python package through `nx:run-commands`, not a Python plugin

**Status:** Accepted, 2026-09-29 · **Story:** 1.4 (#4)

## Context

`secret-scan` is Python; the rest of the workspace is TypeScript. We want one Nx command
(`nx affected -t lint typecheck test`) to cover both, with caching.

Two current options (checked 2026-09-29 with `npm view`):

1. **`@nxlv/python` 23.2.1**, a community plugin versioned in step with Nx. It adds generators and
   executors for Poetry or uv projects, and infers dependencies between Python projects. It brings 17
   runtime dependencies into the workspace (including a tree-sitter parser).
2. **A `project.json` with `nx:run-commands`**, which ships with Nx. Each target is a shell command
   plus a declared list of inputs for the cache.

## Decision

Use `nx:run-commands`. `secret-scan` has zero runtime dependencies and no other Python project depends
on it, so the plugin's main features (dependency management and inferring links between Python
projects) have nothing to do here. A guardrail repo should also keep its own supply chain small.

## Consequences

- Cache inputs are declared by hand in `packages/secret-scan/project.json`. If they're wrong, Nx
  replays stale results. They include the Python and pytest versions (as `runtime` inputs), so
  upgrading either reruns the tests. Measured cost per run: about 0.2 s for the pytest version check and under 0.01 s for Python's (Story 1.5).
- The test that scans the whole repo can't be cached against this package's files alone (a secret
  added anywhere else must fail it). It moved to a separate `scan-repo` target with `cache: false`.
- If the repo grows a second Python project that imports this one, revisit: that's where
  `@nxlv/python` starts to pay for itself.
