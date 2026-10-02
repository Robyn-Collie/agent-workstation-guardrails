# agent-workstation-guardrails

A small, working reference for running coding agents safely on a developer workstation and keeping
the inner loop fast. It is a monorepo with a guardrail checker, a sandboxed devcontainer for the agent,
a pre-commit and pre-push secret scan, and a read-only MCP server. Each guardrail comes with a test that
proves it works and a number that shows what it costs.

**Status:** early build. The plan, epics and stories are in [docs/brief.md](docs/brief.md). This README
only describes what exists and has been tested; it grows as each story lands.

Written from scratch on personal time with public tools and public or synthetic data.

## What works today

- An Nx workspace (TypeScript, strict `tsconfig`, ESLint, Prettier, Vitest).
- `guardrail-check`: a CLI that audits a repo against the standard (24 tests).
- `secret-scan`: a zero-dependency Python secret scanner (39 tests, including one that scans this repo
  and must find nothing).
- Git hooks that run it before code leaves the machine: pre-commit scans what's staged, pre-push scans
  every commit being pushed. `npm install` turns them on. Tests show a fake secret blocked at both;
  they add about 0.09 s per commit and 0.08 s per push.
- A devcontainer for the agent: non-root, no sudo, no Linux capabilities, only the repo mounted.
  `.devcontainer/verify-sandbox.sh` proves it with 18 checks, run in CI on every change.
- A default-deny egress firewall in that devcontainer: outbound HTTPS only to npm, PyPI, GitHub and the
  model API. `.devcontainer/verify-egress.sh` proves a blocked domain is refused, an allowed one works,
  and the agent can't change the rules; CI also runs it without the firewall and requires it to fail.
  Designed and tested with the `devcontainer` CLI; not yet tested in VS Code.
- The agent's model API key is injected at run time, never stored in the image or container.
  `.devcontainer/check-no-baked-secret.sh` searches the image's history, metadata and every layer,
  plus the container, for the key; CI runs it with a random fake key, and also on an image that hides
  the key in a deleted layer, which it must catch. The standard behind all of this is in
  [docs/standard.md](docs/standard.md).
- One git worktree per agent, each in its own sandbox: `scripts/agent-worktree.sh` creates them
  ([docs/worktrees.md](docs/worktrees.md)). CI starts a sandbox in a new worktree, commits from inside
  it, and checks the main checkout is untouched. Creating a worktree took 0.14 s (one local run).

## Measured

A full `nx run-many -t lint typecheck test` takes 6.4 s cold and 0.9 s when nothing changed
(median of 5 and 10 runs, one 4-CPU Linux container). Method, spread and limits:
[docs/measurements.md](docs/measurements.md). Loading the egress firewall at container start took 0.4 s
in CI (one run).

## Quick start

Requires Node 22+, npm 11, and Python 3.9+ with `pytest` on the `PATH`. npm 11 is needed because npm 10's installer crashed while resolving this workspace's dependencies. See [docs/notes/story-1.1-nx-workspace.md](docs/notes/story-1.1-nx-workspace.md).

```sh
npm install
npx nx graph                               # see the projects and how they depend on each other
npx nx run-many -t lint typecheck test     # every check on every project, TypeScript and Python
npx nx affected -t lint typecheck test     # only the projects your branch changed
npx nx run secret-scan:scan-repo           # scan every tracked file for secrets (never cached)
```
