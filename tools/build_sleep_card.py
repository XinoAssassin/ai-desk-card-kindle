#!/usr/bin/env python3
"""Pre-render the V1.1 sleep / business card and save it as raw 4bpp
packed bytes for the firmware to load from LittleFS at boot.

After running, flash the data/ partition once:
    pio run -e card -t uploadfs

The firmware reads /sleep_card.bin from LittleFS when the idle timer
fires (no daemon needed) and blits it before entering deep sleep.

Card content comes from assets/profile.yaml — same source as the
daemon's `/card-sleep` flow. Edit profile.yaml + re-run this script
to refresh.
"""

from __future__ import annotations
import os
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO_ROOT, "daemon"))

import card_render_sleep as crs  # noqa: E402
from PIL import Image            # noqa: E402

OUT = os.path.join(REPO_ROOT, "data", "sleep_card.bin")
PROFILE = os.path.join(REPO_ROOT, "assets", "profile.yaml")
PANEL_W, PANEL_H = 540, 960   # V1.1 panel native portrait


def pack_4bpp(img: Image.Image) -> bytes:
    """Two pixels per byte, high nibble = first pixel, low nibble = second.
    Pixel value = grayscale 0-15 (0 black, 15 white) — matches M5EPD's
    WritePartGram4bpp expectations."""
    if img.mode != "L":
        img = img.convert("L")
    if img.size != (PANEL_W, PANEL_H):
        img = img.resize((PANEL_W, PANEL_H))
    px = img.tobytes()   # one byte per pixel, 0-255
    out = bytearray(len(px) // 2)
    for i in range(0, len(px), 2):
        a = px[i] >> 4
        b = px[i + 1] >> 4
        out[i // 2] = (a << 4) | b
    return bytes(out)


def main():
    profile = crs.load_profile(PROFILE)
    print(f"[render] profile: name={profile.get('name', '?')!r}")
    img = crs.render_sleep_frame(profile)
    if img.size != (PANEL_W, PANEL_H):
        print(f"[render] resize {img.size} → ({PANEL_W}, {PANEL_H})")
        img = img.resize((PANEL_W, PANEL_H))
    packed = pack_4bpp(img)
    expected = PANEL_W * PANEL_H // 2
    assert len(packed) == expected, f"size mismatch: {len(packed)} != {expected}"
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "wb") as f:
        f.write(packed)
    print(f"[ok] wrote {len(packed)} B → {OUT}")
    print(f"[next] pio run -e card -t uploadfs  # flashes data/ to LittleFS")


if __name__ == "__main__":
    main()
