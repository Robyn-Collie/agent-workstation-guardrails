# agent-workstation-guardrails: Build Brief

**Owner:** Robyn Collie · **Status:** Planned · **Timebox:** about 3 weeks of evenings · **Visibility:** private
until the author confirms publishing is allowed

## What this is

A small, working reference for **running AI coding agents safely on a developer workstation** and making
the inner loop fast: a monorepo with a guardrail checker, a sandboxed devcontainer for the agent, a
pre-commit/pre-push secret scan, and a read-only MCP server. Each guardrail comes with a test that
proves it works and a number that shows what it costs.

**The standard it implements (written fresh, vendor-neutral):**

1. **Scoped credentials.** An agent gets only the access its task needs; nothing inherited from the host.
2. **Contained sandbox.** The agent runs in a container as a non-root user, with no host credentials
   mounted and outbound network limited to an allowlist.
3. **Secrets tiers.** No secret at rest by default → OS-encrypted store → git-ignored file as a last
   resort. Secrets are injected at run time, never baked into images.
4. **Secret scan before code leaves the machine.** A zero-dependency scanner runs as a pre-commit hook and
   again as a pre-push hook.
5. **One workspace per agent.** Parallel agents each get their own git worktree, so they never edit the
   same checkout.
6. **Read-only by default.** Tools that agents call (like MCP servers) expose read-only, scoped data unless
   there's a reason not to.

## Repo shape (target)

```
agent-workstation-guardrails/
  apps/
    guardrail-check/        # TypeScript CLI: audits a repo against the standard
    mcp-readonly/           # TypeScript MCP server exposing a scoped, read-only public dataset
  packages/
    secret-scan/            # Python, zero dependencies: pre-commit/pre-push scanner
  .devcontainer/
    devcontainer.json
    Dockerfile
    init-firewall.sh        # egress allowlist
  .githooks/ (or pre-commit config)
  .github/workflows/ci.yml  # Nx affected + cache
  docs/
    brief.md  standard.md  threat-model.md  measurements.md  adr/
  AGENTS.md                 # one entry point any coding agent reads
  nx.json  package.json  tsconfig.base.json
```

## Epics and stories

### Epic 1: Monorepo foundation (Nx + TypeScript + Python) · Week 1

- **1.1 Scaffold the Nx workspace.** Strict `tsconfig`, ESLint, Prettier.
  _Accept:_ `nx graph` shows the projects; `nx run-many -t lint typecheck test` passes.
- **1.2 `guardrail-check` CLI (TypeScript).** Checks a target repo for: an AGENTS.md; a secret-scan hook
  wired in; a devcontainer that isn't root; no `.env` committed; worktree convention documented.
  _Accept:_ unit tests for each check; exits non-zero with a clear report on failure.
- **1.3 `secret-scan` package (Python, zero dependencies).** Regex and entropy rules, an allowlist file,
  fake-secret fixtures. _Accept:_ pytest suite; catches every fixture, no false positives on the repo itself.
- **1.4 Python in Nx.** Wire `secret-scan` into Nx targets (a community plugin such as `@nxlv/python`, or
  plain `nx:run-commands`; **verify which is current**). _Accept:_ one `nx affected` command covers both
  languages.
- **1.5 Measure the loop.** Time lint, typecheck, test and the hooks, cold vs. cached (e.g., `hyperfine`).
  _Accept:_ `docs/measurements.md` with before and after numbers.

### Epic 2: Sandboxed agent devcontainer · Week 2

- **2.1 Devcontainer baseline.** Node and Python, non-root user, workspace-only mount.
  _Accept:_ opens in VS Code Dev Containers; `whoami` isn't root; the host `~/.ssh`, `~/.aws` and similar
  aren't visible.
- **2.2 Egress allowlist.** Default-deny outbound except package registries, GitHub and the model API.
  Study published reference devcontainers for AI coding agents (e.g., Anthropic's Claude Code reference
  devcontainer and its firewall script) and **write your own**. _Accept:_ a test proves a non-allowlisted
  domain is blocked and an allowlisted one works.
- **2.3 Secrets at run time.** Inject the agent's API key at container start from the host's secret
  store or an environment variable, never in the image or the repo. _Accept:_ `docker history` and image
  layers contain no secret; documented in `docs/standard.md`.
- **2.4 Hooks wired in.** `secret-scan` as pre-commit and pre-push. _Accept:_ committing a fixture secret is
  blocked; hook time recorded in measurements.
- **2.5 Cloud parity.** Run the same devcontainer in GitHub Codespaces. _Accept:_ a screenshot or log, plus
  notes on the differences.
- **2.6 Worktree convention.** A script or doc for one worktree per agent, plus a guardrail-check rule for it.

### Epic 3: MCP, CI and write-up · Week 3

- **3.1 `mcp-readonly` server (TypeScript MCP SDK).** Read-only tools over a small public dataset (e.g., a
  wildfire summary table from USFS public data): list, query with limits, describe the schema.
  _Accept:_ works with an MCP client; no write paths; inputs validated; tests.
- **3.2 CI.** GitHub Actions running `nx affected` with caching, plus `secret-scan` and `guardrail-check`
  on the repo itself. _Accept:_ green CI; cache hit rate recorded.
- **3.3 Threat model.** `docs/threat-model.md`: what the sandbox stops (credential theft, exfiltration,
  runaway writes) and what it doesn't. Honest limits.
- **3.4 README.** The standard in plain language, a quick start, the measurements, the limits, "how I'd
  roll this out to a team" (baseline, pilot, measure, iterate), and a note that it's written from scratch
  as a reference.
- **3.5 ADRs.** Short architecture decision records for the big choices (why Nx, why zero-dependency
  scanning, why default-deny egress).

## Definition of done (the whole project)

- A fresh clone → open in devcontainer → `nx run-many -t lint typecheck test` → green, with no host
  credentials visible to the agent.
- Every claim in the README is backed by a test or a number in `docs/measurements.md`.
- No real secrets anywhere in history (run the scanner over the full git history before going public).
- The author can explain every file in an interview.

## Out of scope

Multi-user secret servers, Kubernetes, enterprise SSO, and anything that needs paid infrastructure.
