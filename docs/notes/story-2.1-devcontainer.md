# Story 2.1: Devcontainer baseline

Notes for explaining this story in a review or interview.

## What a devcontainer is, and why an agent should run in one

A devcontainer is a Docker container described by `.devcontainer/devcontainer.json`. Editors (VS Code,
JetBrains), GitHub Codespaces and the `devcontainer` CLI all read the same file, build the image, mount
your repo into it, and run your tools inside. For people, the win is "clone, open, everything works."
For a coding agent, the win is a **boundary**: the agent can only touch what the container can see, so
you decide what that is instead of inheriting everything on your laptop (SSH keys, cloud credentials,
other repos).

## The files

| File                                 | What it does                                                                                                                                                                                  |
| ------------------------------------ | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `.devcontainer/Dockerfile`           | Starts from Microsoft's public Node 22 devcontainer image, **pinned by digest**; adds `python3-venv` and npm 11; **deletes the base image's passwordless sudo**; switches to the `node` user. |
| `.devcontainer/devcontainer.json`    | Runs as `node`; mounts only the repo at `/workspace`; `--cap-drop=ALL` and `--security-opt=no-new-privileges`; installs dependencies inside the container on first start.                     |
| `.devcontainer/verify-sandbox.sh`    | Run inside the container. 18 checks, `[PASS]`/`[FAIL]`, exits with the number of failures.                                                                                                    |
| `.github/workflows/devcontainer.yml` | Builds the real image on a GitHub runner, plants fake credentials on the runner, and runs the checks inside.                                                                                  |

## Proof

**What the checks cover:** not root; `sudo` unavailable; no-new-privileges set; no Linux capabilities;
none of `~/.ssh`, `~/.aws`, `~/.azure`, `~/.kube`, `~/.config/gcloud`, `~/.config/gh`,
`~/.docker/config.json`, `~/.netrc`, `~/.git-credentials`; no Docker socket; no credential environment
variables; no forwarded SSH agent; no git credential helper; nothing mounted from the host except
`/workspace`.

**Positive run (2026-09-29, build container):** all checks passed, started with the `devcontainer` CLI
0.89.0 while the host had `~/.aws`, `~/.ssh`, `AWS_ACCESS_KEY_ID=FAKE` and `SSH_AUTH_SOCK` set. One caveat:
that environment blocks the Debian package mirrors, so the local test build skipped the two
package-install lines (python3-venv, npm 11). None of the checks depend on them. The full image is built
by the CI workflow.

**Full image in CI (2026-09-29, GitHub-hosted `ubuntu-latest`,
[run 36599744460](https://github.com/Robyn-Collie/agent-workstation-guardrails/actions/runs/36599744460)):**
the real Dockerfile built and started in 68 s including `npm ci` and pytest install; all 18 checks passed
with fake credentials planted on the runner; `nx run-many -t lint typecheck test` passed inside the
container (5 tasks, cold cache, 3.2 s Nx run duration).

**Negative controls:** the same script, run in unsafe containers, fails as it should:

- Base image as root, with `~/.aws` mounted and fake credentials in the environment: 8 checks failed.
- Base image as `node` but without our Dockerfile: 2 failed (`sudo works without a password`,
  `no-new-privileges is not set`). That's why the Dockerfile deletes the sudoers entry.
- A git credential helper configured inside the container: 1 failed.

A check you've never seen fail isn't a check.

## Limits, honestly

- **VS Code forwards credentials on its own.** The Dev Containers extension shares your local SSH agent
  and git credential helper by default
  ([docs](https://code.visualstudio.com/remote/advancedcontainers/sharing-git-credentials)). That happens
  outside `devcontainer.json`, so this repo can't turn it off. `verify-sandbox.sh` detects both; if
  you open this in VS Code and those two checks fail, that's the extension, and the fix is a user
  setting, not a repo change. Test on your machine before trusting it.
- **Network isn't restricted yet.** The container can reach the internet. That's Story 2.2.
- **Docker itself is trusted.** Anyone who controls the Docker daemon on the host controls the
  container. This protects the host from the agent, not the agent from the host.
