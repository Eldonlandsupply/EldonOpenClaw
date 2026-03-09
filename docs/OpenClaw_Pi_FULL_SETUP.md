# OpenClaw — Full Raspberry Pi Setup
## From Blank SD Card to Running 24/7 Service
### Every single step. No gaps. No assumptions.

---

# PART 1: FLASH THE SD CARD (on your Mac)

---

## Step 1 — Install Raspberry Pi Imager

Open Terminal on your Mac and run:

```zsh
brew install --cask raspberry-pi-imager
```

If you don't have Homebrew, first install it:

```zsh
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
```

Then re-run the imager install command above.

After it finishes, open Raspberry Pi Imager from your Applications folder (or Spotlight: Cmd+Space → type "Raspberry Pi Imager").

---

## Step 2 — Insert Your SD Card

Put the SD card into your Mac's SD card slot or a USB adapter. It will mount on your Desktop. **Do not open or do anything with it yet.**

---

## Step 3 — Configure and Flash

Inside Raspberry Pi Imager:

**1. Click "Choose Device"**
- Select: **Raspberry Pi 4** (or Pi 5 if that's your hardware)

**2. Click "Choose OS"**
- Click **"Raspberry Pi OS (other)"**
- Select **"Raspberry Pi OS Lite (64-bit)"**
  - It will say "Debian Bookworm" in the description — that is correct
  - Do NOT pick the desktop version. You want Lite (no GUI)

**3. Click "Choose Storage"**
- Select your SD card from the list
  - It will show the card name and size (e.g., "Generic MassStorageClass Media - 32.0 GB")
  - **Triple-check this is your SD card, not an external drive**

**4. Click the pencil/gear icon that appears ("Edit Settings")**

You will see a form. Fill it in exactly:

| Field | Value to enter |
|---|---|
| Hostname | `openclaw` |
| Username | `pi` |
| Password | Pick something strong, write it down — you will need it every SSH session |
| Configure wireless LAN | Check this box if using Wi-Fi |
| SSID | Your Wi-Fi network name (exact, case-sensitive) |
| Password | Your Wi-Fi password |
| Wireless LAN country | `US` |
| Set locale | Check this box |
| Time zone | `America/Chicago` |
| Keyboard layout | `us` |

**5. Click the "Services" tab at the top of that same dialog**
- Check **"Enable SSH"**
- Select **"Use password authentication"**

**6. Click "Save"**

**7. Click "Yes" when asked "Would you like to apply OS customisation settings?"**

**8. Click "Yes" when asked if you're sure you want to erase the SD card**

The flash will take 3–8 minutes. Wait for "Write Successful" before touching the card.

**9. Click "Continue" then close Raspberry Pi Imager**

---

## Step 4 — Eject the SD Card

```zsh
diskutil eject /Volumes/bootfs
```

If that path doesn't work, right-click the SD card on your Desktop and click Eject. Remove the card physically from your Mac.

---

# PART 2: FIRST BOOT AND SSH IN

---

## Step 5 — Insert SD Card into Pi and Power On

1. Insert the SD card into the Raspberry Pi's microSD slot (it's on the underside, card label facing down)
2. Plug in your Ethernet cable if using wired (recommended)
3. Plug in the USB-C power supply

The Pi will boot. The green activity LED will flicker for about 60–90 seconds on first boot while it expands the filesystem.

**Wait a full 90 seconds before trying to connect.**

---

## Step 6 — Find the Pi on Your Network

From your Mac Terminal, try this first:

```zsh
ping -c 3 openclaw.local
```

You should see replies like:
```
64 bytes from openclaw.local (192.168.1.X): icmp_seq=0 ttl=64 time=2.4 ms
```

If ping fails, try scanning your router's network instead:

```zsh
arp -a | grep -v incomplete
```

Look for a line that says `raspberry` in it, or compare IPs to your router's device list.

---

## Step 7 — SSH Into the Pi

```zsh
ssh pi@openclaw.local
```

You will see:
```
The authenticity of host 'openclaw.local' can't be established.
Are you sure you want to continue connecting (yes/no/[fingerprint])?
```

Type `yes` and press Enter.

Enter the password you chose in Step 3 when prompted.

You are now inside the Pi. Your prompt will look like:
```
pi@openclaw:~ $
```

**Everything from this point forward is typed inside that SSH session, not on your Mac.**

---

# PART 3: HARDEN AND UPDATE THE OS

---

## Step 8 — Update the System

Run each of these one at a time:

