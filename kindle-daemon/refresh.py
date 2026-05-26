#!/usr/bin/env python3
"""Refresh entry point — fetch all data sources and POST widgets to the daemon.

Designed to be called by cron every 2 min while the Kindle is plugged in:

  */2 8-22 * * * /path/to/.venv/bin/python /path/to/refresh.py

Each adapter is independent: if one fails, log and continue. The Kindle
keeps showing its last-good frame regardless — the daemon never wipes the
cache on a partial refresh.
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
import time
import urllib.error
import urllib.request

from adapters import exchange_calendar, exchange_inbox, lark_tasks, weather

DAEMON_URL = "http://192.168.15.201:9878"

# (slot, label, fetch_callable)
SOURCES: list[tuple[str, str, callable]] = [
    ("weather",  "weather",           weather.fetch),
    ("calendar", "exchange-calendar", exchange_calendar.fetch),
    ("tasks",    "lark-tasks",        lark_tasks.fetch),
    ("inbox",    "exchange-inbox",    exchange_inbox.fetch),
]


def post_widget(slot: str, data: dict, base_url: str) -> tuple[bool, str]:
    body = json.dumps({"slot": slot, "data": data}).encode("utf-8")
    req = urllib.request.Request(
        f"{base_url}/widget",
        data=body,
        method="POST",
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status == 200, resp.read().decode("utf-8")
    except (urllib.error.URLError, TimeoutError) as e:
        return False, f"network error: {e}"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--daemon", default=DAEMON_URL)
    ap.add_argument("--only", help="comma-separated slot names to refresh")
    args = ap.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )

    only = set(args.only.split(",")) if args.only else None
    n_ok = n_fail = 0

    for slot, label, fetcher in SOURCES:
        if only and slot not in only:
            continue
        t0 = time.monotonic()
        try:
            data = fetcher()
        except Exception as e:  # adapter can raise anything — keep going
            logging.warning("[%s] fetch failed: %s", label, e)
            n_fail += 1
            continue
        elapsed = time.monotonic() - t0
        ok, msg = post_widget(slot, data, args.daemon)
        if ok:
            logging.info("[%s] ok in %.2fs", label, elapsed)
            n_ok += 1
        else:
            logging.warning("[%s] POST failed: %s", label, msg)
            n_fail += 1

    logging.info("refresh done: ok=%d fail=%d", n_ok, n_fail)
    return 0 if n_fail == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
