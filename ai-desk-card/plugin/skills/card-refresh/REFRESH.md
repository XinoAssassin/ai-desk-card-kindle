# AI Desk Card 自动刷新指南

副屏要持续有价值，widget 数据就得新鲜。这篇讲三种刷新方式 + 我推荐的
那种。

## TL;DR — 推荐方案（v0.8 Wi-Fi 已通后）

```cron
# 工作日 8:00-22:00, 每 30 分钟刷一次. 由 cron 拉起一个 headless AI CLI 来跑 skill
*/30 8-21 * * 1-5  /Users/<you>/Documents/code/claude-desktop-buddy-repo/ai-desk-card/plugin/skills/card-refresh/scripts/refresh_loop.sh
```

**为什么 30 分钟而不是 2 小时**：v0.8 Wi-Fi 路径下单 widget 改动 0.2 秒
到屏，没有"刷一次要 30 秒"的物理代价。更短的间隔 = 更新鲜的副屏。

预算大致估计（假设你的 AI CLI 按 token 计费）：每天 28 次 × 每次 ¥0.3-0.8 ≈
¥8-22/天（工作日）。具体看你用哪个 CLI / 哪个模型。

追求最低成本：

- **换 small/cheap 模型** — 大多数 CLI 都支持指定模型；约 1/5 成本
- **拉长间隔** — 改回 `0 9,11,13,15,17 * * 1-5`（每 2 小时）→ 成本 1/4
- **完全用 fallback** — 把 cron 指向 `scripts/fallback_refresh.py`（0 token
  成本但只能刷 weather / system / git-status 这三个本地能算的）

## 三种刷新架构

### A. cron + headless AI CLI（**推荐**）

```
cron (系统定时) → <ai-cli> --print "/card-refresh" → AI 跑 skill 拉数据 → push
```

✅ 简单 — cron 是 macOS/Linux 都自带的成熟机制
✅ 灵活 — AI 可以智能选数据源，遇到 OAuth 没配也能跳过
✅ 可见 — 用户能 `crontab -l` 看到，不会"神秘进程"
✅ 易调试 — 手动跑一次脚本就能验
✅ AI CLI 可换 — 默认走 `$AI_CLI` env var；不设就按顺序找 `claude` / `codex`
   / `gemini` / `aider` 等常见 CLI
❌ 每次刷新约 ¥0.3-0.8（取决于模型）的 token 成本

### B. 设备端定时拉起 AI（设备 ping daemon → daemon 触发 AI session）

❌ 大多数 AI CLI 没有 server mode；要常驻一个 webhook 接收端
❌ 反向通道复杂 — 还要解决设备睡眠时怎么唤醒、怎么不漏触发
❌ 多设备 / 多用户场景几乎跑不通

不推荐。除非你愿意自己维护一个 daemon-of-daemons。

### C. 纯 Python 脚本（不调 AI）

```
cron → scripts/fallback_refresh.py → 硬编码的数据源 → push
```

✅ 0 token 成本
✅ 离线可用
❌ 加新数据源要改代码
❌ 数据源失败 → 整个脚本可能挂；AI 版能跳过
❌ 不能根据 context 智能调整（比如开会时 push next-meeting 提前 15min 警告）

适合：**预算敏感 + 数据源稳定 + 不需要 AI 整理** 的用户。
我们把这个版本留作 fallback，不是默认。

## 安装方案 A（cron + headless AI CLI）

### 1. 确认你装了 AI CLI

```bash
which claude codex gemini aider 2>/dev/null
```

如果都没有，去你常用的 AI 平台官网装一个 CLI（任何一个支持 `--print`
或类似 one-shot 模式的都行）。

### 2. 测试单次刷新

```bash
bash $CLAUDE_PLUGIN_ROOT/skills/card-refresh/scripts/refresh_loop.sh
```

应该看到 stderr 上几行日志，stdout 干净，等 ~0.5 s 副屏上 widget 数据
更新（Wi-Fi 模式）。

### 3. 加 cron 条目

```bash
crontab -e
```

加入：

```cron
*/30 8-21 * * 1-5  /Users/<you>/Documents/code/claude-desktop-buddy-repo/ai-desk-card/plugin/skills/card-refresh/scripts/refresh_loop.sh
```

时区是 macOS 本地时间。**强烈建议限工作时段**（8:00-22:00 周一到周五），
不然半夜也在烧 token + 用户也不看。

### 4. 验证

```bash
crontab -l                                    # 确认条目在
tail -f ~/.ai-desk-card-refresh.log           # 看 cron 日志
```

10 分钟后回来看副屏，widget 应该比 cron 启动前新。

### 5. 指定特定的 AI CLI（可选）

如果你装了多个 CLI 想固定用某一个：

```bash
# 在 cron 行前面加一个 env var
*/30 8-21 * * 1-5  AI_CLI=codex bash /path/to/refresh_loop.sh
```

或者在你的 shell rc 文件里 export `AI_CLI`，cron 也会继承（取决于
cron 的环境策略；如果不继承就用上面的 inline 写法）。

## 安装方案 C（纯脚本 fallback，可选）

如果你想完全离线 / 没预算 / 数据源少：

```cron
0 */2 * * *  /usr/bin/python3 /path/to/ai-desk-card/plugin/skills/card-refresh/scripts/fallback_refresh.py
```

只刷这几个 widget：

- `weather`（wttr.in，根据 `~/.card-refresh.yaml` 里的 `location`）
- `system`（psutil）
- `git-status`（针对 `~/.card-refresh.yaml` 里的 `repo_path`）

其他 widget（calendar / inbox / pr-queue / messages）需要 AI 版才能可靠拉。

## 暂停刷新

短期：注释 crontab 那行。
长期：删掉 crontab 那行 + `rm ~/.ai-desk-card-refresh.log`。

刷新不会自动重启，只有 cron 在跑就会一直来。

## 成本日志

每次 AI CLI 调用的 token 用量（如果你的 CLI 输出）会打到
`~/.ai-desk-card-refresh.log` 的 `[cost]` 行。每周看一眼，如果超预算就要
换更便宜的模型或者拉长 cron 间隔。

## 进阶：让设备主动告诉 cron 跳过

设备端 v0.6.4+ 会上报 `battery_pct`。如果电量 < 15% 你可以让
`refresh_loop.sh` 跳过这次刷新（少一次全屏刷 ≈ 续航多 1-2 天）。

```bash
# 在 refresh_loop.sh 里
BATTERY=$(curl -sf http://127.0.0.1:9877/pair-status | python3 -c 'import sys,json; print(json.load(sys.stdin).get("battery_pct") or 100)')
if [[ "$BATTERY" -lt 15 ]]; then
  echo "[skip] battery low ($BATTERY%); skipping refresh" >&2
  exit 0
fi
```