```bash
sudo apt update
```

Wait for it to finish, then:

```bash
sudo apt upgrade -y
```

This may take 3–10 minutes on first run. Wait for it to fully complete.

```bash
sudo apt autoremove -y
```

---

## Step 9 — Verify Hostname and Timezone

```bash
hostname
```
Should print: `openclaw`

```bash
timedatectl
```
Look for `Time zone: America/Chicago`. If it says something else:

```bash
sudo timedatectl set-timezone America/Chicago
```

---

## Step 10 — Install Required Tools

```bash
sudo apt install -y git curl wget nano unzip fail2ban ufw python3-venv python3-pip
```

This installs Git, the firewall, brute-force protection, and Python tools. Takes about 1–2 minutes.

---

## Step 11 — Configure the Firewall

Run each command separately:

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

```bash
sudo ufw --force enable
```

```bash
sudo ufw status
```

You should see:
```
Status: active

To                         Action      From
--                         ------      ----
22/tcp                     ALLOW       Anywhere
8080/tcp                   ALLOW       Anywhere
```

---

## Step 12 — Harden SSH

```bash
sudo nano /etc/ssh/sshd_config
```

Use Ctrl+W to search. Find and change these three lines:

- Find `#PermitRootLogin prohibit-password` → change to: `PermitRootLogin no`
- Find `#MaxAuthTries 6` → change to: `MaxAuthTries 3`
- Find `PasswordAuthentication` → make sure it says: `PasswordAuthentication yes`

Save with Ctrl+X → Y → Enter

```bash
sudo systemctl restart ssh
```

**Do not close your current SSH window until you verify you can open a new one. Open a second Terminal tab on your Mac and try `ssh pi@openclaw.local` to confirm it still works.**

---

## Step 13 — Enable fail2ban

```bash
sudo systemctl enable fail2ban
```

```bash
sudo systemctl start fail2ban
```

```bash
sudo fail2ban-client status sshd
```

You should see `Number of currently banned IP: 0` — that's normal and correct.

---

## Step 14 — Enable Unattended Security Upgrades

```bash
sudo apt install -y unattended-upgrades
```

```bash
sudo dpkg-reconfigure -plow unattended-upgrades
```

A dialog appears. Use arrow keys to select **Yes** and press Enter.

---

# PART 4: CREATE THE APP USER AND DIRECTORIES

---

## Step 15 — Create a Dedicated System User

OpenClaw will run as its own user, not as `pi`. This is a security best practice.

```bash
sudo useradd -r -s /bin/bash -m -d /opt/openclaw openclaw
```

Verify it was created:

```bash
id openclaw
```

Should show something like: `uid=999(openclaw) gid=999(openclaw) groups=999(openclaw)`

---

## Step 16 — Create the Data and Secrets Directories

```bash
sudo mkdir -p /var/lib/openclaw
```

```bash
sudo mkdir -p /etc/openclaw
```

```bash
sudo chown openclaw:openclaw /var/lib/openclaw
```

```bash
sudo chown root:openclaw /etc/openclaw
```

```bash
sudo chmod 750 /etc/openclaw
```

---

## Step 17 — Create the Secrets File

This file holds your API keys and will never be committed to git.

```bash
sudo nano /etc/openclaw/openclaw.env
```

Paste in exactly the following — these are your real credentials:

```
OPENROUTER_API_KEY=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
SQLITE_PATH=/var/lib/openclaw/openclaw.db
AZURE_TENANT_ID=5afeb96a-473a-4650-81f7-4c61f3bf3461
AZURE_CLIENT_ID=a1c063c0-eefb-465d-90c2-d3eca184d33f
AZURE_CLIENT_SECRET=2acf5611-26fd-4620-907b-bcaffd8d20c6
GMAIL_USER=Matthew.tynski@gmail.com
GMAIL_APP_PASSWORD=ffap povw pdnf zxcp
NOTIFICATION_EMAIL=Matthew.tynski@ou.edu
```

Save: Ctrl+X → Y → Enter

Lock it down:

```bash
sudo chmod 640 /etc/openclaw/openclaw.env
```

```bash
sudo chown root:openclaw /etc/openclaw/openclaw.env
```

Verify permissions:

```bash
ls -la /etc/openclaw/
```

Should show:
```
-rw-r----- 1 root openclaw  ... openclaw.env
```

---

# PART 5: CLONE AND INSTALL OPENCLAW

---

## Step 18 — Clone the Repository

