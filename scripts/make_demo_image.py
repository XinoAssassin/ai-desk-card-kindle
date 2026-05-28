#!/usr/bin/env python3
"""Render a privacy-clean demo frame for screenshots / promotion.

All widget data is synthetic and committed in this script — no real
calendar / inbox / task content ever leaves the user's machine. Run from
the repo root:

    .venv/bin/python scripts/make_demo_image.py --out docs/demo.png
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "kindle-daemon"))

from render import render, render_sleep  # noqa: E402


DEMO_CACHE = {
    "weather": {
        "city":        "Shanghai",
        "temp":        22,
        "feels_like":  21,
        "condition":   "晴间多云",
        "high":        25,
        "low":         16,
        "humidity":    58,
        "wind":        3,
        "aqi":         42,
        "aqi_label":   "优",
        "sunrise":     "05:42",
        "sunset":      "18:31",
        "precip_prob": 10,
    },
    "calendar": {
        "now_iso": "2026-05-28T09:24:00+08:00",
        "events": [
            {"start": "10:00", "end": "10:30", "title": "Daily standup",        "rsvp": "accept",       "date_label": None},
            {"start": "11:00", "end": "12:00", "title": "Design review",        "rsvp": "accept",       "date_label": None},
            {"start": "14:00", "end": "14:30", "title": "1:1 with manager",     "rsvp": "accept",       "date_label": None},
            {"start": "15:00", "end": "16:00", "title": "Roadmap planning",     "rsvp": "tentative",    "date_label": None},
            {"start": "17:30", "end": "18:00", "title": "Lightning demo",       "rsvp": "needs_action", "date_label": None},
            {"start": "09:30", "end": "10:30", "title": "Sprint retrospective", "rsvp": "accept",       "date_label": "明天"},
            {"start": "13:00", "end": "14:00", "title": "Vendor sync",          "rsvp": "decline",      "date_label": "明天"},
            {"start": "16:00", "end": "17:00", "title": "Architecture workshop","rsvp": "needs_action", "date_label": "明天"},
        ],
    },
    "tasks": {
        "total": 7,
        "tasks": [
            {"title": "起草下季度 OKR 草案",          "due": "今天", "urgent": True},
            {"title": "Review pending pull requests", "due": "今天", "urgent": False},
            {"title": "整理 e-ink 渲染调研笔记",      "due": "明天", "urgent": False},
            {"title": "Update onboarding guide",      "due": "周五", "urgent": False},
            {"title": "梳理上线发布检查清单",         "due": "下周", "urgent": False},
            {"title": "Prepare demo for tech talk",   "due": "下周", "urgent": False},
            {"title": "整理读书笔记 inbox",           "due": "",     "urgent": False},
        ],
    },
    "inbox": {
        "total": 3,
        "emails": [
            {"from": "GitHub",         "subject": "[repo] New release v1.4.0 published",        "time": "09:18", "unread": True},
            {"from": "Calendar",       "subject": "Invitation: Lightning demo @ Thu May 28",    "time": "08:55", "unread": True},
            {"from": "Newsletter",     "subject": "This week in distributed systems",           "time": "07:42", "unread": True},
            {"from": "Cron",           "subject": "Backup completed: 12.4 GB archived",          "time": "昨天", "unread": False},
            {"from": "Hacker News",    "subject": "Show HN: A weekend project that took 3 years","time": "昨天", "unread": False},
        ],
    },
}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="docs/demo.png", help="Output path for dashboard frame")
    ap.add_argument("--sleep-out", default="docs/demo-sleep.png", help="Output path for sleep frame")
    ap.add_argument("--no-sleep", action="store_true", help="Skip the sleep frame")
    args = ap.parse_args()

    out = (REPO_ROOT / args.out).resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    render(DEMO_CACHE, str(out), usb_ok=True)
    print(f"dashboard → {out}")

    if not args.no_sleep:
        sleep_out = (REPO_ROOT / args.sleep_out).resolve()
        sleep_out.parent.mkdir(parents=True, exist_ok=True)
        render_sleep(DEMO_CACHE["weather"], str(sleep_out))
        print(f"sleep     → {sleep_out}")


if __name__ == "__main__":
    main()
