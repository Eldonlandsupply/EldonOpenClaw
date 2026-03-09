# EldonOpenClaw — Raspberry Pi 24/7 Deployment Guide

---

## 1. VERDICT: Is EldonOpenClaw Ready for Raspberry Pi 24/7?

**Mostly yes, with two important caveats.**

The core stack (Python 3.11+, asyncio, pydantic, pyyaml, aiohttp, sqlite3) is fully ARM64-compatible and runs cleanly on Raspberry Pi OS Lite 64-bit. No compiled binaries, no architecture-specific wheels, no GPU dependencies.

**Two issues require attention before deployment:**

1. **Dual config system divergence.** The repo has two separate config systems that partially overlap: `src/config/` (Pydantic-based, used by `main.py`) and `src/openclaw/config.py` (used by `src/openclaw/main.py`). The `src/openclaw/main.py` entry point is what the systemd service runs (`python -m openclaw.main`), but `src/openclaw/config.py` calls `sys.exit(1)` on bad config rather than raising an exception — this is acceptable for production but means you cannot catch config errors in tests without patching. Confirm which entry point you intend to run before deploying.

2. **`dry_run: true` is the safe default.** `config.yaml.example` ships with `dry_run: true`. Actions will log intent but not execute. **Flip this to `false` only when you are ready.** The systemd service will inherit whatever is in your `config.yaml`.

---

## 2. Top Risks / Blockers

| Risk | Severity | Fix |
|---|---|---|
| `dry_run: true` left in config | Silent failure — agent does nothing | Set `dry_run: false` in `config.yaml` |
| `OPENAI_API_KEY` not set | Fatal startup error if `llm.provider=openai` | Set in `/etc/openclaw/openclaw.env` |
| SD card wear from SQLite writes | Data corruption over months | Enable WAL mode (already done), consider tmpfs for logs |
| No Telegram connector implemented | Warning only, not fatal | Do not enable `connectors.telegram.enabled: true` |
| `require_confirm: true` on CLI | Blocks autonomous operation | Set to `false` for headless/autonomous mode |
| Python < 3.11 on Pi | Syntax errors | Raspberry Pi OS Lite (Bookworm) ships 3.11 — use Bookworm |

---

## 3. Recommended OS

**Raspberry Pi OS Lite 64-bit (Bookworm, Debian 12)**

Reasons:
- Ships Python 3.11 natively — no manual Python install required
- Smaller footprint than Ubuntu Server, better first-party Pi support
- Better thermal and GPIO support (relevant for 24/7 hardware)
- systemd-based, matches the included `deploy/systemd/openclaw.service`

Use Ubuntu Server 24.04 LTS only if you need snaps, newer kernel features, or enterprise tooling. For this repo there is no benefit.

---

## 4. Step-by-Step: Blank SD Card to Running Service

---

### A. Pre-flight Checklist

**Required hardware:**
- Raspberry Pi 4 (2GB minimum, 4GB recommended for headroom) or Pi 5
- MicroSD card: **32GB minimum, A2-rated** (e.g., SanDisk Extreme Pro A2 or Samsung PRO Endurance)
- USB-C power supply: **official Pi 4/5 supply (5V/3A)**. Underpowered PSUs cause random reboots.
- Ethernet cable (preferred for stability) OR 2.4/5GHz Wi-Fi credentials

**Optional but strongly recommended:**
- Passive heatsink or fan case — required for sustained 24/7 load
- UPS (CyberPower CP600LCD or similar) — protects against power loss corruption

**SD card note:** SD cards wear out from repeated writes. SQLite WAL mode reduces this. For a write-heavy agent, an external USB SSD is better long-term. See section H.

---

### B. Flash the SD Card (from your Mac)

**Step 1: Install Raspberry Pi Imager**
```
brew install --cask raspberry-pi-imager
```
Or download from: https://www.raspberrypi.com/software/

**Step 2: Flash with preconfiguration**

