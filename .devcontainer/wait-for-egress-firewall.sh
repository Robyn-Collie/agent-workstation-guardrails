#!/usr/bin/env bash
# Lifecycle commands (npm ci, pip install) start as soon as the container exists. Hold
# them until the entrypoint has finished loading the firewall, so nothing runs unfiltered.
for _ in $(seq 1 60); do
  [ -f /run/sandbox/egress-ready ] && exit 0
  sleep 0.5
done
echo "egress firewall not ready after 30 s; check the container log (docker logs)" >&2
exit 1
