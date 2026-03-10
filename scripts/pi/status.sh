#!/usr/bin/env bash
# openclaw status — show runtime state, health, and config summary
# Usage: ./scripts/pi/status.sh
set -euo pipefail

INSTALL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PYTHON="${INSTALL_DIR}/.venv/bin/python"
HEALTH_URL="http://127.0.0.1:8080/health"

echo "=== OpenClaw Status ==="
echo "Install dir : ${INSTALL_DIR}"
echo "Python      : $("${PYTHON}" --version 2>&1)"

echo ""
echo "--- Process ---"
if pgrep -f "openclaw.main" > /dev/null 2>&1; then
    PID=$(pgrep -f "openclaw.main" | head -1)
    echo "Running     : YES (PID ${PID})"
    ps -p "${PID}" -o pid,user,pcpu,pmem,etime --no-headers 2>/dev/null || true
else
    echo "Running     : NO"
fi

echo ""
echo "--- Health endpoint ---"
if curl -sf --max-time 3 "${HEALTH_URL}" > /tmp/openclaw_health.json 2>/dev/null; then
    cat /tmp/openclaw_health.json
    echo ""
else
    echo "UNREACHABLE (service not running or not yet started)"
fi

echo ""
echo "--- systemd ---"
if systemctl is-active --quiet openclaw 2>/dev/null; then
    echo "systemd     : active"
    systemctl status openclaw --no-pager -l 2>/dev/null | tail -5
else
    echo "systemd     : not active (manual mode or not installed)"
fi

echo ""
echo "--- Config doctor ---"
if [[ -f "${INSTALL_DIR}/config.yaml" ]]; then
    cd "${INSTALL_DIR}" && "${PYTHON}" scripts/doctor.py 2>&1 | head -20
else
    echo "WARN: config.yaml not found — run: cp config.yaml.example config.yaml"
fi
