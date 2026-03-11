# Threat Model — OpenClaw Telegram/SMS Gateway

## Trust Boundaries

```
[ Telegram Servers ] ──HTTPS──► [ Pi (gateway) ] ──► [ OpenClaw runtime ]
[ Twilio Servers   ] ──HTTPS──►        │
[ Internet         ]                   │── [ Audit log ]
                                       │── [ Agents dir ]
                                       │── [ SQLite memory ]
```

- **Trusted**: Messages from allowlisted Telegram chat/user IDs or SMS numbers
- **Untrusted**: All other senders; Telegram server itself for payload integrity (mitigated by webhook secret)
- **Semi-trusted**: The Pi OS (assumed physically secure in your building)

---

## Threats and Mitigations

| Threat | Mitigation |
|---|---|
| Unknown sender sending commands | Allowlist rejects before any processing |
| Attacker spoofing Telegram webhook | `TELEGRAM_WEBHOOK_SECRET` header verified via `hmac.compare_digest` |
| Replay attack (resending old message) | `message_id` dedupe set (in-memory, resets on restart) |
| High-risk command executed without consent | Confirmation token required; expires in 120s; sender must match |
| Confirmation token stolen from chat | Token is short-lived (120s); only original sender can redeem |
| Arbitrary shell injection | `ENABLE_RAW_SHELL=false` by default; registry blocks unregistered commands |
| Secret leaked in logs | Audit log explicitly excludes secret fields; no stack traces to users |
| `.env` committed to git | `.env` in `.gitignore`; only `.env.example` committed |
| Bot token exposed | Rotate via @BotFather; update `.env` on Pi |
| Attachment upload with malicious file | MIME type allowlist; size limit (20MB); no auto-execution |
| Pi physically compromised | Out of scope for software controls; use disk encryption |
| Twilio webhook spoofing | OPEN ITEM: Twilio signature validation not yet implemented |

---

## Residual Risks

- **In-memory dedupe resets on restart** — an attacker could replay a message immediately after a restart. Mitigated by: authorization still required; confirmation still required for HIGH-risk.
- **Twilio webhook signature** — not yet validated. Mitigate by setting `ALLOWED_SMS_NUMBERS` tightly and enabling `ENABLE_SMS=false` unless needed.
- **Confirmation token in Telegram chat** — visible to anyone with access to the chat. Mitigate by using private 1:1 bot chat, not group chats.
- **`APPROVE` token can be phished** — if attacker can read your Telegram messages, they can approve HIGH-risk commands. Mitigate: use bot in private chat only.
- **No rate limiting** — a compromised allowed sender could spam LOW-risk commands. Mitigate: add per-sender rate limiter (OPEN ITEM).

---

## Recommended Next Hardening Steps

1. **Twilio request signature validation** — verify `X-Twilio-Signature` header using `twilio.request_validator`
2. **Per-sender rate limiting** — add token bucket per sender_id in the pipeline
3. **SQLite-backed dedupe** — persist seen message IDs across restarts
4. **mTLS or VPN** — run gateway behind WireGuard or Tailscale instead of exposing to internet
5. **HTTPS/TLS termination** — use nginx + Let's Encrypt in front of the aiohttp server
6. **Two-factor confirmation** — for CRITICAL actions, require a second channel confirmation
7. **Audit log rotation** — rotate `data/audit.jsonl` daily; ship to remote log store
8. **Pi disk encryption** — encrypt SD card to protect secrets if Pi is physically accessible
