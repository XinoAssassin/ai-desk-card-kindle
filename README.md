# Kindle Desk Card · 越狱 Kindle 桌面副屏

把一台闲置的越狱 Kindle Paperwhite 3 立在显示器旁边，作为 ambient 桌面状态屏，显示日程 / 任务 / 邮件 / 天气。Mac 渲染 PNG，Kindle 通过 USB 网络每 2 分钟拉一次。

> 🌏 **English: [README.en.md](./README.en.md)**

```
┌──────── Mac ────────┐                  ┌──── Kindle (USB-Eth) ────┐
│ launchd refresh.py  │                  │ upstart                  │
│   ├─ weather        │   POST /widget   │  └─ poll.sh              │
│   ├─ exchange-cal   │ ───────────────► │       wget PNG          │
│   ├─ lark-tasks     │                  │       eips -f -g        │
│   └─ exchange-inbox │                  │                          │
│       │             │                  │                          │
│ launchd daemon.py   │   GET frame.png  │                          │
│   render → frame.png│ ◄─────────────── │                          │
│   render_sleep      │                  │                          │
│     → sleep.png     │                  │                          │
│  (Mac 锁屏时返回)    │                  │                          │
└─────────────────────┘                  └──────────────────────────┘
```

## 你需要什么

- **越狱的 Kindle Paperwhite 3** (5.14.x)，已装 KUAL + USBNetwork
- **Mac**（任意 macOS，开发机常驻；Mac 睡眠时 Kindle 保留最后一帧）
- **USB 数据线** — 既供电又走网络（不依赖公司 Wi-Fi）
- **Python 3.10+** 在 Mac 上

## 数据源

| Slot | 默认 adapter | 备选 | 说明 |
|------|-------------|------|------|
| `weather`  | `weather`           | —                  | Open-Meteo 免 key，含 AQI / 体感 / 降雨 / 日出日落 |
| `calendar` | `exchange_calendar` | `lark_calendar`    | EWS NTLM（公司 Exchange）/ lark-cli +agenda |
| `tasks`    | `lark_tasks`        | —                  | lark-cli +get-my-tasks |
| `inbox`    | `exchange_inbox`    | `gmail`            | EWS 5 封最新 / Gmail API OAuth |

数据源用 `~/.config/kindle-desk-card/sources.json` 配置，缺省使用默认：

```json
{
  "weather":  "weather",
  "calendar": "exchange_calendar",
  "tasks":    "lark_tasks",
  "inbox":    "exchange_inbox"
}
```

设为 `null` 跳过：`"tasks": null` 会让任务区显示"暂无数据"占位。运行 `python kindle-daemon/config.py` 检查当前生效配置。

## 安装

### 1. Clone + venv

```bash
git clone https://github.com/XinoAssassin/ai-desk-card-kindle ~/Develop/ai-desk-card-kindle
cd ~/Develop/ai-desk-card-kindle/kindle-daemon
python3 -m venv .venv
.venv/bin/pip install pillow exchangelib  # gmail 用户加: google-auth-oauthlib google-api-python-client
```

### 2. 字体

下载 Noto Sans CJK SC 三种字重到 `kindle-daemon/fonts/`：

```bash
cd kindle-daemon/fonts
for w in Regular Medium Bold; do
  curl -sSL -o "NotoSansCJKsc-$w.otf" \
    "https://raw.githubusercontent.com/googlefonts/noto-cjk/main/Sans/OTF/SimplifiedChinese/NotoSansCJKsc-$w.otf"
done
```

### 3. 凭证

按选用的 adapter 放到 `~/.config/kindle-desk-card/`（权限 0600）：

- **Exchange**：`exchange.env` —
  ```
  EXCHANGE_EMAIL=you@example.com
  EXCHANGE_USERNAME=you@example.com
  EXCHANGE_PASSWORD=xxx
  EXCHANGE_SERVER=mail.example.com
  ```
- **Gmail**：`client_secret.json`（Google Cloud 创建桌面 OAuth client），第一次跑触发浏览器授权，token 写入 `gmail_token.json`
- **Lark**：先跑一次 `lark-cli auth login`

### 4. USB Ethernet

把 Kindle 用数据线插 Mac。系统设置 → 网络 → 看到 "RNDIS/Ethernet Gadget"：

- Mac 端配置静态 IP `192.168.15.201/24`
- Kindle 端的 IP 是 `192.168.15.244`（USBNetwork 默认）
- `ssh root@192.168.15.244`（密码 `mario`）确认能连

### 5. Mac launchd

