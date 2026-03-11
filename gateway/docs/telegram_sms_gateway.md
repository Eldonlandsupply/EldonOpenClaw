# OpenClaw Telegram/SMS Gateway

Secure remote-control gateway for your Raspberry Pi.
Command your Pi through Telegram (primary) or SMS via Twilio (secondary).

---

## Architecture

```
Telegram Bot API ──POST──► /webhooks/telegram ──► pipeline ──► reply
Twilio SMS       ──POST──► /webhooks/sms      ──► pipeline ──► TwiML reply

pipeline:
  1. Normalize (channel → GatewayRequest)
  2. Deduplicate (message_id seen set)
  3. Authenticate (allowlist check)
  4. Route (deterministic intent classification)
  5. Risk classify (LOW / MEDIUM / HIGH)
  6. Confirmation gate (HIGH → token required)
  7. Registry dispatch (approved commands only)
  8. Audit log (every request recorded)
  9. Reply
```

---

## Setup

### 1. Create Telegram Bot

1. Message [@BotFather](https://t.me/botfather) on Telegram
2. Send `/newbot`
3. Follow prompts → receive `TELEGRAM_BOT_TOKEN`
4. Message [@userinfobot](https://t.me/userinfobot) to get your chat ID

### 2. Install

```bash
cd EldonOpenClaw
pip install -r gateway/requirements.txt
# Optional better system stats:
pip install psutil
```

### 3. Configure .env

```bash
cp gateway/.env.example .env
# Edit .env:
#   TELEGRAM_BOT_TOKEN=...
#   ALLOWED_TELEGRAM_CHAT_IDS=<your chat id>
#   ENABLE_TELEGRAM=true
```

### 4. Bootstrap data dirs

```bash
python gateway/scripts/bootstrap_gateway_data_dir.py
```

### 5. Run locally

```bash
python gateway/scripts/run_gateway.py
```

### 6. Expose Pi publicly (for Telegram webhooks)

Option A — ngrok (dev/testing):
```bash
ngrok http 8443
# Use the https URL for webhook registration
```

Option B — DuckDNS + port forward (production):
- Register at duckdns.org, set GATEWAY_BASE_URL=https://yourname.duckdns.org
- Port forward 443→8443 on your router, or use nginx with TLS

### 7. Register Telegram webhook

```bash
python gateway/scripts/setup_telegram_webhook.py https://yourname.duckdns.org
```

### 8. Deploy on Raspberry Pi (systemd)

```bash
sudo cp gateway/infra/openclaw-gateway.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable openclaw-gateway
sudo systemctl start openclaw-gateway
sudo journalctl -u openclaw-gateway -f
```

---

## Env Vars

| Variable | Required | Default | Description |
|---|---|---|---|
| `TELEGRAM_BOT_TOKEN` | Yes | — | Bot token from @BotFather |
| `ALLOWED_TELEGRAM_CHAT_IDS` | Yes | — | Comma-separated allowed chat IDs |
| `ALLOWED_TELEGRAM_USER_IDS` | No | — | Comma-separated allowed user IDs |
| `TELEGRAM_WEBHOOK_SECRET` | Recommended | — | Shared secret for webhook verification |
| `ENABLE_TELEGRAM` | No | `true` | Enable Telegram channel |
| `ENABLE_SMS` | No | `false` | Enable SMS channel |
| `TWILIO_ACCOUNT_SID` | If SMS | — | Twilio account SID |
| `TWILIO_AUTH_TOKEN` | If SMS | — | Twilio auth token |
| `TWILIO_PHONE_NUMBER` | If SMS | — | Your Twilio number (E.164) |
| `ALLOWED_SMS_NUMBERS` | If SMS | — | Comma-separated allowed numbers |
| `ENABLE_RAW_SHELL` | No | `false` | Allow arbitrary shell (keep false) |
| `ENABLE_COMMAND_CONFIRMATION` | No | `true` | Require APPROVE for HIGH-risk |
| `GATEWAY_PORT` | No | `8443` | Server port |
| `GATEWAY_BASE_URL` | Webhook setup | — | Public URL for webhook registration |
| `DATA_DIR` | No | `./data` | Data/audit log directory |
| `AGENTS_DIR` | No | `./agents` | Agent spec storage directory |
| `LOG_LEVEL` | No | `INFO` | Logging level |

---

## Security Model

- **Unknown senders** — rejected before any processing
- **Allowlist** — chat IDs and/or user IDs checked on every message
- **HIGH-risk commands** — never execute immediately; require `APPROVE <token>` from original sender within 120 seconds
- **Raw shell** — disabled by default (`ENABLE_RAW_SHELL=false`)
- **Webhook secret** — Telegram supports a shared secret header to prevent spoofed requests
- **Audit log** — every request logged to `data/audit.jsonl` (no secrets in log)
- **No stack traces** to users — only sanitized error strings

---

## Approved Commands

### Telegram (full set)

| Command | Risk | Notes |
|---|---|---|
| `status` | LOW | System health, CPU, memory, disk, temp |
| `health` | LOW | Quick health check |
| `queue status` | LOW | Show pending tasks |
| `list agents` | LOW | Show configured agents |
| `help` | LOW | Command list |
| `check failed jobs` | LOW | Recent job failures |
| `run morning brief` | MEDIUM | Morning workflow |
| `git pull` | MEDIUM | Pull latest repo |
| `create agent <description>` | MEDIUM | Generate agent YAML spec |
| `schedule <task>` | MEDIUM | Schedule a task |
| `restart openclaw` | **HIGH** | Requires APPROVE token |

### SMS (subset)

`status`, `health`, `queue status`, `help`, `restart openclaw` (HIGH, needs APPROVE)

---

## Confirmation Flow

```
You:  restart openclaw
Bot:  Authenticated: YES
      Intent: EXECUTE_TASK
      Risk: HIGH
      Action: restart_openclaw
      Result: CONFIRM REQUIRED
      Reply exactly: APPROVE restart-openclaw-7f3a

You:  APPROVE restart-openclaw-7f3a
Bot:  Authenticated: YES
      Intent: APPROVE
      Risk: HIGH
      Action: restart_openclaw
      Result: OpenClaw service restart initiated.
      (ran in 0.3s)
```

Tokens expire after **120 seconds**. Only the original sender can approve.

---

## Twilio SMS Setup

1. Create a Twilio account at twilio.com
2. Buy a phone number with SMS capability
3. Set the "A MESSAGE COMES IN" webhook to: `https://yourpi.domain.com/webhooks/sms`
4. Set env vars: `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_PHONE_NUMBER`
5. Set `ENABLE_SMS=true` and `ALLOWED_SMS_NUMBERS=+1XXXXXXXXXX`

---

## Troubleshooting

**"REJECTED: Unauthorized sender"**
→ Your chat ID is not in `ALLOWED_TELEGRAM_CHAT_IDS`. Message @userinfobot to find it.

**Telegram bot not responding**
→ Check `sudo journalctl -u openclaw-gateway -f`
→ Verify webhook: `python gateway/scripts/setup_telegram_webhook.py <url>`
→ Ensure port is publicly reachable

**Token expired**
→ Tokens expire in 120s. Re-send the original command to get a new token.

**`OPEN_ITEM` responses**
→ Those handlers are stubbed. Wire them in `app/handlers/task_handler.py`.
