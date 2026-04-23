#!/bin/bash
# Runs leancontext-activate.js using nvm-managed node without sourcing nvm.
# Resolution order:
#   1. Latest installed node under ~/.nvm/versions/node/ (version-agnostic)
#   2. node on PATH (catches system installs, Homebrew, etc.)
# Falls through silently on failure — never blocks Codex session start.

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
NVM_DIR="${NVM_DIR:-$HOME/.nvm}"

# Find latest installed node version under nvm (sort -V = natural version order)
NODE=""
if [ -d "$NVM_DIR/versions/node" ]; then
  LATEST=$(ls "$NVM_DIR/versions/node/" 2>/dev/null | sort -V | tail -1)
  if [ -n "$LATEST" ] && [ -x "$NVM_DIR/versions/node/$LATEST/bin/node" ]; then
    NODE="$NVM_DIR/versions/node/$LATEST/bin/node"
  fi
fi

# Fallback: node on PATH
if [ -z "$NODE" ]; then
  NODE=$(command -v node 2>/dev/null)
fi

# Run or exit silently
if [ -n "$NODE" ] && [ -x "$NODE" ]; then
  exec "$NODE" "$REPO_ROOT/hooks/leancontext-activate.js"
fi