```bash
sudo git clone https://github.com/Eldonlandsupply/EldonOpenClaw.git /opt/openclaw
```

```bash
sudo chown -R openclaw:openclaw /opt/openclaw
```

Verify it cloned:

```bash
ls /opt/openclaw
```

You should see files like `requirements.txt`, `config.yaml.example`, `src/`, etc.

---

## Step 19 — Switch to the openclaw User

```bash
sudo -u openclaw bash
```

Your prompt changes to:
```
openclaw@openclaw:/home/pi $
```

Navigate into the repo:

```bash
cd /opt/openclaw
```

---

## Step 20 — Verify Python Version

```bash
python3 --version
```

Must show `Python 3.11.x` or higher. If it shows 3.9 or 3.10, stop here — you need Raspberry Pi OS Bookworm (Debian 12), not Bullseye.

---

## Step 21 — Create the Virtual Environment

```bash
python3 -m venv .venv
```

Activate it:

```bash
source .venv/bin/activate
```

Your prompt now shows `(.venv)` at the start. This means you are inside the virtual environment. Every `pip install` from now on goes into this isolated environment, not the system Python.

---

## Step 22 — Install Python Dependencies

```bash
pip install --upgrade pip
```

```bash
pip install -r requirements.txt
```

This may take 3–5 minutes on a Pi. Watch for any red ERROR lines. Yellow warnings are fine.

```bash
pip install -e .
```

Verify the install worked:

```bash
python3 -c "import openclaw; print('openclaw import OK')"
```

Should print: `openclaw import OK`

If it errors with `ModuleNotFoundError`, run `pip install -e .` again and check for errors.

---

## Step 23 — Create config.yaml

```bash
cp config.yaml.example config.yaml
```

```bash
nano config.yaml
```

You need to set these values. Navigate through the file and update each section. The full file should look like this when done (overwrite the whole contents if easier):

```yaml
app:
  env: production
  log_level: INFO

llm:
  provider: openrouter
  chat_model: openai/gpt-4o-mini
  embedding_model: null

runtime:
  tick_seconds: 10
  data_dir: /var/lib/openclaw
  dry_run: false

connectors:
  cli:
    enabled: true
  telegram:
    enabled: false
  email:
    enabled: true
    provider: gmail

actions:
  require_confirm: false
  allowlist:
    - echo
    - memory_write
    - memory_read
    - send_email

health:
  enabled: true
  host: 0.0.0.0
  port: 8080

memory:
  enabled: false
  vector_store: local
  vector_store_path: /var/lib/openclaw/vector_store
```

Save: Ctrl+X → Y → Enter

---

## Step 24 — Run the Config Doctor Check

```bash
python3 scripts/doctor.py
```

Expected output:
```
OK config loaded
chat_model=openai/gpt-4o-mini
embedding_model=(none)
memory_enabled=False
vector_store=local
vector_store_path=/var/lib/openclaw/vector_store
```

If it errors:
- `placeholder` in output → you still have `YOUR_CHAT_MODEL` somewhere in config.yaml, fix it
- `memory enabled but no embed model` → set `memory.enabled: false` in config.yaml

---

## Step 25 — First Manual Test Run

Still as the `openclaw` user with the venv active:

```bash
python -m openclaw.main config.yaml
```

Watch the output. Healthy startup looks like:
```json
{"level":"INFO","event":"openclaw starting","version":"..."}
{"level":"INFO","event":"health server started","host":"0.0.0.0","port":8080}
{"level":"INFO","event":"openclaw running"}
```

**Open a second SSH session (new Terminal tab on your Mac) and test the health endpoint:**

```bash
curl http://openclaw.local:8080/health
```

Should return:
```json
{"status": "ok", "uptime_s": 5, ...}
```

If health returns OK, you are good to go. Stop the app:

Press **Ctrl+C** in the first SSH window.

Exit back to the `pi` user:

```bash
exit
```

Your prompt returns to `pi@openclaw`.

---

# PART 6: INSTALL THE systemd SERVICE

---

## Step 26 — Write the systemd Service File

```bash
sudo nano /etc/systemd/system/openclaw.service
```

Paste in the entire contents below exactly:

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

Save: Ctrl+X → Y → Enter

---

## Step 27 — Enable and Start the Service

```bash
sudo systemctl daemon-reload
```

```bash
sudo systemctl enable openclaw
```

```bash
sudo systemctl start openclaw
```

---

## Step 28 — Verify the Service is Running

```bash
sudo systemctl status openclaw
```

