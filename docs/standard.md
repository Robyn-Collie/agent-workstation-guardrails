# The standard

Six rules for running a coding agent on a developer workstation. They're vendor-neutral and written
from scratch for this repo. Each rule says how this repo implements it and what proves it. Where a rule
isn't built yet, it says so.

## 1. Scoped credentials

An agent gets only the access its task needs. Nothing is inherited from the host.

- **Here:** the devcontainer mounts only the repo. No SSH keys, cloud credentials, git credential
  helper or Docker socket reach it. The one credential it's given on purpose is its model API key
  (rule 3).
- **Proof:** `.devcontainer/verify-sandbox.sh`, run in CI with fake credentials planted on the host
  ([Story 2.1 notes](notes/story-2.1-devcontainer.md)).

## 2. Contained sandbox

The agent runs in a container as a non-root user, with no host credentials mounted and outbound
network limited to an allowlist.

- **Here:** user `node`, no sudo, no Linux capabilities, no-new-privileges; a default-deny egress
  firewall that allows HTTPS only to the hosts in `.devcontainer/egress-allowlist.txt`.
- **Proof:** `verify-sandbox.sh` and `verify-egress.sh` in CI, each with a negative control
  ([Story 2.1](notes/story-2.1-devcontainer.md), [Story 2.2](notes/story-2.2-egress-allowlist.md)).

## 3. Secrets tiers, injected at run time

Where a secret lives, best first:

1. **Nowhere at rest.** Type or paste it into the shell that starts the container, for that session
   only.
2. **An OS-encrypted store.** The OS keychain or a password manager's CLI, read when the container
   starts.
3. **A file, as a last resort.** Plain text, readable only by you, and **outside the repo**. The repo is
   mounted into the sandbox, so a git-ignored file inside it is still visible to the agent.

Whichever tier, the secret is injected into the container at run time. It never goes into the image,
the Dockerfile, a build argument, `containerEnv`, or any file in the repo.

**How the injection works here.** `devcontainer.json` sets

```jsonc
"remoteEnv": { "ANTHROPIC_API_KEY": "${localEnv:ANTHROPIC_API_KEY}" }
```

`remoteEnv` is applied each time a command starts in the container, and `${localEnv:...}` reads the
host's environment at that moment. The value never becomes part of the container's configuration.
Two alternatives look similar and aren't:

| Setting                                   | Where the value ends up                                                                     |
| ----------------------------------------- | ------------------------------------------------------------------------------------------- |
| `remoteEnv` with `${localEnv:...}` (used) | The environment of each process started in the container. Nothing stored.                   |
| `containerEnv`                            | The container's configuration: anyone who can run `docker inspect` on the host can read it. |
| A build argument or `ENV` in a Dockerfile | The image: its history, its config, or a layer. Anyone with the image can read it.          |

**Proof.** `.devcontainer/check-no-baked-secret.sh` runs on the host. Give it a value and an image (and
optionally a container), and it searches the build history, the image and container metadata, every
image layer, and the container's filesystem. CI makes a new random fake key each run, checks that it
reaches the agent, and checks that it's stored nowhere. As a negative control, CI also builds an image
that copies the key in and deletes it one layer later, and requires the checker to catch it. Locally it
also caught a key passed as a build argument and one set with `ENV`
([Story 2.3 notes](notes/story-2.3-runtime-secrets.md)).

**Reading the key from each tier.** These commands are the tools' documented usage. I haven't tested
them in this repo; CI only tests the environment variable they produce. Run the one for your
platform in the shell that starts the container:

```sh
# Tier 1: nothing at rest. Prompts without echoing; gone when the shell exits.
read -rs ANTHROPIC_API_KEY && export ANTHROPIC_API_KEY

# Tier 2, macOS Keychain (store once with: security add-generic-password -a "$USER" -s anthropic-api-key -w)
export ANTHROPIC_API_KEY="$(security find-generic-password -a "$USER" -s anthropic-api-key -w)"

# Tier 2, Linux Secret Service (store once with: secret-tool store --label='Anthropic API key' service anthropic-api-key)
export ANTHROPIC_API_KEY="$(secret-tool lookup service anthropic-api-key)"

# Tier 2, 1Password CLI
export ANTHROPIC_API_KEY="$(op read 'op://Private/anthropic-api-key/credential')"

# Tier 3, a file outside the repo (chmod 600)
export ANTHROPIC_API_KEY="$(cat ~/.config/agent-keys/anthropic)"

# Then start the container from the same shell:
npx @devcontainers/cli@0.89.0 up --workspace-folder .
```

References: `man security` (macOS), `man secret-tool` (libsecret), the 1Password CLI
[`op read` docs](https://developer.1password.com/docs/cli/reference/commands/read/). Windows isn't
covered yet.

**What this doesn't protect.** Every process in the container can read the key, including anything
`npm ci` runs. That's the point of giving it to the agent, but it means the key should be one you can
revoke, with a spending limit, used for nothing else. Anyone who controls the host can read it too.

## 4. Secret scan before code leaves the machine

A zero-dependency scanner runs as a pre-commit hook and again as a pre-push hook.

- **Here:** the scanner exists (`packages/secret-scan`), and `npx nx run secret-scan:scan-repo` scans
  every tracked file.
- **Not yet:** the hooks. That's Story 2.4.

## 5. One workspace per agent

Parallel agents each get their own git worktree, so they never edit the same checkout.

- **Here:** `guardrail-check` has a rule that the convention is documented.
- **Not yet:** the convention itself and a helper script. That's Story 2.6.

## 6. Read-only by default

Tools that agents call (like MCP servers) expose read-only, scoped data unless there's a reason not to.

- **Not yet:** the read-only MCP server is Story 3.1.
