# One worktree per agent

When two coding agents (or an agent and you) work at the same time, each gets its own git worktree:
a separate folder with its own checkout and branch, sharing one repository. They never edit the same
files on disk, and each one's changes arrive as an ordinary branch you review and merge.

## The convention

- **One worktree per agent, one branch per worktree.** Branches are named `agent/<name>`.
- **Worktrees live next to the repo**, in `<repo>.worktrees/<name>`, never inside it. (Inside the repo
  they'd be mounted into every other agent's sandbox.)
- **Each agent runs in its own sandbox**, started in its worktree.
- **You merge.** An agent pushes its branch and opens a pull request; it doesn't merge into `main`.

## Commands

`scripts/agent-worktree.sh` wraps the git commands so names and paths stay consistent. It needs git
2.48 or newer (`git --version`).

```sh
scripts/agent-worktree.sh new docs-fix        # ../<repo>.worktrees/docs-fix on branch agent/docs-fix
scripts/agent-worktree.sh list
scripts/agent-worktree.sh remove docs-fix     # refuses if there are uncommitted changes; keeps the branch
```

Under the hood, `new` runs:

```sh
git worktree add --relative-paths -b agent/docs-fix ../<repo>.worktrees/docs-fix HEAD
```

Then start that agent's sandbox in the worktree:

```sh
npx @devcontainers/cli@0.89.0 up --workspace-folder ../<repo>.worktrees/docs-fix --mount-git-worktree-common-dir
```

## Why `--relative-paths` and `--mount-git-worktree-common-dir`

A worktree doesn't have its own `.git` folder. It has a `.git` _file_ that points back to the main
repo's `.git` folder, where all the history lives. In a sandbox that mounts only the worktree, that
pointer leads nowhere and every git command fails.

`--mount-git-worktree-common-dir` tells the devcontainer CLI to also mount the main repo's `.git`
folder. It only works if the pointer is a relative path, because the folders sit at different absolute
paths inside the container than on your machine. Git writes relative pointers only when asked
(`--relative-paths`, new in git 2.48). The CLI's help text says the same; check it with
`npx @devcontainers/cli@0.89.0 up --help`.

## What the agent can and can't see

- **Can:** its own worktree, and the shared `.git` folder: all branches and history, and the repo's
  git config.
- **Can't:** the main checkout's files, or any other worktree's files.

`verify-sandbox.sh` checks that those two folders are the only things mounted from the host.

## Limits

- **The `.git` folder is shared.** An agent can read every branch, and could change the shared git
  config (for example, turn off the hooks for every worktree). That was already true with one agent:
  the `.git` folder was inside its workspace. Server-side checks (Story 3.2) are the backstop.
- **Your git must be 2.48 or newer.** Older git can't read a worktree created with relative paths, and
  the script refuses to run.
- **Each worktree installs its own dependencies.** `node_modules` and `.venv` aren't shared, so every
  new sandbox runs `npm ci` and the pytest install.
- **Untested in VS Code.** Tested with the `devcontainer` CLI only.
