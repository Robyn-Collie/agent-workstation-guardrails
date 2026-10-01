# Story 2.3: Secrets at run time

Notes for explaining this story in a review or interview.

## The problem

The agent needs one real secret: its model API key. Stories 2.1 and 2.2 kept everything else out. The
risk now is putting the key in the wrong place. A Docker image is a stack of layers plus a config file,
and anything that goes into it stays there: in the build history, in the config, or in a layer. That
includes a file you delete in a later step. Anyone who gets the image gets the key. The rule is to
inject the key when the container runs, never when the image is built. The tiers for where the key
lives on the host are in [docs/standard.md](../standard.md#3-secrets-tiers-injected-at-run-time).

## What changed

| File                                     | What it does                                                                                                                                                                                                                                  |
| ---------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `.devcontainer/devcontainer.json`        | `remoteEnv` gains `"ANTHROPIC_API_KEY": "${localEnv:ANTHROPIC_API_KEY}"`.                                                                                                                                                                     |
| `.devcontainer/check-no-baked-secret.sh` | Runs on the host. Searches the build history, image metadata, every image blob (layers and config), container metadata and the container's filesystem for a value. Takes the value from an environment variable, so it isn't visible in `ps`. |
| `.devcontainer/verify-sandbox.sh`        | Allows `ANTHROPIC_API_KEY`, and still fails on any other credential variable.                                                                                                                                                                 |
| `.github/workflows/devcontainer.yml`     | Makes a random, masked fake key each run and proves it arrives but isn't stored. Includes a negative control.                                                                                                                                 |
| `docs/standard.md`                       | The six rules of the standard, with the secrets tiers and how to read a key from each.                                                                                                                                                        |

## Why `remoteEnv` and not the alternatives

The devcontainer spec has two ways to set an environment variable. `containerEnv` is passed to
`docker run`, so the value becomes part of the container's configuration. `remoteEnv` is applied each
time a tool starts a process in the container. `${localEnv:NAME}` reads the host's environment at that
moment.

I checked this rather than trusting the description, because the `devcontainer` CLI 0.89.0 records
`remoteEnv` in a `devcontainer.metadata` label on the container (the CLI has a hidden
`--omit-config-remote-env-from-metadata` flag, which is how I noticed). A local test with a random
value showed the label keeps only the unresolved text `${localEnv:ANTHROPIC_API_KEY}`, not the value.
Also, `docker inspect` of the container and the image didn't contain the value. A second `exec` with a
different host value got the new value, so the key is read fresh each time and nothing is cached.

## Proof

**CI (2026-09-30, GitHub-hosted `ubuntu-latest`,
[run 36753700515](https://github.com/Robyn-Collie/agent-workstation-guardrails/actions/runs/36753700515)):**

- The fake key reached the agent: `printenv ANTHROPIC_API_KEY` inside the container matched the host
  value.
- The checker found it nowhere: the build history, image metadata, image blobs, container metadata and
  container filesystem were all clean. The check took 28 s.
- **Negative control:** CI built an image that copies the key in and deletes it in the next layer. The
  history and metadata checks passed, because the key really isn't there. The layer check failed, as
  required. This is why the layer check exists: the finished filesystem looks clean.
- Every earlier check still passed (18 sandbox, 9 egress, the toolchain).

**Local negative controls (2026-09-30, build container):** the checker also caught a key passed as a
build argument (in the history and the image config) and one set with `ENV` (in the history, metadata
and config).

**Speed:** the first version took 203 s locally, because it asked `tar` to list, then extract, every
layer. A layer is already a tar file that stores contents as-is, so the checker now searches
uncompressed layers directly and only decompresses gzip or zstd ones. That brought the time down to
51 s locally and 28 s in CI. Most of the time left is `docker save` and `docker export` copying the
roughly 600 MB image.

## Limits, honestly

- **Every process in the container can read the key.** That includes install scripts from `npm ci`
  and `pip install`. That's inherent in giving the agent a key, so use a key you can revoke, with a
  spending limit, used for nothing else.
- **The checker finds a value you give it.** It proves this key isn't stored. It doesn't find secrets
  it doesn't know about; that's the secret scanner's job, and the scanner runs on the repo, not the
  image.
- **The key-store commands in `docs/standard.md` are untested here.** They're the tools' documented
  usage. CI only tests the environment variable they produce.
- **VS Code is untested.** I expect VS Code to read `${localEnv:...}` from its own environment, which
  would mean starting it from a shell that has the key, but I've only tested the `devcontainer` CLI.
- **The host is trusted.** Anyone who can read the host process's environment can read the key.
