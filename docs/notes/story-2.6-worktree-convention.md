# Story 2.6: One worktree per agent

Notes for explaining this story in a review or interview. The convention itself is in
[docs/worktrees.md](../worktrees.md).

## What a worktree is, and why one per agent

A git worktree is a second working folder for the same repository. It has its own checkout and its
own branch, but shares the history in the main repo's `.git` folder. Two agents in two worktrees can't
overwrite each other's files, and each one's work arrives as an ordinary branch. Cloning twice would
also separate them, but then the clones don't share branches or objects, and keeping them in sync is
extra work.

## What changed

| File                                     | What it does                                                                                                                                      |
| ---------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------- |
| `docs/worktrees.md`                      | The convention: one worktree and one `agent/<name>` branch per agent, next to the repo, each in its own sandbox; you merge.                       |
| `scripts/agent-worktree.sh`              | `new`, `list`, `remove`. Validates the name, refuses git older than 2.48, refuses to remove a worktree with uncommitted changes.                  |
| `.devcontainer/devcontainer.json`        | Drops the custom `workspaceMount` so the CLI's default layout applies, which `--mount-git-worktree-common-dir` needs.                             |
| `.devcontainer/verify-sandbox.sh`        | The mount check allows the workspace plus, in a worktree, the shared `.git` folder. Anything else mounted from the host still fails.              |
| `apps/guardrail-check/src/lib/checks.ts` | `worktree-convention` now needs the actual command (`git worktree add`) in AGENTS.md, `docs/` or `scripts/`. Mentioning the word isn't enough.    |
| `.github/workflows/devcontainer.yml`     | New step: create a worktree, start a sandbox in it, run the sandbox checks there, commit from inside, and confirm the main checkout is untouched. |

## The problem I hit: the `.git` pointer

A worktree's `.git` is a file containing a path back to the main repo's `.git` folder. My first try
started a sandbox in a worktree and every git command failed with "not a git repository": the path
pointed to a folder that wasn't mounted.

The devcontainer CLI 0.89.0 has a flag for this, `--mount-git-worktree-common-dir`, which also mounts
the shared `.git` folder. Two conditions, both found by testing rather than from the docs:

1. **The pointer must be relative.** Inside the container the folders sit at different absolute paths
   than on the host. `git worktree add --relative-paths` writes relative pointers. It's new in git
   2.48, and older git (this build machine has 2.43) can't read a repo that uses it. The script checks
   the version and refuses with a clear message.
2. **The CLI's default mount layout.** The flag places both folders under `/workspaces/` so the
   relative path works. Our custom `workspaceMount` put the repo somewhere else, which broke it. So the
   custom mount is gone; the default mounts the same single folder.

## Proof

**CI** runs the whole path on a GitHub-hosted runner: `agent-worktree.sh new ci-agent`, start a
sandbox in the worktree, run all of `verify-sandbox.sh` inside it, commit from inside the sandbox, then
check from the host that the commit is on `agent/ci-agent`, the file isn't in the main checkout, and
the main checkout's `HEAD` hasn't moved.

**Locally** (git 2.55 in a container): a bad name, a duplicate name, running `new` from inside another
worktree, `list`, `remove` refusing a dirty worktree, then removing a clean one, and the usage message.
`new` took 139 ms. On git 2.43 the script exits with code 2 and says why.

**guardrail-check** passes `worktree-convention` on this repo (4 passed, 1 failed; AGENTS.md is still
missing). Two new tests: a command in a script passes, and a doc that mentions worktrees without the
command fails. 24 tests in total.

## Limits, honestly

- **The `.git` folder is shared and writable.** An agent can read every branch and could change the
  shared git config, including turning hooks off for every worktree. That was already true with one
  agent. Server-side checks (Story 3.2) are the backstop.
- **git 2.48 or newer on the host.**
- **Dependencies aren't shared.** Each worktree's sandbox runs `npm ci` and the pytest install.
- **Untested in VS Code**, and in Codespaces (Story 2.5).
