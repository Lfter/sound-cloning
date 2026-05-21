#!/bin/sh
ROOT="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
NODE_DIR="$ROOT/.tools/node-v24.15.0-darwin-arm64/bin"
NODE="$NODE_DIR/node"
export PATH="$NODE_DIR:$PATH"
cd "$ROOT"
exec "$NODE" "$ROOT/.tools/npm/bin/npm-cli.js" "$@"
