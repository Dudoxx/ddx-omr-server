#!/usr/bin/env bash
# =============================================================================
# ddx-omr-server — start
#
# Usage: ./start.sh [--port PORT] [--log-level LEVEL]
#
# The port may be overridden so the manager can place the service in the
# Sentinel block; 11513 is its only assignment.
# =============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_DIR="${SCRIPT_DIR}/logs"
PID_FILE="${LOG_DIR}/omr.pid"
ENV_FILE="${SCRIPT_DIR}/.env"
EXAMPLE_FILE="${SCRIPT_DIR}/.env.example"

mkdir -p "$LOG_DIR"

if [ ! -f "$ENV_FILE" ]; then
  if [ ! -f "$EXAMPLE_FILE" ]; then
    echo "ERROR: neither .env nor .env.example exists in ${SCRIPT_DIR}" >&2
    exit 1
  fi
  echo "WARN: .env missing — copying .env.example. Set DDX_OMR_API_KEY and OMR_SOURCE_URL." >&2
  cp "$EXAMPLE_FILE" "$ENV_FILE"
fi

set -a
# shellcheck source=/dev/null
source "$ENV_FILE"
set +a

# UnifiedSettings overlay (written by ddx-api, exported by ddx-manage). Sourced
# AFTER .env so an admin override wins: settings > env > default.
if [ -n "${DDX_SETTINGS_OVERLAY:-}" ] && [ -f "$DDX_SETTINGS_OVERLAY" ]; then
  set -a
  # shellcheck source=/dev/null
  . "$DDX_SETTINGS_OVERLAY"
  set +a
  echo "settings overlay: $DDX_SETTINGS_OVERLAY"
fi

PORT="${OMR_PORT:-11513}"
LOG_LEVEL="${LOG_LEVEL:-info}"

while [ $# -gt 0 ]; do
  case "$1" in
    --port)      PORT="$2"; shift 2 ;;
    --log-level) LOG_LEVEL="$2"; shift 2 ;;
    *) echo "Unknown option: $1" >&2; exit 1 ;;
  esac
done

PY="${SCRIPT_DIR}/.venv/bin/python"
if [ ! -x "$PY" ]; then
  echo "ERROR: no virtualenv at ${SCRIPT_DIR}/.venv" >&2
  echo "       Create it: uv sync" >&2
  exit 1
fi

if lsof -nP -iTCP:"${PORT}" -sTCP:LISTEN >/dev/null 2>&1; then
  echo "ERROR: port ${PORT} is already bound. Resolve it with:" >&2
  echo "       lsof -nP -iTCP:${PORT} -sTCP:LISTEN" >&2
  exit 1
fi

echo "▶  Starting ddx-omr-server on :${PORT}"
echo "   env: ${ENV_FILE}"

cd "$SCRIPT_DIR"

# EXEC, never background-and-exit: the manager records THIS pid. A child left
# behind would make the tracked pid die while the server keeps running.
echo "$$" > "$PID_FILE"
exec env OMR_PORT="$PORT" LOG_LEVEL="$LOG_LEVEL" \
  PYTHONPATH="${SCRIPT_DIR}/src" \
  "$PY" -m uvicorn ddx_omr_server.api.app:create_app \
    --factory --host "${HOST:-127.0.0.1}" --port "$PORT" \
    --log-level "$LOG_LEVEL"
