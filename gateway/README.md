# Gateway Sub-Package (Experimental / Not Active)

This directory contains an experimental FastAPI-based webhook gateway.

## Status

**NOT active.** The deployed runtime is `src/openclaw/main.py`, managed by
`deploy/systemd/openclaw.service`. This gateway sub-package is retained for
reference and future architecture exploration.

## Architecture relationship

The active runtime uses polling connectors (Telegram getUpdates, Gmail IMAP,
Outlook Graph). This gateway was intended as an alternative architecture using
webhook-based inbound routing. The two architectures are not currently integrated.

## If you want to experiment with this

```bash
cd gateway
pip install -r requirements.txt
python scripts/run_gateway.py
```

The gateway is **not wired to the ActionRegistry** from the main runtime.
It has its own auth, risk scoring, and routing pipeline.

## Do not enable in production

Do not enable `gateway/infra/openclaw-gateway.service` on the Pi alongside the
main `openclaw.service`. They listen on different ports but the webhook architecture
is incomplete and not production-hardened.

See `docs/operations.md` for the production runbook.
