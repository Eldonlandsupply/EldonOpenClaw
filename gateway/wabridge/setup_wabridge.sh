#!/bin/bash
# setup_wabridge.sh — build and install the whatsmeow bridge on the Pi
set -e

BRIDGE_DIR="/opt/wabridge"
DB_DIR="/var/lib/wabridge"

echo "==> Creating directories"
sudo mkdir -p "$BRIDGE_DIR" "$DB_DIR"

echo "==> Copying source"
sudo cp main.go go.mod "$BRIDGE_DIR/"
cd "$BRIDGE_DIR"

echo "==> Downloading dependencies"
sudo go mod tidy

echo "==> Building bridge"
sudo go build -o /usr/local/bin/wabridge .

echo "==> Installing systemd service"
sudo tee /etc/systemd/system/wabridge.service > /dev/null << SERVICE
[Unit]
Description=WhatsApp Bridge (whatsmeow)
After=network.target

[Service]
Type=simple
ExecStart=/usr/local/bin/wabridge
Restart=always
RestartSec=5
Environment=WA_BRIDGE_PORT=8181
Environment=WA_BRIDGE_DB=/var/lib/wabridge/wabridge.db
StandardOutput=journal
StandardError=journal
SyslogIdentifier=wabridge

[Install]
WantedBy=multi-user.target
SERVICE

sudo systemctl daemon-reload
echo "==> Done. Run: sudo systemctl start wabridge"
echo "    Then watch QR: sudo journalctl -u wabridge -f"
