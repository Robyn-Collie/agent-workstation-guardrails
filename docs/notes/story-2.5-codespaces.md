# Story 2.5: Cloud parity (GitHub Codespaces)

Notes for explaining this story in a review or interview.

## The question

Does the same `devcontainer.json` give the same sandbox in GitHub Codespaces as on a laptop? A
devcontainer is a spec. Each host that runs it (the `devcontainer` CLI, VS Code, Codespaces) can add
its own settings, so the only way to know is to run it and look.

## What happened

**First run (2026-10-05).** The Codespace built our image and started the container, then creation
failed. The recovery container couldn't pull its image: `connect EHOSTUNREACH`.

**Cause.** Codespaces starts the container with `--network host`, so the container shares the
Codespace machine's network instead of getting its own. Our entrypoint loaded the egress firewall
as designed, and the rules applied to the whole machine. They blocked the machine's own traffic.
`EHOSTUNREACH` is the error our `reject with icmpx type admin-prohibited` rule produces.

**Fix ([PR #31](https://github.com/Robyn-Collie/agent-workstation-guardrails/pull/31)).** The
firewall now checks which network it's on before loading. In a container's own network, every
interface except `lo` is one end of a virtual cable (a veth pair), and its `iflink` names the other
end. On a host, a network card or bridge is its own link (`iflink` equals `ifindex`). If the
firewall sees one, it refuses (exit 3) and the container doesn't start. CI runs the script with
`--network host` and checks the refusal.

## Differences seen in the Codespaces creation log

| Codespaces adds                                                        | Why it matters for an agent sandbox                                                                                     |
| ---------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------- |
| `--network host`                                                       | No network of its own, so no egress firewall is possible. This is the blocker.                                          |
| Its own devcontainer CLI, 0.83.3 (we pin 0.89.0)                       | Behaviour can differ by version; `--mount-git-worktree-common-dir` (Story 2.6) isn't among the options it was run with. |
| `/root/.codespaces/shared` mounted at `/workspaces/.codespaces/shared` | Codespaces passes `--secrets-file` from that folder, so your Codespaces secrets are on a path inside the container.     |
| The host's `/mnt/containerTmp` mounted at `/tmp`                       | A host folder the sandbox check doesn't expect.                                                                         |
| The whole `/workspaces` folder mounted, not just the repo              | Anything else in that folder is visible.                                                                                |
| `--cap-add sys_nice`                                                   | One Linux capability on top of ours (we drop all and add back three).                                                   |

These are read from the `devcontainer up` and `docker run` command lines in the log. I didn't see
inside a running Codespace, because none got that far.

## Decision

The agent sandbox isn't supported in Codespaces. With host networking there is no way to limit the
agent's outbound traffic without also limiting the machine, and the standard requires that limit.
The sandbox refuses to start there rather than run without it. Agents run in the local devcontainer.

## Limits, honestly

- **One run, one log.** Codespaces may change these settings; the check in the firewall doesn't
  depend on Codespaces, only on what the network looks like.
- **The interface check is a rule of thumb.** Some container setups (for example, rootless Podman
  with a `tap` device) also have an interface that is its own link. There the firewall refuses too,
  which is the safe way to be wrong.
- **Not tested: Codespaces for people, without the firewall.** That would show what a running
  Codespace exposes (tokens, the secrets folder). Out of scope for this story.
