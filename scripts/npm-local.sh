#!/bin/sh
# Use the bundled Node/npm runtime so users do not need global npm installed.
ROOT="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
NODE_DIR="$ROOT/.tools/node-v24.15.0-darwin-arm64/bin"
NODE="$NODE_DIR/node"
export PATH="$NODE_DIR:$PATH"
cd "$ROOT"

# Delegate every argument to npm-cli.js after pinning the working directory.
exec "$NODE" "$ROOT/.tools/npm/bin/npm-cli.js" "$@"
