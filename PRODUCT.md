# AI Desk Card — Product Document

## What it is

AI Desk Card is **a small e-ink panel that sits on your desk and shows
you what an AI agent thinks is important right now**. The agent decides
what to show; the device renders.

The hardware is M5Paper V1.1 — a 4.7-inch, 540 × 960 grayscale e-ink
display with built-in ESP32, Wi-Fi, BLE, and a 1150 mAh battery. About
the size of a Kindle Touch screen with no bezel-mounted keyboard.

The software is two halves:

- A **firmware** on the M5Paper that listens for pre-rendered pixels
  over Wi-Fi / USB / BLE and pushes them to the e-ink panel.
- A **daemon** on the user's computer that talks to AI agent plugins,
  renders 16 widget types server-side, and ships only the changed pixels.

A user installs the plugin into any compatible AI CLI (Claude Code,
Codex, Gemini, Aider, ...), sets up Wi-Fi once, and from then on can
say things like "show me my schedule" or "what's in my inbox" and
have the agent push a widget to the card in under a second.

## What problem this solves

People who live in their AI agent spend a lot of context on
"things-I-need-to-be-aware-of": calendar, todos, recent messages,
status of long-running tasks. Two failure modes:

- **Tab fatigue**: glance at the screen, lose your train of thought.
  Each context switch costs ~25 minutes of recovery in deep work.
- **Asking the agent over and over**: "what's on my schedule today?"
  burns tokens, slows down whatever you were actually working on, and
  the answer disappears the moment the agent moves on.

A glanceable side panel solves both: never costs your screen real
estate, the information persists at zero power, and once the agent
has pushed something it stays there until the next push (e-ink retains
the last frame indefinitely without power).

## Who this is for

Developers, designers, and writers who:

1. **Use an AI agent CLI in their workflow** (Claude Code, Codex,
   Gemini, Aider, etc.). The plugin format is the
   common ground.
2. **Want a calm-tech side display** — not another notification source,
   not a tablet, not a smartwatch. Something paper-like that doesn't
   demand attention.
3. **Are comfortable plugging a USB-C device in once to flash firmware**.
   Then it's plug-and-forget.

Not for: passive screen-fillers, people who want photo / animation
displays (e-ink is grayscale and slow), people uncomfortable wiring
their AI to a physical device.

## Key features

### 16 widget types across 4 slots

The 540 × 960 canvas is split into four slots: two narrow (270 × 280)
at the top, one wide middle (540 × 340), one wide bottom (540 × 280),
plus a 60 px settings bar at the very bottom.

- **Work staples**: weather, calendar, next-meeting, messages,
  inbox, system stats, git-status, pr-queue, now-playing
- **Note-taking & focus**: scratch (free-form sticky note), todo,
  focus (one active task + Pomodoro), deadlines (multi-day countdown),
  break-reminder
- **AI monitoring**: ai-status (current AI task + context bar),
  ai-tasks (running / waiting / blocked / done-today counters)

Each widget is a JSON schema; the agent fills the schema and pushes.
The daemon renders, diffs against the previous frame, and ships only
the changed region — typical single-widget update is 5-30 KB.

### Three power-mode architectures, one device

Same firmware runs in three power profiles based on whether USB-C is
supplying power:

| Mode | Setup | Latency | Battery life | When to use |
|---|---|---|---|---|
| **A** Always plugged in | USB-C power, Wi-Fi always on | 0.2 s/frame | n/a (powered) | Desk companion, primary use case |
| **B** USB-serial only | USB-C data, no Wi-Fi yet | 1 s region / 32 s full | n/a | First-time flash / debug / no Wi-Fi |
| **C** Battery + BLE standby | No USB, Wi-Fi on-demand | 5 s wake + 0.2 s push | months | Truly portable (rare for desk use) |

Architecture C is interesting: the device sleeps with only BLE
listening (low milliamp draw), the daemon wakes Wi-Fi via BLE
command when it needs to push, sends the frame as a single HTTP
POST, then tells the radio to sleep again. Each push costs about
0.2 mAh — a 24-pushes-per-day cadence gives months of life.

