#!/usr/bin/env bash
# =============================================================================
# ddx-omr-server — stop
#
# Stops ONLY the process this directory started, by its own pid file. Never a
# pattern match: `pkill -f uvicorn` would stop every Python service on the host.
# =============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PID_FILE="${SCRIPT_DIR}/logs/omr.pid"

if [ ! -f "$PID_FILE" ]; then
  echo "not running (no pid file)"
  exit 0
fi

PID="$(cat "$PID_FILE")"
if [ -z "$PID" ] || ! kill -0 "$PID" 2>/dev/null; then
  echo "not running (pid ${PID:-none} is gone)"
  rm -f "$PID_FILE"
  exit 0
fi

echo "stopping pid $PID"
kill "$PID" 2>/dev/null || true

for _ in 1 2 3 4 5 6 7 8 9 10; do
  if ! kill -0 "$PID" 2>/dev/null; then
    rm -f "$PID_FILE"
    echo "stopped"
    exit 0
  fi
  sleep 1
done

echo "did not exit on SIGTERM; sending SIGKILL to pid $PID"
kill -9 "$PID" 2>/dev/null || true
rm -f "$PID_FILE"
echo "stopped (forced)"
