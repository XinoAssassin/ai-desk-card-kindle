#!/usr/bin/env python3
"""Kindle desk card daemon.

Endpoints
---------
POST /widget          {"slot":"weather|calendar|inbox", "data": {...}}
                      Caches the widget data, re-renders the full frame to
                      /tmp/kindle-frame.png. Returns {"ok": true}.
GET  /kindle/frame.png
                      Returns the latest rendered PNG. If the cache is empty
                      or the file is missing, renders a "no data yet" frame
                      on the fly.
DELETE /widget?slot=X Clears one slot (or all slots if ?slot is omitted).
GET  /widget          Snapshot of the cache (debugging).
GET  /health          "ok\\n"

Bind
----
Tries to bind the USB-Ethernet IP first (so only the Kindle on the other
end of the cable can reach it). Falls back to 127.0.0.1 if the USB cable
isn't plugged in — useful for local rendering tests.
"""
from __future__ import annotations

import argparse
import json
import logging
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from mac_lock import is_locked
from render import render, render_sleep

DEFAULT_BIND = "192.168.15.201"
DEFAULT_PORT = 9878
FRAME_PATH = "/tmp/kindle-frame.png"
SLEEP_FRAME_PATH = "/tmp/kindle-sleep.png"
VALID_SLOTS = {"weather", "calendar", "tasks", "inbox"}

_cache_lock = threading.Lock()
_widget_cache: dict[str, dict] = {}
_usb_ok: bool = True


def _render_now() -> None:
    with _cache_lock:
        snapshot = dict(_widget_cache)
    render(snapshot, FRAME_PATH, usb_ok=_usb_ok)
    render_sleep(snapshot.get("weather"), SLEEP_FRAME_PATH)


class Handler(BaseHTTPRequestHandler):

    # ---- helpers --------------------------------------------------------

    def _json(self, status: int, body: dict) -> None:
        payload = json.dumps(body).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def _read_json(self) -> dict | None:
        try:
            n = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            return None
        if n <= 0 or n > 1_000_000:
            return None
        raw = self.rfile.read(n)
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return None

    # ---- GET ------------------------------------------------------------

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)

        if parsed.path == "/kindle/frame.png":
            path = SLEEP_FRAME_PATH if is_locked() else FRAME_PATH
            try:
                with open(path, "rb") as f:
                    body = f.read()
            except FileNotFoundError:
                _render_now()
                with open(path, "rb") as f:
                    body = f.read()
            self.send_response(200)
            self.send_header("Content-Type", "image/png")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)
            return

        if parsed.path == "/widget":
            with _cache_lock:
                self._json(200, {"widgets": dict(_widget_cache)})
            return

        if parsed.path == "/health":
            self._json(200, {
                "ok": True,
                "usb_ok": _usb_ok,
                "locked": is_locked(),
                "slots": sorted(_widget_cache),
            })
            return

        self.send_error(404, "not found")

    # ---- POST -----------------------------------------------------------

    def do_POST(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        if parsed.path != "/widget":
            self.send_error(404, "not found")
            return

        body = self._read_json()
        if not isinstance(body, dict):
            self._json(400, {"ok": False, "error": "json body required"})
            return

        slot = body.get("slot") or body.get("type")
        if slot not in VALID_SLOTS:
            self._json(400, {"ok": False, "error": f"slot must be one of {sorted(VALID_SLOTS)}"})
            return

        data = body.get("data")
        if not isinstance(data, dict):
            self._json(400, {"ok": False, "error": "data must be an object"})
            return

        with _cache_lock:
            _widget_cache[slot] = data

        try:
            _render_now()
        except Exception as e:
            logging.exception("render failed: %s", e)
            self._json(500, {"ok": False, "error": f"render failed: {e}"})
            return

        self._json(200, {"ok": True, "slot": slot, "frame": FRAME_PATH})

    # ---- DELETE ---------------------------------------------------------

    def do_DELETE(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        if parsed.path != "/widget":
            self.send_error(404, "not found")
            return

        qs = parse_qs(parsed.query)
        slot = (qs.get("slot") or [None])[0]
        cleared: list[str] = []
        with _cache_lock:
            if slot is None:
                cleared = list(_widget_cache)
                _widget_cache.clear()
            elif slot in _widget_cache:
                del _widget_cache[slot]
                cleared = [slot]
        try:
            _render_now()
        except Exception as e:
            logging.exception("render after delete failed: %s", e)
        self._json(200, {"ok": True, "cleared": cleared})

    def log_message(self, fmt: str, *args) -> None:  # noqa: A003
        logging.info("%s - %s", self.address_string(), fmt % args)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--bind", default=DEFAULT_BIND)
    ap.add_argument("--port", type=int, default=DEFAULT_PORT)
    args = ap.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )

    global _usb_ok
    try:
        server = ThreadingHTTPServer((args.bind, args.port), Handler)
    except OSError as e:
        # Exit non-zero so launchd KeepAlive retries every ~10s until the USB
        # cable is back. Falling back to 127.0.0.1 would silently strand the
        # Kindle on a port it can't reach.
        logging.error("Could not bind %s:%d (%s) — exiting for supervisor", args.bind, args.port, e)
        raise SystemExit(2) from e

    # Pre-render an empty frame so the first GET responds instantly.
    _render_now()

    host, port = server.server_address[:2]
    logging.info("Listening on http://%s:%d/kindle/frame.png  (frame=%s)", host, port, FRAME_PATH)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        logging.info("Shutting down")
        server.server_close()


if __name__ == "__main__":
    main()
