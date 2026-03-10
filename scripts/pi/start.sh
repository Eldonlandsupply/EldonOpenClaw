#!/usr/bin/env bash
# openclaw start — start runtime in background, log to file
# Usage: ./scripts/pi/start.sh
# For production use: install the systemd service instead.
set -euo pipefail

INSTALL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PYTHON="${INSTALL_DIR}/.venv/bin/python"
LOG_FILE="${INSTALL_DIR}/logs/openclaw.log"
PID_FILE="${INSTALL_DIR}/logs/openclaw.pid"

cd "${INSTALL_DIR}"

# Check already running
if [[ -f "${PID_FILE}" ]]; then
    OLD_PID=$(cat "${PID_FILE}")
    if kill -0 "${OLD_PID}" 2>/dev/null; then
        echo "OpenClaw already running (PID ${OLD_PID})"
        echo "Stop it first with: ./scripts/pi/stop.sh"
        exit 1
    else
        rm -f "${PID_FILE}"
    fi
fi

# Require config
if [[ ! -f "config.yaml" ]]; then
    echo "ERROR: config.yaml not found"
    echo "Run: cp config.yaml.example config.yaml"
    exit 1
fi

mkdir -p logs

echo "Starting OpenClaw..."
nohup "${PYTHON}" -m openclaw.main config.yaml < /dev/null >> "${LOG_FILE}" 2>&1 &
echo $! > "${PID_FILE}"

sleep 2
PID=$(cat "${PID_FILE}")

if kill -0 "${PID}" 2>/dev/null; then
    echo "Started (PID ${PID})"
    echo "Log: ${LOG_FILE}"
    echo ""
    # Quick health check
    sleep 2
    if curl -sf --max-time 3 http://127.0.0.1:8080/health > /dev/null 2>&1; then
        echo "Health: OK"
    else
        echo "Health: not yet responding (may still be starting)"
    fi
else
    echo "ERROR: Process died immediately. Check logs:"
    echo "  tail -20 ${LOG_FILE}"
    rm -f "${PID_FILE}"
    exit 1
fi