Look for `Active: active (running)` in green. Example:
```
● openclaw.service - OpenClaw Agent Runtime
     Loaded: loaded (/etc/systemd/system/openclaw.service; enabled)
     Active: active (running) since Mon 2026-03-09 10:00:00 CST; 5s ago
```

If it shows `failed` or `activating` stuck, check logs immediately:

```bash
sudo journalctl -u openclaw -n 30
```

---

## Step 29 — Confirm Health Endpoint from Your Mac

Back on your Mac (not SSH), open a new Terminal and run:

```zsh
curl http://openclaw.local:8080/health
```

Expected:
```json
{"status": "ok", "uptime_s": 12, "version": "0.1.0"}
```

If this works, **OpenClaw is fully deployed and running 24/7.**

---

# PART 7: RESILIENCE HARDENING

---

## Step 30 — Reduce SD Card Wear

```bash
sudo nano /etc/fstab
```

Find the line that starts with `PARTUUID=` and ends with `/ ext4`. Add `noatime` to the options. It will look something like:

```
PARTUUID=xxxxxxxx  /  ext4  defaults,noatime  0  1
```

The key addition is `,noatime` in the options column.

Save: Ctrl+X → Y → Enter

---

## Step 31 — Enable Hardware Watchdog

The watchdog auto-reboots the Pi if the OS freezes.

```bash
sudo nano /etc/systemd/system.conf
```

Find the lines (they may be commented out with `#`). Uncomment them and set:

```
RuntimeWatchdogSec=15
RebootWatchdogSec=2min
```

Save: Ctrl+X → Y → Enter

```bash
sudo systemctl daemon-reload
```

---

## Step 32 — Configure Log Rotation

```bash
sudo nano /etc/systemd/journald.conf
```

Find the `[Journal]` section and add or update:

```
SystemMaxUse=200M
MaxRetentionSec=4week
```

Save: Ctrl+X → Y → Enter

```bash
sudo systemctl restart systemd-journald
```

---

## Step 33 — Reboot and Confirm Auto-Start

This is the final test. Reboot the Pi:

```bash
sudo reboot
```

Your SSH session will disconnect. That is expected.

**Wait 90 seconds**, then from your Mac:

```zsh
ssh pi@openclaw.local
```

Once logged in:

```bash
sudo systemctl status openclaw
```

Should show `active (running)`. The service came back up on its own.

Then from your Mac directly:

```zsh
curl http://openclaw.local:8080/health
```

If this returns `{"status": "ok", ...}` — you are done. OpenClaw is running 24/7 on your Pi.

---

# PART 8: DAY-TO-DAY OPERATIONS

---

## Watch Live Logs

```bash
sudo journalctl -u openclaw -f
```

Press Ctrl+C to stop watching.

## Check Last 50 Log Lines

```bash
sudo journalctl -u openclaw -n 50
```

## Restart the Service

```bash
sudo systemctl restart openclaw
```

## Stop the Service

```bash
sudo systemctl stop openclaw
```

## Pull Latest Code and Restart

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

## Check Pi Temperature

```bash
vcgencmd measure_temp
```

Should be below 70°C at idle, below 80°C under load. Above 85°C means you need a heatsink or fan.

## Check Disk Space

```bash
df -h
```

Watch the `/` line. Stay below 80% usage.

## Check Database Size

```bash
du -sh /var/lib/openclaw/
```

---

# TROUBLESHOOTING REFERENCE

| Problem | What to run | What to look for |
|---|---|---|
| Service won't start | `sudo journalctl -u openclaw -n 30` | Error message on last few lines |
| Health endpoint refused | `sudo systemctl status openclaw` | Is it even running? |
| Config error at startup | `sudo -u openclaw bash -c "cd /opt/openclaw && source .venv/bin/activate && python scripts/doctor.py"` | Placeholder or missing key error |
| ModuleNotFoundError | `sudo -u openclaw /opt/openclaw/.venv/bin/pip install -e /opt/openclaw` | Re-run install |
| Can't SSH in | Connect keyboard+HDMI directly, run `sudo ufw allow ssh` | UFW may have blocked you |
| Pi not found on network | Check router device list, or `arp -a` from Mac | Find its IP and use that instead of `.local` |
| High CPU | `top` then press 1 to see per-core | Look for python process, check tick_seconds in config.yaml |
| Wrong API key error in logs | `sudo nano /etc/openclaw/openclaw.env` | Fix the key, then `sudo systemctl restart openclaw` |
