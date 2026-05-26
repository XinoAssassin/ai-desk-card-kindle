"""Render a 1072×1448 grayscale PNG for the Kindle Paperwhite 3 from the
widget cache.

Layout (portrait, fixed 4 regions):
  weather   y=  0  h= 220   top strip: city + temp + condition + hi/lo
  calendar  y=220  h= 760   main: today's agenda list
  inbox     y=980  h= 380   lark unread mail + sender breakdown
  footer    y=1360 h=  88   last-refresh timestamp

The render is forgiving: missing widget data renders an empty region with a
"no data" hint. Bad fields are clipped, not raised. The Kindle is ambient,
not transactional — never crash a render over malformed input.
"""
from __future__ import annotations

import datetime as dt
import os
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont

CANVAS_W, CANVAS_H = 1072, 1448
WHITE = 255
BLACK = 0
GRAY = 160       # divider lines / labels
DIM = 80         # secondary text

# Kindle visible-area calibration (KPW3 5.14.1):
#   y < 48     hidden by system status bar
#   Content runs to the canvas bottom y=1448 with a tight footer.
TOP_RESERVE = 48
BOTTOM_SAFETY_END = 1448

LAYOUT = {
    "weather":  (0,    TOP_RESERVE,           1072, 200),
    "calendar": (0,    TOP_RESERVE +  200,     536, 848),
    "tasks":    (536,  TOP_RESERVE +  200,     536, 848),
    "inbox":    (0,    TOP_RESERVE + 1048,    1072, 300),
    "footer":   (0,    TOP_RESERVE + 1348,    1072,  52),
}
PAD = 24

FONT_DIR = Path(__file__).parent / "fonts"
FONT_FILES = {
    "normal": FONT_DIR / "NotoSansCJKsc-Regular.otf",
    "medium": FONT_DIR / "NotoSansCJKsc-Medium.otf",
    "bold":   FONT_DIR / "NotoSansCJKsc-Bold.otf",
}

_font_cache: dict[tuple[str, int], ImageFont.FreeTypeFont] = {}


def font(size: int, weight: str = "normal") -> ImageFont.FreeTypeFont:
    """Cached font loader. weight ∈ {'normal', 'medium', 'bold'}."""
    key = (weight, size)
    if key not in _font_cache:
        path = FONT_FILES.get(weight, FONT_FILES["normal"])
        _font_cache[key] = ImageFont.truetype(str(path), size)
    return _font_cache[key]


def _text_w(d: ImageDraw.ImageDraw, s: str, f: ImageFont.FreeTypeFont) -> int:
    return int(d.textlength(s, font=f))


def _truncate(d: ImageDraw.ImageDraw, s: str, f: ImageFont.FreeTypeFont, max_w: int) -> str:
    if _text_w(d, s, f) <= max_w:
        return s
    ellipsis = "…"
    while s and _text_w(d, s + ellipsis, f) > max_w:
        s = s[:-1]
    return s + ellipsis


