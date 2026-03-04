#!/usr/bin/env bash
# ============================================================
# Golden-path verification: tests + live health check
# Run from repo root: ./scripts/verify.sh
# Exit 0 = everything is good. Exit non-zero = broken.
# ============================================================
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

source .venv/bin/activate 2>/dev/null || {
  echo "ERROR: .venv not found. Run ./scripts/run_local.sh first."
  exit 1
}

echo "=== [1/4] Unit tests ==="
pytest tests/ -v

echo ""
echo "=== [2/4] Config load check ==="
python - <<'EOF'
import sys, os
sys.path.insert(0, "src")
os.chdir(".")
from openclaw.config import AppConfig
cfg = AppConfig(yaml_path="config.yaml")
import json
print(json.dumps(cfg.summary(), indent=2))
print("Config OK")
EOF

echo ""
echo "=== [3/4] Starting agent for 5 seconds ==="
timeout 5 python -m openclaw.main config.yaml &
AGENT_PID=$!
sleep 3

echo ""
echo "=== [4/4] Health check ==="
HEALTH=$(curl -sf http://127.0.0.1:8080/health || echo '{"status":"unreachable"}')
echo "Health response: $HEALTH"

# Clean up
kill "$AGENT_PID" 2>/dev/null || true
wait "$AGENT_PID" 2>/dev/null || true

if echo "$HEALTH" | grep -q '"status":"ok"'; then
  echo ""
  echo "✅ All checks passed — OpenClaw is healthy"
  exit 0
else
  echo ""
  echo "❌ Health check failed"
  exit 1
fi