### Digital business card mode

`/card-sleep` renders a name card (name, tagline, bio, tags, QR code)
from `assets/profile.yaml` and tells the device to deep-sleep.
E-ink holds the image at 0 W indefinitely. Hand the device to someone
as a business card; they see your contact info even though the device
is off.

### AI-agnostic plugin

The plugin format ships slash commands and skills for any AI agent
that supports the plugin spec. The cron-driven auto-refresh script
auto-detects which AI CLI is installed (claude, codex, gemini, aider)
or you set `$AI_CLI` to pin a specific one. No vendor lock-in.

### Server-side rendering

All text rendering happens in the daemon using Pillow + a bundled CJK
TTF (3.5 MB). The firmware never decodes a glyph — it just receives
4-bit-per-pixel grayscale data and blits to the e-ink driver. This
side-steps every TTF / font-coverage / multi-size bug we hit trying
on-device rendering in v0.5.

Cost: a daemon process must be running while the device is in use.
For most users this just means a 50 MB Python process in the background.

### Dirty-region diff

Between consecutive frames, the daemon computes the bounding box of
changed pixels (`PIL.ImageChops.difference`). Typical change is a
single widget updating → bbox is ~200 × 100 px → ~10 KB on the wire
instead of the 250 KB full frame. Falls back to full frame when the
bbox covers > 50 % of the canvas.

### Auto-refresh via cron

A cron-driven refresh script runs a headless AI CLI on a schedule
(default: every 30 minutes during work hours). The AI pulls data from
configured sources — calendar, mail, git, GitHub, weather APIs etc. —
and pushes whichever widgets the user has on the card. Token budget:
about $1-3/day on a small/cheap model.

For users who don't want token cost, a no-AI `fallback_refresh.py`
ships weather + system stats + git-status using only local APIs.

## How a user interacts with it (typical day)

```
07:00  Cron fires. Headless AI pulls calendar / weather / inbox / PRs.
       Daemon diffs, sends 10 KB region update. Device shows today's
       agenda when user walks into office.

09:30  User: "show me the PR queue"
       AI pushes pr-queue widget to slot bottom. 0.2 s later it's on
       the card.

11:00  User starts a Pomodoro: "track my focus on the auth refactor for 25 min"
       AI pushes focus widget with countdown to middle. Updates the
       countdown every minute (small region, cheap).

12:00  User leaves for lunch. Card stays on; e-ink frozen.

13:30  User: "I'm back, what was I doing"
       AI re-pushes focus widget showing "completed: auth refactor".

22:00  Cron stops firing. Card holds last state until tomorrow morning.
```

Some users go further: hook the daemon to their iMessage db, Slack
API, oncall paging system, etc. The widget schemas accept arbitrary
data — the AI fills it however the user trains it to.

## How the user sets it up (first time)

1. **Buy an M5Paper V1.1** (about $90 from M5Stack / Amazon).
2. **Clone the repo, install PlatformIO**, flash the firmware:
   ```bash
   pio run -e card -t uploadfs   # CJK font
   pio run -e card -t upload     # firmware
   ```
3. **Install the plugin** into their AI CLI of choice. Plugin dir is
   `plugin/`; the AI CLI's plugin loader picks it up.
4. **Start the daemon**: `/card-start`
5. **Provision Wi-Fi**: `/card-wifi-setup "MyHomeNetwork" "password"`
6. **Ask the AI to push something**: "show me today's weather"

Total time: 5-10 minutes if PlatformIO is already installed,
30 minutes if not.

## Cost model

### Hardware (one-time)

- M5Paper V1.1: about ¥600 / $90
- USB-C cable: $5 (or use one you already own)
- Optional: USB-C charger for always-on use: $10

### Software

- Open source (GPL-3.0 with attribution). No license fees.

### Operating cost

