---
name: kindle-desk-card
description: |
  Operate the user's Kindle Desk Card setup — a jailbroken Kindle Paperwhite 3
  acting as an ambient desk sidecar that pulls a PNG from a Mac daemon every
  ~2 minutes over USB Ethernet. Use this skill when the user wants to check
  status, force a refresh, view the current frame, switch a data source
  (weather / calendar / tasks / inbox), restart the services, tail logs, or
  diagnose why a slot has gone blank. Do not use it for initial install —
  point the user at README.md for that.
trigger_keywords:
  - kindle 卡片
  - 桌面卡片
  - 桌面副屏
  - desk card
  - desk-card
  - 刷新卡片
  - kindle 刷新
  - kindle daemon
  - kindle-daemon
  - 切换数据源
  - sources.json
allowed-tools:
  - Bash
  - Read
  - Edit
  - Write
---

# kindle-desk-card — operate the Kindle desk sidecar

You're helping the user manage an already-installed Kindle Desk Card. The
hardware and services are running; you're here for **runtime ops, config
changes, and debugging** — not first-time install (that's in README.md).

## Architecture in one breath

- **Mac launchd → `daemon.py`** binds `192.168.15.201:9878`, holds the
  widget cache, renders `/tmp/kindle-frame.png` (dashboard) and
  `/tmp/kindle-sleep.png` (weather-only, served when the Mac is locked).
- **Mac launchd → `refresh.py`** runs every 120s. Fetches data from each
  adapter configured in `sources.json` and POSTs to the daemon.
- **Kindle upstart → `poll.sh`** wgets the PNG every 120s and displays it
  with `eips -f -g`. KUAL menu provides Start / Stop / Status / Redraw.

## Known paths

| Thing | Location |
|-------|----------|
| Mac code (dev install) | `~/Develop/ai-desk-card-kindle/kindle-daemon/` |
| Mac venv Python | `…/kindle-daemon/.venv/bin/python` |
| Mac launchd plists | `~/Library/LaunchAgents/com.kindle-desk-card.{daemon,refresh}.plist` |
| Data-source config | `~/.config/kindle-desk-card/sources.json` |
| Credentials | `~/.config/kindle-desk-card/{exchange.env,client_secret.json,gmail_token.json}` |
| Frame cache | `/tmp/kindle-frame.png`, `/tmp/kindle-sleep.png` |
| Mac logs | `/tmp/kindle-daemon.log`, `/tmp/kindle-refresh.log` |
| Kindle host | `root@192.168.15.244` (password `mario`, key auth set up) |
| Kindle log | `/tmp/poll.log` on the device |

The install root may differ — verify by reading the daemon plist:
```bash
plutil -extract ProgramArguments xml1 -o - ~/Library/LaunchAgents/com.kindle-desk-card.daemon.plist | grep -o '/Users/[^<]*'
```

## What you can do

### 1. Status check ("how's my card doing?")

Run all four in parallel; aggregate into one short report.

```bash
# Is the daemon serving?
curl -s --max-time 3 http://192.168.15.201:9878/health | jq

# When did refresh last succeed?
tail -8 /tmp/kindle-refresh.log

# Is the Kindle reachable over USB?
ping -c 1 -W 1 192.168.15.244 >/dev/null && echo "kindle: up" || echo "kindle: unreachable"

# Are the launchd jobs loaded?
launchctl print gui/$UID/com.kindle-desk-card.daemon  | grep -E 'state|last exit'
launchctl print gui/$UID/com.kindle-desk-card.refresh | grep -E 'state|last exit'
```

Report shape (terse, one line per fact):
- `daemon: ok (slots: weather,calendar,tasks,inbox; locked: false)`
- `refresh: 4/4 ok at HH:MM:SS`
- `kindle USB: up`
- Surface failures bluntly; don't sugarcoat.

### 2. Force a refresh ("refresh now" / "拉一下天气")

```bash
# All slots
~/Develop/ai-desk-card-kindle/kindle-daemon/.venv/bin/python \
  ~/Develop/ai-desk-card-kindle/kindle-daemon/refresh.py

# Just one slot
.venv/bin/python refresh.py --only weather  # or calendar / tasks / inbox
```

After it returns, **always** verify the daemon got the update:
```bash
curl -s http://192.168.15.201:9878/health | jq '.slots'
```

### 3. Show the current frame ("show me what's on screen")

```bash
curl -s http://192.168.15.201:9878/kindle/frame.png > /tmp/preview.png
open /tmp/preview.png  # macOS Preview
# Or, if running headless, Read /tmp/preview.png so the user sees it inline.
```

### 4. Switch a data source

Available adapters per slot are documented in
`kindle-daemon/sources.example.json`. To change one:

1. Read the current config:
   ```bash
   cat ~/.config/kindle-desk-card/sources.json 2>/dev/null || echo "(using defaults)"
   ```
2. Use Edit / Write to update the JSON. Always preserve unchanged slots
   — don't blow away the user's other choices.
3. Verify it parses:
   ```bash
   .venv/bin/python kindle-daemon/config.py
   ```
4. Force a refresh so the change takes effect immediately rather than at
   the next 2-min tick.

Setting a slot to `null` (or omitting it) makes the dashboard render an
empty placeholder for that area.

### 5. Restart the services

After editing **render.py / daemon.py / mac_lock.py**, the daemon caches
the module in memory — you **must** kickstart:

```bash
launchctl kickstart -k gui/$UID/com.kindle-desk-card.daemon
```

After editing **refresh.py or adapters** the next 120s tick picks it up
automatically; kickstart only if the user wants it now:

```bash
launchctl kickstart -k gui/$UID/com.kindle-desk-card.refresh
```

After editing **poll.sh / KUAL extension**, SCP to the Kindle and ask
upstart to restart the job:

```bash
scp kindle/poll.sh root@192.168.15.244:/mnt/us/extensions/desk-card/poll.sh
ssh root@192.168.15.244 '/sbin/stop kindle-desk-card; /sbin/start kindle-desk-card'
```

### 6. Tail logs while reproducing an issue

```bash
tail -F /tmp/kindle-refresh.log         # adapter failures
tail -F /tmp/kindle-daemon.log          # bind / render errors
ssh root@192.168.15.244 tail -F /tmp/poll.log   # wget + eips errors
```

## Common symptoms → first check

| Symptom | First check |
|---------|-------------|
| Frame frozen on Kindle | `launchctl print gui/$UID/com.kindle-desk-card.daemon` — supervisor exit loop? `tail /tmp/kindle-daemon.log` |
| `[exchange-*] fetch failed` in refresh log | Off-VPN → expected. On-VPN → `cat ~/.config/kindle-desk-card/exchange.env` exists + 0600? |
| `[lark-tasks] command not found: lark-cli` | refresh plist's `EnvironmentVariables.PATH` lost `/opt/homebrew/bin` |
| Kindle reachable but no PNG | `curl -s -o /dev/null -w '%{http_code}\n' http://192.168.15.201:9878/kindle/frame.png` — if 200 from Mac side, run `ssh kindle 'cat /tmp/poll.log | tail'` |
| Mac says daemon dead, `lsof -i :9878` shows nothing | USB cable unplugged or interface IP not 192.168.15.201 — `ifconfig | grep 192.168.15` |
| Sleep frame stuck even after unlock | `ioreg -n Root -d1 -a | grep -A1 IOConsoleLocked` — should be `<false/>`. If still `<true/>` while user is logged in, that's a macOS bug; `launchctl kickstart -k …daemon` clears the cache. |
| Edits to render.py have no effect | Forgot to kickstart the daemon — long-running process caches the module. |

## Guardrails

- **Never destructively edit `~/.config/kindle-desk-card/*`** without
  showing the user the diff first. Those files hold secrets.
- **Don't push to GitHub.** This is a personal repo and the user
  controls the publish cadence.
- **Don't toggle `lipc-set-prop preventScreenSaver`** in `poll.sh` —
  it disables the Kindle's power button on KPW3 5.14.x. The current
  comment in `poll.sh` documents this.
- **Don't blindly `pkill -f poll`** from the Kindle's own SSH session —
  pkill matches its own argv and may kill the SSH shell. Use the KUAL
  `bin/stop.sh` or upstart's `/sbin/stop kindle-desk-card`.
- **Read `sources.example.json` before editing `sources.json`** so you
  pick a real adapter name, not a guess.

## When to bail out

Send the user back to `README.md` and stop guessing if:
- They're describing first-time install (fonts, plists, USB IP setup)
- The hardware isn't recognized (no `RNDIS/Ethernet Gadget` in System
  Settings → Network)
- They report KUAL not appearing — that's outside this skill (jailbreak +
  KUAL install belongs to the Kindle jailbreak community docs)
