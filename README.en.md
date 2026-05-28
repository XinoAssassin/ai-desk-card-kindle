# Kindle Desk Card · Jailbroken Kindle as a Desk Sidecar

Turn an idle, jailbroken Kindle Paperwhite 3 into an ambient desk display
showing calendar, tasks, mail, and weather. The Mac renders a PNG; the
Kindle pulls it every two minutes over USB Ethernet.

> 🌏 **中文: [README.md](./README.md)**

```
┌──────── Mac ────────┐                  ┌──── Kindle (USB-Eth) ────┐
│ launchd refresh.py  │                  │ upstart                  │
│   ├─ weather        │   POST /widget   │  └─ poll.sh              │
│   ├─ exchange-cal   │ ───────────────► │       wget PNG          │
│   ├─ lark-tasks     │                  │       eips -f -g        │
│   └─ exchange-inbox │                  │                          │
│       │             │                  │                          │
│ launchd daemon.py   │   GET frame.png  │                          │
│   render → frame.png│ ◄─────────────── │                          │
│   render_sleep      │                  │                          │
│     → sleep.png     │                  │                          │
│  (when Mac locked)  │                  │                          │
└─────────────────────┘                  └──────────────────────────┘
```

## Requirements

- **Jailbroken Kindle Paperwhite 3** (5.14.x) with KUAL + USBNetwork installed
- **Mac** (any macOS, used as the always-on host; while the Mac sleeps,
  the Kindle keeps showing its last frame)
- **USB cable** — provides both power and network (no corporate Wi-Fi needed)
- **Python 3.10+** on the Mac

## Data sources

| Slot | Default adapter | Alternative | Notes |
|------|-----------------|-------------|-------|
| `weather`  | `weather`           | —                  | Open-Meteo, no key. Includes AQI / feels-like / precipitation / sunrise & sunset |
| `calendar` | `exchange_calendar` | `lark_calendar`    | EWS NTLM (on-prem Exchange) / `lark-cli calendar +agenda` |
| `tasks`    | `lark_tasks`        | —                  | `lark-cli task +get-my-tasks` |
| `inbox`    | `exchange_inbox`    | `gmail`            | 5 most recent EWS messages / Gmail API via OAuth |

Configure via `~/.config/kindle-desk-card/sources.json`. Defaults apply if
the file is missing:

```json
{
  "weather":  "weather",
  "calendar": "exchange_calendar",
  "tasks":    "lark_tasks",
  "inbox":    "exchange_inbox"
}
```

Set a slot to `null` to skip it — for example `"tasks": null` will render
an empty placeholder in the tasks area. Run
`python kindle-daemon/config.py` to print the effective configuration.

## Setup

### 1. Clone + venv

```bash
git clone https://github.com/XinoAssassin/ai-desk-card-kindle ~/Develop/ai-desk-card-kindle
cd ~/Develop/ai-desk-card-kindle/kindle-daemon
python3 -m venv .venv
.venv/bin/pip install pillow exchangelib
# Gmail users also need: google-auth-oauthlib google-api-python-client
```

### 2. Fonts

Download the three Noto Sans CJK SC weights into `kindle-daemon/fonts/`:

```bash
cd kindle-daemon/fonts
for w in Regular Medium Bold; do
  curl -sSL -o "NotoSansCJKsc-$w.otf" \
    "https://raw.githubusercontent.com/googlefonts/noto-cjk/main/Sans/OTF/SimplifiedChinese/NotoSansCJKsc-$w.otf"
done
```

### 3. Credentials

Drop secrets into `~/.config/kindle-desk-card/` (mode 0600):

- **Exchange** — `exchange.env`:
  ```
  EXCHANGE_EMAIL=you@example.com
  EXCHANGE_USERNAME=you@example.com
  EXCHANGE_PASSWORD=xxx
  EXCHANGE_SERVER=mail.example.com
  ```
- **Gmail** — `client_secret.json` (Google Cloud → Desktop OAuth client).
  The first run opens a browser; the resulting token is cached at
  `gmail_token.json`.
- **Lark** — run `lark-cli auth login` once.

### 4. USB Ethernet

Plug the Kindle into the Mac with a data cable. In System Settings →
Network you'll see "RNDIS/Ethernet Gadget":

- Mac side: static IP `192.168.15.201/24`
- Kindle side: `192.168.15.244` (the USBNetwork default)
- Verify `ssh root@192.168.15.244` works (password `mario`)

### 5. macOS launchd

Drop two plists into `~/Library/LaunchAgents/`, replacing `<you>` with
your macOS username:

