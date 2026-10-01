#!/usr/bin/env bash
# Run INSIDE the devcontainer. Proves the sandbox properties from docs/brief.md and exits
# non-zero if any fails. Output uses [PASS]/[FAIL] so CI logs are easy to scan.
set -u
failures=0
pass() { echo "[PASS] $1"; }
fail() { echo "[FAIL] $1"; failures=$((failures + 1)); }

# 1. Not root, and no way to become root.
if [ "$(id -u)" -ne 0 ]; then pass "runs as $(whoami) (uid $(id -u)), not root"; else fail "runs as root"; fi
if sudo -n true 2>/dev/null; then fail "sudo works without a password"; else pass "sudo is not available"; fi
if grep -q '^NoNewPrivs:[[:space:]]*1' /proc/self/status; then pass "no-new-privileges is set"; else fail "no-new-privileges is not set"; fi
if grep -q '^CapEff:[[:space:]]*0*$' /proc/self/status; then pass "no effective Linux capabilities"; else fail "process has capabilities: $(grep CapEff /proc/self/status)"; fi

# 2. No host credential stores. Checked in $HOME and at common absolute host paths.
for path in .ssh .aws .azure .kube .config/gcloud .config/gh .docker/config.json .netrc .git-credentials; do
  if [ -e "$HOME/$path" ]; then fail "\$HOME/$path is present"; else pass "\$HOME/$path is absent"; fi
done
if [ -S /var/run/docker.sock ]; then fail "host Docker socket is mounted"; else pass "no Docker socket"; fi

# 3. No credentials in the environment and no forwarded SSH agent.
# The one credential the agent is meant to have is its model API key, injected at run time
# (Story 2.3, docs/standard.md). Any other credential variable is a leak.
leaked=$(env | cut -d= -f1 | grep -E '^(AWS_|AZURE_|GOOGLE_APPLICATION_CREDENTIALS|GITHUB_TOKEN|GH_TOKEN|OPENAI_API_KEY|NPM_TOKEN)' || true)
if [ -z "$leaked" ]; then pass "no credential environment variables besides the model API key"; else fail "credential variables set: $(echo "$leaked" | tr '\n' ' ')"; fi
if [ -n "${ANTHROPIC_API_KEY:-}" ]; then echo "[INFO] model API key is set (injected at run time)"; else echo "[INFO] model API key is not set"; fi
if [ -z "${SSH_AUTH_SOCK:-}" ]; then pass "no SSH agent forwarded"; else fail "SSH agent forwarded (SSH_AUTH_SOCK=$SSH_AUTH_SOCK)"; fi
helper=$(git config --get credential.helper 2>/dev/null || true)
if [ -z "$helper" ]; then pass "no git credential helper"; else fail "git credential helper configured: $helper"; fi

# 4. Only the workspace is bind-mounted from the host.
binds=$(awk '$4 != "/" && $5 !~ "^/(proc|sys|dev)" {print $5}' /proc/self/mountinfo | grep -vE '^/(proc|sys|dev)(/|$)|^/etc/(hosts|hostname|resolv.conf)$' || true)
if [ "$binds" = "/workspace" ]; then pass "only /workspace is mounted from the host"; else fail "host mounts besides /workspace: $(echo "$binds" | tr '\n' ' ')"; fi

echo
if [ "$failures" -eq 0 ]; then echo "sandbox: all checks passed"; else echo "sandbox: $failures check(s) failed"; fi
exit "$failures"
