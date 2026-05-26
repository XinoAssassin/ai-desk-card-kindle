"""Weather adapter using wttr.in (no auth required).

Outputs the dict shape expected by paint_weather:
  {"city": str, "temp": int, "condition": str, "high": int, "low": int}
"""
from __future__ import annotations

import json
import os
import time
import urllib.request
from pathlib import Path

DEFAULT_CITY = os.environ.get("KINDLE_WEATHER_CITY", "Minhang")
DISPLAY_CITY = os.environ.get("KINDLE_WEATHER_CITY_DISPLAY", "上海闵行")
TIMEOUT_S = 8

CACHE_PATH = Path.home() / ".cache" / "kindle-desk-card" / "weather.json"
CACHE_TTL_S = 3600   # 1 hour — weather changes slowly, polling more is wasteful


def _english_to_zh(desc: str) -> str:
    """Tiny English→Chinese mapping for wttr.in's weatherDesc.
    Falls back to original string if unknown.
    """
    table = {
        "sunny": "晴",
        "clear": "晴",
        "partly cloudy": "多云",
        "cloudy": "阴",
        "overcast": "阴",
        "mist": "雾",
        "fog": "雾",
        "patchy rain possible": "可能小雨",
        "patchy rain nearby": "局部小雨",
        "light rain": "小雨",
        "light rain shower": "小阵雨",
        "moderate rain": "中雨",
        "moderate rain at times": "时有中雨",
        "heavy rain": "大雨",
        "light snow": "小雪",
        "heavy snow": "大雪",
        "thunderstorm": "雷暴",
        "thundery outbreaks possible": "可能雷阵雨",
        "patchy light rain with thunder": "局部小雨雷电",
    }
    return table.get(desc.strip().lower(), desc.strip())


def _load_cache() -> dict | None:
    """Return cached weather data if it's still fresh, else None."""
    try:
        if not CACHE_PATH.exists():
            return None
        if time.time() - CACHE_PATH.stat().st_mtime > CACHE_TTL_S:
            return None
        return json.loads(CACHE_PATH.read_text())
    except (OSError, json.JSONDecodeError):
        return None


def _save_cache(data: dict) -> None:
    try:
        CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
        CACHE_PATH.write_text(json.dumps(data, ensure_ascii=False))
    except OSError:
        pass


def _fetch_remote(city: str) -> dict:
    url = f"https://wttr.in/{city}?format=j1"
    req = urllib.request.Request(url, headers={"User-Agent": "curl/8.0"})
    with urllib.request.urlopen(req, timeout=TIMEOUT_S) as resp:
        payload = json.loads(resp.read().decode("utf-8"))

    cur = payload["current_condition"][0]
    today = payload["weather"][0]

    cond_zh = ""
    for key in ("lang_zh", "lang_zh-cn"):
        if key in cur and cur[key]:
            cond_zh = cur[key][0].get("value", "").strip()
            if cond_zh:
                break
    if not cond_zh:
        cond_zh = _english_to_zh(cur["weatherDesc"][0]["value"])

    return {
        "city": DISPLAY_CITY,
        "temp": int(cur["temp_C"]),
        "condition": cond_zh,
        "high": int(today["maxtempC"]),
        "low": int(today["mintempC"]),
    }


def fetch(city: str | None = None) -> dict:
    cached = _load_cache()
    if cached is not None:
        return cached
    data = _fetch_remote(city or DEFAULT_CITY)
    _save_cache(data)
    return data


if __name__ == "__main__":
    print(json.dumps(fetch(), ensure_ascii=False, indent=2))
