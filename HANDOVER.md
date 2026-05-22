# AI Desk Card — Engineering Handover

This document is for someone who just inherited the project and needs
to ship the next iteration. It assumes you've already read
[README.md](README.md). What you'll find here: how each piece is wired,
where state lives, what's brittle, what's safe to touch, and the most
useful commands you'll run while debugging.

## Current state at handover (v0.8)

- **Firmware version**: `CARD_VERSION = "0.8.0"` defined in
  `platformio.ini` via `-DCARD_VERSION`.
- **Daemon**: Python 3.9+ acceptable for serial-only; **Python 3.10+
  required for the BLE path** (bleak's source uses `match` statements).
  `plugin/scripts/start.sh` auto-selects PlatformIO's bundled Python
  3.14 if present, otherwise falls back to system `python3`.
- **Transports**: Wi-Fi (HTTP) > USB serial (chunked JSON @ 115200
  baud) > BLE (NUS, chunked JSON for small commands; **frame data path
  is broken** — see Known Issues).
- **Three power-mode flows** all verified end-to-end on M5Paper V1.1:
  architecture A (USB-powered, Wi-Fi always on), B (USB-serial only),
  C (battery + BLE standby + Wi-Fi on demand).

## Architecture in one diagram

```
                 ┌──────────────────────────────────────────────┐
                 │  M5Paper V1.1  (ESP32, 8 MB PSRAM, 16 MB flash) │
                 │                                              │
                 │  ┌── ble_bridge ──┐  ┌── wifi_bridge ──┐   │
                 │  │ NUS GATT       │  │ NVS creds       │   │
                 │  │ pair + passkey │  │ connect SM      │   │
                 │  └────────────────┘  └─────────────────┘   │
                 │  ┌── http_server (port 9880)         ─────┐ │
                 │  │ POST /frame  POST /cmd  GET /status   │ │
                 │  └──────────────┬─────────────────────────┘ │
                 │  ┌──────────────▼ frame_receiver ─────────┐ │
                 │  │   259 200 B PSRAM buffer + display    │ │
                 │  │   full + region update support        │ │
                 │  └────────────────────────────────────────┘ │
                 │  ┌── M5GFX → e-ink panel (540×960 4bpp) ──┐ │
                 │  └────────────────────────────────────────┘ │
                 └──────────────────────────────────────────────┘
                                   ▲
                                   │ (one of)
                                   │
   ┌───────────────────────────────┴────────────────────────────────┐
   │  daemon/card_daemon.py  (port 9877 HTTP API)                   │
   │                                                                │
   │  WiFiTransport ──── HTTP POST raw 4bpp to device :9880         │
   │  SerialTransport ── chunked JSON over /dev/cu.usbserial-*      │
   │  BLETransport ──── chunked JSON over NUS RX char               │
   │       └─ Architecture C: temporarily WiFi-transport for push   │
   │                                                                │
   │  FrameDiff: PIL ImageChops.difference + getbbox + threshold    │
   │  Persistence: TMPDIR/ai_desk_card_{last_frame.png, widget_     │
   │                cache.json, daemon.log}                         │
   │  mDNS discovery: zeroconf _ai-desk-card._tcp at startup        │
   └────────────────────────────────────────────────────────────────┘
                                   ▲
                                   │ HTTP
                                   │
   ┌───────────────────────────────┴────────────────────────────────┐
   │  plugin/                                                       │
   │   commands/ (slash-command stubs)                              │
   │   scripts/  (start/stop/status/sleep/wifi-setup wrappers)      │
   │   skills/   (AI-facing playbooks: onboard / widget / wifi-     │
   │              setup / refresh)                                  │
   └────────────────────────────────────────────────────────────────┘
                                   ▲
                                   │
   ┌───────────────────────────────┴────────────────────────────────┐
   │  Any AI CLI (claude / codex / gemini / aider / ...)            │
   │  Plugin slot: /card-onboard /card-widget /card-wifi-setup ...  │
   └────────────────────────────────────────────────────────────────┘
```

## Per-module map

### Firmware (`src/`)

| File | Lines | Purpose |
|---|---|---|
| `main.cpp` | ~470 | Boot, dispatch loop, command router, status_report emitter, power-mode detection (charging > 4150 mV heuristic), BLE passkey overlay UI. |
| `frame_receiver.{h,cpp}` | ~280 | PSRAM-buffered frame ingest. Two paths: `frame_begin → frame_chunk[] → frame_end` (full) and `frame_region_begin → ... → frame_end` (partial). Shared `frameBuffer()` exposed so http_server can write into the same PSRAM region; `frameAcquire/ReleaseBuffer()` is a non-recursive busy flag. |
| `ble_bridge.{h,cpp}` | ~180 | NUS GATT server (NUS_SERVICE_UUID `6e400001-…`). Auth: ESP_LE_AUTH_REQ_SC_MITM_BOND. Characteristics use ENC_MITM perm (tightened from plain ENC during v0.7). Scan response carries explicit local name to override NVS-cached name from prior firmware. |
| `wifi_bridge.{h,cpp}` | ~170 | NVS-backed credentials (Preferences ns `"wifi"`). State machine: UNCONFIGURED / CONNECTING / CONNECTED / DISCONNECTED / SLEPT. 12 s connect timeout, 30 s retry gap. `wifiAutoConnect()` for architecture A boot; `wifiWakeNow()` / `wifiPowerDown()` for architecture C. |
| `http_server.{h,cpp}` | ~230 | Hand-rolled HTTP/1.1 parser on WiFiServer. Routes: `POST /frame` (raw 4bpp body + optional `?x=&y=&w=&h=`), `POST /cmd` (JSON dispatched via `dispatchCmd()`), `GET /status` (battery / firmware / mac / uptime / wifi). |
| `widgets.{h,cpp}` | ~250 | Legacy v0.5 on-device widget cache. Kept so older daemons still parse without crashing; rendering happens daemon-side now (v0.6+). |

Build: `pio run -e card`. Compiles to `~1.75 MB` flash (55 %) + 96 KB RAM
(29 %). LittleFS partition holds the CJK font, flashed once via
`pio run -e card -t uploadfs`.

### Daemon (`daemon/`)

| File | Purpose |
|---|---|
| `card_daemon.py` | Main daemon (~1300 lines). HTTP API on 127.0.0.1:9877, transport classes, frame push pipeline, FrameDiff, mDNS discovery, telemetry listener, settings page + sleep page dispatchers. |
| `card_render.py` | PIL-based widget renderer. `render_image(snapshot, status=None)` is the entry point; `to_4bpp_packed(img)` packs to M5EPD's 4-bit packed grayscale (2 px / byte, 0 = white, 15 = black). |
| `card_render_settings.py` | Full-screen settings page (DEVICE / CONNECTION / Wi-Fi / ACTIONS sections). Returns hot zones for touch routing (firmware-side touch dispatch is v0.9 work). |
| `card_render_sleep.py` | Digital business-card sleep frame. Reads `assets/profile.yaml`. |

**HTTP endpoints exposed by daemon** (port 9877):

| Method | Path | Purpose |
|---|---|---|
| POST | `/widget` | Push or replace one widget |
| DELETE | `/widget?slot=X` | Clear a slot (no `slot` arg = clear all) |
| GET | `/widget` | Return cache snapshot |
| POST | `/widgets/preview` | Render to PNG without device |
| GET | `/pair-status` | `{connected, transport}` |
| GET | `/version` | Daemon version string |
| POST | `/refresh` | Force re-push current cache |
| POST | `/restart` | Forward cmd:restart to device |
| POST | `/sleep` | Render sleep card → push → cmd:sleep_now |
| POST | `/settings` | Switch to full-screen settings view |
| POST | `/back` | Return to widget view |
| POST | `/firmware-probe` | Send cmd:owner + cmd:ping; report device fw / mac / battery |
| POST | `/status_report` | Manual telemetry injection (mainly for testing; firmware reports via BLE) |
| POST | `/provision-wifi` | Forward `{ssid, password}` to device as cmd:wifi_set |
| POST | `/touch` | Map `{x, y}` to a hot zone action (used by v0.9 touch dispatch) |
| POST | `/unpair` | Forward cmd:unpair (clear bond) |

### Plugin (`plugin/`)

Standard plugin-shape: `commands/` (slash stubs), `scripts/` (wrappers),
`skills/` (AI playbooks with frontmatter). All slash commands the user
runs go through one of `plugin/scripts/*.sh`.

| Skill | Role |
|---|---|
| `card-onboard` | First-time setup decision tree. `scripts/probe.sh` outputs structured JSON; SKILL.md walks the AI through branches G / A / B / C / D / E / F / Z. |
| `card-widget` | AI's reference for the 16 widget types + the 4-slot layout grid + push-frequency etiquette. |
| `card-wifi-setup` | Privacy-aware Wi-Fi provisioning. Handles the SSID-vs-MAC misunderstanding the user actually hit in early testing. |
| `card-refresh` | Cron entry point + per-data-source fetch strategy. AI-CLI-agnostic: `$AI_CLI` or auto-pick from `{claude, codex, gemini, aider}`. |

### Persistence

The daemon stashes state to `$TMPDIR` (macOS: `/var/folders/.../T/`,
Linux: `/tmp/`):

| File | What |
|---|---|
| `ai_desk_card_last_frame.png` | Last successfully rendered frame, used as the diff baseline. Persists across daemon restarts. Cleared on detected device reboot (uptime drop). |
| `ai_desk_card_widget_cache.json` | WIDGET_CACHE snapshot. Restored on daemon start so a USB→Wi-Fi transport switch doesn't dump current widgets. |
| `ai_desk_card_daemon.log` | Daemon stdout/stderr. `~10 KB/day` typical. |

User-level config:

- `~/.card-refresh.yaml` (optional) — used by `fallback_refresh.py`.
  Keys: `location`, `repo_path`.
- `~/.ai-desk-card-refresh.log` — cron refresh log.

Device-side persistence (NVS):

- Namespace `"wifi"`: keys `ssid`, `pass`.
- BLE bonding state (managed by Bluedroid).

## Build & deploy workflow

### First-time flash

```bash
cd ai-desk-card
pio run -e card -t uploadfs           # CJK font → LittleFS
pio run -e card -t upload             # firmware → main partition
```

### Iterative firmware change

```bash
pkill -f card_daemon.py               # release the serial port
pio run -e card -t upload             # ~30 s
bash plugin/scripts/start.sh          # daemon back up
```

### Iterative daemon change (no firmware reflash needed)

```bash
# card_render.py edits hot-reload via importlib.reload() — no daemon restart needed
# card_daemon.py / card_render_settings.py / card_render_sleep.py edits do require restart:
/card-stop && /card-start
```

### Switching transports

The daemon picks transport once at startup (Wi-Fi > USB > BLE). To
change, restart it:

```bash
/card-stop && /card-start    # auto re-pick
```

Force a specific transport:

```bash
python3 daemon/card_daemon.py --transport wifi    # require mDNS peer
python3 daemon/card_daemon.py --transport serial  # require /dev/cu.usbserial-*
python3 daemon/card_daemon.py --transport ble     # fall back to BLE only
```

## Wire protocol cheat sheet

### Serial / BLE — line-based JSON

Each line is one JSON object terminated by `\n`. Device buffers up to
8192 bytes per line.

**Daemon → device:**

```
{"cmd":"owner","name":"…"}
{"cmd":"ping"}
{"cmd":"unpair"}
{"cmd":"restart"}
{"cmd":"sleep_now","wake_after_sec":0}
{"cmd":"wifi_set","ssid":"…","password":"…"}
{"cmd":"wifi_wake_now"}
{"cmd":"wifi_power_down"}
{"cmd":"frame_begin","fid":N,"w":540,"h":960,"bpp":4,"chunks":K,"crc":X}
{"cmd":"frame_region_begin","fid":N,"x":X,"y":Y,"w":W,"h":H,"bpp":4,"chunks":K,"crc":X}
{"cmd":"frame_chunk","fid":N,"seq":S,"data":"<base64 of 2 KB raw>"}
{"cmd":"frame_end","fid":N}
{"time":[unix_ts,tz_offset_sec]}
```

**Device → daemon (notifications):**

```
{"ack":"owner","ok":true}
{"ack":"unpair","ok":true}
{"ack":"restart","ok":true}
{"ack":"wifi_set","ok":true,"ssid":"…"}
{"ack":"wifi_wake_now","ok":true}
{"ack":"wifi_power_down","ok":true}
{"ack":"paired","ok":true}                     # passkey cleared
{"ack":"status","fw":"…","proto":1,"mac":"…","uptime_s":N,
 "battery_pct":N,"battery_mv":N,"on_usb":bool,
 "wifi_connected":bool,"wifi_ssid":"…","wifi_ip":"…","wifi_rssi":N}
```

`ack:status` fires periodically (~60 s) and immediately after Wi-Fi
state change or in response to `cmd:ping`.

### Wi-Fi — HTTP on device port 9880

```
POST /frame                         body = 259200 raw bytes (4bpp full)
POST /frame?x=X&y=Y&w=W&h=H         body = W*H/2 raw bytes (4bpp region)
POST /cmd                           body = JSON command (same shape as serial)
GET  /status                        returns JSON status report
```

Frame body is plain bytes (no chunking, no base64). 250 KB full frame
on a typical home LAN: about 2 seconds; typical region: about 0.2 s.

## Known issues + workarounds

### 1. BLE frame data: silent drop after first chunk

Daemon's `write_gatt_char(..., response=True)` returns ACK successfully,
but ESP32's `RxCallbacks::onWrite()` never fires for the second/third
write in a burst. macOS CoreBluetooth doesn't expose tracing; the
proximate cause is uncertain (Bluedroid prepared-write handling vs
macOS retry semantics).

**Workaround**: the daemon's `push_frame_bytes()` short-circuits BLE
transport by sending `cmd:wifi_wake_now`, switching to a temporary
WiFiTransport for the frame, then power-cycling Wi-Fi back off. This
is architecture C and works reliably (~5 s cold wake + 0.2 s push).

**To revisit**: would need a BLE sniffer (Nordic nRF52 dongle + Wireshark)
to trace the air interface, or instrument the Bluedroid stack directly.

### 2. Power-mode detection is voltage-based

`isOnUSBPower()` returns `M5.getBatteryVoltage() > 4150` mV. Pure-battery
M5Paper reads up to ~4200 mV when fully charged, so freshly-unplugged
devices look like USB-powered for the first few minutes. This affects
architecture C selection at boot — wrong arch picked → daemon doesn't
trigger BLE wake.

**Workaround**: just wait until battery drops below 4150 mV (minutes),
or manually send `cmd:wifi_power_down` to force the radio off.

**To revisit**: M5Paper has a USB VBUS pin on the PCB (GPIO35 or
similar — check schematic). Direct GPIO read would be precise.

### 3. Daemon writes log to `$TMPDIR`, not `/tmp`

On macOS `$TMPDIR` is `/var/folders/<hash>/T/`, not `/tmp`. Skill docs
that hard-code `/tmp/ai_desk_card_daemon.log` were a bug; current files
use `${TMPDIR:-/tmp}/`. **Don't hard-code `/tmp` in new code.**

### 4. macOS Bluetooth UI doesn't list GATT-only peripherals

System Settings > Bluetooth shows HID / audio / Apple-accessory class
devices only; our NUS-based peripheral never appears in the "nearby
devices" list. Pair has to be initiated via `bleak.connect()` from the
daemon — macOS then prompts (or auto-pairs Just Works depending on IO
capabilities).

### 5. Dirty-region diff bbox can balloon

`ImageChops.difference + getbbox` returns the smallest axis-aligned
rectangle. Two small changes far apart → bbox spans both. The 50 %
threshold falls back to full frame in those cases. This is by design,
but worth knowing if you see surprising full-frame pushes for what
look like small UI changes (the bar's transport label change + a
widget update is a typical trigger).

### 6. v0.5 widget renderer still compiles

`src/widgets.{h,cpp}` is dead code in v0.6+ but stays compiled so older
daemons that send the legacy `widget_set` JSON don't crash the device.
Can be removed once you're confident no one's running an old daemon.

## Debugging recipes

### "I just pushed but nothing changed on screen"

```bash
LOG="${TMPDIR:-/tmp}/ai_desk_card_daemon.log"
tail -30 "$LOG" | grep -E '\[diff\]|\[frame\]|\[http\]|\[burst\]'
```

Expected line for a successful push:

```
[diff] region (X,Y W×H) = NB vs full 259200B (X%)
[frame] http push fid=N ... ok          # Wi-Fi
# or:
[frame] pushed fid=N NB region(...) in K chunks (S.SSs)
```

If you see `[diff] noop`, the new frame is pixel-identical to the
persisted last frame. To force a push, delete the persist file:

```bash
rm "${TMPDIR:-/tmp}/ai_desk_card_last_frame.png"
curl -X POST http://127.0.0.1:9877/refresh
```

### "Device shows boot splash forever"

The daemon isn't connected. Run:

```bash
bash plugin/skills/card-onboard/scripts/probe.sh
```

Read the JSON. `daemon.running == false` → `/card-start`. `transport.connected
== false && serial_ports == []` → check USB cable; or Wi-Fi isn't joined
yet (run `/card-wifi-setup`).

### "Wi-Fi connect keeps failing"

```bash
tail -30 "${TMPDIR:-/tmp}/ai_desk_card_daemon.log" | grep wifi
```

Status codes from `[wifi] connect timeout (status=N)`:

- `1` = SSID not found (typo, or 5 GHz-only)
- `4` = auth fail (wrong password)
- `6` = DHCP fail (router issue)

### "I want to see the rendered frame without flashing"

```bash
curl -sf -X POST http://127.0.0.1:9877/widgets/preview -o /tmp/preview.png
open /tmp/preview.png
```

### "I want to push a test widget"

```bash
curl -sf -X POST http://127.0.0.1:9877/widget \
  -H 'Content-Type: application/json' \
  -d '{"type":"scratch","slot":"middle",
       "data":{"text":"hello world","source":"manual","age":"now"}}'
```

### "I want to verify my firmware is running v0.8"

```bash
curl -sf -X POST http://127.0.0.1:9877/firmware-probe | python3 -m json.tool
# expect: ack.fw = "0.8.0"
```

## Open work / next iteration candidates

In rough priority:

1. **Touch dispatch firmware-side**. Daemon already returns hot zones
   per render (`card_render_settings.HOT_ZONES`); the firmware needs
   a touch poll → POST `/touch` to daemon → daemon maps to action.
2. **BLE frame-data path**. Currently broken; architecture C papers
   over it with Wi-Fi burst. With a BLE sniffer this could be made to
   work for pure-BLE deployments (no Wi-Fi credential setup).
3. **Power-mode detection accuracy**. GPIO-based VBUS detection
   instead of voltage heuristic.
4. **Captive portal Wi-Fi provisioning**. Currently provisioning
   requires existing serial / BLE transport; first-time-out-of-the-box
   user needs USB or BLE first. Captive portal would let them set
   Wi-Fi via phone directly. About 150 LOC firmware.
5. **OTA firmware updates over Wi-Fi**. ESP32 ArduinoOTA library;
   would skip the USB-to-flash flow for non-first-time users.
6. **More widget renderers**. The 16 we have are decent for desk
   work; people will want more (Pomodoro stats, RSS, IoT device states).
7. **Multiple-device support**. Daemon currently assumes one peer.
   Probably wants a `--device-name` flag and per-device cache files.
8. **Remove the legacy v0.5 widget cache** (`src/widgets.{h,cpp}`)
   once enough time has passed.

## Useful commands reference

```bash
# Daemon lifecycle
/card-start         # auto-pick transport, start daemon
/card-stop          # kill daemon, release port
/card-status        # human-readable transport + cache state

# Setup
/card-onboard               # AI walks you through first-time setup
/card-install               # build (if needed) + flash firmware
/card-wifi-setup "SSID" pw  # provision Wi-Fi credentials

# Day-to-day
/card-widget        # AI pushes a widget
/card-sleep         # name card → deep sleep
/card-refresh       # cron entrypoint (one-shot AI run)

# Manual HTTP poking
curl http://127.0.0.1:9877/widget                              # cache snapshot
curl http://127.0.0.1:9877/pair-status                         # transport state
curl -X POST http://127.0.0.1:9877/firmware-probe              # full status
curl -X POST http://127.0.0.1:9877/refresh                     # force re-push

# When things are weird
tail -30 "${TMPDIR:-/tmp}/ai_desk_card_daemon.log"
bash plugin/skills/card-onboard/scripts/probe.sh
```

## Style + conventions

- **Wire format**: JSON lines for serial / BLE (`\n`-terminated). HTTP
  for Wi-Fi.
- **Logging**: daemon `log()` writes to stderr → captured by `start.sh`
  into the rotating log file. Firmware uses `Serial.printf` which goes
  to USB and also to BLE TX char (notifications).
- **Persistence**: only at hard state boundaries. Don't litter `$TMPDIR`.
- **AI-facing skill prose**: tell the AI what it *should* do, not what
  the code does. Skill docs are read by AI agents, not by users.
- **Slash commands**: stay in `/card-*` namespace.
- **Versioning**: bump `CARD_VERSION` in `platformio.ini` + `plugin.json`
  on every release. Minor (0.8 → 0.9) for new features; patch
  (0.8.0 → 0.8.1) for bug fixes.