放两个 plist 到 `~/Library/LaunchAgents/`，把 `<you>` 替换成自己的用户名：

`com.kindle-desk-card.daemon.plist`：
```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>com.kindle-desk-card.daemon</string>
  <key>ProgramArguments</key><array>
    <string>/Users/&lt;you&gt;/Develop/ai-desk-card-kindle/kindle-daemon/.venv/bin/python</string>
    <string>/Users/&lt;you&gt;/Develop/ai-desk-card-kindle/kindle-daemon/daemon.py</string>
  </array>
  <key>WorkingDirectory</key><string>/Users/&lt;you&gt;/Develop/ai-desk-card-kindle/kindle-daemon</string>
  <key>RunAtLoad</key><true/>
  <key>KeepAlive</key><true/>
  <key>ThrottleInterval</key><integer>10</integer>
  <key>StandardOutPath</key><string>/tmp/kindle-daemon.log</string>
  <key>StandardErrorPath</key><string>/tmp/kindle-daemon.log</string>
</dict></plist>
```

`com.kindle-desk-card.refresh.plist`：
```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>com.kindle-desk-card.refresh</string>
  <key>ProgramArguments</key><array>
    <string>/Users/&lt;you&gt;/Develop/ai-desk-card-kindle/kindle-daemon/.venv/bin/python</string>
    <string>/Users/&lt;you&gt;/Develop/ai-desk-card-kindle/kindle-daemon/refresh.py</string>
  </array>
  <key>WorkingDirectory</key><string>/Users/&lt;you&gt;/Develop/ai-desk-card-kindle/kindle-daemon</string>
  <key>StartInterval</key><integer>120</integer>
  <key>RunAtLoad</key><true/>
  <key>EnvironmentVariables</key><dict>
    <key>PATH</key><string>/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin</string>
  </dict>
  <key>StandardOutPath</key><string>/tmp/kindle-refresh.log</string>
  <key>StandardErrorPath</key><string>/tmp/kindle-refresh.log</string>
</dict></plist>
```

加载：
```bash
launchctl load -w ~/Library/LaunchAgents/com.kindle-desk-card.daemon.plist
launchctl load -w ~/Library/LaunchAgents/com.kindle-desk-card.refresh.plist
```

### 6. Kindle 端

```bash
# 推 KUAL 扩展
scp -r kindle/extensions/desk-card root@192.168.15.244:/mnt/us/extensions/

# 装开机自启 (upstart)
scp kindle/upstart/kindle-desk-card.conf root@192.168.15.244:/tmp/
ssh root@192.168.15.244 '
  mount -o remount,rw / &&
  cp /tmp/kindle-desk-card.conf /etc/upstart/ &&
  mount -o remount,ro /
'
```

Kindle 重启后 upstart 自动启动 poll 循环。KUAL 菜单也提供 Start / Stop / Status / Redraw 入口。

## 锁屏行为

Mac 锁屏时 daemon 通过 `ioreg IOConsoleLocked` 检测到，下次 Kindle poll 会拿到一张只显示天气的精简卡（`render_sleep`）。解锁后下次 poll 切回完整 dashboard。切换延迟 = 一个 Kindle poll 周期（≤2min）。

## 验证 / 调试

```bash
# 当前生效的数据源配置
.venv/bin/python kindle-daemon/config.py

# 手动触发一次完整刷新
.venv/bin/python kindle-daemon/refresh.py

# 只刷某个 slot
.venv/bin/python kindle-daemon/refresh.py --only weather

# Daemon 健康检查
curl -s http://192.168.15.201:9878/health | jq

# 直接抓当前 frame
curl -s http://192.168.15.201:9878/kindle/frame.png > /tmp/preview.png && open /tmp/preview.png

# 改动 render.py 后必须 kickstart 让 launchd 重新 import
launchctl kickstart -k gui/$UID/com.kindle-desk-card.daemon
```

## 已知问题

- **公司网络外**: Exchange 在内网，无 VPN 时 calendar/inbox 失败；weather/tasks 仍能跑（每个 adapter 独立容错）
- **OTA 升级**: Kindle 系统升级会清空 `/etc/upstart/kindle-desk-card.conf`，重新跑安装第 6 步即可
- **lipc preventScreenSaver**: 不要用 — 在 KPW3 5.14.x 上会锁死电源键；接受默认 10-15min 自动锁屏，下次 poll 覆盖锁屏图

## 鸣谢

本仓库的渲染思路 + widget 契约源自 [op7418/ai-desk-card](https://github.com/op7418/ai-desk-card)（M5Paper 版本）。Kindle port 完全独立实现，不共享代码。
