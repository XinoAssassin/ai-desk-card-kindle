"""Color renderer for M5Paper Color (600×400, Spectra 6 palette).

Different layout from V1.1's card_render.py because the panel is half the
height and much wider per row. 2×2 grid feels more natural than V1.1's
2-1-1 layout. Returns PIL Image in RGB mode; the device's M5GFX quantizes
to Spectra 6 on push.

Color philosophy:
- Black ink for body text (most readable on e-ink)
- Red for urgent / negative states (low battery, overdue, late)
- Blue for accents (links, brand, secondary header)
- Yellow for highlights / warnings / "now"
- Green for OK / success
- White background
"""

from __future__ import annotations
from typing import Iterable
from PIL import Image, ImageDraw, ImageFont
import os

CANVAS_W = 600
CANVAS_H = 400

# 2×2 grid. Each slot is 295×190 with a 5 px gap. Bottom 20 px reserved
# for a status bar (battery / wifi / time) — the Color panel's slow
# refresh makes a per-frame status bar less useful than on V1.1, so it's
# slim by design.
GAP = 5
BAR_H = 20
SLOT_H = (CANVAS_H - BAR_H - GAP * 3) // 2
SLOT_W = (CANVAS_W - GAP * 3) // 2

SLOT_RECTS = {
    "top-left":  (GAP, GAP, SLOT_W, SLOT_H),
    "top-right": (GAP * 2 + SLOT_W, GAP, SLOT_W, SLOT_H),
    "bottom-left":  (GAP, GAP * 2 + SLOT_H, SLOT_W, SLOT_H),
    "bottom-right": (GAP * 2 + SLOT_W, GAP * 2 + SLOT_H, SLOT_W, SLOT_H),
    "full": (0, 0, CANVAS_W, CANVAS_H),
}

# Colors anchored to Spectra 6. RGB888 — M5GFX picks the closest panel
# pixel during pushSprite. Slightly over-saturated picks for cleaner
# quantization (the chip's color-mapper is conservative).
COL = {
    "ink":    (0, 0, 0),
    "paper":  (255, 255, 255),
    "red":    (220, 30, 30),
    "yellow": (235, 215, 30),
    "green":  (40, 165, 80),
    "blue":   (40, 90, 200),
    "muted":  (110, 110, 110),
}

# ----- font loading ----------------------------------------------------------

_FONT_PATHS = [
    "/System/Library/Fonts/PingFang.ttc",
    "/System/Library/Fonts/STHeiti Medium.ttc",
    "/System/Library/Fonts/Hiragino Sans GB.ttc",
    "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
]

def _try_font(size: int) -> ImageFont.ImageFont:
    for p in _FONT_PATHS:
        if os.path.exists(p):
            try:
                return ImageFont.truetype(p, size)
            except Exception:
                pass
    return ImageFont.load_default()

def font(size: int) -> ImageFont.ImageFont:
    return _try_font(size)

# ----- per-widget painters ---------------------------------------------------

def _slot_chrome(d: ImageDraw.ImageDraw, rect, title: str, accent=COL["ink"]):
    """Common chrome: thin border + title bar in accent color."""
    x, y, w, h = rect
    d.rectangle([x, y, x + w, y + h], outline=COL["ink"], width=1)
    d.rectangle([x, y, x + w, y + 28], fill=accent)
    label_color = COL["paper"] if accent != COL["paper"] else COL["ink"]
    d.text((x + 8, y + 4), title, fill=label_color, font=font(18))

