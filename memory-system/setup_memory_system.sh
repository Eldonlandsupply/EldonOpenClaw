#!/usr/bin/env bash
# ============================================================
# setup_memory_system.sh
# Installs the OpenClaw semantic memory system on Raspberry Pi
# Run as: bash setup_memory_system.sh
# ============================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INSTALL_DIR="/opt/openclaw-memory"
VENV="$INSTALL_DIR/.venv"
SERVICE_NAME="openclaw-memory"

echo "============================================================"
echo " OpenClaw Semantic Memory — Setup"
echo " Install dir: $INSTALL_DIR"
echo "============================================================"

# ── Copy files to install dir ─────────────────────────────────
echo ""
echo "→ Installing files to $INSTALL_DIR ..."
sudo mkdir -p "$INSTALL_DIR"
sudo cp "$SCRIPT_DIR"/*.py "$INSTALL_DIR/"
sudo cp "$SCRIPT_DIR/config.yaml" "$INSTALL_DIR/"
sudo chown -R openclaw:openclaw "$INSTALL_DIR" 2>/dev/null || sudo chown -R pi:pi "$INSTALL_DIR"

# ── Create symlink for repo_search_cli ────────────────────────
sudo ln -sf "$INSTALL_DIR/repo_search_cli.py" /usr/local/bin/repo-search
sudo chmod +x /usr/local/bin/repo-search

# ── Create index directory ────────────────────────────────────
mkdir -p ~/.openclaw-memory

# ── Create virtualenv ─────────────────────────────────────────
echo ""
echo "→ Creating virtual environment ..."
if [ ! -d "$VENV" ]; then
    sudo -u "${SUDO_USER:-$(whoami)}" python3 -m venv "$VENV" 2>/dev/null || python3 -m venv "$VENV"
fi

echo ""
echo "→ Installing Python dependencies ..."

# Core deps always needed
"$VENV/bin/pip" install --quiet --upgrade pip
"$VENV/bin/pip" install --quiet \
    pyyaml \
    numpy \
    httpx

# Try chromadb (preferred vector store)
echo "  Installing chromadb ..."
"$VENV/bin/pip" install --quiet chromadb || {
    echo "  chromadb failed — will use FAISS"
    "$VENV/bin/pip" install --quiet faiss-cpu || \
    "$VENV/bin/pip" install --quiet faiss || \
    echo "  FAISS also failed — TF-IDF fallback will be used"
}

# Try sentence-transformers (offline embedding fallback)
echo "  Installing sentence-transformers (offline fallback) ..."
"$VENV/bin/pip" install --quiet sentence-transformers || echo "  sentence-transformers skipped"

# scikit-learn for TF-IDF fallback
"$VENV/bin/pip" install --quiet scikit-learn || echo "  scikit-learn skipped"

echo ""
echo "→ Dependencies installed."

# ── Update shebang in CLI tool ────────────────────────────────
sudo sed -i "1s|.*|#!$VENV/bin/python3|" "$INSTALL_DIR/repo_search_cli.py"
sudo chmod +x "$INSTALL_DIR/repo_search_cli.py"

# ── Create systemd service ────────────────────────────────────
echo ""
echo "→ Creating systemd service ..."

CURRENT_USER="${SUDO_USER:-$(whoami)}"

sudo tee /etc/systemd/system/${SERVICE_NAME}.service > /dev/null << UNITEOF
[Unit]
Description=OpenClaw Semantic Memory Daemon
After=network.target openclaw.service
Wants=openclaw.service

[Service]
Type=simple
User=${CURRENT_USER}
WorkingDirectory=${INSTALL_DIR}
EnvironmentFile=-/etc/openclaw/openclaw.env
ExecStart=${VENV}/bin/python3 ${INSTALL_DIR}/repo_memory_daemon.py ${INSTALL_DIR}/config.yaml
Restart=always
RestartSec=30
StandardOutput=journal
StandardError=journal
SyslogIdentifier=openclaw-memory

[Install]
WantedBy=multi-user.target
UNITEOF

sudo systemctl daemon-reload
sudo systemctl enable ${SERVICE_NAME}

# ── Run initial index ─────────────────────────────────────────
echo ""
echo "→ Running initial index build (this may take a few minutes) ..."
echo "  Using OpenRouter API key from environment if available."

# Source openclaw env if it exists
if [ -f /etc/openclaw/openclaw.env ]; then
    set -a; source /etc/openclaw/openclaw.env; set +a
fi

"$VENV/bin/python3" - << PYEOF
import sys
sys.path.insert(0, "$INSTALL_DIR")
from repo_indexer import load_config, index_repos
cfg = load_config("$INSTALL_DIR/config.yaml")
n = index_repos(cfg)
print(f"  Initial index complete: {n} chunks indexed")
PYEOF

# ── Start daemon ──────────────────────────────────────────────
echo ""
echo "→ Starting memory daemon ..."
sudo systemctl start ${SERVICE_NAME}
sleep 2
sudo systemctl status ${SERVICE_NAME} --no-pager | head -12

echo ""
echo "============================================================"
echo " Setup complete!"
echo ""
echo " Commands:"
echo "   Search:   repo-search \"your query\""
echo "   Status:   sudo systemctl status openclaw-memory"
echo "   Logs:     sudo journalctl -u openclaw-memory -f"
echo "   Restart:  sudo systemctl restart openclaw-memory"
echo "============================================================"
