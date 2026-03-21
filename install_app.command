#!/bin/zsh
set -e
ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
exec "$ROOT_DIR/install_app.sh"