def paint_weather(d, rect, data, stale=False):
    _slot_chrome(d, rect, "WEATHER", accent=COL["blue"])
    x, y, w, h = rect
    loc = data.get("location", "")
    cur = data.get("current") or {}
    temp = cur.get("temp_c")
    cond = cur.get("condition") or ""
    forecast = data.get("forecast") or []

    d.text((x + w - 6 - len(loc) * 12, y + 4), loc, fill=COL["paper"], font=font(16))

    if temp is not None:
        tx = f"{int(round(temp))}°"
        d.text((x + 12, y + 38), tx, fill=COL["ink"], font=font(48))
    d.text((x + 110, y + 60), cond, fill=COL["muted"], font=font(18))

    # Forecast strip at bottom
    fy = y + h - 50
    d.line([x + 10, fy, x + w - 10, fy], fill=COL["muted"], width=1)
    for i, f in enumerate(forecast[:2]):
        fx = x + 10 + i * (w // 2 - 10)
        day = f.get("day", "")
        hi = f.get("high", "")
        lo = f.get("low", "")
        cond = f.get("condition", "")
        d.text((fx, fy + 6), f"{day}", fill=COL["ink"], font=font(14))
        d.text((fx, fy + 24), f"{hi}° / {lo}°", fill=COL["ink"], font=font(13))
        d.text((fx + 90, fy + 6), cond, fill=COL["muted"], font=font(13))

def paint_focus(d, rect, data, stale=False):
    _slot_chrome(d, rect, "FOCUS", accent=COL["ink"])
    x, y, w, h = rect
    task = data.get("task", "")
    big = data.get("big_text", "")
    sub = data.get("subtitle", "")
    done = int(data.get("pomodoros_done") or 0)
    plan = int(data.get("pomodoros_planned") or 0)

    # Task line (wraps if needed — simple greedy)
    f_t = font(14)
    words = list(task)
    line, lines = "", []
    for ch in words:
        if d.textlength(line + ch, font=f_t) > w - 20:
            lines.append(line); line = ch
        else:
            line += ch
    if line: lines.append(line)
    for i, ln in enumerate(lines[:2]):
        d.text((x + 10, y + 34 + i * 18), ln, fill=COL["ink"], font=f_t)

    # Big countdown — red if overdue (string starts with +), else ink
    big_color = COL["red"] if big.startswith("+") else COL["ink"]
    bbox = d.textbbox((0, 0), big, font=font(40))
    bw = bbox[2] - bbox[0]
    d.text((x + (w - bw) // 2, y + 80), big, fill=big_color, font=font(40))

    # Subtitle small
    d.text((x + 10, y + h - 38), sub, fill=COL["muted"], font=font(12))

    # Pomodoro dots — green=done, gray=planned
    if plan > 0:
        dy = y + h - 14
        dot_total = min(plan, 6)
        dx = x + 10
        for i in range(dot_total):
            color = COL["green"] if i < done else COL["muted"]
            d.ellipse([dx, dy - 4, dx + 8, dy + 4], fill=color)
            dx += 13

def paint_next_meeting(d, rect, data, stale=False):
    _slot_chrome(d, rect, "NEXT", accent=COL["yellow"])
    x, y, w, h = rect
    title = data.get("title", "")
    start_in = data.get("start_in", "")
    start_at = data.get("start_at", "")
    attendees = data.get("attendees", "")
    location = data.get("location", "")

    # When (highlighted yellow box)
    cnt_color = COL["red"] if "now" in start_in.lower() else COL["ink"]
    d.text((x + 10, y + 34), start_in, fill=cnt_color, font=font(22))
    d.text((x + w - 75, y + 34), start_at, fill=COL["blue"], font=font(20))

    # Title
    f_t = font(18)
    line = title if d.textlength(title, font=f_t) < w - 20 else title[:14] + "..."
    d.text((x + 10, y + 68), line, fill=COL["ink"], font=f_t)

    # Attendees
    d.text((x + 10, y + h - 50), attendees, fill=COL["muted"], font=font(13))
    d.text((x + 10, y + h - 30), location, fill=COL["muted"], font=font(13))

def paint_todo(d, rect, data, stale=False):
    _slot_chrome(d, rect, "TODO", accent=COL["green"])
    x, y, w, h = rect
    items = data.get("items") or []
    title = data.get("title", "")
    if title:
        d.text((x + w - 60, y + 4), title, fill=COL["paper"], font=font(14))

    # Up to 3 items, color-coded by tag
    tag_colors = {
        "today":     COL["red"],
        "tomorrow":  COL["yellow"],
        "this-week": COL["blue"],
        "overdue":   COL["red"],
        "later":     COL["muted"],
        "":          COL["ink"],
    }
    for i, it in enumerate(items[:3]):
        ty = y + 38 + i * 36
        tag = it.get("tag", "") or ""
        bullet = tag_colors.get(tag, COL["ink"])
        # Bullet + text
        d.ellipse([x + 12, ty + 5, x + 20, ty + 13], fill=bullet)
        text = it.get("text", "")
        f_t = font(15)
        if d.textlength(text, font=f_t) > w - 40:
            # Truncate
            while text and d.textlength(text + "...", font=f_t) > w - 40:
                text = text[:-1]
            text += "..."
        d.text((x + 28, ty), text, fill=COL["ink"], font=f_t)
        if tag:
            d.text((x + 28, ty + 18), tag, fill=bullet, font=font(11))

PAINTERS = {
    "weather":      paint_weather,
    "focus":        paint_focus,
    "next-meeting": paint_next_meeting,
    "todo":         paint_todo,
}

def paint_empty(d, rect, label="—"):
    x, y, w, h = rect
    d.rectangle([x, y, x + w, y + h], outline=COL["muted"], width=1)
    d.text((x + w // 2 - 8, y + h // 2 - 10), label,
           fill=COL["muted"], font=font(20))

def paint_status_bar(d, status: dict):
    """Slim 20px bottom strip: battery + wifi + time."""
    y = CANVAS_H - BAR_H
    d.rectangle([0, y, CANVAS_W, CANVAS_H], fill=COL["ink"])
    bp = status.get("battery_pct")
    wifi = status.get("wifi", "")
    ts = status.get("time", "")
    pieces = []
    if bp is not None:
        col = COL["red"] if bp <= 20 else COL["paper"]
        pieces.append((f"{bp}%", col))
    if wifi: pieces.append((wifi, COL["paper"]))
    if ts: pieces.append((ts, COL["paper"]))
    x = 10
    for txt, col in pieces:
        d.text((x, y + 2), txt, fill=col, font=font(13))
        x += int(d.textlength(txt, font=font(13))) + 16

# ----- public API ------------------------------------------------------------

def render_image(widgets: Iterable[dict],
                 status: "dict | None" = None) -> Image.Image:
    """Build a 600×400 RGB image from a widget snapshot.

    `widgets` is a list of {slot, type, data} dicts; same shape as the
    V1.1 daemon's WIDGET_CACHE serialisation but slots are the 2×2 grid
    names defined above.
    """
    img = Image.new("RGB", (CANVAS_W, CANVAS_H), COL["paper"])
    d = ImageDraw.Draw(img)
    seen = set()
    for w in widgets or []:
        slot = w.get("slot")
        wtype = w.get("type")
        rect = SLOT_RECTS.get(slot)
        fn = PAINTERS.get(wtype)
        if rect and fn:
            seen.add(slot)
            try:
                fn(d, rect, w.get("data") or {})
            except Exception as e:
                d.text((rect[0] + 4, rect[1] + 30),
                       f"err {wtype}: {e!r}"[:36],
                       fill=COL["red"], font=font(10))
    for slot, rect in SLOT_RECTS.items():
        if slot == "full" or slot in seen: continue
        paint_empty(d, rect, slot.replace("-", " "))
    paint_status_bar(d, status or {})
    return img
