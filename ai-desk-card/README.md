# AI Desk Card

A glanceable e-ink 副屏 driven by an AI agent. The M5Paper sits next to
your monitor and shows weather, todos, today's calendar, message previews,
PR queue, current focus task, and the running AI session's status. Data
is pushed by an AI agent through a plugin Skill; the device just renders.

Designed for: **Wi-Fi LAN push (0.2 s/frame) · battery-powered standby
(months of life) · USB-C optional · zero cloud dependency**.

```
You ──ask──▶ AI agent ──push──▶ Skill ──HTTP──▶ daemon ──Wi-Fi / USB / BLE──▶ M5Paper
                                                                                │
                                                                                └──▶ 16 widgets across a 4-slot grid
```

## Why

Most "always-on dashboards" use a tablet or monitor — high power, screen
fatigue, another distracting glowing rectangle. E-ink is the opposite:
0 W idle, paper-grade contrast, persists the last frame after power off.
Wire it to an AI agent's plugin Skill and you get a sub-second glanceable
view of whatever's important right now: schedule, code review queue,
todos, weather, current focus task.

This project is **agent-agnostic** — it works with any AI CLI that supports
slash-command plugins (Claude, Codex, Gemini, Aider, ...).

## Hardware

- **M5Paper V1.1** (M5Stack's 4.7" 540×960 e-ink, ESP32, 8 MB PSRAM, 16 MB
  flash, 1150 mAh battery, USB-C, Wi-Fi 2.4 GHz, BLE 4.2). About ¥600 / $90.
- A USB-C cable (data — only needed once to flash firmware)
- Optional: USB-C charger for always-on mode (architecture A)

## Quick start

```bash
git clone https://github.com/op7418/ai-desk-card.git
cd ai-desk-card

# 1. flash CJK font to LittleFS (one-time)
pio run -e card -t uploadfs

# 2. flash firmware
pio run -e card -t upload

# 3. start the daemon (auto-picks Wi-Fi > USB > BLE)
/card-start

# 4. provision Wi-Fi over USB serial or BLE (one-time)
/card-wifi-setup "<YourSSID>" "<password>"

# 5. install the plugin into your AI CLI of choice, then ask it to push
#    widgets — or set up the cron-driven auto-refresh (see below).
```

After step 4, the device joins your LAN, mDNS-advertises as
`_ai-desk-card._tcp`, and the daemon discovers it. From then on widget
pushes land on the e-ink in about 0.2 seconds.

## Three power-mode architectures

The daemon picks transport automatically per push; the firmware picks Wi-Fi
strategy based on whether USB-C is supplying power.

| Mode | Device on | Latency | Battery life |
|---|---|---|---|
| **A** Always plugged in | USB-C power, Wi-Fi always on | 0.2 s/frame | n/a (powered) |
| **B** USB serial only | USB-C data cable (no Wi-Fi yet) | 1 s region / 32 s full | n/a (powered) |
| **C** Battery + BLE standby | Wi-Fi off until daemon BLE-wakes it | 5 s wake + 0.2 s push | months |

Architecture C: device sleeps with BLE in standby, daemon's `/card-refresh`
cron sends `cmd:wifi_wake_now` over BLE, device brings Wi-Fi up, daemon
pushes the frame via HTTP, device drops Wi-Fi after a 30-second linger.
~0.2 mAh per wake-and-push; 24 pushes/day → 6 months on a charge.

## 16 widget types across a 4-slot grid

```
┌───────────┬───────────┐   top-left  / top-right : 270×280   (narrow)
│ top-left  │ top-right │
├───────────┴───────────┤   middle               : 540×340   (wide)
│        middle         │
├───────────────────────┤   bottom               : 540×280   (wide)
│        bottom         │
└───────────────────────┘
        bar (60 px)         status/settings bar — always on
```

**Work staples**: `weather`, `calendar`, `next-meeting`, `messages`,
`inbox`, `system`, `git-status`, `pr-queue`, `now-playing`

**Note-taking & focus**: `scratch`, `todo`, `focus`, `deadlines`,
`break-reminder`

**AI monitoring**: `ai-status`, `ai-tasks`

Every widget is a JSON schema. AI agents fill the schema; the daemon
renders server-side (Python + Pillow) and ships pixels to the device.
See [plugin/skills/card-widget/schemas/](plugin/skills/card-widget/schemas/)
for the full schemas.

## Slash commands

After installing the plugin into your AI agent:

