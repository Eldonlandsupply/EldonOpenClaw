#!/usr/bin/env bash
# openclaw install-service — install and enable systemd service
# Usage: sudo ./scripts/pi/install_service.sh
# Must be run as root (or with sudo)
set -euo pipefail

if [[ "${EUID}" -ne 0 ]]; then
    echo "ERROR: must run as root. Use: sudo ./scripts/pi/install_service.sh"
    exit 1
fi

INSTALL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
SERVICE_SRC="${INSTALL_DIR}/deploy/systemd/openclaw.service"
SERVICE_DST="/etc/systemd/system/openclaw.service"
PYTHON="${INSTALL_DIR}/.venv/bin/python"

# Verify venv exists
if [[ ! -f "${PYTHON}" ]]; then
    echo "ERROR: venv not found at ${INSTALL_DIR}/.venv"
    echo "Run ./scripts/pi/install.sh first"
    exit 1
fi

# Verify config exists
if [[ ! -f "${INSTALL_DIR}/config.yaml" ]]; then
    echo "ERROR: config.yaml not found"
    echo "Run: cp config.yaml.example config.yaml and configure it"
    exit 1
fi

# Write the service file with real paths substituted
echo "Writing ${SERVICE_DST}..."
sed \
    -e "s|/opt/openclaw|${INSTALL_DIR}|g" \
    -e "s|User=openclaw|User=$(stat -c '%U' "${INSTALL_DIR}")|g" \
    -e "s|Group=openclaw|Group=$(stat -c '%G' "${INSTALL_DIR}")|g" \
    "${SERVICE_SRC}" > "${SERVICE_DST}"

# Handle EnvironmentFile — use .env in install dir if /etc/openclaw doesn't exist
if [[ ! -f "/etc/openclaw/openclaw.env" ]]; then
    sed -i "s|EnvironmentFile=/etc/openclaw/openclaw.env|EnvironmentFile=${INSTALL_DIR}/.env|g" "${SERVICE_DST}"
    echo "NOTE: Using ${INSTALL_DIR}/.env as EnvironmentFile"
    echo "      For production, move secrets to /etc/openclaw/openclaw.env (chmod 600)"
fi

# Fix ReadWritePaths
sed -i "s|ReadWritePaths=/var/lib/openclaw|ReadWritePaths=${INSTALL_DIR}/data ${INSTALL_DIR}/logs|g" "${SERVICE_DST}"

echo "Reloading systemd..."
systemctl daemon-reload

echo "Enabling openclaw service..."
systemctl enable openclaw

echo ""
echo "=== Service installed ==="
echo "Start :  sudo systemctl start openclaw"
echo "Status:  sudo systemctl status openclaw"
echo "Logs  :  journalctl -u openclaw -f"
echo ""
echo "Service file written to: ${SERVICE_DST}"
