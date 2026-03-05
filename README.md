# EldonOpenClaw

Production-grade, 24/7 Raspberry Pi agent runtime — Python/asyncio, pluggable connectors (CLI/Telegram/voice), centralized config (.env + YAML), safe action gating, memory storage, health checks, structured logs, systemd/Docker deployment.

---

## Quickstart

### 1. Clone and create virtualenv

```bash
git clone <repo-url>
cd EldonOpenClaw
python -m venv .venv
source .venv/bin/activate        # Linux/macOS
# .\.venv\Scripts\Activate.ps1  # PowerShell
pip install -r requirements.txt
```

### 2. Configure

```bash
cp .env.example .env
# Edit .env — at minimum set:
#   OPENCLAW_CHAT_MODEL=<your-model-name>
#   OPENAI_API_KEY=<your-key>
```

### 3. Validate config (no side effects)

```bash
python scripts/doctor.py
```

Expected output:
```
✓ Config loaded successfully
  env           = development
  log_level     = info
  chat_model    = <your-model>
  embed_model   = (none)
  ...
```

If you see `✗ Config FAILED`, the error message tells you exactly what to fix.

### 4. Run

```bash
python main.py
```

---

## Required config

| Env var | Required | Description |
|---|---|---|
| `OPENCLAW_CHAT_MODEL` | ✅ | LLM model name (e.g. `gpt-4o-mini`) |
| `OPENAI_API_KEY` | ✅ | API key for your LLM provider |
| `OPENCLAW_EMBED_MODEL` | Only if memory enabled | Embedding model (e.g. `text-embedding-3-small`) |
| `TELEGRAM_BOT_TOKEN` | Only if Telegram enabled | Telegram bot token |

All other settings have safe defaults. See `.env.example` for the full list.

---

## Feature flags

Enable/disable features in `.env`:

```bash
OPENCLAW_CONNECTOR_CLI=true        # default: true
OPENCLAW_CONNECTOR_TELEGRAM=false  # requires TELEGRAM_BOT_TOKEN
OPENCLAW_CONNECTOR_VOICE=false

OPENCLAW_MEMORY_ENABLED=false      # requires OPENCLAW_EMBED_MODEL
OPENCLAW_ACTION_CONFIRM=true       # require confirmation before destructive actions
```

Enabling a feature without its required config causes a **loud startup failure** with an actionable error message — no silent misbehavior.

---

## Local LLM / custom endpoint

To use Ollama, LM Studio, or any OpenAI-compatible server:

```bash
OPENAI_BASE_URL=http://localhost:11434/v1
OPENCLAW_CHAT_MODEL=llama3.2
```

---

## Project layout

```
.
├── .env.example          # Copy to .env; placeholders only
├── config.yaml           # Non-secret config (env-var interpolation)
├── main.py               # Async entry point
├── requirements.txt
├── scripts/
│   └── doctor.py         # Config validation without starting the runtime
├── src/
│   └── config/
│       ├── schema.py     # Pydantic models — single source of truth
│       └── loader.py     # YAML load + env expansion + validation
└── tests/
    └── test_config.py    # 10 config tests (no network)
```

**OPEN_ITEM:** `src/connectors/`, `src/memory/`, `src/actions/` are not yet implemented.

---

## Running tests

```bash
pytest tests/ -v
```

All tests run offline — no API calls, no network mocks needed.

---

## CI

GitHub Actions runs on every push/PR:
- Lint (ruff)
- Tests (Python 3.11, 3.12)
- Golden-path config check (`scripts/doctor.py`)

See `.github/workflows/ci.yml`.
