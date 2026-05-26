"""Lark task adapter — shells out to `lark-cli task +get-my-tasks`.

Outputs the dict shape expected by paint_tasks:
  {"total": int, "tasks": [{"title": str}, ...]}

`+get-my-tasks` returns summary + guid + created_at but no due date / urgent
flag — those would need a per-task lookup (N+1). For MVP we just show titles
sorted by most-recently-created first.
"""
from __future__ import annotations

import json
import subprocess


LARK_CLI = "lark-cli"
TIMEOUT_S = 15
MAX_TASKS = 9   # paint_tasks renders up to 9 rows


def fetch() -> dict:
    out = subprocess.run(
        [LARK_CLI, "task", "+get-my-tasks", "--complete=false", "--format", "json"],
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

    items = (payload.get("data") or {}).get("items") or []
    items.sort(key=lambda t: t.get("created_at", ""), reverse=True)

    return {
        "total": len(items),
        "tasks": [{"title": (t.get("summary") or "").strip() or "(无标题)"} for t in items[:MAX_TASKS]],
    }


if __name__ == "__main__":
    print(json.dumps(fetch(), ensure_ascii=False, indent=2))
