#!/usr/bin/env bash
# Repair frontend/package-lock.json so that `npm ci` works on Linux.
#
# Why: when a dependency is added with npm on Windows, the lockfile can miss optional
# packages that only Linux needs, and `npm ci` then fails in CI and in the Docker build.
# This script completes the lockfile inside a Linux container without changing any resolved
# version, proves a clean install works there, and copies the lockfile back.
#
# Run inside WSL after adding or updating a front-end dependency:
#   wsl -e bash /mnt/d/Projects/Hackathon/dev/fix-lock.sh
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
WORK="$(mktemp -d)"
cp "$ROOT/frontend/package.json" "$ROOT/frontend/package-lock.json" "$WORK/"
cp "$WORK/package-lock.json" "$WORK/lock.before"

docker run --rm -v "$WORK":/w -w /w node:24-alpine sh -c '
  set -e
  npm install --package-lock-only --ignore-scripts --no-audit --no-fund >/dev/null
  npm ci --ignore-scripts --no-audit --no-fund 2>&1 | tail -1
  find node_modules -mindepth 1 -maxdepth 1 -exec rm -r {} +
'

echo "packages added to the lockfile:"
diff "$WORK/lock.before" "$WORK/package-lock.json" | grep -E '^> +"node_modules/' || echo "  none"
cp "$WORK/package-lock.json" "$ROOT/frontend/package-lock.json"
echo "lockfile updated"
