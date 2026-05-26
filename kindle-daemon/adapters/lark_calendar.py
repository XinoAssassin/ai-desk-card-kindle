"""Lark calendar adapter — shells out to `lark-cli calendar +agenda`.

Outputs the dict shape expected by paint_calendar:
  {"now_iso": str,
   "events": [
     {"start":"HH:MM","end":"HH:MM","title":str,"rsvp":str,"date_label":str|None},
     ...
   ]}

Fetches a 3-day window so the desk card can show tomorrow's invites too —
otherwise at end-of-day / overnight the screen would be near-empty.
"""
from __future__ import annotations

import datetime as dt
import json
import subprocess


LARK_CLI = "lark-cli"
TIMEOUT_S = 15
WINDOW_DAYS = 3   # today + 2 more days
MAX_EVENTS = 9


def _hhmm(iso: str) -> str:
    try:
        return dt.datetime.fromisoformat(iso).strftime("%H:%M")
    except (ValueError, TypeError):
        return ""


def _parse(iso: str) -> dt.datetime | None:
    try:
        return dt.datetime.fromisoformat(iso)
    except (ValueError, TypeError):
        return None


def _date_label(start: dt.datetime, today: dt.date) -> str | None:
    """Returns None for today, '明天' for tomorrow, 'M/D 周X' for later."""
    delta = (start.date() - today).days
    if delta <= 0:
        return None
    if delta == 1:
        return "明天"
    weekday = "一二三四五六日"[start.weekday()]
    return f"{start.month}/{start.day} 周{weekday}"


def fetch() -> dict:
    now = dt.datetime.now().astimezone()
    start_iso = now.strftime("%Y-%m-%dT00:00:00") + now.strftime("%z")
    # Insert colon in tz offset: +0800 -> +08:00
    if len(start_iso) >= 5 and start_iso[-5] in "+-":
        start_iso = start_iso[:-2] + ":" + start_iso[-2:]
    end_dt = now + dt.timedelta(days=WINDOW_DAYS - 1)
    end_iso = end_dt.strftime("%Y-%m-%dT23:59:59") + now.strftime("%z")
    if len(end_iso) >= 5 and end_iso[-5] in "+-":
        end_iso = end_iso[:-2] + ":" + end_iso[-2:]

    out = subprocess.run(
        [LARK_CLI, "calendar", "+agenda",
         "--start", start_iso, "--end", end_iso, "--format", "json"],
        capture_output=True,
        text=True,
        timeout=TIMEOUT_S,
        check=False,
    )
    if out.returncode != 0:
        raise RuntimeError(f"lark-cli exit {out.returncode}: {out.stderr[:200]}")

    payload = json.loads(out.stdout)
    if not payload.get("ok"):
        raise RuntimeError(f"lark-cli error: {payload.get('error')}")

    raw_events = payload.get("data") or []
    today = now.date()

    events: list[dict] = []
    for ev in raw_events:
        title = (ev.get("summary") or "").strip() or "(无标题)"
        start_iso_ev = (ev.get("start_time") or {}).get("datetime", "")
        end_iso_ev   = (ev.get("end_time")   or {}).get("datetime", "")
        start_dt = _parse(start_iso_ev)
        end_dt   = _parse(end_iso_ev)

        # Skip events that already ended (with 30 min grace) — past noise
        if end_dt and end_dt + dt.timedelta(minutes=30) < now:
            continue
        if not start_dt:
            continue

        events.append({
            "start": _hhmm(start_iso_ev),
            "end":   _hhmm(end_iso_ev),
            "title": title,
            "rsvp":  ev.get("self_rsvp_status") or "needs_action",
            "date_label": _date_label(start_dt, today),
            "_sort": start_dt.timestamp(),
        })

    events.sort(key=lambda e: e["_sort"])
    for e in events:
        e.pop("_sort", None)

    return {
        "now_iso": now.isoformat(timespec="seconds"),
        "events": events[:MAX_EVENTS],
    }


if __name__ == "__main__":
    print(json.dumps(fetch(), ensure_ascii=False, indent=2))
