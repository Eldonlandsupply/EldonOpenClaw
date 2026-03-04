#!/usr/bin/env bash
# ============================================================
# Run OpenClaw locally (dev mode)
# Usage: ./scripts/run_local.sh [config.yaml]
# ============================================================
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CONFIG="${1:-config.yaml}"

cd "$REPO_ROOT"

# Ensure .env exists
if [ ! -f .env ]; then
  echo "No .env found — copying .env.example"
  cp .env.example .env
fi

# Ensure config.yaml exists
if [ ! -f "$CONFIG" ]; then
  echo "No $CONFIG found — copying config.yaml.example"
  cp config.yaml.example "$CONFIG"
fi

# Create venv if missing
if [ ! -d .venv ]; then
  echo "Creating virtual environment..."
  python3 -m venv .venv
fi

source .venv/bin/activate

# Install in editable mode
pip install -e ".[dev]" --quiet

echo ""
echo "============================================================"
echo " OpenClaw starting (config: $CONFIG)"
echo " Health: http://127.0.0.1:8080/health"
echo " Stop:   Ctrl+C"
echo "============================================================"
echo ""

python -m openclaw.main "$CONFIG"
