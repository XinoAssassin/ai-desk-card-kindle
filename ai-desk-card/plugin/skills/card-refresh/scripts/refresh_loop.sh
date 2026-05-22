#!/usr/bin/env bash
# AI Desk Card cron 入口 — 每次 cron 触发跑一次。
# 用 headless AI CLI 来执行 /card-refresh skill。
#
# AI CLI 选择策略：
#   1. 如果 $AI_CLI 设置了 → 用它（路径或名字均可）
#   2. 否则按顺序找：claude, codex, gemini, aider — 哪个先存在用哪个
#
# crontab 示例（工作日 8-21 点 每 30min）:
#   */30 8-21 * * 1-5  /path/to/refresh_loop.sh
#
# 日志：~/.ai-desk-card-refresh.log

set -u

LOG="${HOME}/.ai-desk-card-refresh.log"
DAEMON_URL="${CARD_DAEMON_URL:-http://127.0.0.1:9877}"

ts() { date "+%Y-%m-%d %H:%M:%S"; }
log() { echo "[$(ts)] $*" >> "$LOG"; }

log "=== refresh start ==="

# 0. daemon 必须在跑
if ! curl -sf -m 2 "$DAEMON_URL/pair-status" >/dev/null; then
  log "ERROR daemon not reachable at $DAEMON_URL — skipping refresh"
  exit 1
fi

# 1. 选 AI CLI
AI_BIN=""
if [[ -n "${AI_CLI:-}" ]]; then
  AI_BIN="$(command -v "$AI_CLI" || true)"
  [[ -z "$AI_BIN" && -x "$AI_CLI" ]] && AI_BIN="$AI_CLI"
fi
if [[ -z "$AI_BIN" ]]; then
  for c in claude codex gemini aider; do
    AI_BIN="$(command -v "$c" || true)"
    [[ -n "$AI_BIN" ]] && { log "auto-picked AI CLI: $c"; break; }
  done
fi
if [[ -z "$AI_BIN" ]]; then
  log "ERROR no AI CLI in PATH. Set \$AI_CLI or install one (claude/codex/gemini/aider)."
  exit 2
fi

# 2. 跑 headless AI CLI 执行 /card-refresh skill
#    --print          → 一次性、非交互模式（兼容多数 CLI 的"single-shot"开关）
#    --max-turns 5    → 限制 turn 数，避免失控
#    /card-refresh   → skill slash command
# stderr 进日志、stdout 默默吃掉（cron 不需要看）
"$AI_BIN" --print --max-turns 5 "/card-refresh" \
    > /dev/null \
    2>> "$LOG"
RC=$?

log "headless AI rc=$RC"

# 3. 抓最后几行 token 用量（很多 CLI 会在 stderr 打 [cost] 之类）
COST=$(tail -50 "$LOG" | grep -E '(\$|tokens|cost)' | tail -1 || true)
[[ -n "$COST" ]] && log "[cost] $COST"

log "=== refresh end ==="
exit "$RC"
