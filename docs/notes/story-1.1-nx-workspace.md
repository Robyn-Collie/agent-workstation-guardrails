# Story 1.1: Scaffold the Nx workspace

Notes for explaining this story in a review or interview.

## What Nx is, and why use it here

Nx is a build system for monorepos. It reads every project in the repo, works out which depends on
which (the "project graph"), and runs tasks such as `lint`, `typecheck` and `test` across them. Two
features matter for this repo: **caching** (if a project's inputs haven't changed, Nx replays the saved
result instead of rerunning the task) and **affected** (on a branch, Nx runs tasks only for the projects
your change touches). Both make the inner loop faster, and both can be measured, which is the point of
Story 1.5.

## How it was created

```sh
npx create-nx-workspace@23.2.1 agent-workstation-guardrails \
  --preset=ts --formatter=prettier --linter=eslint --unitTestRunner=vitest \
  --nxCloud=skip --aiAgents=none --analytics=false --pm=npm --interactive=false
npx nx add @nx/eslint
npm install -D @nx/vitest@23.2.1 && npx nx g @nx/vitest:init
npx nx g @nx/js:lib apps/guardrail-check --name=guardrail-check \
  --bundler=tsc --linter=eslint --unitTestRunner=vitest
```

Flags were checked against `npx create-nx-workspace@23.2.1 --help` on 2026-09-28, not taken from memory.
`--nxCloud=skip` keeps the cache local: no account and no remote service, so every number in
`docs/measurements.md` comes from this machine.

**npm 10 bug:** `npm install` on npm 10.9 crashed with `Cannot read properties of null (reading
'edgesOut')` while resolving Vitest's optional peer dependencies. `npx npm@11 install` worked, so
`package.json` pins `"packageManager": "npm@11.20.0"`.

## The files, one line each

| File                    | What it does                                                                                                                                                                                                                                                                                                                                                                                  |
| ----------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `package.json`          | Workspace root. `workspaces` tells npm that `apps/*` and `packages/*` are local packages. Dev tools only.                                                                                                                                                                                                                                                                                     |
| `nx.json`               | Nx settings. `plugins` _infer_ tasks from config files: a `tsconfig.lib.json` gives a project `build` and `typecheck`, an `eslint.config.mjs` gives it `lint`, a `vitest.config.mts` gives it `test`. `namedInputs.production` lists what counts as a change for cache purposes (test files don't affect a production build). `testMode: "run"` makes `nx test` run once instead of watching. |
| `tsconfig.base.json`    | Shared TypeScript compiler settings. `strict: true` turns on all strict type checks; `noUnusedLocals`, `noImplicitReturns` and friends add more. `module`/`moduleResolution: nodenext` means Node's real ES module rules.                                                                                                                                                                     |
| `tsconfig.json`         | Root file that lists each project as a TypeScript _project reference_, so `tsc -b` can build them in order. Nx keeps this list in sync (`nx sync`).                                                                                                                                                                                                                                           |
| `eslint.config.mjs`     | ESLint "flat config" shared by all projects. `@nx/enforce-module-boundaries` stops a project importing another in ways the graph doesn't allow.                                                                                                                                                                                                                                               |
| `vitest.config.mts`     | Root Vitest config that finds each project's own config.                                                                                                                                                                                                                                                                                                                                      |
| `.prettierrc`           | Formatting: single quotes. `npx prettier --check .` verifies it.                                                                                                                                                                                                                                                                                                                              |
| `apps/guardrail-check/` | Placeholder for the Story 1.2 CLI. Its `tsconfig.lib.json` compiles `src/` (not tests); `tsconfig.spec.json` type-checks the tests.                                                                                                                                                                                                                                                           |

## Acceptance check (run 2026-09-28, in a Linux cloud container)

- `npx nx show projects` → `guardrail-check`
- `npx nx run-many -t lint typecheck test` → 4 tasks succeeded (the 4th is `build`, because tests
  depend on `^build`). Cold: 2.2 s, 0/4 cache hits. Second run: 56 ms, 4/4 cache hits.

These are single runs, not benchmarks. Story 1.5 measures properly with repeated runs.

## Open item

`npm audit` reports high-severity advisories in `smol-toml`, pulled in by `nx` itself. The suggested
`npm audit fix --force` would change Nx's version, so it's left for now and tracked as an issue.
