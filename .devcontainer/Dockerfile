# Base: Microsoft's public devcontainer image (Node 22 on Debian bookworm, with git and a
# non-root "node" user). Pinned by digest so every build starts from the same bytes; a tag
# like :22-bookworm can move. Pulled from mcr.microsoft.com, which (unlike Docker Hub) has
# no anonymous pull rate limit.
FROM mcr.microsoft.com/devcontainers/javascript-node:22-bookworm@sha256:ec12180252047b3400ffffe008789cb8462bfff6f0703e285c2fb9986d47dae7

# Python for secret-scan. python3 (3.11) ships in the base; venv lets us install pytest
# without touching the system Python (Debian blocks `pip install` there, PEP 668).
# nftables provides `nft`, which loads the egress firewall (Story 2.2).
RUN apt-get update \
    && apt-get install -y --no-install-recommends python3-venv nftables \
    && rm -rf /var/lib/apt/lists/*

# The workspace pins npm 11 (npm 10 crashes on this lockfile; see docs/notes/story-1.1).
RUN npm install -g npm@11.20.0

# The base image gives "node" passwordless sudo. An agent that can become root can undo
# every other guardrail, so remove it.
RUN rm -f /etc/sudoers.d/node

# Egress firewall (Story 2.2). Root-owned and not writable by "node". The entrypoint loads
# the firewall as root, then switches to "node" for the life of the container, so there
# is no `USER node` line here: dropping root is the entrypoint's job.
COPY --chmod=644 egress-allowlist.txt /usr/local/share/sandbox/egress-allowlist.txt
COPY --chmod=755 egress-firewall.sh sandbox-entrypoint.sh wait-for-egress-firewall.sh /usr/local/bin/
ENTRYPOINT ["/usr/local/bin/sandbox-entrypoint.sh"]
CMD ["sleep", "infinity"]
