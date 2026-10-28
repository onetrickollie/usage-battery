#!/usr/bin/env bash
# Select or preview a style. Does not install, restart, or contact Bluetooth.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
if [ -x "$HERE/.venv/bin/python" ]; then
  exec "$HERE/.venv/bin/python" "$HERE/style.py" "$@"
else
  exec python3 "$HERE/style.py" "$@"
fi