1. Open Raspberry Pi Imager
2. Choose Device: Raspberry Pi 4 (or 5)
3. Choose OS: **Raspberry Pi OS Lite (64-bit)** — under "Raspberry Pi OS (other)"
4. Choose Storage: your SD card
5. Click **Edit Settings** (gear icon) before writing:
   - Set hostname: `openclaw`
   - Enable SSH: Use password authentication
   - Set username: `pi` (or `openclaw`)
   - Set password: (strong password, save it)
   - Configure Wi-Fi: enter SSID and password if not using Ethernet
   - Set locale: your timezone (e.g., `America/Chicago`)
6. Write and wait.

**Step 3: Find the Pi on your network**

Insert SD card, power on, wait 60 seconds, then from your Mac:
```bash
ping openclaw.local
```
Or scan your network:
```bash
arp -a | grep -i raspberry
```

**Step 4: SSH in**
```bash
ssh pi@openclaw.local
```
Accept the fingerprint, enter your password.

---

### C. Base Linux Hardening

Run these commands after first SSH login. Each command is on its own line — paste one at a time.

**Update everything:**
```bash
sudo apt update
```
```bash
sudo apt upgrade -y
```
```bash
sudo apt autoremove -y
```

**Verify hostname and timezone:**
```bash
hostname
```
```bash
timedatectl
```
```bash
sudo timedatectl set-timezone America/Chicago
```
(Replace with your timezone. Find options with: `timedatectl list-timezones`)

**Install essentials:**
```bash
sudo apt install -y git curl wget nano unzip fail2ban ufw
```

