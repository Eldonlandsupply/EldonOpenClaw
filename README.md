# OpenClaw

> A production-grade, 24/7 Raspberry Pi agent runtime.
> Python + asyncio · pluggable connectors · safe action gating · SQLite memory · health endpoint · systemd deployment.

---

## What it does (v1)

| Feature | Status |
|---------|--------|
| CLI connector (stdin/stdout) | ✅ |
| Action allowlist + dry_run gating | ✅ |
| SQLite memory (KV + event log) | ✅ |
| JSON structured logging | ✅ |
| HTTP health endpoint | ✅ |
| systemd auto-start/restart | ✅ |
| Telegram connector | 🔜 (flagged, behind feature flag) |
| LLM integration (OpenAI / Anthropic) | 🔜 (config ready, wiring OPEN_ITEM) |

---

## Quick start (laptop / local dev)

```bash
git clone https://github.com/yourname/EldonOpenClaw.git
cd EldonOpenClaw

# 1. Copy config files
cp .env.example .env
cp config.yaml.example config.yaml

# 2. Edit config.yaml — set dry_run: false when ready
# 3. Run
./scripts/run_local.sh
```

Agent starts, health endpoint is live at `http://127.0.0.1:8080/health`.

### Send a command

```bash
# In another terminal (or just type in the same terminal after startup):
echo "echo hello world"
```

### Verify health

```bash
curl http://127.0.0.1:8080/health
# Expected:
# {"status": "ok", "uptime_s": 12, "last_tick": "2024-...", "version": "0.1.0"}
```

---

## Golden path verification (one command)

```bash
./scripts/verify.sh
```

This runs:
1. Unit tests
2. Config load check (prints redacted summary)
3. Starts agent for 5 seconds
4. Hits health endpoint
5. Exits 0 on success

---

## Project layout

```
src/openclaw/
├── main.py              # async entry point + tick/message loops
├── config.py            # pydantic settings + yaml loader (fails loud)
├── logging.py           # structured JSON logs
├── health.py            # aiohttp health server
├── connectors/
│   ├── base.py          # BaseConnector ABC
│   └── cli.py           # stdin/stdout connector
├── actions/
│   ├── base.py          # BaseAction ABC + ActionResult
│   └── registry.py      # allowlist gating + dispatch
└── memory/
    └── sqlite.py        # KV store + event log

tests/
├── test_config.py       # config loading + validation
└── test_action_gating.py  # allowlist + dry_run

deploy/systemd/openclaw.service  # systemd unit file
scripts/
├── run_local.sh         # dev runner
└── verify.sh            # golden-path check
```

---

## Configuration reference

### `.env` (secrets only — never commit)

| Variable | Required | Description |
|----------|----------|-------------|
| `OPENAI_API_KEY` | if llm.provider=openai | OpenAI API key |
| `TELEGRAM_BOT_TOKEN` | if telegram enabled | Bot token from @BotFather |
| `TELEGRAM_ALLOWED_CHAT_IDS` | if telegram enabled | Comma-separated chat IDs |
| `SQLITE_PATH` | No | DB path (default: `./data/openclaw.db`) |

### `config.yaml` (non-secrets)

| Key | Default | Description |
|-----|---------|-------------|
| `llm.provider` | `"none"` | `"openai"` \| `"anthropic"` \| `"none"` |
| `llm.chat_model` | `"gpt-4o-mini"` | Model name (ignored if provider=none) |
| `llm.embedding_model` | `null` | null = embeddings disabled |
| `runtime.tick_seconds` | `10` | Main loop heartbeat interval |
| `runtime.log_level` | `"INFO"` | `DEBUG\|INFO\|WARNING\|ERROR` |
| `runtime.data_dir` | `"./data"` | Created automatically |
| `runtime.dry_run` | `true` | **Safe default.** Set false when ready. |
| `connectors.cli.enabled` | `true` | Enable stdin connector |
| `connectors.telegram.enabled` | `false` | Enable Telegram connector |
| `actions.allowlist` | `["echo"]` | Action names the agent may execute |
| `actions.require_confirm` | `false` | CLI prompts before each action |
| `health.enabled` | `true` | HTTP health server |
| `health.host` | `"127.0.0.1"` | Bind address |
| `health.port` | `8080` | Port |