def _empty(d: ImageDraw.ImageDraw, rect: tuple[int, int, int, int], label: str) -> None:
    x, y, w, h = rect
    f = font(32, "normal")
    msg = f"{label} · 暂无数据" if label else "暂无数据"
    tw = _text_w(d, msg, f)
    d.text((x + (w - tw) // 2, y + h // 2 - 18), msg, fill=GRAY, font=f)


# ---------------------------------------------------------------- weather ---


def paint_weather(d: ImageDraw.ImageDraw, rect: tuple[int, int, int, int], data: dict[str, Any] | None) -> None:
    x, y, w, h = rect
    if not data:
        _empty(d, rect, "天气")
        return

    city = str(data.get("city", ""))[:12]
    temp = data.get("temp")
    cond = str(data.get("condition", ""))[:8]
    hi = data.get("high")
    lo = data.get("low")

    feels = data.get("feels_like")
    humidity = data.get("humidity")
    wind = data.get("wind")
    aqi = data.get("aqi")
    aqi_label = data.get("aqi_label") or ""
    sunrise = data.get("sunrise") or ""
    sunset = data.get("sunset") or ""
    precip = data.get("precip_prob")

    # ROW 1 — baseline-aligned on the left: city + temp + hi/lo
    city_font = font(42, "bold")
    temp_font = font(80, "bold")
    hilo_font = font(22, "normal")
    baseline_y = y + 82
    cursor = x + PAD

    d.text((cursor, baseline_y), city, fill=BLACK, font=city_font, anchor="ls")
    cursor += _text_w(d, city, city_font) + 20

    temp_str = f"{int(temp)}°" if isinstance(temp, (int, float)) else "—"
    d.text((cursor, baseline_y), temp_str, fill=BLACK, font=temp_font, anchor="ls")
    cursor += _text_w(d, temp_str, temp_font) + 22

    if isinstance(hi, (int, float)) and isinstance(lo, (int, float)):
        hilo = f"H {int(hi)}°  L {int(lo)}°"
        d.text((cursor, baseline_y), hilo, fill=DIM, font=hilo_font, anchor="ls")

    sub_font_lg = font(24, "normal")
    sub_font_sm = font(22, "normal")
    sep = "  ·  "

    # ROW 2 — condition + feels + precipitation (left) | AQI (right)
    row2_y = y + 108
    row2_left: list[str] = []
    if cond:
        row2_left.append(cond)
    if isinstance(feels, (int, float)):
        row2_left.append(f"体感 {int(feels)}°")
    if isinstance(precip, (int, float)):
        row2_left.append(f"降雨 {int(precip)}%")
    if row2_left:
        d.text((x + PAD, row2_y), sep.join(row2_left), fill=DIM, font=sub_font_lg)
    if aqi is not None:
        aqi_text = f"AQI {int(aqi)} {aqi_label}".rstrip()
        aqi_w = _text_w(d, aqi_text, sub_font_lg)
        d.text((x + w - PAD - aqi_w, row2_y), aqi_text, fill=DIM, font=sub_font_lg)

    # ROW 3 — humidity + wind (left) | sunrise / sunset (right)
    row3_y = y + 148
    row3_left: list[str] = []
    if isinstance(humidity, (int, float)):
        row3_left.append(f"湿度 {int(humidity)}%")
    if isinstance(wind, (int, float)):
        row3_left.append(f"风 {int(wind)}级")
    if row3_left:
        d.text((x + PAD, row3_y), sep.join(row3_left), fill=DIM, font=sub_font_sm)
    if sunrise or sunset:
        sun_parts = []
        if sunrise:
            sun_parts.append(f"日出 {sunrise}")
        if sunset:
            sun_parts.append(f"日落 {sunset}")
        sun_text = sep.join(sun_parts)
        sun_w = _text_w(d, sun_text, sub_font_sm)
        d.text((x + w - PAD - sun_w, row3_y), sun_text, fill=DIM, font=sub_font_sm)


# --------------------------------------------------------------- calendar ---


def paint_calendar(d: ImageDraw.ImageDraw, rect: tuple[int, int, int, int], data: dict[str, Any] | None) -> None:
    x, y, w, h = rect
    d.text((x + PAD, y + 14), "近期日程", fill=BLACK, font=font(32, "bold"))

    # "now" indicator on the right
    now_iso = (data or {}).get("now_iso")
    if now_iso:
        try:
            hhmm = dt.datetime.fromisoformat(now_iso.replace("Z", "+00:00")).strftime("%H:%M")
        except (ValueError, TypeError):
            hhmm = dt.datetime.now().strftime("%H:%M")
    else:
        hhmm = dt.datetime.now().strftime("%H:%M")
    now_font = font(24, "normal")
    now_text = hhmm
    d.text((x + w - PAD - _text_w(d, now_text, now_font), y + 24), now_text, fill=DIM, font=now_font)

    events = (data or {}).get("events") or []
    if not events:
        _empty(d, (x, y + 60, w, h - 60), "")
        return

    events = events[:9]
    rows_top = y + 64
    row_h = (h - 74) // max(len(events), 1)
    row_h = min(row_h, 88)

    time_font_b = font(28, "bold")
    end_font = font(20, "normal")
    title_font_r = font(28, "medium")
    time_col_w = 104   # "09:30" at 28pt fits in ~100px
    glyph_w = 26       # left column for RSVP indicator

    for i, ev in enumerate(events):
        row_y = rows_top + i * row_h
        start = str(ev.get("start", ""))[:5]
        end = str(ev.get("end", ""))[:5]
        title = str(ev.get("title", ""))
        rsvp = str(ev.get("rsvp") or "needs_action")

        # RSVP status glyph at the far left
        cx_pt = x + PAD + 9
        cy_pt = row_y + 26
        r = 8
        if rsvp == "accept":
            d.ellipse([(cx_pt - r, cy_pt - r), (cx_pt + r, cy_pt + r)], fill=BLACK)
        elif rsvp == "decline":
            d.line([(cx_pt - r, cy_pt - r), (cx_pt + r, cy_pt + r)], fill=BLACK, width=2)
            d.line([(cx_pt - r, cy_pt + r), (cx_pt + r, cy_pt - r)], fill=BLACK, width=2)
        else:
            # tentative / needs_action — hollow circle
            d.ellipse([(cx_pt - r, cy_pt - r), (cx_pt + r, cy_pt + r)], outline=BLACK, width=2)

        time_x = x + PAD + glyph_w
        d.text((time_x, row_y + 6), start, fill=BLACK, font=time_font_b)
        date_label = str(ev.get("date_label") or "")
        if date_label:
            # Show "明天" / "5/28 周四" instead of end time — date is more useful
            # than end-time when the event isn't today
            d.text((time_x, row_y + 42), date_label, fill=BLACK, font=end_font)
        elif end:
            d.text((time_x, row_y + 42), f"→ {end}", fill=GRAY, font=end_font)

        title_x = time_x + time_col_w
        title_max_w = (x + w - PAD) - title_x
        title_color = GRAY if rsvp == "decline" else BLACK
        title = _truncate(d, title, title_font_r, title_max_w)
        d.text((title_x, row_y + 14), title, fill=title_color, font=title_font_r)
        if rsvp == "decline":
            tw = _text_w(d, title, title_font_r)
            sline_y = row_y + 14 + 18
            d.line([(title_x, sline_y), (title_x + tw, sline_y)], fill=GRAY, width=2)

        if i < len(events) - 1:
            line_y = row_y + row_h - 2
            d.line([(x + PAD, line_y), (x + w - PAD, line_y)], fill=220, width=1)


# ------------------------------------------------------------------ tasks ---


def paint_tasks(d: ImageDraw.ImageDraw, rect: tuple[int, int, int, int], data: dict[str, Any] | None) -> None:
    x, y, w, h = rect
    d.text((x + PAD, y + 14), "待办任务", fill=BLACK, font=font(32, "bold"))

    tasks = (data or {}).get("tasks") or []
    total = (data or {}).get("total", len(tasks))
    if total:
        suffix = f"{len(tasks)}/{total}" if total != len(tasks) else str(total)
        sf = font(24, "normal")
        d.text((x + w - PAD - _text_w(d, suffix, sf), y + 24), suffix, fill=DIM, font=sf)

    if not tasks:
        _empty(d, (x, y + 60, w, h - 60), "")
        return

    tasks = tasks[:9]
    rows_top = y + 64
    row_h = (h - 74) // max(len(tasks), 1)
    row_h = min(row_h, 88)

    title_font_r = font(28, "medium")
    title_font_b = font(28, "bold")
    due_font = font(22, "normal")
    box_size = 26

    for i, t in enumerate(tasks):
        row_y = rows_top + i * row_h
        title = str(t.get("title", ""))
        due = str(t.get("due", "")) if t.get("due") is not None else ""
        urgent = bool(t.get("urgent"))

        # checkbox glyph
        bx0 = x + PAD
        by0 = row_y + 16
        d.rectangle(
            [(bx0, by0), (bx0 + box_size, by0 + box_size)],
            outline=BLACK,
            width=2,
        )

        # title (bold if urgent)
        title_x = bx0 + box_size + 16
        title_font = title_font_b if urgent else title_font_r
        # Reserve space for due chip on the right if present
        right_reserve = 0
        if due:
            right_reserve = _text_w(d, due, due_font) + 16
        title_max_w = (x + w - PAD) - title_x - right_reserve
        title = _truncate(d, title, title_font, title_max_w)
        d.text((title_x, row_y + 14), title, fill=BLACK, font=title_font)

        if due:
            dw = _text_w(d, due, due_font)
            d.text(
                (x + w - PAD - dw, row_y + 20),
                due,
                fill=BLACK if urgent else DIM,
                font=due_font,
            )

        if i < len(tasks) - 1:
            line_y = row_y + row_h - 2
            d.line([(x + PAD, line_y), (x + w - PAD, line_y)], fill=220, width=1)


# ------------------------------------------------------------------ inbox ---


def paint_inbox(d: ImageDraw.ImageDraw, rect: tuple[int, int, int, int], data: dict[str, Any] | None) -> None:
    x, y, w, h = rect
    d.text((x + PAD, y + 12), "最新邮件", fill=BLACK, font=font(32, "bold"))

    total = (data or {}).get("total", 0)
    emails = (data or {}).get("emails") or []

    # Unread count hint on the right of the header
    unread_n = int(total) if isinstance(total, (int, float)) else None
    if unread_n is not None and unread_n > 0:
        hint = f"{unread_n} 封未读"
        hint_fill = BLACK
    else:
        hint = "全部已读"
        hint_fill = DIM
    hint_font = font(22, "normal")
    d.text(
        (x + w - PAD - _text_w(d, hint, hint_font), y + 22),
        hint,
        fill=hint_fill,
        font=hint_font,
    )

    if not emails:
        _empty(d, (x, y + 56, w, h - 56), "")
        return

    rows_top = y + 64
    rows = emails[:5]
    row_h = (h - 72) // max(len(rows), 1)
    row_h = min(row_h, 56)

    sender_col_w = 148
    sender_font = font(20, "medium")
    subject_font_b = font(24, "bold")    # unread
    subject_font_r = font(24, "medium")  # read
    time_font = font(18, "normal")
    dot_r = 5
    bullet_col_w = 22

    for i, em in enumerate(rows):
        row_y = rows_top + i * row_h
        sender = str(em.get("from", ""))
        subject = str(em.get("subject", "")) or "(无主题)"
        when = str(em.get("time", ""))
        unread = bool(em.get("unread"))

        # Unread indicator (solid dot)
        if unread:
            cx_pt = x + PAD + dot_r
            cy_pt = row_y + row_h // 2
            d.ellipse(
                [(cx_pt - dot_r, cy_pt - dot_r), (cx_pt + dot_r, cy_pt + dot_r)],
                fill=BLACK,
            )

        # Sender (after bullet column)
        sender_x = x + PAD + bullet_col_w
        sender_clip = _truncate(d, sender, sender_font, sender_col_w - 8)
        d.text((sender_x, row_y + 10), sender_clip, fill=BLACK, font=sender_font)

        # Time on the right
        when_w = _text_w(d, when, time_font)
        d.text(
            (x + w - PAD - when_w, row_y + 12),
            when,
            fill=DIM,
            font=time_font,
        )

        # Subject (bold if unread)
        subj_font = subject_font_b if unread else subject_font_r
        subj_x = sender_x + sender_col_w
        subj_max = (x + w - PAD - when_w - 12) - subj_x
        subject_clip = _truncate(d, subject, subj_font, subj_max)
        d.text((subj_x, row_y + 8), subject_clip, fill=BLACK, font=subj_font)

        if i < len(rows) - 1:
            line_y = row_y + row_h - 1
            d.line([(x + PAD, line_y), (x + w - PAD, line_y)], fill=220, width=1)


# ----------------------------------------------------------------- footer ---


def paint_footer(d: ImageDraw.ImageDraw, rect: tuple[int, int, int, int], usb_ok: bool) -> None:
    x, y, w, h = rect
    ts = dt.datetime.now().strftime("%Y-%m-%d  %H:%M")
    status = "● USB connected" if usb_ok else "○ USB disconnected"
    f = font(20, "normal")
    text_y = y + 14
    d.text((x + PAD, text_y), f"刷新于 {ts}", fill=DIM, font=f)
    sw = _text_w(d, status, f)
    d.text((x + w - PAD - sw, text_y), status, fill=DIM if usb_ok else BLACK, font=f)


# ---------------------------------------------------------- compose & save ---


def render(cache: dict[str, dict], out_path: str, usb_ok: bool = True) -> None:
    img = Image.new("L", (CANVAS_W, CANVAS_H), color=WHITE)
    d = ImageDraw.Draw(img)

    paint_weather(d,  LAYOUT["weather"],  cache.get("weather"))
    paint_calendar(d, LAYOUT["calendar"], cache.get("calendar"))
    paint_tasks(d,    LAYOUT["tasks"],    cache.get("tasks"))
    paint_inbox(d,    LAYOUT["inbox"],    cache.get("inbox"))
    paint_footer(d,   LAYOUT["footer"],   usb_ok)

    # Horizontal section dividers
    for slot in ("calendar", "inbox", "footer"):
        _, sy, _, _ = LAYOUT[slot]
        d.line([(12, sy), (CANVAS_W - 12, sy)], fill=BLACK, width=1)

    # Vertical divider between calendar and tasks (middle row only)
    cx, cy, cw, ch = LAYOUT["calendar"]
    split_x = cx + cw
    d.line([(split_x, cy + 8), (split_x, cy + ch - 8)], fill=BLACK, width=1)

    # Outer border — confined within calibrated visible area
    d.rectangle([(4, TOP_RESERVE), (CANVAS_W - 4, BOTTOM_SAFETY_END)], outline=BLACK, width=1)

    tmp = out_path + ".tmp"
    img.save(tmp, format="PNG", optimize=True)
    os.replace(tmp, out_path)
