#!/usr/bin/env bash
# Run on the HOST. Proves a secret value was injected at run time and never stored in a
# Docker image or container: not in the build history, not in image or container
# metadata (environment, labels), not in any image layer (even one a later layer deleted
# it from), and not in the container's filesystem.
#
# Usage: SECRET_VALUE=... check-no-baked-secret.sh IMAGE [CONTAINER]
# The value comes from the environment, not an argument, so it never shows up in `ps`.
# Exits with the number of places the value was found.
set -u
image=${1:?usage: SECRET_VALUE=... $0 IMAGE [CONTAINER]}
container=${2:-}
secret=${SECRET_VALUE:?set SECRET_VALUE to the value to look for}
failures=0
pass() { echo "[PASS] $1"; }
fail() { echo "[FAIL] $1"; failures=$((failures + 1)); }
contains() { grep -qaF -- "$secret"; }

work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT

# 1. Build history: every RUN, ARG and ENV line, untruncated.
if docker history --no-trunc "$image" | contains; then fail "image build history contains the secret"; else pass "image build history is clean"; fi

# 2. Image metadata: environment, labels, entrypoint, everything `inspect` reports.
if docker image inspect "$image" | contains; then fail "image metadata contains the secret"; else pass "image metadata is clean"; fi

# 3. Every blob of the image, one at a time: each layer, plus the config. `docker save`
# writes them as separate files. A file added in one layer and deleted in the next is gone
# from the final filesystem but still inside the first layer, so this is the check that
# catches it. A tar stores file contents as-is, so an uncompressed layer can be searched
# directly; a gzip- or zstd-compressed one is decompressed first.
docker save -o "$work/image.tar" "$image"
mkdir "$work/image"
tar -xf "$work/image.tar" -C "$work/image"
found=0
blobs=0
while IFS= read -r -d '' blob; do
  blobs=$((blobs + 1))
  case $(od -An -tx1 -N4 "$blob" | tr -d ' \n') in
    1f8b*) gzip -dc "$blob" | contains && found=1 ;;
    28b52ffd)
      if ! command -v zstd >/dev/null; then fail "zstd layer found but zstd is not installed"; continue; fi
      zstd -dcq "$blob" | contains && found=1 ;;
    *) contains <"$blob" && found=1 ;;
  esac
done < <(find "$work/image" -type f -print0)
if [ "$found" -eq 1 ]; then fail "an image layer or config contains the secret"; else pass "all $blobs image blobs (layers and config) are clean"; fi

# 4. The running container: its metadata and its whole filesystem (image plus anything
# written since start). Bind mounts such as /workspace are not part of the export.
if [ -n "$container" ]; then
  if docker inspect "$container" | contains; then fail "container metadata contains the secret"; else pass "container metadata is clean"; fi
  if docker export "$container" | contains; then fail "container filesystem contains the secret"; else pass "container filesystem is clean"; fi
fi

echo
if [ "$failures" -eq 0 ]; then echo "no-baked-secret: all checks passed"; else echo "no-baked-secret: $failures check(s) failed"; fi
exit "$failures"