`com.kindle-desk-card.daemon.plist`:
```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>com.kindle-desk-card.daemon</string>
  <key>ProgramArguments</key><array>
    <string>/Users/&lt;you&gt;/Develop/ai-desk-card-kindle/kindle-daemon/.venv/bin/python</string>
    <string>/Users/&lt;you&gt;/Develop/ai-desk-card-kindle/kindle-daemon/daemon.py</string>
  </array>
  <key>WorkingDirectory</key><string>/Users/&lt;you&gt;/Develop/ai-desk-card-kindle/kindle-daemon</string>
  <key>RunAtLoad</key><true/>
  <key>KeepAlive</key><true/>
  <key>ThrottleInterval</key><integer>10</integer>
  <key>StandardOutPath</key><string>/tmp/kindle-daemon.log</string>
  <key>StandardErrorPath</key><string>/tmp/kindle-daemon.log</string>
</dict></plist>
```

`com.kindle-desk-card.refresh.plist`:
```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>com.kindle-desk-card.refresh</string>
  <key>ProgramArguments</key><array>
    <string>/Users/&lt;you&gt;/Develop/ai-desk-card-kindle/kindle-daemon/.venv/bin/python</string>
    <string>/Users/&lt;you&gt;/Develop/ai-desk-card-kindle/kindle-daemon/refresh.py</string>
  </array>
  <key>WorkingDirectory</key><string>/Users/&lt;you&gt;/Develop/ai-desk-card-kindle/kindle-daemon</string>
  <key>StartInterval</key><integer>120</integer>
  <key>RunAtLoad</key><true/>
  <key>EnvironmentVariables</key><dict>
    <key>PATH</key><string>/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin</string>
  </dict>
  <key>StandardOutPath</key><string>/tmp/kindle-refresh.log</string>
  <key>StandardErrorPath</key><string>/tmp/kindle-refresh.log</string>
</dict></plist>
```

Load them:
```bash
launchctl load -w ~/Library/LaunchAgents/com.kindle-desk-card.daemon.plist
launchctl load -w ~/Library/LaunchAgents/com.kindle-desk-card.refresh.plist
```

### 6. Kindle side

```bash
# Push the KUAL extension
scp -r kindle/extensions/desk-card root@192.168.15.244:/mnt/us/extensions/

# Install the upstart job (auto-start on boot)
scp kindle/upstart/kindle-desk-card.conf root@192.168.15.244:/tmp/
ssh root@192.168.15.244 '
  mount -o remount,rw / &&
  cp /tmp/kindle-desk-card.conf /etc/upstart/ &&
  mount -o remount,ro /
'
```

After a Kindle reboot upstart starts the poll loop automatically. KUAL
gains Start / Stop / Status / Redraw menu entries.

## Lock-screen behavior

When the Mac is locked, the daemon detects it via `ioreg IOConsoleLocked`
and the next Kindle poll receives a weather-only frame (`render_sleep`).
Unlocking flips back to the full dashboard on the next poll. Switch
latency is one poll cycle (≤ 2 min) in either direction.

## Verify / debug

```bash
# Effective data-source configuration
.venv/bin/python kindle-daemon/config.py

# Force one full refresh
.venv/bin/python kindle-daemon/refresh.py

# Refresh a single slot
.venv/bin/python kindle-daemon/refresh.py --only weather

# Daemon health check
curl -s http://192.168.15.201:9878/health | jq

# Pull the current frame as a PNG
curl -s http://192.168.15.201:9878/kindle/frame.png > /tmp/preview.png && open /tmp/preview.png

# After editing render.py, kickstart launchd so it re-imports the module
launchctl kickstart -k gui/$UID/com.kindle-desk-card.daemon
```

## Caveats

- **Off the corporate network**: Exchange is internal; without a VPN the
  calendar / inbox adapters fail. Weather and tasks still work — each
  adapter fails independently.
- **OTA upgrades**: a Kindle system upgrade wipes
  `/etc/upstart/kindle-desk-card.conf`. Re-run setup step 6.
- **lipc preventScreenSaver**: don't use it — on KPW3 5.14.x it locks out
  the power button. Accept the default 10-15 min auto-lock; the next
  poll repaints over the lockscreen image.

## For AI agents

`skills/kindle-desk-card/SKILL.md` is an ops skill for Claude Code /
Codex / other agents. It documents what to run, where to look, and what
to edit for the common runtime tasks (status check, force refresh, swap
a data source, restart services, tail logs). Once installed, asking the
agent "refresh the card" or "check desk card status" routes through it.

## Credits

The rendering approach and widget contracts originate from
[op7418/ai-desk-card](https://github.com/op7418/ai-desk-card) (M5Paper
version). The Kindle port is an independent implementation; no code is
shared.
