# agent-workstation-guardrails

A small, working reference for running coding agents safely on a developer workstation and keeping
the inner loop fast. It is a monorepo with a guardrail checker, a sandboxed devcontainer for the agent,
a pre-commit and pre-push secret scan, and a read-only MCP server. Each guardrail comes with a test that
proves it works and a number that shows what it costs.

**Status:** early build. The plan, epics and stories are in [docs/brief.md](docs/brief.md). This README
only describes what exists and has been tested; it grows as each story lands.

Written from scratch on personal time with public tools and public or synthetic data.

## What works today

- An Nx workspace (TypeScript, strict `tsconfig`, ESLint, Prettier, Vitest) with one project,
  `guardrail-check`, which is still a placeholder.

## Quick start

Requires Node 22+ and npm 11 (npm 10's installer crashed while resolving this workspace's dependencies;
see [docs/notes/story-1.1-nx-workspace.md](docs/notes/story-1.1-nx-workspace.md)).

```sh
npm install
npx nx graph                               # see the projects and how they depend on each other
npx nx run-many -t lint typecheck test     # run every check on every project
```
