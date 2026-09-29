# Story 1.4: Python in Nx

Notes for explaining this story in a review or interview.

## What changed

`packages/secret-scan/project.json` tells Nx this folder is a project called `secret-scan` with two
targets. Nx now sees both languages:

```sh
npx nx show projects            # guardrail-check, secret-scan
npx nx run secret-scan:test     # pytest, cached
npx nx run secret-scan:scan-repo  # scan every tracked file, never cached
```

Why `nx:run-commands` and not the `@nxlv/python` plugin: see
[ADR 0001](../adr/0001-python-in-nx-with-run-commands.md).

## Inputs: the idea to own

For a TypeScript project, Nx's plugins work out the cache inputs from the config files. For a plain
command, Nx can't know what the command reads, so `project.json` declares it:

- `{projectRoot}/**/*.py` and `pyproject.toml`: the code and test settings.
- `{ "runtime": "python3 --version" }` and `{ "runtime": "python3 -m pytest --version" }`: Nx runs
  these commands and hashes their output, so a different Python or pytest version means a cache miss.

Too few inputs and Nx replays a stale "pass". That's why the whole-repo scan got its own uncached
target: its real input is every file in the repo, and caching it against this package's files would
let a secret added to `apps/` slip past a cached green result.

## `affected`: proof that one command covers both languages

`nx show projects --affected --files=<file>` shows which projects a change touches:

| Changed file                                | Affected projects |
| ------------------------------------------- | ----------------- |
| `packages/secret-scan/secret_scan/rules.py` | `secret-scan`     |
| `apps/guardrail-check/src/lib/checks.ts`    | `guardrail-check` |
| `docs/brief.md`                             | none              |
| `tsconfig.base.json` or `package-lock.json` | both              |

The last row is Nx being cautious: root config files mark every project as affected, even the Python
one that doesn't read them. Correct but slower; fixing it would need custom `namedInputs`, which isn't
worth it at two projects.

## A bug this story found

While checking the cache, `guardrail-check:typecheck` was failing on `main` (TS6307: the Story 1.2 test
helpers weren't in `tsconfig.spec.json`). It had slipped through because the run summary was read
without checking the exit code. Fixed in #22. Lesson for the measurements to come: judge every run by
its exit code, not its last lines of output.

## Setup

`secret-scan:test` needs `pytest` on the `PATH` (for example `python3 -m venv .venv`,
`.venv/bin/pip install pytest`, then activate the venv). The devcontainer (Story 2.1) will install it.