**Configure firewall (UFW):**
```bash
sudo ufw default deny incoming
```
```bash
sudo ufw default allow outgoing
```
```bash
sudo ufw allow ssh
```
```bash
sudo ufw allow 8080/tcp
```
(Port 8080 is the health check endpoint. If you don't need external access to it, skip this line.)
```bash
sudo ufw --force enable
```
```bash
sudo ufw status
```

**SSH hardening — edit sshd_config:**
```bash
sudo nano /etc/ssh/sshd_config
```
Find and set these lines (add if missing):
```
PermitRootLogin no
PasswordAuthentication yes
MaxAuthTries 3
```
Then:
```bash
sudo systemctl restart ssh
```

**fail2ban — protect against brute force:**
```bash
sudo systemctl enable fail2ban
```
```bash
sudo systemctl start fail2ban
```
```bash
sudo fail2ban-client status sshd
```

**Unattended security upgrades:**
```bash
sudo apt install -y unattended-upgrades
```
```bash
sudo dpkg-reconfigure -plow unattended-upgrades
```
Select "Yes" when prompted.

---

### D. Repository Readiness Audit

**Confirmed from source inspection:**

| Item | Finding |
|---|---|
| Language | Python 3.11+ |
| Package manager | pip, no poetry/uv/npm required |
| OS dependencies | None beyond Python stdlib + pip packages |
| Docker | Optional, not required |
| Virtual environment | Required (pip install into venv) |
| ARM64 compatibility | ✅ All packages are pure-Python or have ARM64 wheels |
| Required env vars | `OPENAI_API_KEY` (if provider=openai), config via `.env` |
| Entry point | `python -m openclaw.main config.yaml` |
| Config system | `src/openclaw/config.py` + `config.yaml.example` |
| Health endpoint | `http://HOST:8080/health` |
| SQLite | WAL mode enabled — write-safe |
| Systemd service | `deploy/systemd/openclaw.service` — needs path edits |

**Missing from repo (you must provide):**
- A real `.env` file with secrets
- `config.yaml` with non-placeholder values
- `OPENAI_API_KEY` if using OpenAI

---

### E. Full Install Procedure

**Create a dedicated user:**
```bash
sudo useradd -r -s /bin/bash -m -d /opt/openclaw openclaw
```

**Clone the repo:**
```bash
sudo git clone https://github.com/Eldonlandsupply/EldonOpenClaw.git /opt/openclaw
```

**Set ownership:**
```bash
sudo chown -R openclaw:openclaw /opt/openclaw
```

**Switch to the openclaw user:**
```bash
sudo -u openclaw bash
```

**Enter repo directory:**
```bash
cd /opt/openclaw
```

**Verify Python version:**
```bash
python3 --version
```
Expected: `Python 3.11.x` or higher.

**Create virtual environment:**
```bash
python3 -m venv .venv
```

**Activate it:**
```bash
source .venv/bin/activate
```

**Install dependencies:**
```bash
pip install --upgrade pip
```
```bash
pip install -r requirements.txt
```
```bash
pip install -e ".[dev]"
```

**Create config.yaml from example:**
```bash
cp config.yaml.example config.yaml
```

**Edit config.yaml — required changes:**
```bash
nano config.yaml
```

Set these values:
```yaml
llm:
  provider: "openai"          # or "none" if no LLM needed yet
  chat_model: "gpt-4o-mini"   # replace with your real model

runtime:
  dry_run: false               # SET THIS TO false WHEN READY

connectors:
  cli:
    enabled: true
  telegram:
    enabled: false             # keep false until implemented
```

**Create the secrets directory and env file:**
```bash
exit   # back to your sudo user
```
```bash
sudo mkdir -p /etc/openclaw
```
```bash
sudo nano /etc/openclaw/openclaw.env
```

Add your secrets:
```bash
OPENAI_API_KEY=sk-your-real-key-here
SQLITE_PATH=/var/lib/openclaw/openclaw.db
```

```bash
sudo chmod 600 /etc/openclaw/openclaw.env
```
```bash
sudo chown openclaw:openclaw /etc/openclaw/openclaw.env
```

**Create data directory:**
```bash
sudo mkdir -p /var/lib/openclaw
```
```bash
sudo chown openclaw:openclaw /var/lib/openclaw
```

---

### F. First-Run Test (Manual)

Switch to the openclaw user and run manually first:
```bash
sudo -u openclaw bash
```
```bash
cd /opt/openclaw
```
```bash
source .venv/bin/activate
```
```bash
python -m openclaw.main config.yaml
```

**Healthy startup looks like:**
```json
{"timestamp":"...","level":"INFO","logger":"openclaw.main","event":"openclaw starting","version":"0.1.0"}
{"timestamp":"...","level":"INFO","logger":"openclaw.health","event":"health server started","host":"127.0.0.1","port":8080}
{"timestamp":"...","level":"INFO","logger":"openclaw.connectors.cli","event":"CLI connector started — type commands and press Enter"}
{"timestamp":"...","level":"INFO","logger":"openclaw.main","event":"openclaw running — Ctrl+C to stop"}
```

**Verify health endpoint (from another terminal):**
```bash
curl http://127.0.0.1:8080/health
```
Expected:
```json
{"status": "ok", "uptime_s": 12, "last_tick": "...", "version": "0.1.0"}
```

**Common failure modes:**

| Error | Cause | Fix |
|---|---|---|
| `FATAL CONFIG ERROR: llm.provider=openai but OPENAI_API_KEY is not set` | Key missing from env | Add to `/etc/openclaw/openclaw.env` |
| `Config file not found: config.yaml` | Wrong working directory | `cd /opt/openclaw` first |
| `ModuleNotFoundError: No module named 'openclaw'` | Venv not active or package not installed | `source .venv/bin/activate && pip install -e .` |
| `Address already in use` on port 8080 | Another process using it | Change `health.port` in `config.yaml` |
| `{"status":"degraded"}` from health | Main loop stalled > 60s | Check logs, likely startup error |

Stop with `Ctrl+C`, then `exit` back to your sudo user.

---

### G. systemd Service

**Edit the included service file:**
```bash
sudo nano /opt/openclaw/deploy/systemd/openclaw.service
```

Replace the entire file content with:

```ini
[Unit]
Description=OpenClaw Agent Runtime
Documentation=https://github.com/Eldonlandsupply/EldonOpenClaw
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=openclaw
Group=openclaw

WorkingDirectory=/opt/openclaw

EnvironmentFile=/etc/openclaw/openclaw.env

ExecStart=/opt/openclaw/.venv/bin/python -m openclaw.main /opt/openclaw/config.yaml

Restart=always
RestartSec=5
TimeoutStopSec=15

StandardOutput=journal
StandardError=journal
SyslogIdentifier=openclaw

NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ReadWritePaths=/var/lib/openclaw /opt/openclaw/data

[Install]
WantedBy=multi-user.target
```

**Install and enable the service:**
```bash
sudo cp /opt/openclaw/deploy/systemd/openclaw.service /etc/systemd/system/openclaw.service
```
```bash
sudo systemctl daemon-reload
```
```bash
sudo systemctl enable openclaw
```
```bash
sudo systemctl start openclaw
```
```bash
sudo systemctl status openclaw
```

**Watch live logs:**
```bash
sudo journalctl -u openclaw -f
```

**Check last 100 lines:**
```bash
sudo journalctl -u openclaw -n 100
```

---

### H. Resilience and Operations

**Starts on boot:** `systemctl enable` handles this. Confirmed by the `WantedBy=multi-user.target` in the service file.

**Crash recovery:** `Restart=always` + `RestartSec=5` means systemd restarts it within 5 seconds of any crash.

**SD card wear:**
The biggest long-term risk for 24/7 Pi deployments is SD card wear from write-heavy workloads. SQLite WAL mode (already enabled in `memory/sqlite.py`) significantly reduces write amplification. Additional measures:

```bash
sudo nano /etc/fstab
```
Add a tmpfs for logs (reduces SD writes):
```
tmpfs /tmp tmpfs defaults,noatime,nosuid,size=64m 0 0
```

For a write-heavy agent, migrate to USB SSD:
```bash
sudo apt install -y rpi-imager   # or use Raspberry Pi Imager on Mac to clone
```
Then update `/boot/firmware/config.txt` and boot from USB. This eliminates SD card wear entirely.

**Power loss protection:**
The sqlite WAL mode provides crash-safe writes. For additional protection:

1. Add `noatime` to your filesystem mount options in `/etc/fstab`
2. Use a UPS — even a basic one (CyberPower CP600LCD ~$60) prevents the most common corruption scenario
3. Enable the hardware watchdog so the Pi auto-reboots if the kernel freezes:

```bash
sudo nano /etc/systemd/system.conf
```
Set:
```
RuntimeWatchdogSec=15
RebootWatchdogSec=2min
```

**Docker Compose:** Not needed for this repo. systemd restart policy is simpler, lighter, and better integrated with journald logging on Pi.

---

### I. Monitoring and Maintenance

**Health check from anywhere on your network:**
```bash
curl http://openclaw.local:8080/health
```

**Disk usage:**
```bash
df -h
```
```bash
du -sh /var/lib/openclaw/
```

**Memory and CPU:**
```bash
free -h
```
```bash
vcgencmd measure_temp
```
(Temperature should stay below 80°C under load. Above 85°C = throttling.)

**Service status:**
```bash
sudo systemctl status openclaw
```

**Pull latest changes and restart:**
```bash
cd /opt/openclaw
```
```bash
sudo git pull origin main
```
```bash
sudo -u openclaw bash -c "cd /opt/openclaw && source .venv/bin/activate && pip install -e . -q"
```
```bash
sudo systemctl restart openclaw
```
```bash
sudo systemctl status openclaw
```

**Log rotation** is handled automatically by journald. Default retention is 100MB or 2 weeks. To set explicitly:
```bash
sudo nano /etc/systemd/journald.conf
```
Add:
```
SystemMaxUse=200M
MaxRetentionSec=4week
```
```bash
sudo systemctl restart systemd-journald
```

**Config/secrets backup** — run from your Mac periodically:
```bash
scp pi@openclaw.local:/etc/openclaw/openclaw.env ./openclaw.env.backup
```
```bash
scp pi@openclaw.local:/opt/openclaw/config.yaml ./config.yaml.backup
```
Store these encrypted, never in git.

---

## 5. Exact Config Files to Create

### `/opt/openclaw/config.yaml`
```yaml
llm:
  provider: "openai"
  chat_model: "gpt-4o-mini"
  embedding_model: null

runtime:
  tick_seconds: 10
  log_level: "INFO"
  data_dir: "/var/lib/openclaw"
  dry_run: false

connectors:
  cli:
    enabled: true
  telegram:
    enabled: false

actions:
  allowlist:
    - "echo"
    - "memory_write"
    - "memory_read"
  require_confirm: false

health:
  enabled: true
  host: "0.0.0.0"
  port: 8080
```

Note: Change `host` to `"0.0.0.0"` to allow health checks from other machines on your network. Keep `"127.0.0.1"` for localhost-only.

### `/etc/openclaw/openclaw.env`
```bash
OPENAI_API_KEY=sk-your-real-key-here
SQLITE_PATH=/var/lib/openclaw/openclaw.db
```

---

## 6. Verification Commands

```bash
sudo systemctl status openclaw
```
```bash
curl http://openclaw.local:8080/health
```
```bash
sudo journalctl -u openclaw -n 50
```
```bash
sudo -u openclaw /opt/openclaw/.venv/bin/python scripts/doctor.py
```

---

## 7. Troubleshooting Table

| Symptom | Likely Cause | Fix |
|---|---|---|
| Service fails to start | Bad config.yaml or missing env vars | `journalctl -u openclaw -n 30`, fix error shown |
| `FATAL CONFIG ERROR` in logs | Missing or placeholder secrets | Edit `/etc/openclaw/openclaw.env` |
| `/health` returns `{"status":"degraded"}` | Main loop stalled | Check logs for exception, restart service |
| `/health` connection refused | Port 8080 not open or wrong host binding | Check `health.host` in config.yaml, check UFW |
| Service starts then immediately stops | Python error at boot | Run manually first: `sudo -u openclaw bash -c "cd /opt/openclaw && source .venv/bin/activate && python -m openclaw.main config.yaml"` |
| `ModuleNotFoundError` | Package not installed in venv | `sudo -u openclaw /opt/openclaw/.venv/bin/pip install -e /opt/openclaw` |
| High CPU on Pi | Tick loop too fast | Increase `runtime.tick_seconds` in config.yaml |
| SD card corruption after power loss | Write-heavy SQLite without protection | Enable WAL (already done), add UPS, consider USB SSD |
| SSH locked out | UFW misconfigured or fail2ban ban | Connect via HDMI+keyboard, `sudo ufw allow ssh` or `sudo fail2ban-client unban YOUR_IP` |

---

## 8. Minimum Viable Path (Fastest Clean Install)

1. Flash Raspberry Pi OS Lite 64-bit (Bookworm) with Raspberry Pi Imager, enable SSH
2. SSH in: `ssh pi@openclaw.local`
3. `sudo apt update && sudo apt upgrade -y && sudo apt install -y git`
4. `sudo git clone https://github.com/Eldonlandsupply/EldonOpenClaw.git /opt/openclaw`
5. `cd /opt/openclaw && python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt && pip install -e .`
6. `cp config.yaml.example config.yaml && nano config.yaml` — set `dry_run: false`, set LLM model
7. `echo "OPENAI_API_KEY=sk-your-key" > .env`
8. `python -m openclaw.main config.yaml` — verify healthy startup
9. Copy service file, `systemctl enable --now openclaw`

Done in ~15 minutes.

---

## 9. Best Production Path (Most Reliable Long-Term)

1. Flash Bookworm Lite 64-bit via Imager with hostname, SSH, Wi-Fi preconfigured
2. SSH in, run full hardening: `apt upgrade`, `ufw`, `fail2ban`, SSH config, unattended-upgrades
3. Create dedicated `openclaw` user with `useradd -r`
4. Clone to `/opt/openclaw`, set ownership to `openclaw:openclaw`
5. Install into `.venv` as `openclaw` user
6. Store secrets in `/etc/openclaw/openclaw.env` with `chmod 600`
7. Store SQLite database in `/var/lib/openclaw/` (survives repo updates)
8. Set `health.host: "0.0.0.0"` to allow remote monitoring
9. Copy and customize the systemd service, `daemon-reload`, `enable`, `start`
10. Add `noatime` to `/etc/fstab`, enable watchdog in `system.conf`
11. Set up journald retention limits
12. Optional: migrate to USB SSD if write-heavy
13. Optional: add UPS
14. Schedule weekly `git pull` + `pip install -e .` + `systemctl restart openclaw` via cron

Total time: ~45 minutes. Expected uptime: months without intervention.
