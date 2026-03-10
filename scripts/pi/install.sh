#!/usr/bin/env bash
# openclaw install — idempotent install or update from git
# Usage: ./scripts/pi/install.sh
# Safe to re-run. Does not touch .env or config.yaml if they already exist.
set -euo pipefail

INSTALL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PYTHON_BIN="${INSTALL_DIR}/.venv/bin/python"
PIP_BIN="${INSTALL_DIR}/.venv/bin/pip"

echo "=== OpenClaw Install/Update ==="
echo "Install dir: ${INSTALL_DIR}"
cd "${INSTALL_DIR}"

# 1. Pull latest
echo ""
echo "[1/5] Pulling latest from git..."
git pull origin main

# 2. Create venv if missing
echo ""
echo "[2/5] Virtual environment..."
if [[ ! -f "${PYTHON_BIN}" ]]; then
    python3 -m venv .venv
    echo "      Created .venv"
else
    echo "      Already exists"
fi

# 3. Install/upgrade package
echo ""
echo "[3/5] Installing package..."
"${PIP_BIN}" install -q --upgrade pip
"${PIP_BIN}" install -q -e ".[dev]"
echo "      Done"

# 4. Copy config templates if not present
echo ""
echo "[4/5] Config files..."
if [[ ! -f "config.yaml" ]]; then
    cp config.yaml.example config.yaml
    echo "      Created config.yaml from example — EDIT BEFORE RUNNING"
else
    echo "      config.yaml already exists (not overwritten)"
fi

if [[ ! -f ".env" ]]; then
    cp .env.example .env
    echo "      Created .env from example — ADD SECRETS BEFORE RUNNING"
else
    echo "      .env already exists (not overwritten)"
fi

# 5. Run doctor
echo ""
echo "[5/5] Running doctor..."
"${PYTHON_BIN}" scripts/doctor.py

echo ""
echo "=== Install complete ==="
echo "Next: verify config.yaml and .env, then run:"
echo "  systemctl start openclaw   (if systemd service is installed)"
echo "  OR"
echo "  ./scripts/pi/start.sh      (manual foreground start)"
