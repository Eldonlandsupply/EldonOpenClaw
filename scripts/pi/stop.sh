#!/usr/bin/env bash
# openclaw stop — gracefully stop the background runtime
# Usage: ./scripts/pi/stop.sh
set -euo pipefail

INSTALL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PID_FILE="${INSTALL_DIR}/logs/openclaw.pid"

if [[ -f "${PID_FILE}" ]]; then
    PID=$(cat "${PID_FILE}")
    if kill -0 "${PID}" 2>/dev/null; then
        echo "Stopping OpenClaw (PID ${PID})..."
        kill -TERM "${PID}"
        sleep 2
        if kill -0 "${PID}" 2>/dev/null; then
            echo "Still running — sending SIGKILL"
            kill -9 "${PID}"
        fi
        rm -f "${PID_FILE}"
        echo "Stopped"
    else
        echo "Process ${PID} not running — cleaning up stale PID file"
        rm -f "${PID_FILE}"
    fi
else
    # Try pkill fallback
    if pgrep -f "openclaw.main" > /dev/null 2>&1; then
        pkill -TERM -f "openclaw.main"
        echo "Stopped (via pkill)"
    else
        echo "OpenClaw not running"
    fi
fi
