"""Exchange inbox adapter — most-recent messages + unread count.

Output shape (matches paint_inbox):
  {"total": <unread int, for the "共 N 封未读" hint>,
   "emails": [
     {"from": "<sender>", "subject": "<subj>",
      "time": "HH:MM | 昨天 | M/D", "unread": <bool>},
     ...
   ]}

Pulls the latest N messages regardless of read state. Subject + sender +
datetime_received + is_read only — no message bodies fetched.
"""
from __future__ import annotations

import datetime as dt
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from adapters._exchange import get_account  # noqa: E402


MAX_LIST = 5   # paint_inbox renders up to 5 rows
TZ_NAME = os.environ.get("KINDLE_TZ", "Asia/Shanghai")


_NAME_TAIL = re.compile(r"[\s（(<].*$")
_SUBJECT_PREFIX = re.compile(r"^(?:\s*(?:RE|FW|FWD|答复|回复|回覆|回收|转发|轉發)\s*[:：]\s*)+", re.I)


def _short_name(mailbox) -> str:
    if mailbox is None:
        return "?"
    name = (mailbox.name or "").strip()
    if name:
        cleaned = _NAME_TAIL.sub("", name).strip(" ,_")
        return (cleaned or name)[:14]
    addr = (mailbox.email_address or "").strip()
    if "@" in addr:
        return addr.split("@", 1)[0][:14]
    return addr[:14] or "?"


def _fmt_time(received, now: dt.datetime) -> str:
    """Smart time label: HH:MM if today, '昨天' if yesterday, M/D otherwise."""
    if received is None:
        return ""
    try:
        local = received.astimezone(now.tzinfo)
    except Exception:
        return ""
    delta_days = (now.date() - local.date()).days
    if delta_days <= 0:
        return local.strftime("%H:%M")
    if delta_days == 1:
        return "昨天"
    return f"{local.month}/{local.day}"


def fetch() -> dict:
    from exchangelib import EWSTimeZone
    tz = EWSTimeZone(TZ_NAME)
    now = dt.datetime.now(tz)

    account = get_account()
    inbox = account.inbox
    total_unread = int(getattr(inbox, "unread_count", 0) or 0)

    emails: list[dict] = []
    recent = (
        inbox.all()
        .only("sender", "subject", "datetime_received", "is_read")
        .order_by("-datetime_received")[:MAX_LIST]
    )
    for item in recent:
        subj = _SUBJECT_PREFIX.sub("", (item.subject or "").strip()) or "(无主题)"
        emails.append({
            "from":    _short_name(item.sender),
            "subject": subj,
            "time":    _fmt_time(item.datetime_received, now),
            "unread":  not bool(item.is_read),
        })

    return {
        "total":  total_unread,
        "emails": emails,
    }


if __name__ == "__main__":
    import json
    print(json.dumps(fetch(), ensure_ascii=False, indent=2))