| Command | What it does |
|---|---|
| `/card-onboard` | First-time setup: detects daemon / USB / firmware / Wi-Fi state, walks you through whatever's missing |
| `/card-widget` | Push widgets to slots (AI uses this when you ask it to show something) |
| `/card-wifi-setup "<SSID>" "<pw>"` | Provision Wi-Fi credentials to the device's NVS over BLE/USB |
| `/card-sleep` | Show your digital business card + put device to deep sleep |
| `/card-refresh` | Cron-driven auto-refresh entry point |
| `/card-start`, `/card-stop`, `/card-status` | Daemon lifecycle |
| `/card-install` | Flash firmware (build first if no `.pio` cache) |

## Auto-refresh via cron

A typical setup runs an AI CLI headless on a schedule:

```cron
# Workday 8:00-22:00, every 30 min
*/30 8-21 * * 1-5  /path/to/ai-desk-card/plugin/skills/card-refresh/scripts/refresh_loop.sh
```

The script auto-picks any AI CLI in your PATH (`claude`, `codex`,
`gemini`, `aider`) or honors `$AI_CLI=<binary>`. Pull data from your
calendar, mail, git, GitHub, weather APIs etc., push to the daemon,
device updates in 0.2 s.

Budget: about $1-3/day on a small/cheap model. See
[REFRESH.md](plugin/skills/card-refresh/REFRESH.md) for the full
cost / cadence / no-AI-fallback story.

## Sleep card (digital business card mode)

E-ink keeps the last frame at 0 W after power off. `/card-sleep`
renders a name card from `assets/profile.yaml` (name, tagline, bio,
tags, QR code, footer) and tells the device to deep-sleep. Pick the
card up off your desk, hand it to someone, they see your contact info.

Edit `assets/profile.yaml` to customise.

## Architecture

The full design rationale is in [PLAN.md](PLAN.md) and
[PLAN_RENDERING_V06.md](PLAN_RENDERING_V06.md). Highlights:

- **Server-side rendering**: daemon (Python + Pillow) renders 540×960
  pixels and ships them to the device. Avoids ESP32 TTF/glyph hell.
- **Dirty-region diff**: only changed pixels go on the wire. Typical
  single-widget update is 5-30 KB instead of the 250 KB full frame.
- **Frame cache persistence**: `_last_frame.png` survives daemon
  restarts → USB↔Wi-Fi transport switch doesn't trigger a full re-push.
- **Three transports, one buffer**: Wi-Fi (HTTP), USB serial
  (chunked JSON), and BLE (chunked JSON, small commands work, frame
  data is a known-issue on macOS CoreBluetooth) all write to the same
  PSRAM frame buffer with a busy-flag lock.
- **mDNS discovery**: device broadcasts `_ai-desk-card._tcp` so the
  daemon finds it automatically — no fixed IP setup.

## Layout

```
ai-desk-card/
├── README.md
├── PLAN.md                 architecture decisions + scope rules
├── PLAN_RENDERING_V06.md   v0.6 server-side rendering migration notes
├── platformio.ini          env:card
├── partitions.csv          custom partition table (LittleFS for the CJK font)
├── assets/
│   ├── profile.yaml        sleep-card / business-card content
│   └── qr.png              optional QR override
├── data/
│   └── cjk.ttf             CJK font for the daemon's PIL renderer
├── src/                    firmware (ESP-IDF / Arduino)
│   ├── main.cpp            boot + transport poll loop + command dispatch
│   ├── frame_receiver.{h,cpp}  full + region pixel ingest, PSRAM buffer
│   ├── ble_bridge.{h,cpp}      BLE NUS + pair + passkey UI
│   ├── wifi_bridge.{h,cpp}     NVS creds + connect state machine
│   ├── http_server.{h,cpp}     POST /frame, /cmd; GET /status
│   └── widgets.{h,cpp}         widget cache (legacy v0.5 path)
├── daemon/                 Python bridge
│   ├── card_daemon.py      HTTP API + transport pick + push pipeline
│   ├── card_render.py      PIL widget renderers + 4bpp packer
│   ├── card_render_settings.py  on-device settings page
│   └── card_render_sleep.py     digital business card
└── plugin/                 commands, scripts, skills
    ├── plugin.json
    ├── commands/           slash-command stubs
    ├── scripts/            daemon lifecycle + flash + wifi-setup
    └── skills/
        ├── card-onboard/       first-time setup decision tree
        ├── card-widget/        AI-friendly widget catalog + schemas
        ├── card-wifi-setup/    privacy-aware Wi-Fi provisioning
        └── card-refresh/       cron + AI CLI entrypoint
```

## License + attribution

GPL-3.0 with attribution clause. See [LICENSE](LICENSE).

Vendored EPDGUI framework (parent project's `src/paper/epdgui/`): MIT,
© 2020 m5stack — see the parent repo's NOTICE.md.
