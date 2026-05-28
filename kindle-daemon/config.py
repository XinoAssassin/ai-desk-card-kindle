"""Data source configuration for the dashboard.

Lets the user pick which adapter feeds each slot — useful when the upstream
service differs from the default (e.g. Gmail instead of Exchange for inbox,
or Lark instead of Exchange for calendar).

Config file
-----------
Optional file at ~/.config/kindle-desk-card/sources.json. Example:

    {
      "weather":  "weather",
      "calendar": "exchange_calendar",
      "tasks":    "lark_tasks",
      "inbox":    "exchange_inbox"
    }

Set a slot to null (or omit it) to skip that data source — the frame will
just render an "暂无数据" placeholder for it.

If the file doesn't exist, DEFAULT_SOURCES is used.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Callable

from adapters import (
    exchange_calendar,
    exchange_inbox,
    gmail,
    lark_calendar,
    lark_tasks,
    weather,
)

CONFIG_PATH = Path.home() / ".config" / "kindle-desk-card" / "sources.json"

# Registry of every adapter we know how to call. The key is what users
# put in sources.json; the value is the slot it feeds + its fetch().
ADAPTERS: dict[str, tuple[str, Callable[[], dict]]] = {
    "weather":           ("weather",  weather.fetch),
    "exchange_calendar": ("calendar", exchange_calendar.fetch),
    "lark_calendar":     ("calendar", lark_calendar.fetch),
    "lark_tasks":        ("tasks",    lark_tasks.fetch),
    "exchange_inbox":    ("inbox",    exchange_inbox.fetch),
    "gmail":             ("inbox",    gmail.fetch),
}

DEFAULT_SOURCES: dict[str, str | None] = {
    "weather":  "weather",
    "calendar": "exchange_calendar",
    "tasks":    "lark_tasks",
    "inbox":    "exchange_inbox",
}

VALID_SLOTS = set(DEFAULT_SOURCES)


def load_sources() -> dict[str, str | None]:
    """Return {slot: adapter-name-or-None} merged from defaults + config file."""
    merged = dict(DEFAULT_SOURCES)
    if not CONFIG_PATH.exists():
        return merged
    try:
        raw = json.loads(CONFIG_PATH.read_text())
    except (OSError, json.JSONDecodeError) as e:
        logging.warning("config %s unreadable (%s) — using defaults", CONFIG_PATH, e)
        return merged
    if not isinstance(raw, dict):
        logging.warning("config %s is not a JSON object — using defaults", CONFIG_PATH)
        return merged
    for slot, name in raw.items():
        if slot not in VALID_SLOTS:
            logging.warning("config: ignoring unknown slot %r", slot)
            continue
        if name is None:
            merged[slot] = None
            continue
        if name not in ADAPTERS:
            logging.warning("config: ignoring unknown adapter %r (slot=%s)", name, slot)
            continue
        adapter_slot, _ = ADAPTERS[name]
        if adapter_slot != slot:
            logging.warning("config: adapter %r feeds slot %r, not %r — skipping", name, adapter_slot, slot)
            continue
        merged[slot] = name
    return merged


def resolved_sources() -> list[tuple[str, str, Callable[[], dict]]]:
    """Iteration order for refresh.py: list of (slot, adapter_label, fetch)."""
    out: list[tuple[str, str, Callable[[], dict]]] = []
    for slot, name in load_sources().items():
        if name is None:
            continue
        _, fetcher = ADAPTERS[name]
        out.append((slot, name, fetcher))
    return out


if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    print(f"config path: {CONFIG_PATH}  (exists={CONFIG_PATH.exists()})")
    for slot, name, _ in resolved_sources():
        print(f"  {slot:<10} -> {name}")
    sys.exit(0)
