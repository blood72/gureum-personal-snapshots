#!/bin/bash
set -euo pipefail

# Only public upstream is fetched. No token is stored or passed to its build.
python3 scripts/snapshot.py validate-inputs
mkdir -p diagnostics dist
git init source
git -C source remote add origin https://github.com/gureum/gureum.git
git -C source fetch --no-recurse-submodules --tags origin \
  +refs/heads/main:refs/remotes/origin/main
if [[ "$UPSTREAM_REF" == main ]]; then
  upstream_sha=$(git -C source rev-parse refs/remotes/origin/main)
else
  upstream_sha=$(printf '%s' "$UPSTREAM_REF" | tr '[:upper:]' '[:lower:]')
fi
# Object existence and ancestry are checked before checkout/submodule execution.
test "$(git -C source rev-parse "$upstream_sha^{commit}")" = "$upstream_sha"
git -C source merge-base --is-ancestor "$upstream_sha" refs/remotes/origin/main
git -C source checkout --detach "$upstream_sha"
git -C source -c protocol.file.allow=never submodule update --init --recursive
python3 scripts/snapshot.py metadata
