# Story 1.2: `guardrail-check` CLI

Notes for explaining this story in a review or interview.

## What it does

`guardrail-check [--json] [path]` reads a repository and reports five checks. It exits `0` if all pass,
`1` if any fail, and `2` on bad usage, so CI or a hook can act on the result. It never writes to the
repo it checks.

| Check                   | Passes when                                                                                              | Standard rule                                 |
| ----------------------- | -------------------------------------------------------------------------------------------------------- | --------------------------------------------- |
| `agents-md`             | `AGENTS.md` exists at the root and isn't blank                                                           | One entry point any agent reads               |
| `secret-scan-hook`      | a hook file (`.githooks/`, `.husky/`, or `.pre-commit-config.yaml`) calls `secret-scan` or `secret_scan` | 4. Secret scan before code leaves the machine |
| `devcontainer-non-root` | `remoteUser`, else `containerUser`, else the Dockerfile's last `USER` is not root                        | 2. Contained sandbox                          |
| `no-env-committed`      | git tracks no `.env` or `.env.*` (except `.env.example`, `.sample`, `.template`)                         | 3. Secrets tiers                              |
| `worktree-convention`   | `AGENTS.md` or a file under `docs/` mentions `git worktree`                                              | 5. One workspace per agent                    |

**Honest limits.** These are presence checks. `secret-scan-hook` confirms a hook _mentions_ the
scanner, not that git runs it (that needs `core.hooksPath`, which Story 2.4 sets and could check).
`worktree-convention` passes on a mention; Story 2.6 makes it stricter. Run against this repo today it
reports 2 passed, 3 failed, which is correct: the devcontainer, hooks and AGENTS.md don't exist yet.

## TypeScript ideas used here

- **`interface`** (`types.ts`): describes the shape of an object. `CheckResult` says every result has
  an `id`, a `title`, a `passed` boolean and a `detail` string. The compiler rejects code that builds a
  result without one. This is the main thing TypeScript adds over JavaScript: mistakes in shape are
  caught before the code runs.
- **`import type`**: imports only the type, which disappears at compile time. It tells readers (and
  the compiler) that no runtime code is pulled in.
- **`.js` in imports of `.ts` files**: with `module: nodenext`, TypeScript follows Node's rules, and
  Node loads the compiled `.js` file. So the source names the file it will run, not the one you edit.
- **`unknown` then narrowing**: `parseJsonc` returns `unknown` because JSON can be anything. The code
  checks `typeof user === 'string'` before using a value, and TypeScript tracks that the check happened.
- **`string | undefined`**: `readIfExists` returns `undefined` for a missing file, and strict mode forces
  every caller to handle that case. `?? ''` means "use an empty string if it's undefined".

## Why these design choices

- **Zero runtime dependencies.** Only Node built-ins (`node:fs`, `node:child_process`, `node:util`
  `parseArgs`). A guardrail tool with a big dependency tree is itself a supply-chain risk.
- **`main(argv, write)` returns an exit code** instead of calling `process.exit`. That makes the CLI
  testable in-process: tests pass arguments and capture output without spawning a process.
- **Tests build real throwaway git repos** (`src/test/fixture-repo.ts`) in the OS temp folder, so
  `git ls-files` runs for real. Nothing is mocked.
- **Own JSONC parser** (about 30 lines): `devcontainer.json` allows comments and trailing commas, which
  `JSON.parse` rejects. A test proves URLs like `https://` inside strings survive comment stripping.

## Try it

```sh
npx nx build guardrail-check
node apps/guardrail-check/dist/cli.js          # this repo
node apps/guardrail-check/dist/cli.js --json .
```