---

## Raspberry Pi 24/7 deployment

### Step 1: Prepare the Pi

```bash
# On Raspberry Pi OS (Debian-based), as a user with sudo

# Create dedicated user
sudo useradd --system --no-create-home --shell /sbin/nologin openclaw

# Create install and data directories
sudo mkdir -p /opt/openclaw /var/lib/openclaw /etc/openclaw
sudo chown openclaw:openclaw /opt/openclaw /var/lib/openclaw
```

### Step 2: Install the code

```bash
# Copy repo to Pi (from laptop)
rsync -av --exclude='.git' --exclude='.venv' . pi@raspberrypi.local:/opt/openclaw/

# Or on the Pi:
sudo apt install -y git python3 python3-venv
git clone https://github.com/yourname/EldonOpenClaw.git /opt/openclaw
sudo chown -R openclaw:openclaw /opt/openclaw
```

### Step 3: Create the virtualenv and install

```bash
sudo -u openclaw python3 -m venv /opt/openclaw/.venv
sudo -u openclaw /opt/openclaw/.venv/bin/pip install -e "/opt/openclaw[dev]"
```

### Step 4: Configure

```bash
# Copy and edit config
sudo -u openclaw cp /opt/openclaw/config.yaml.example /opt/openclaw/config.yaml
sudo -u openclaw nano /opt/openclaw/config.yaml
# Set: runtime.data_dir: "/var/lib/openclaw"
# Set: runtime.dry_run: false  (when ready)

# Create secrets file (root-owned, locked down)
sudo cp /opt/openclaw/.env.example /etc/openclaw/openclaw.env
sudo chmod 600 /etc/openclaw/openclaw.env
sudo chown openclaw:openclaw /etc/openclaw/openclaw.env
sudo nano /etc/openclaw/openclaw.env
# Fill in real values: SQLITE_PATH=/var/lib/openclaw/openclaw.db
```

### Step 5: Install systemd service

```bash
sudo cp /opt/openclaw/deploy/systemd/openclaw.service /etc/systemd/system/

# EDIT the service file to confirm WorkingDirectory and paths are correct
sudo nano /etc/systemd/system/openclaw.service

sudo systemctl daemon-reload
sudo systemctl enable openclaw
sudo systemctl start openclaw
```

### Step 6: Verify it's running

```bash
# Check status
systemctl status openclaw

# Expected output contains:
# Active: active (running)

# Follow live logs
journalctl -u openclaw -f

# Hit health endpoint
curl http://127.0.0.1:8080/health
# Expected: {"status": "ok", "uptime_s": ..., "last_tick": "...", "version": "0.1.0"}
```

---

## Running tests

```bash
# From repo root, with venv active
pip install -e ".[dev]"
pytest tests/ -v
```

---

## Troubleshooting

**Agent exits immediately on start**
- Check logs: `journalctl -u openclaw -n 50`
- Most likely: missing `config.yaml` or misconfigured `.env`
- Look for `FATAL CONFIG ERROR` or `FATAL:` in output

**Health returns `degraded`**
- Main loop stalled. Check CPU, disk space, Python exceptions in logs.
- `journalctl -u openclaw -p err`

**Actions are silently ignored**
- Check `actions.allowlist` in config.yaml — the action name must be listed
- Check `runtime.dry_run` — if true, actions are logged but not executed

**systemd won't start**
- `sudo journalctl -u openclaw --no-pager -n 30`
- Verify `User=openclaw` exists: `id openclaw`
- Verify `EnvironmentFile` path exists and is readable by openclaw user
- Verify `WorkingDirectory` exists

**SD card wearing out**
- Move `SQLITE_PATH` and `runtime.data_dir` to an external SSD
- Use `journal.conf` to cap journald size: `SystemMaxUse=50M`

---

## Adding a new action

1. Create a class in `src/openclaw/actions/` inheriting `BaseAction`
2. Set `name = "my_action"`
3. Implement `async def run(self, args, dry_run) -> ActionResult`
4. Register it: `registry.register(MyAction())`  (in `main.py`)
5. Add `"my_action"` to `actions.allowlist` in `config.yaml`

---

## License

Apache 2.0 — see LICENSE.
