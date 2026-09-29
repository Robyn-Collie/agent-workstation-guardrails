#!/usr/bin/env bash
# Container entrypoint. Starts as root only long enough to load the egress firewall,
# then becomes "node" for good. If the firewall fails to load, the container exits:
# fail closed, never run open.
set -euo pipefail
/usr/local/bin/egress-firewall.sh
# setpriv switches user and group. The kernel clears a process's capabilities when it
# leaves uid 0, so nothing started after this line can change the firewall.
exec setpriv --reuid=node --regid=node --init-groups --inh-caps=-all -- "$@"
