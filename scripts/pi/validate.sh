#!/usr/bin/env bash
# openclaw validate — end-to-end acceptance test
# Usage: ./scripts/pi/validate.sh
# Boots the runtime, checks all endpoints, runs tests, shuts down cleanly.
set -euo pipefail

INSTALL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PYTHON="${INSTALL_DIR}/.venv/bin/python"
PASS=0
FAIL=0

cd "${INSTALL_DIR}"

ok()   { echo "  PASS: $1"; PASS=$((PASS+1)); }
fail() { echo "  FAIL: $1"; FAIL=$((FAIL+1)); }

echo "=== OpenClaw Acceptance Test ==="
echo ""

# 1. Python version
PY_VER=$("${PYTHON}" -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
if python3 -c "import sys; assert sys.version_info >= (3,11)" 2>/dev/null; then
    ok "Python ${PY_VER} >= 3.11"
else
    fail "Python ${PY_VER} < 3.11 required"
fi

# 2. Package importable
if "${PYTHON}" -c "import openclaw" 2>/dev/null; then
    ok "Package importable"
else
    fail "Package not importable — run install.sh"
fi

# 3. Config exists
if [[ -f "config.yaml" ]]; then
    ok "config.yaml exists"
else
    fail "config.yaml missing — cp config.yaml.example config.yaml"
fi

# 4. Doctor passes
if "${PYTHON}" scripts/doctor.py > /dev/null 2>&1; then
    ok "doctor.py exits 0"
else
    fail "doctor.py failed — check config.yaml"
fi

# 5. Tests
echo ""
echo "--- Test suite ---"
if "${PYTHON}" -m pytest tests/ -q --tb=no 2>&1 | tail -3; then
    ok "Test suite passed"
else
    fail "Test suite has failures"
fi

# 6. Runtime boot + health check
echo ""
echo "--- Runtime boot ---"

# Kill any existing instance
pkill -f "openclaw.main" 2>/dev/null || true
sleep 1

mkdir -p logs
nohup "${PYTHON}" -m openclaw.main config.yaml < /dev/null > logs/validate_boot.log 2>&1 &
BOOT_PID=$!
echo "  Booted PID ${BOOT_PID}, waiting 4s..."
sleep 4

if kill -0 "${BOOT_PID}" 2>/dev/null; then
    ok "Process still alive after 4s"
else
    fail "Process died — check logs/validate_boot.log"
    cat logs/validate_boot.log | tail -10
fi

# 7. Health endpoints
for ENDPOINT in health ready ping; do
    RESP=$(curl -sf --max-time 3 "http://127.0.0.1:8080/${ENDPOINT}" 2>/dev/null || echo "FAILED")
    if [[ "${RESP}" != "FAILED" ]]; then
        ok "/${ENDPOINT} responded"
    else
        fail "/${ENDPOINT} unreachable"
    fi
done

# 8. Health status=ok
HEALTH=$(curl -sf --max-time 3 http://127.0.0.1:8080/health 2>/dev/null || echo "{}")
if echo "${HEALTH}" | grep -q '"status": "ok"'; then
    ok "Health status=ok"
else
    fail "Health status not ok: ${HEALTH}"
fi

# 9. Graceful shutdown
kill -TERM "${BOOT_PID}" 2>/dev/null
sleep 2
if ! kill -0 "${BOOT_PID}" 2>/dev/null; then
    ok "Graceful SIGTERM shutdown"
else
    kill -9 "${BOOT_PID}" 2>/dev/null
    fail "Did not shut down cleanly on SIGTERM"
fi

# Summary
echo ""
echo "=== Result: ${PASS} passed, ${FAIL} failed ==="
if [[ "${FAIL}" -eq 0 ]]; then
    echo "DEPLOYABLE: YES"
    exit 0
else
    echo "DEPLOYABLE: NO — fix failures above"
    exit 1
fi
