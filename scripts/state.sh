#!/usr/bin/env bash
# ai-desk-card Skill — full-state probe.
#
# Wraps plugin/skills/card-onboard/scripts/probe.sh and adds three fields
# the Skill's router needs:
#   hardware.pio_installed   — is PlatformIO on PATH?
#   firmware.flashed         — derived: serial port present + ack heard
#   wifi.provisioned         — derived: mDNS peer found OR daemon reports IP
#   interests.configured     — ~/.ai-desk-card/interests.yaml exists
#
# Output is a single JSON blob written to stdout. The Skill reads it and
# routes to the right sub-flow.
#
# Usage:
#   bash scripts/state.sh           # full probe
#   bash scripts/state.sh --quick   # skip firmware-detect (faster, no port grab)

set -u

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PROBE="$REPO_ROOT/plugin/skills/card-onboard/scripts/probe.sh"
INTERESTS="${HOME}/.ai-desk-card/interests.yaml"

# 1. Run the inner probe
if [[ ! -x "$PROBE" && ! -f "$PROBE" ]]; then
  echo "{\"error\": \"probe.sh not found at $PROBE\"}"
  exit 1
fi
INNER_JSON="$(bash "$PROBE" "${1:-}" 2>/dev/null)"
if [[ -z "$INNER_JSON" ]]; then
  echo "{\"error\": \"probe.sh produced no output\"}"
  exit 1
fi

# 2. PlatformIO
if command -v pio >/dev/null 2>&1 || command -v platformio >/dev/null 2>&1; then
  PIO_INSTALLED=true
else
  PIO_INSTALLED=false
fi

# 3. Interests config
if [[ -f "$INTERESTS" ]]; then
  INTERESTS_CONFIGURED=true
else
  INTERESTS_CONFIGURED=false
fi

# 4. Merge: emit unified shape
export INNER_JSON PIO_INSTALLED INTERESTS_CONFIGURED INTERESTS
python3 - <<'PY'
import json, os, sys
inner = json.loads(os.environ["INNER_JSON"])
pio   = os.environ["PIO_INSTALLED"] == "true"
icfg  = os.environ["INTERESTS_CONFIGURED"] == "true"
ipath = os.environ["INTERESTS"]

ports = inner.get("serial_ports") or []
fw    = inner.get("firmware") or {}
mdns  = inner.get("mdns_peer")

# flashed: either daemon got an ack (our_firmware=true) OR mDNS peer is
# visible (means firmware is up and advertising) OR there's a banner from
# install_firmware --detect.
flashed = bool(fw.get("our")) or bool(mdns) or bool(fw.get("banner"))

state = {
  "hardware": {
    "pio_installed": pio,
    "m5paper_usb":   ports[0] if ports else None,
    "all_ports":     ports,
  },
  "firmware": {
    "flashed":  flashed,
    "ours":     bool(fw.get("our")),
    "note":     fw.get("note") or "",
    "banner":   fw.get("banner"),
  },
  "daemon":    inner.get("daemon"),
  "transport": inner.get("transport"),
  "wifi": {
    "provisioned": bool(mdns),
    "ip":          (mdns or {}).get("ip"),
    "port":        (mdns or {}).get("port"),
    "fw_via_mdns": ((mdns or {}).get("txt") or {}).get("fw"),
  },
  "interests": {
    "configured": icfg,
    "path":       ipath if icfg else None,
  },
}
print(json.dumps(state, indent=2, ensure_ascii=False))
PY
