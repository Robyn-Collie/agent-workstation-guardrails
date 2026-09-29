#!/usr/bin/env bash
# Run INSIDE the devcontainer as the agent user. Proves the egress allowlist from
# docs/brief.md Story 2.2: non-allowlisted destinations are refused, allowlisted ones
# work, and the agent cannot change the rules. Exits with the number of failed checks.
set -u
failures=0
pass() { echo "[PASS] $1"; }
fail() { echo "[FAIL] $1"; failures=$((failures + 1)); }
reachable() { curl -sS -o /dev/null --max-time 10 "$1" 2>/dev/null; }

# 1. The firewall is loaded and out of the agent's reach.
if [ -f /run/sandbox/egress-ready ]; then pass "egress firewall loaded at start"; else fail "egress firewall ready marker missing"; fi
if ! command -v nft >/dev/null; then
  fail "nft is not installed, so no firewall can be loaded"
elif nft list ruleset >/dev/null 2>&1; then
  fail "agent user can read and change firewall rules"
else
  pass "agent user cannot read or change firewall rules"
fi
if grep -q '^Uid:[[:space:]]*0[[:space:]]' /proc/1/status; then fail "PID 1 still runs as root"; else pass "PID 1 dropped root after loading the firewall"; fi

# 2. Destinations that are not on the allowlist are refused.
for url in https://example.com https://1.1.1.1 http://example.com; do
  if reachable "$url"; then fail "$url is reachable (should be blocked)"; else pass "$url is blocked"; fi
done

# 3. Allowlisted destinations work.
for url in https://registry.npmjs.org/ https://pypi.org/simple/ https://api.github.com/zen; do
  if reachable "$url"; then pass "$url is reachable"; else fail "$url is blocked (should be allowed)"; fi
done

echo
if [ "$failures" -eq 0 ]; then echo "egress: all checks passed"; else echo "egress: $failures check(s) failed"; fi
exit "$failures"
