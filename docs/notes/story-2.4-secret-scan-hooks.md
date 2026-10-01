# Story 2.4: Secret-scan hooks

Notes for explaining this story in a review or interview.

## What a git hook is, and why two of them

A git hook is a script git runs at a set moment. If the script exits non-zero, git stops. `pre-commit`
runs before a commit is recorded; `pre-push` runs before anything is sent to a remote. Git looks for
hooks in `.git/hooks`, which isn't version-controlled, so a team can't share them that way. Setting
`core.hooksPath` points git at a folder in the repo instead, here `.githooks/`.

Two hooks because they catch different mistakes. `pre-commit` is the fast, early catch: it scans what's
staged. But it can be skipped (`git commit --no-verify`), and it only sees one commit. `pre-push` is the
last point before code leaves the machine, and it scans **every commit being pushed**. A secret that was
committed and then deleted in a later commit is still in the history, and pushing would publish it.

## The files

| File                                      | What it does                                                                                                                                 |
| ----------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------- |
| `.githooks/pre-commit`                    | Runs the scanner with `--staged`.                                                                                                            |
| `.githooks/pre-push`                      | Runs the scanner with `--pre-push`; git passes the refs being pushed on stdin.                                                               |
| `.githooks/run-secret-scan`               | Shared by both: runs the scanner from source (no install, it has no dependencies). Fails closed if Python is missing.                        |
| `packages/secret-scan/secret_scan/cli.py` | New `--pre-push` mode: works out which commits a push sends and scans each file each commit added or changed.                                |
| `package.json`                            | A `prepare` script sets `core.hooksPath`. npm runs `prepare` after `npm install` and `npm ci`, so cloning and installing turns the hooks on. |

**How `--pre-push` picks commits.** Git gives the hook one line per ref:
`<local ref> <local sha> <remote ref> <remote sha>`. For an existing branch the commits are
`remote..local`. For a new branch (remote sha all zeros) they're the commits no remote branch has yet
(`git rev-list <local> --not --remotes`). A deleted branch (local sha all zeros) sends nothing. Findings
name the commit, for example `settings.py (commit 1a2b3c4d)`, so you know where to look.

## Proof

**End-to-end tests** (`packages/secret-scan/tests/test_hooks.py`) build a throwaway repo and a bare
remote, point `core.hooksPath` at this repo's real hooks, and use a fake key assembled at run time:

- Committing a fake AWS key is blocked, nothing is committed, and the output names the rule without
  echoing the key.
- Committing the key with `--no-verify` and deleting it in the next commit, then pushing, is blocked by
  `pre-push`, and the remote stays empty.
- Clean commits and pushes go through.

**Negative control:** pointed at a folder with no hooks, the two "blocked" tests fail, so they test the
hooks, not something else.

**Unit tests** cover the commit selection: only new commits for an existing branch, full history for a
new branch, nothing for a deletion, and the allowlist still matching when findings carry a commit.

All 39 secret-scan tests pass on Python 3.9, 3.11 and 3.13.

**Cost:** the hooks add about 0.09 s to a commit and 0.08 s to a push
([measurements](../measurements.md)).

**guardrail-check** now passes its `secret-scan-hook` check on this repo (4 passed, 1 failed; the one
left is AGENTS.md).

**Nx cache:** the tests now depend on files outside the project (`.githooks/`), so I added
`{workspaceRoot}/.githooks/*` to the test target's inputs. Without it, editing a hook wouldn't re-run
the tests; Nx would replay the cached pass.

## Limits, honestly

- **`--no-verify` skips both hooks.** Hooks protect against mistakes, not against someone determined.
  The backstop is the same scan running in CI on the server (Story 3.2).
- **Hooks must be enabled.** `npm install` does it. Someone who clones and commits without installing
  has no hooks. `guardrail-check` checks that the hooks exist in the repo, not that they're enabled on
  your machine.
- **The pre-push scan is per file, per commit.** Pushing a long history scans every file every commit
  touched; fine for a feature branch, slow for a first push of a big repo.
- **It finds what its rules know.** Vendor prefixes plus an entropy check. A secret with no known
  prefix and low randomness gets through (see [Story 1.3](story-1.3-secret-scan.md)).
