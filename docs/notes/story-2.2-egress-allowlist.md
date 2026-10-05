# Story 2.2: Egress allowlist

Notes for explaining this story in a review or interview.

## Why an agent sandbox needs an egress allowlist

Story 2.1 kept host credentials out of the container. But an agent that can read your code and reach
the whole internet can still send that code anywhere: a paste site, a webhook, a server someone planted
in a prompt injection. **Egress** is outbound network traffic. An **allowlist** flips the default: the
container can reach nothing except the few places the work actually needs (package registries, GitHub,
the model API). Anything else is refused at the network layer, whatever the agent was talked into.

## What I studied, and what I did differently

The brief asked me to study a published reference and write my own. The reference was Anthropic's Claude
Code devcontainer (`.devcontainer/init-firewall.sh` in the public `anthropics/claude-code` repo, read on
2026-09-29). Its idea
is sound: resolve the allowed hosts at start, put their addresses in a set, drop everything else. I wrote
a separate implementation because this repo's sandbox has constraints the reference doesn't:

| Question                        | Reference                                                                                                 | This repo                                                                                                                                           |
| ------------------------------- | --------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------- |
| Who loads the rules?            | `node` runs the script through a `sudo` rule.                                                             | The entrypoint loads them as root, then drops to `node` for good. No `sudo` at all, so Story 2.1's no-new-privileges and no-sudo checks still hold. |
| Can the agent change the rules? | The sudo rule lets `node` re-run the script, which starts by flushing all rules.                          | No. `node` has no capabilities, so `nft` fails with "Operation not permitted". A check proves it.                                                   |
| IPv6                            | `iptables` only covers IPv4.                                                                              | One nftables `inet` table covers IPv4 and IPv6, so there's no unfiltered IPv6 path.                                                                 |
| Ports                           | Allowed hosts on any port; SSH (22) open to any host.                                                     | Only HTTPS (443) to allowed hosts. SSH is closed; use git over HTTPS.                                                                               |
| DNS                             | UDP 53 to any server.                                                                                     | Only to the resolvers Docker put in `/etc/resolv.conf`.                                                                                             |
| Other rules in the container    | Flushes all tables, then restores Docker's DNS rules.                                                     | Adds its own table and touches nothing else.                                                                                                        |
| If setup fails                  | Runs as `postStartCommand`, after the container is already up; a failure is reported but doesn't stop it. | **Fails closed**: the entrypoint exits, so the container stops. Lifecycle commands wait for a ready marker and fail if it never appears.            |

## The files

| File                                        | What it does                                                                                                                        |
| ------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------- |
| `.devcontainer/egress-allowlist.txt`        | The allowed hosts, one per line, with a comment for why each is there. Reviewable in a PR like any other code.                      |
| `.devcontainer/egress-firewall.sh`          | Loads a deny-by-default nftables table in one atomic step, then resolves each allowed host and adds its addresses. Writes a marker. |
| `.devcontainer/sandbox-entrypoint.sh`       | Runs the firewall as root, then `exec setpriv` to become `node`.                                                                    |
| `.devcontainer/wait-for-egress-firewall.sh` | Run by `onCreateCommand` and `postStartCommand`: blocks until the marker exists, so `npm ci` never runs before the firewall.        |
| `.devcontainer/verify-egress.sh`            | Run inside the container as `node`. The acceptance test.                                                                            |

`devcontainer.json` changed in three ways: `containerUser` is `root` (only the entrypoint runs as root),
`overrideCommand` is `false` (so the image's entrypoint runs instead of the CLI's keep-alive command), and
three capabilities are added back after `--cap-drop=ALL`: `NET_ADMIN` to load rules, `SETUID` and `SETGID`
to switch to `node`. When a process leaves uid 0 the kernel clears its capabilities, so none of the three
reach anything running as `node`. `verify-sandbox.sh`'s "no effective capabilities" check still passes.

## Why nftables, in one paragraph

`iptables` is the older Linux firewall tool; `nftables` (`nft`) replaced it in the kernel and is the
default backend on Debian. Two features made it the simpler choice here. An `inet` table filters IPv4 and
IPv6 with one set of rules, where iptables needs a second tool (`ip6tables`) and a second copy. And
`nft -f` loads a whole ruleset as one transaction, so there's never a moment with half the rules loaded.
Sets (`allow_v4`, `allow_v6`) are built in, so there's no separate `ipset` tool either.

## Proof

**Acceptance test (`verify-egress.sh`):**

