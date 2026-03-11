#!/usr/bin/env bash
# scripts/pi/bootstrap.sh
# One-shot install for Raspberry Pi.
# Run as the 'pi' user from any directory.
# Usage: bash <(curl -sL https://raw.githubusercontent.com/Eldonlandsupply/EldonOpenClaw/main/scripts/pi/bootstrap.sh)
set -euo pipefail

REPO_URL="https://github.com/Eldonlandsupply/EldonOpenClaw.git"
INSTALL_DIR="/home/pi/EldonOpenClaw"
SERVICE_NAME="openclaw"

echo "=== EldonOpenClaw Bootstrap ==="

# ── deps ─────────────────────────────────────────────────────────────────
echo "[1/7] Installing system packages..."
sudo apt-get update -qq
sudo apt-get install -y -qq git python3 python3-venv python3-pip

# ── clone or pull ────────────────────────────────────────────────────────
echo "[2/7] Cloning / updating repo..."
if [ -d "$INSTALL_DIR/.git" ]; then
    cd "$INSTALL_DIR"
    git pull --ff-only
else
    git clone "$REPO_URL" "$INSTALL_DIR"
    cd "$INSTALL_DIR"
fi

# ── venv + pip ───────────────────────────────────────────────────────────
echo "[3/7] Creating virtualenv and installing dependencies..."
python3 -m venv .venv
.venv/bin/pip install --upgrade pip -q
.venv/bin/pip install -r requirements.txt -q

# ── .env setup ───────────────────────────────────────────────────────────
echo "[4/7] Configuring .env..."
if [ ! -f .env ]; then
    cp .env.example .env
    echo ""
    echo "  !! EDIT .env NOW before continuing !!"
    echo "     nano .env"
    echo "     Set OPENROUTER_API_KEY and OPENCLAW_CHAT_MODEL at minimum."
    echo ""
    read -rp "  Press ENTER after saving .env to continue..."
fi

# ── validate config ──────────────────────────────────────────────────────
echo "[5/7] Validating config..."
PYTHONPATH=src .venv/bin/python scripts/doctor.py

# ── create required dirs ─────────────────────────────────────────────────
echo "[6/7] Creating data directories..."
mkdir -p data logs .data/vector_store

# ── systemd ──────────────────────────────────────────────────────────────
echo "[7/7] Installing systemd service..."
sudo cp deploy/systemd/openclaw.service /etc/systemd/system/openclaw.service
sudo systemctl daemon-reload
sudo systemctl enable openclaw
sudo systemctl restart openclaw

echo ""
echo "=== Bootstrap complete ==="
echo "  Status:  sudo systemctl status openclaw"
echo "  Logs:    journalctl -u openclaw -f"
echo "  Stop:    sudo systemctl stop openclaw"
echo "  Restart: sudo systemctl restart openclaw"
