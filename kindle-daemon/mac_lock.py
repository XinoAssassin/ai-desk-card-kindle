"""Mac lock-screen detection via `ioreg`.

`ioreg -n Root -d1 -a` exposes the `IOConsoleLocked` key, which flips to
`<true/>` while the login window is showing the lock UI. No PyObjC / no
Quartz framework needed — just a shell out to a tool that's always present.

Result is cached for a few seconds so a burst of HTTP requests doesn't
spawn `ioreg` over and over.
"""
from __future__ import annotations

import subprocess
import time

_TTL_S = 5.0

_cache: dict[str, float | bool] = {"t": 0.0, "v": False}


def is_locked() -> bool:
    now = time.monotonic()
    if now - float(_cache["t"]) < _TTL_S:
        return bool(_cache["v"])
    try:
        r = subprocess.run(
            ["ioreg", "-n", "Root", "-d1", "-a"],
            capture_output=True,
            text=True,
            timeout=2,
        )
        # ioreg plist puts `<true/>` on the line right after the key
        out = r.stdout
        i = out.find("IOConsoleLocked")
        locked = i != -1 and "<true/>" in out[i : i + 80]
    except (subprocess.SubprocessError, OSError):
        locked = False
    _cache["t"] = now
    _cache["v"] = locked
    return locked


if __name__ == "__main__":
    print("locked" if is_locked() else "unlocked")
