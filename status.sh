#!/usr/bin/env bash
# =============================================================================
# ddx-omr-server — status
#
# Reports what is ACTUALLY listening, not what the pid file believes.
# =============================================================================
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PID_FILE="${SCRIPT_DIR}/logs/omr.pid"
ENV_FILE="${SCRIPT_DIR}/.env"

PORT=11513
if [ -f "$ENV_FILE" ]; then
  PORT="$(sed -n 's/^[[:space:]]*OMR_PORT[[:space:]]*=[[:space:]]*//p' "$ENV_FILE" | tail -1)"
  PORT="${PORT:-11513}"
fi

EXIT=1

echo "ddx-omr-server"
echo "  port     : ${PORT}"

if [ -f "$PID_FILE" ]; then
  echo "  pid file : $(cat "$PID_FILE")"
else
  echo "  pid file : (none)"
fi

LISTENER="$(lsof -nP -iTCP:"${PORT}" -sTCP:LISTEN 2>/dev/null || true)"
if [ -n "$LISTENER" ]; then
  echo "  listening: YES"
  echo "$LISTENER" | sed 's/^/             /'
  EXIT=0
else
  echo "  listening: NO"
fi

HEALTH="$(curl -fsS --max-time 3 "http://127.0.0.1:${PORT}/health" 2>/dev/null || true)"
if [ -n "$HEALTH" ]; then
  echo "  health   : OK ${HEALTH}"
else
  echo "  health   : unreachable"
  EXIT=1
fi

exit "$EXIT"
