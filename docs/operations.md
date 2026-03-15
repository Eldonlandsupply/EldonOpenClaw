# OpenClaw Operations Runbook

## Service management

```bash
# Status
sudo systemctl status openclaw

# Restart
sudo systemctl restart openclaw

# Reload config without restart (SIGHUP)
sudo systemctl kill -s HUP openclaw

# View live logs
sudo journalctl -u openclaw -f

# View last 100 lines
sudo journalctl -u openclaw -n 100 --no-pager
```

## Health check

```bash
curl -s http://localhost:8080/health | python3 -m json.tool
curl -s http://localhost:8080/ready
curl -s http://localhost:8080/ping
```

A healthy response looks like:

```json
{
  "status": "ok",
  "uptime_s": 3600,
  "last_tick": "2026-03-14T07:00:00+00:00",
  "version": "0.1.0",
  "connectors": {"telegram": "ok", "gmail": "ok"},
  "reason": ""
}
```

If `status` is `degraded`, check `reason` and `connectors` fields.

## Connector failure recovery

### Telegram stops responding
```bash
sudo systemctl restart openclaw
```
Verify bot token is still valid: `curl https://api.telegram.org/bot$TOKEN/getMe`

### Gmail IMAP drops
Gmail IMAP4_SSL connections drop silently after ~30 min idle.
The connector auto-reconnects on the next poll cycle (30s default).
If polls stop entirely:
```bash
sudo systemctl restart openclaw
```
Verify app password is still valid by testing IMAP manually:
```bash
python3 -c "import imaplib; m=imaplib.IMAP4_SSL('imap.gmail.com'); m.login('$GMAIL_USER','$GMAIL_APP_PASSWORD'); print('ok')"
```

### Outlook token expires
Microsoft Graph tokens expire after 1 hour but auto-refresh on each poll.
If token refresh fails (network issue, secret rotation):
1. Check `AZURE_CLIENT_SECRET` is still valid in `/etc/openclaw/openclaw.env`
2. `sudo systemctl restart openclaw`
3. Monitor logs for `Outlook poll error`

## Audit log

```bash
# View last 20 events
tail -n 20 /opt/openclaw/action_allowlist/audit_log.jsonl | python3 -c "
import sys, json
for line in sys.stdin:
    e = json.loads(line)
    print(e.get('timestamp','')[:19], e.get('action',''), e.get('source',''))
"

# Search by action
grep '"action": "attio_search"' /opt/openclaw/action_allowlist/audit_log.jsonl | tail -5
```

## Doctor script

Run after any config change:
```bash
cd /opt/openclaw && .venv/bin/python scripts/doctor.py
```

Expected output:
```
OK config loaded
chat_model=grok-3-mini
embedding_model=(none)
memory_enabled=False
```

## Config reload (without restart)

Edit `/opt/openclaw/config.yaml` or `/etc/openclaw/openclaw.env`, then:
```bash
sudo systemctl kill -s HUP openclaw
```
The service will reload config and restart the message loop without losing the systemd PID.

## SIGHUP reload behavior

On `SIGHUP`:
1. Current tasks are cancelled gracefully
2. All connectors are stopped
3. Chat client and memory are closed
4. Config is reloaded from disk
5. Everything restarts fresh

This is safe to use for config changes. It does NOT clear SQLite memory.

## Gateway sub-package (unused)

The `gateway/` directory contains an experimental FastAPI webhook gateway.
It is **not running** as a systemd service on the Pi. The active runtime is
`deploy/systemd/openclaw.service`. The gateway sub-package is kept for
reference and future webhook-based architecture.

Do not start `gateway/infra/openclaw-gateway.service` — it is not integrated
with the main runtime.

## Adding a new action

1. Create a class inheriting `BaseAction` in `src/openclaw/actions/` or a new
   integration directory.
2. Register it in `main.py`'s `run()` function (alongside the Attio block).
3. Add the action name to `actions.allowlist` in `config.yaml`.
4. Add an entry to `action_allowlist/top_100_actions.json` with the correct
   `execution_mode` and `risk_score`.
5. Write a test in `tests/test_actions_extended.py`.

## Secret rotation

All secrets live in `/etc/openclaw/openclaw.env`.

After rotating any key:
1. Edit `/etc/openclaw/openclaw.env`
2. `sudo systemctl kill -s HUP openclaw` (SIGHUP reload)
3. Verify health endpoint returns `"status": "ok"`

Never commit real secrets to the repo. `.env` is gitignored.
The only file committed is `.env.example`.
