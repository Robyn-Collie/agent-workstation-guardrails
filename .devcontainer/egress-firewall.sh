#!/usr/bin/env bash
# Default-deny outbound network for the agent sandbox, written with nftables.
# Runs as root from sandbox-entrypoint.sh, before the container drops to "node".
# Design notes and limits: docs/notes/story-2.2-egress-allowlist.md.
set -euo pipefail

ALLOWLIST=/usr/local/share/sandbox/egress-allowlist.txt
READY=/run/sandbox/egress-ready
started=$(date +%s%N)
log() { echo "egress-firewall: $*" >&2; }

mkdir -p /run/sandbox
rm -f "$READY"
if [ ! -r "$ALLOWLIST" ]; then
  log "allowlist $ALLOWLIST is missing"
  exit 1
fi

# DNS is allowed only to the resolvers Docker wrote into resolv.conf.
dns4=$(awk '$1 == "nameserver" && $2 !~ /:/ {printf "%s%s", sep, $2; sep=", "}' /etc/resolv.conf)
dns6=$(awk '$1 == "nameserver" && $2 ~ /:/ {printf "%s%s", sep, $2; sep=", "}' /etc/resolv.conf)
dns4_elements=${dns4:+"elements = { $dns4 };"}
dns6_elements=${dns6:+"elements = { $dns6 };"}

# Step 1: load the deny-by-default table in one atomic transaction. The first two lines
# make a re-run replace the table instead of failing. One "inet" table covers IPv4 and
# IPv6, so there is no unfiltered IPv6 path. The allow sets start empty.
nft -f - <<NFT
table inet agent_egress
delete table inet agent_egress
table inet agent_egress {
  set allow_v4 { type ipv4_addr; flags interval; auto-merge; }
  set allow_v6 { type ipv6_addr; flags interval; auto-merge; }
  set dns_v4 { type ipv4_addr; $dns4_elements }
  set dns_v6 { type ipv6_addr; $dns6_elements }

  chain output {
    type filter hook output priority filter; policy drop;
    oif "lo" accept
    ct state established,related accept
    meta l4proto { tcp, udp } th dport 53 ip daddr @dns_v4 accept
    meta l4proto { tcp, udp } th dport 53 ip6 daddr @dns_v6 accept
    tcp dport 443 ip daddr @allow_v4 accept
    tcp dport 443 ip6 daddr @allow_v6 accept
    # Refuse rather than silently drop, so a blocked call fails at once.
    reject with icmpx type admin-prohibited
  }

  chain input {
    type filter hook input priority filter; policy drop;
    iif "lo" accept
    ct state established,related accept
  }
}
NFT

# Step 2: resolve each allowlisted host (DNS already works) and add its addresses.
hosts=0
while read -r host; do
  v4=$(getent ahostsv4 "$host" | awk '{print $1}' | sort -u | paste -sd, - || true)
  v6=$(getent ahostsv6 "$host" | awk '$1 ~ /:/ && $1 !~ /^::ffff:/ {print $1}' | sort -u | paste -sd, - || true)
  if [ -z "$v4$v6" ]; then
    log "cannot resolve $host"
    exit 1
  fi
  if [ -n "$v4" ]; then nft add element inet agent_egress allow_v4 "{ $v4 }"; fi
  if [ -n "$v6" ]; then nft add element inet agent_egress allow_v6 "{ $v6 }"; fi
  log "$host -> ${v4:-} ${v6:-}"
  hosts=$((hosts + 1))
done < <(sed -e 's/#.*//' -e 's/[[:space:]]//g' "$ALLOWLIST" | grep -v '^$')

# A failure inside "< <(...)" does not stop the script, so check the result directly.
if [ "$hosts" -eq 0 ]; then
  log "allowlist $ALLOWLIST has no hosts"
  exit 1
fi

# Step 3: GitHub serves the same name from several addresses, so one lookup can miss the
# address the next request uses. (The first CI run saw api.github.com refused a second
# after it was allowed.) GitHub publishes its ranges at api.github.com/meta; add
# the web, api and git ranges. --resolve pins the request to the address just allowed.
# If the fetch fails (for example GitHub's unauthenticated rate limit), keep going with
# the looked-up addresses and say so, rather than refuse to start.
gh_ip=$(getent ahostsv4 api.github.com | awk 'NR == 1 {print $1}' || true)
if meta=$(curl -fsS --max-time 10 --resolve "api.github.com:443:$gh_ip" https://api.github.com/meta); then
  gh4=$(jq -r '(.web + .api + .git)[] | select(contains(":") | not)' <<<"$meta" | sort -u | paste -sd, -)
  gh6=$(jq -r '(.web + .api + .git)[] | select(contains(":"))' <<<"$meta" | sort -u | paste -sd, -)
  if [ -n "$gh4" ]; then nft add element inet agent_egress allow_v4 "{ $gh4 }"; fi
  if [ -n "$gh6" ]; then nft add element inet agent_egress allow_v6 "{ $gh6 }"; fi
  log "added GitHub's published ranges ($(tr ',' '\n' <<<"$gh4,$gh6" | grep -c .) CIDRs)"
else
  log "WARNING: could not fetch GitHub's ranges; GitHub may fail when its address rotates"
fi

touch "$READY"
log "ready: $hosts hosts allowed, took $(( ($(date +%s%N) - started) / 1000000 )) ms"
