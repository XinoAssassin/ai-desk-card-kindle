"""Exchange (on-prem) calendar adapter via EWS.

Reads credentials from ~/.config/kindle-desk-card/exchange.env (mode 0600):
    EXCHANGE_EMAIL=you@example.com
    EXCHANGE_USERNAME=you@example.com
    EXCHANGE_PASSWORD=...
    EXCHANGE_SERVER=mail.example.com

Outputs the same shape as lark_calendar.fetch():
    {"now_iso": str,
     "events": [{"start":"HH:MM","end":"HH:MM","title":str,
                 "rsvp":str,"date_label":str|None}, ...]}
"""
from __future__ import annotations

import datetime as dt
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from exchangelib import EWSDateTime, EWSTimeZone  # noqa: E402

from adapters._exchange import get_account  # noqa: E402


# Outlook recurring invitations sometimes glue the original invite metadata
# onto the subject:  "Real Title@2026年4月21日（周二） 09:30 - ... (email)"
# Strip everything from the first "@<year>年" we see.
_OUTLOOK_TAIL = re.compile(r"@\d{4}年.*$")


WINDOW_DAYS = 2   # today + tomorrow only
MAX_EVENTS = 9
TZ_NAME = os.environ.get("KINDLE_TZ", "Asia/Shanghai")


_RSVP_MAP = {
    "Accept":            "accept",
    "Tentative":         "tentative",
    "Decline":           "decline",
    "NoResponseReceived":"needs_action",
    "Organizer":         "accept",     # you organized it → effectively confirmed
    "Unknown":           "needs_action",
}


def _date_label(start: dt.datetime, today: dt.date) -> str | None:
    delta = (start.date() - today).days
    if delta <= 0:
        return None
    if delta == 1:
        return "明天"
    weekday = "一二三四五六日"[start.weekday()]
    return f"{start.month}/{start.day} 周{weekday}"


def fetch() -> dict:
    account = get_account()
    tz = EWSTimeZone(TZ_NAME)
    now_local = dt.datetime.now(tz)
    # Construct EWSDateTime directly — exchangelib refuses plain datetime here
    start_ews = EWSDateTime(now_local.year, now_local.month, now_local.day, 0, 0, 0, tzinfo=tz)
    end_ews = start_ews + dt.timedelta(days=WINDOW_DAYS) - dt.timedelta(seconds=1)

    events: list[dict] = []
    today = now_local.date()
    for item in account.calendar.view(start=start_ews, end=end_ews):
        # Items expanded by .view() include recurring instances flattened
        start = item.start.astimezone(tz) if item.start else None
        end_ = item.end.astimezone(tz) if item.end else None
        if not start:
            continue
        # Drop events that have already ended
        if end_ and end_ <= now_local:
            continue
        title = _OUTLOOK_TAIL.sub("", (item.subject or "")).strip() or "(无标题)"
        rsvp_raw = getattr(item, "my_response_type", None) or "Unknown"
        rsvp = _RSVP_MAP.get(rsvp_raw, "needs_action")
        events.append({
            "start": start.strftime("%H:%M"),
            "end":   end_.strftime("%H:%M") if end_ else "",
            "title": title,
            "rsvp":  rsvp,
            "date_label": _date_label(start, today),
            "_sort": start.timestamp(),
        })

    events.sort(key=lambda e: e["_sort"])
    for e in events:
        e.pop("_sort", None)

    return {
        "now_iso": now_local.isoformat(timespec="seconds"),
        "events": events[:MAX_EVENTS],
    }


if __name__ == "__main__":
    import json
    print(json.dumps(fetch(), ensure_ascii=False, indent=2))
