"""Weather adapter using Open-Meteo (free, no API key).

Two upstream endpoints, called sequentially (both cheap, ~200 ms each):
  - api.open-meteo.com           : temperature / humidity / hi-lo / wind / WMO code
  - air-quality-api.open-meteo.com: US-AQI air quality index

Output shape consumed by paint_weather:
  {"city":      str,
   "temp":      int,
   "feels_like":int,
   "condition": str (Chinese, mapped from WMO weather code),
   "high":      int,
   "low":       int,
   "humidity":  int (%),
   "wind":      int (Beaufort scale 0-12),
   "aqi":       int (US-AQI), or None
   "aqi_label": str ("优 / 良 / 轻度污染 / ..."), or None}

Cached locally for 1 hour (~/.cache/kindle-desk-card/weather.json) — weather
moves slowly; calling the API every refresh tick (2 min) is wasteful.
"""
from __future__ import annotations

import json
import os
import time
import urllib.parse
import urllib.request
from pathlib import Path

# Default: 上海闵行 (Minhang, Shanghai). Override via env if needed.
DEFAULT_LAT = float(os.environ.get("KINDLE_WEATHER_LAT", "31.1812"))
DEFAULT_LON = float(os.environ.get("KINDLE_WEATHER_LON", "121.3786"))
DISPLAY_CITY = os.environ.get("KINDLE_WEATHER_CITY_DISPLAY", "上海闵行")
TZ = os.environ.get("KINDLE_TZ", "Asia/Shanghai")
TIMEOUT_S = 8

CACHE_PATH = Path.home() / ".cache" / "kindle-desk-card" / "weather.json"
CACHE_TTL_S = 3600   # 1 hour


# WMO weather codes → Chinese. See open-meteo.com/en/docs#weathervariables
_WMO_ZH: dict[int, str] = {
    0:  "晴",
    1:  "晴间多云", 2: "多云", 3: "阴",
    45: "雾",       48: "冻雾",
    51: "毛毛雨",   53: "小雨",   55: "中雨",
    56: "冻毛毛雨", 57: "冻雨",
    61: "小雨",     63: "中雨",   65: "大雨",
    66: "冻雨",     67: "强冻雨",
    71: "小雪",     73: "中雪",   75: "大雪",
    77: "雪粒",
    80: "小阵雨",   81: "中阵雨", 82: "暴雨",
    85: "小阵雪",   86: "大阵雪",
    95: "雷阵雨",   96: "雷阵雨夹冰雹", 99: "强雷雨夹冰雹",
}


def _wmo_to_zh(code: int | None) -> str:
    if code is None:
        return ""
    return _WMO_ZH.get(int(code), f"代码 {code}")


def _aqi_label(aqi: float | None) -> str | None:
    if aqi is None:
        return None
    a = float(aqi)
    if a <= 50:   return "优"
    if a <= 100:  return "良"
    if a <= 150:  return "轻度污染"
    if a <= 200:  return "中度污染"
    if a <= 300:  return "重度污染"
    return "严重污染"


def _ms_to_beaufort(ms: float | None) -> int | None:
    """Convert m/s wind speed to Beaufort scale (0..12)."""
    if ms is None:
        return None
    thresholds = [0.3, 1.6, 3.4, 5.5, 8.0, 10.8, 13.9, 17.2, 20.8, 24.5, 28.5, 32.7]
    v = float(ms)
    for i, t in enumerate(thresholds):
        if v < t:
            return i
    return 12


def _http_json(url: str) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": "kindle-desk-card/1.0"})
    with urllib.request.urlopen(req, timeout=TIMEOUT_S) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _fetch_remote(lat: float, lon: float) -> dict:
    forecast_url = (
        "https://api.open-meteo.com/v1/forecast?"
        + urllib.parse.urlencode({
            "latitude": lat,
            "longitude": lon,
            "current": "temperature_2m,relative_humidity_2m,apparent_temperature,"
                       "weather_code,wind_speed_10m",
            "daily":   "temperature_2m_max,temperature_2m_min,"
                       "sunrise,sunset,precipitation_probability_max",
            "wind_speed_unit": "ms",
            "timezone": TZ,
            "forecast_days": 1,
        })
    )
    aqi_url = (
        "https://air-quality-api.open-meteo.com/v1/air-quality?"
        + urllib.parse.urlencode({
            "latitude": lat,
            "longitude": lon,
            "current": "us_aqi",
            "timezone": TZ,
        })
    )

    fc = _http_json(forecast_url)
    try:
        aqi_doc = _http_json(aqi_url)
        aqi = aqi_doc.get("current", {}).get("us_aqi")
    except Exception:
        aqi = None  # AQI is optional — never block the widget on it

    cur = fc.get("current", {})
    daily = fc.get("daily", {})

    def _first(arr, default=None):
        return arr[0] if isinstance(arr, list) and arr else default

    def _hhmm(iso: str | None) -> str:
        if not iso or "T" not in iso:
            return ""
        return iso.split("T", 1)[1][:5]

    precip_prob = _first(daily.get("precipitation_probability_max"))

    return {
        "city":       DISPLAY_CITY,
        "temp":       int(round(cur.get("temperature_2m", 0))),
        "feels_like": int(round(cur.get("apparent_temperature", 0))),
        "condition":  _wmo_to_zh(cur.get("weather_code")),
        "high":       int(round(_first(daily.get("temperature_2m_max")) or 0)),
        "low":        int(round(_first(daily.get("temperature_2m_min")) or 0)),
        "humidity":   int(round(cur.get("relative_humidity_2m", 0))),
        "wind":       _ms_to_beaufort(cur.get("wind_speed_10m")),
        "aqi":        int(round(aqi)) if aqi is not None else None,
        "aqi_label":  _aqi_label(aqi),
        "sunrise":    _hhmm(_first(daily.get("sunrise"))),
        "sunset":     _hhmm(_first(daily.get("sunset"))),
        "precip_prob": int(round(precip_prob)) if precip_prob is not None else None,
    }


def _load_cache() -> dict | None:
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


def fetch() -> dict:
    cached = _load_cache()
    if cached is not None and "sunrise" in cached and "precip_prob" in cached:
        # Bust caches that pre-date a schema change so we don't render a frame
        # missing the new fields after we expand Open-Meteo's query.
        return cached
    data = _fetch_remote(DEFAULT_LAT, DEFAULT_LON)
    _save_cache(data)
    return data


if __name__ == "__main__":
    if CACHE_PATH.exists():
        CACHE_PATH.unlink()
    print(json.dumps(fetch(), ensure_ascii=False, indent=2))