- Daemon: free (runs on your computer)
- AI CLI token costs (only if you use the cron auto-refresh):
  - **Small/cheap model**: ~$0.10 per refresh × 28 refreshes/day on a
    30-min cadence ≈ **$2-3/day during work hours**
  - **Larger model**: ~$0.30-0.80 per refresh × same → **$8-22/day**
  - **No-AI fallback**: $0/day (loses calendar / mail / pr-queue;
    keeps weather + system + git)
- Optional: pin the cron cadence longer (2 h instead of 30 min) →
  6 refreshes/day → cuts cost 5×.

## Comparison to alternatives

| Approach | Pros | Cons |
|---|---|---|
| **Old tablet running a dashboard webpage** | Cheap, easy to set up | Power-hungry, distracting backlight, screen burn, needs Wi-Fi 24/7 |
| **Vendor smart displays (Skylight, Lametric, TRMNL...)** | Polished UX | Closed ecosystem, monthly subscription typical, limited customisation |
| **Sticky notes** | Zero cost, paper-tier focus | Manual, doesn't update, doesn't carry AI awareness |
| **AI Desk Card** | Open, agent-driven, calm-tech, hackable | DIY assembly + Wi-Fi setup (one-time), hardware ~$90, requires an AI CLI |

The honest positioning: this is a project for people who want a
side display **driven by their existing AI workflow**, not a polished
appliance. If you'd rather buy something off the shelf and not touch
config, TRMNL exists. If you'd rather drive a panel from your own
agent's plugin Skill, this is for you.

## Differentiation summary

1. **Driven by AI agent plugin Skills, not a closed app.** Switch
   agents anytime; switch data sources anytime; teach the AI to push
   anything you want by writing a new widget schema.
2. **Three-mode architecture covers desk-companion + truly-wireless
   without compromise.** Same firmware, same UX, same widgets.
3. **Sub-second refresh on LAN.** Most e-ink solutions are 5-30 s/frame;
   ours is 0.2 s by combining server-side rendering + dirty-region
   diff + raw HTTP push.
4. **Agent-agnostic.** Plugin works with any AI CLI that supports the
   plugin spec (Claude Code, Codex, Gemini, Aider, ...).

## Roadmap

### v0.9 (likely next)

- Touch dispatch firmware-side (settings page buttons fully clickable)
- Captive portal Wi-Fi provisioning (no need for USB / BLE first)
- More widget renderers (Pomodoro stats, RSS, IoT device state)
- Multi-device support (`--device-name` flag on daemon)

### v1.0 (production-ready)

- OTA firmware updates over Wi-Fi
- Standalone macOS app for daemon (LaunchAgent + menu bar UI)
- Public widget marketplace / community schemas
- Prebuilt firmware binaries (no PlatformIO needed for users)

### v1.x (research)

- BLE frame-data path repair (needs BLE sniffer hardware)
- Windows / Linux daemon parity testing
- Alternative hardware backends (Inkplate 10, Waveshare e-ink hat
  drivers)

## Constraints worth knowing

- **2.4 GHz Wi-Fi only.** ESP32 doesn't do 5 GHz. If your router is
  5 GHz-only the setup will fail; you need a 2.4 GHz SSID exposed.
- **macOS-tested, Linux untested.** The daemon's transport / mDNS
  / persistence layers all use OS-portable libraries (zeroconf,
  bleak, pyserial, Pillow) but only macOS has been put through
  real-device validation.
- **No native Windows support yet.** Daemon would likely work via
  WSL2 but not validated.
- **One peer per daemon.** Multi-device support is roadmap work.
- **CJK font is 3.5 MB.** Hardcoded in `data/cjk.ttf`. Other locales
  need their own font drop-in.

## License

GPL-3.0 with attribution clause. Code: yours to modify and redistribute
under GPL-3.0. The attribution clause requires preserving credit to
the original author (op7418) in derivative works.

The vendored EPDGUI framework in the parent buddy project (referenced
by some shared code) is MIT, © 2020 m5stack — see the parent repo's
NOTICE.md.

## Contact / contributions

Project lives at https://github.com/op7418/ai-desk-card. Issues and
pull requests welcome. Hardware photos / videos especially welcome —
helps anyone discovering the project see what they're getting into.