- Blocked: `https://example.com`, `http://example.com`, and `https://1.1.1.1` (a raw IP, to show DNS
  isn't the only gate).
- Allowed: `https://registry.npmjs.org/`, `https://pypi.org/simple/`, `https://api.github.com/zen`.
- The firewall loaded (ready marker), `node` can't read or change the rules, and PID 1 no longer runs as
  root.

**CI (2026-09-29, GitHub-hosted `ubuntu-latest`,
[run 36602350548](https://github.com/Robyn-Collie/agent-workstation-guardrails/actions/runs/36602350548)):**
all 9 egress checks and all 18 sandbox checks passed. `npm ci` and `pip install pytest` ran through the
firewall during setup, and `nx run-many -t lint typecheck test` passed inside the container afterwards.
Loading the firewall took **417 ms** (one run), most of it the GitHub ranges fetch: without it, the
first run took 166 ms.

**The first CI run failed, usefully**
([run 36601883071](https://github.com/Robyn-Collie/agent-workstation-guardrails/actions/runs/36601883071)):
8 of 9 checks passed, but `https://api.github.com/zen` was refused a second after the firewall had allowed
`api.github.com`. The second run's log shows why this is likely: each lookup of `api.github.com` returned
a single address (`140.82.114.5` that time), while GitHub serves the name from several. One lookup at
start can miss the address the next request uses. I haven't proved it was a different address, since the
first run didn't log them; it now does. The fix: GitHub publishes its address ranges at
`https://api.github.com/meta`, so the firewall also adds the `web`, `api` and `git` ranges (80 CIDRs in
that run). That's why the allowlist says "hosts" but GitHub gets ranges.

**Negative control:** CI runs the same script in the plain base image (no firewall) and requires it to
fail. In the run above it failed 5 checks: no ready marker, no `nft`, and all three blocked destinations
reachable. (The PID 1 check passed there, because that test container was started as `node` directly;
it only means something in the real container.)

**Local tests (build container, 2026-09-29):** the build container blocks Debian's package mirrors, so
the full image is only built in CI. Locally I loaded the ruleset with the host's `nft` inside an isolated
network namespace (`unshare -n -m`), which checked the syntax and that a re-run replaces the table
cleanly. The same test caught a real bug: with the allowlist file missing, the script still marked the
firewall ready with zero hosts, because a failure inside `< <(...)` doesn't stop a bash script even with
`set -e`. It now refuses a missing or empty allowlist; both cases exit 1 and leave the deny-all rules in
place.

## Limits, honestly

- **It needs the container's own network.** With `--network host`, which GitHub Codespaces adds, the
  rules would apply to the host itself. The first Codespaces test (2026-10-05) did exactly that: the
  firewall blocked the Codespace's own traffic and creation failed. The script now refuses to load
  (exit 3) when it sees a host interface, so the container doesn't start, and CI checks the refusal.
  _Added 2026-10-05._
- **Allowed hosts are allowed for everything.** GitHub is on the list, so an agent could push code to any
  GitHub repo or gist it can authenticate to. The allowlist narrows where data can go; it doesn't make
  those places safe. Keeping tokens out of the container (Story 2.1, 2.3) is the other half.
- **DNS is a side channel.** Queries to the allowed resolver can carry data in hostnames (DNS
  tunnelling). Closing that needs a filtering DNS resolver; not done here.
- **Addresses are resolved once, at start.** CDNs (npm and PyPI sit behind them) can change addresses,
  as the first CI run showed for GitHub. GitHub is covered by its published ranges; the others aren't.
  If a registry call starts failing mid-session, restart the container to re-resolve. I haven't measured
  how often that happens.
- **GitHub's ranges are a copy.** _Updated 2026-10-02._ The first version fetched them from
  `api.github.com/meta` inside the container at start. On 2026-10-02 that fetch failed in CI
  ([run 36943728991](https://github.com/Robyn-Collie/agent-workstation-guardrails/actions/runs/36943728991)),
  most likely GitHub's unauthenticated rate limit, which is per IP address and shared on CI runners.
  The firewall fell back to single lookups and GitHub was refused, the same failure as the first run.
  GitHub's main ranges are now listed in `egress-allowlist.txt`, and the container no longer makes
  that call. CI resolves GitHub's hostnames several times each run and fails if any address falls
  outside the listed ranges. It also reports how much of GitHub's full published list they cover; that
  list includes many single addresses for regional services this sandbox doesn't use.
- **Shared CDN addresses.** An allowed address may also serve other sites on the same CDN. The filter
  works on IP addresses, not hostnames.
- **Untested in VS Code.** The VS Code Dev Containers extension installs its server and extensions from
  Microsoft's hosts, which aren't on the list. I've only run this with the `devcontainer` CLI, which
  doesn't need them. Expect to add hosts if you open it in VS Code, and verify on your machine.
- **Docker is still trusted.** `docker exec -u root` from the host bypasses everything. This protects the
  host from the agent, not the agent from the host.
