# AI Desk Card · 工程交接

> 给下一个接手项目的人。读完应该能：跑起来、定位 bug、加 widget、改架构。
> 前置阅读：[README.md](./README.md) 看产品定位，[PRODUCT.md](./PRODUCT.md) 看为什么这样设计。

---

## 当前版本 (v0.9)

- **固件**：`CARD_VERSION = "0.8.0"`（platformio.ini 里 `-DCARD_VERSION`），代码已加入 v0.9 触屏 poll / chip 反色 / WiFi 回程 POST，下次发版改成 0.9.0
- **daemon**：Python 3.10+（BLE 路径用了 `match` 语句）。`plugin/scripts/start.sh` 优先选 PlatformIO 自带的 3.14，没有就用系统 `python3`
- **Skill 入口**：根 `SKILL.md` 是 agent-agnostic 主入口，**不是** `plugin/plugin.json`。plugin/ 目录是 Claude Code slash 命令兼容层
- **传输优先级**：Wi-Fi (HTTP) > USB serial (115200 baud chunked JSON) > BLE (NUS chunked JSON，仅小命令；**frame data 还是断的**，见已知问题)
- **三种供电模式**全部端到端验过：A 常插电 Wi-Fi 长开 / B USB only / C 电池 + BLE 待机 + Wi-Fi 按需唤醒

---

## 一图看懂架构

```
                ┌──────────────────────────────────────────────┐
                │ M5Paper V1.1 · ESP32 · 8 MB PSRAM · 16 MB flash │
                │                                              │
                │  ┌── ble_bridge ──┐  ┌── wifi_bridge ──┐    │
                │  │ NUS GATT       │  │ NVS creds       │    │
                │  │ pair + passkey │  │ connect SM      │    │
                │  └────────────────┘  └─────────────────┘    │
                │  ┌── http_server (:9880) ─────────────────┐ │
                │  │ POST /frame  POST /cmd  GET /status   │ │
                │  │ + 缓存 daemon 的 peer IP                │ │
                │  │ + httpPostJsonToDaemon() 回程通道       │ │
                │  └──────────────┬─────────────────────────┘ │
                │  ┌──────────────▼ frame_receiver ────────┐  │
                │  │ 259 200 B PSRAM buffer + display      │  │
                │  │ full + region update                  │  │
                │  └───────────────────────────────────────┘  │
                │  ┌── pollTouchAndEmit (50 Hz, GT911) ──┐    │
                │  │ → {event:touch,x,y} via Serial+BLE+HTTP │
                │  │ + 本地 flashChipAck (A2 partial)        │
                │  └─────────────────────────────────────┘    │
                │  ┌── M5GFX → 540×960 e-ink panel (4bpp) ─┐  │
                │  └──────────────────────────────────────┘  │
                └──────────────────────────────────────────────┘
                                  ▲ (any of)
                                  │
   ┌──────────────────────────────┴──────────────────────────────┐
   │ daemon/card_daemon.py (HTTP API @ 127.0.0.1:9877)            │
   │                                                              │
   │  TRANSPORT (one of):                                         │
   │    WiFiTransport ── HTTP POST /frame (raw 4bpp)             │
   │    SerialTransport ─ chunked JSON @ 115200                  │
   │    BLETransport ──── chunked JSON @ NUS (frame data broken) │
   │                                                              │
   │  当 Wi-Fi 是主 transport，且 USB 也插着：                      │
   │    _start_side_serial_reader() 另开只读 serial 收 status     │
   │                                                              │
   │  CardHandler routes:                                         │
   │    POST /widget         → WIDGET_CACHE + schedule_push       │
   │    POST /widgets/preview → render PNG                        │
   │    POST /provision-wifi → forward cmd:wifi_set 给设备         │
   │    POST /sleep          → 渲染名片 + cmd:sleep_now            │
   │    POST /refresh        → schedule_push                       │
   │    POST /firmware-probe → cmd:ping/owner，2.5s 等 ack         │
   │    POST /status_report  → 设备回包，更新 DEVICE_TELEMETRY      │
   │    POST /touch          → hit-test VIEW_HOT_ZONES → dispatch  │
   │    GET  /pair-status    → {connected, transport}              │
   │    GET  /heartbeat      → {alive, last_seen_s, active_xport} │
   │                                                              │
   │  后台线程：                                                    │
   │    push_loop          coalesce dirty flag → render+push      │
   │    keepalive_loop     5 min idle 重推一次防丢                  │
   │    _burst_power_down_loop  arch C linger 后断 Wi-Fi          │
   │    _quiet_hours_loop  到 quiet_hours.start 自动 sleep         │
   │                                                              │
   │  RX listeners (on_rx_byte → 解析 JSON 行 → 派发):              │
   │    _telemetry_listener  ack:status → DEVICE_TELEMETRY        │
   │    _touch_event_listener  event:touch → _internal_dispatch   │
   │                                                              │
   │  渲染：                                                        │
   │    card_render.render_image()       widget 视图               │
   │      + LAST_BOTTOM_BAR_HOT_ZONES 导出给 daemon                │
   │    card_render_settings.render_settings_page()  设置页        │
   │    card_render_sleep                电子名片                  │
   └──────────────────────────────────────────────────────────────┘
                                  ▲
                                  │ POST / curl
   ┌──────────────────────────────┴──────────────────────────────┐
   │ Skill (根 SKILL.md) — agent 主入口                           │
   │                                                              │
   │  1. 收到 trigger → bash scripts/state.sh 探测                 │
   │  2. 按决策表选 flows/0X_*.md 子流程                            │
   │  3. flows/*.md 描述 agent 该做啥（curl / shell / ask 用户）    │
   │                                                              │
   │  state.sh 输出 JSON:                                          │
   │    hardware {pio, m5paper_usb}                                │
   │    firmware {flashed, ours, version}                          │
   │    daemon   {running, pid}                                    │
   │    transport {connected, type}                                │
   │    device   {alive, last_seen_s, active_transport, battery}  │
   │    wifi     {provisioned, ip, port}                          │
   │    interests {configured, path}                              │
   └──────────────────────────────────────────────────────────────┘
```

---

## 仓库布局

```
ai-desk-card/
├── SKILL.md                  ← agent 入口
├── scripts/state.sh          ← 状态探测，组合 probe.sh + heartbeat + interests
├── flows/0[1-7]_*.md         ← 7 个子流程
├── plugin/                   ← Claude Code 兼容层
│   ├── plugin.json           ← 给 Claude Code 识别
│   ├── commands/             ← /card-* slash 命令
│   ├── scripts/              ← start.sh / stop.sh / status.sh / install.sh
│   └── skills/               ← sub-skill (主 SKILL.md 引用其中部分内容)
│       ├── card-onboard/scripts/probe.sh     ← 被 state.sh 包了一层
│       ├── card-widget/schemas/*.schema.json ← 16 widget 的 JSON schema
│       ├── card-widget/themes/               ← Pillow 主题
│       ├── card-wifi-setup/                  ← Wi-Fi 配网入口
│       └── card-refresh/                     ← cron 兜底 + AI loop
├── daemon/
│   ├── card_daemon.py         ← 主进程
│   ├── card_render.py         ← widget 视图渲染 (1055 行)
│   ├── card_render_settings.py ← 设置页渲染
│   └── card_render_sleep.py    ← 名片渲染
├── src/                       ← 固件
│   ├── main.cpp               ← 命令派发 + loop + 触屏 poll + sleep
│   ├── frame_receiver.{h,cpp} ← PSRAM 帧缓冲 + 显示
│   ├── http_server.{h,cpp}    ← :9880 HTTP server + 回程 POST helper
│   ├── ble_bridge.{h,cpp}     ← NUS GATT + 配对
│   ├── wifi_bridge.{h,cpp}    ← NVS creds + 连接状态机
│   └── widgets.{h,cpp}        ← v0.5 fallback (基本废弃)
├── assets/profile.yaml        ← 你的电子名片
├── data/cjk.ttf               ← 烧到 LittleFS
├── partitions.csv             ← 给 CJK 字体留分区
└── platformio.ini             ← env:card
```

---

## v0.9 端到端验证（开发机起步流程）

```bash
# 1. 装 PlatformIO（系统级一次）
pipx install platformio

# 2. clone 项目
git clone https://github.com/op7418/ai-desk-card.git
cd ai-desk-card

# 3. 编译（首次会拉 ESP32 toolchain，~5min）
pio run -e card

# 4. 设备 USB 连接，烧 CJK 字体（首次必须）
pio run -e card -t uploadfs

# 5. 烧固件
pio run -e card -t upload

# 6. 启动 daemon
bash plugin/scripts/start.sh

# 7. 看状态
bash scripts/state.sh | python3 -m json.tool

# 8. 推个测试 widget
curl -X POST http://127.0.0.1:9877/widget \
  -H 'Content-Type: application/json' \
  -d '{"slot":"top-left","type":"scratch","data":{"text":"hello"}}'

# 9. 看屏上预览
curl -X POST http://127.0.0.1:9877/widgets/preview -o /tmp/p.png && open /tmp/p.png
```

---

## 已知问题 + 解决方案

### 1. BLE frame-data 路径断了

**症状**：BLE 命令（owner / ping / wifi_set）能通；frame_chunk 写入 daemon 端完成，但设备 `onWrite` 不触发。

**Workaround**：用 Wi-Fi 推帧（架构 A 或 C）。BLE 只用作小命令通道。

**根因**（未确认）：NUS 长写包在 ESP32-NimBLE 栈下的 fragment 重组可能丢字节。需要抓包确认。

### 2. M5Paper V1.1 长按旋钮 2s = 关机

V1.1 砍掉了侧按键，改用旋转编码器。旋钮长按 2s 直接被 AXP192 切电源 — **固件来不及拦截**。

**影响**：cmd:sleep_now 走的是 `esp_deep_sleep_start()`，名片渲染 → settling → 进 deep sleep 全程 OK。但用户硬关机时屏上停在关机前那一帧，**不是名片**。

**Plan C（未做）**：在 setup() 拦截 AXP power button 长按 ISR，先发 cmd:want_sleep → daemon 推名片 → 再 deep sleep。约 100 行 + 时序调整。

### 3. GT911 IRQ 在 V1.1 不稳定，必须直接 poll

GT911 INT 接 GPIO 36（input-only，无内部上拉）。`M5.TP.available()` 在我们这块板上几乎不返回 true。改成 50 Hz 直接 `M5.TP.update()` 轮询 I2C。开销 ~1ms/poll，可忽略。

### 4. `GT911::getFingerNum()` 释放后返回 stale 值

M5EPD 库的 GT911::update() 在新数据 num=0 时只置 `_is_finger_up=true`，**`_num` 不重置**。所以 `getFingerNum() > 0` 在 finger lift 之后还是 true。

**正确检测**：用 `(getFingerNum() > 0) && !isFingerUp()` 作为 "fresh press"。release 检测用 "最近 200ms 没有 fresh press" 作为超时。`isFingerUp()` 是 flag-consuming，调一次就清。

### 5. `WiFiTransport.connected()` sticky-false

之前 `connected()` 只看 `_connect_ok` 缓存。单次 POST 超时（比如 cmd:sleep_now 时设备已经在 deep_sleep settling）就把 `_connect_ok` 锁死成 False，后续所有 push 都被 `push_loop` 的 `if not TRANSPORT.connected()` 跳过 → 永久 deadlock。

**修复**：`connected()` 缓存为 False 时主动开一个 0.5s TCP probe 重测（card_daemon.py:194）。

### 6. mDNS 探测 2.5s 太短

设备刚 reboot → Wi-Fi reassoc → mDNS advertise 总共 ~5-6s。daemon 重启时如果只等 2.5s 找不到 peer，会降级到 USB serial（32s 一帧）。**改成 8s**（card_daemon.py:1378）。

### 7. 持久化 last_frame.png 不识别设备重启

daemon 起来从磁盘 load `${TMPDIR}/ai_desk_card_last_frame.png`，以为是设备当前画面。但设备如果在两次 daemon 启动之间 reboot 过，实际画面是 boot splash。diff 结果是 144×33 的底栏，daemon 只推了那一小块 → 设备永远卡 splash。

**修复**：`_telemetry_listener` 现在在收到第一个 status_report 且 uptime<60s 时，主动 `reset_frame_diff() + schedule_push()` 强推全帧。

### 8. Arch A 没回程通道

当 TRANSPORT 是 WiFiTransport 时，daemon 没监听 Serial/BLE，**收不到设备的 status_report**。所以 device.alive 永远 false。

**修复 1**：firmware 在 wifi_connected 时也 POST `/status_report` 给 daemon（IP 从最近的 inbound /frame 请求 cache）。

**修复 2**：daemon 启动时如果 TRANSPORT 是 WiFi 且 USB 也插着，开 `_start_side_serial_reader()` 只读 serial 当回程通道。

两种修复并存，任意一个生效都能让 heartbeat 工作。

### 9. ESP32 baud 切换不可靠

不要在固件里中途切 Serial baud。固件 + daemon 都固定 115200。

### 10. 默认 partition table 不够大

我们改了 `partitions.csv` 给 LittleFS 留了 1.5MB（CJK 字体 ~1MB）。如果 board upload max_size 报错，先 `pio run -e card -t erase` 再 `uploadfs`+`upload`。

### 11. CJK TTF glyph 黑名单

`data/cjk.ttf` 不包含 ▢ ▶ ✎ ♪ ↑ ↓ ● ○ — … °。`PIL.textlength()` 对 missing glyph 撒谎导致 overflow，最后看到 widget 裁掉一半。

**注意**：daemon 渲染时用的是 PingFang（系统字体），有这些 glyph；只有固件本地渲染（boot splash、passkey overlay、chip flash）受 cjk.ttf 限制。

---

## 调试 recipes

### "Daemon 起不来"

```bash
tail -30 "${TMPDIR:-/tmp}/ai_desk_card_daemon.log"
```

常见：

- Serial port 被别的进程占（`lsof /dev/cu.usbserial-*`）
- Python 3.10+ 缺失（BLE 路径要 match 语句）
- 9877 端口占用（`lsof -i :9877`）

### "设备在但 device.alive=false"

```bash
curl http://127.0.0.1:9877/heartbeat | python3 -m json.tool
```

- 主 TRANSPORT 是 Wi-Fi 且没 side-serial → 看 daemon 日志有没有 `[side-serial] reading` 行；没有就 daemon 启动时 USB 还没插，重启 daemon
- 主 TRANSPORT 是 Wi-Fi 但 firmware 没把 daemon IP 缓存上 → 让 daemon 先推一次 frame（任何 widget 都行）；设备收到 /frame 时缓存 peer IP，下一个 status_report 自然回 POST
- `device.last_seen_seconds > 90` → 设备睡死了/没电了/掉 Wi-Fi 了

### "推完 widget 屏幕没变"

```bash
tail -50 "${TMPDIR:-/tmp}/ai_desk_card_daemon.log" | grep -E "frame|render|diff"
```

- `[render] no pixel change` → 你推的 widget 跟当前一模一样，daemon diff 觉得没变。换内容或先 DELETE /widget?slot=X 清掉
- `[diff] region (..) ...` 但屏上没动 → 设备 chunk 解码失败，看 device 日志的 `[frame] CRC mismatch` 或 `base64 decode err`
- `[wifi] frame: TimeoutError` → 设备 HTTP server 没响应；多半是 deep sleep 或 Wi-Fi 掉了

### "触屏没反应"

```bash
tail -f "${TMPDIR:-/tmp}/ai_desk_card_daemon.log" | grep -E "touch"
```

按一下屏，看：

1. `[dev<] [touch-debug] press x=.. y=..` — firmware 检测到 finger down 了吗
2. `[dev<] [touch-debug] release x=.. y=.. hold=..` — 检测到 lift 了吗
3. `[dev<] {"event":"touch",...}` 或 `[touch<] (..,..)` — event 上来了吗
4. `[touch<] → settings` 或 `→ no zone match` — 派发结果

每一步缺失对应不同 bug 域：1 缺 = GT911 I2C；2 缺 = 释放检测；3 缺 = serial/wifi 回程；4 缺 = VIEW_HOT_ZONES 没设置或 chip rect 不覆盖按下位置。

### "想看屏上当前是什么"

```bash
curl -X POST http://127.0.0.1:9877/widgets/preview -o /tmp/p.png && open /tmp/p.png
```

走的是 daemon 的 `_widget_snapshot()` + render_image()，跟实际推的帧一致（设置页和 sleep card 用各自的 render 函数，preview 只渲染 widget 视图）。

### 看实际推到设备上的帧

daemon 启动时从磁盘 load 最后一帧，正常路径下也会持久化到：

```bash
ls -la "${TMPDIR:-/tmp}/ai_desk_card_last_frame.png"
open "${TMPDIR:-/tmp}/ai_desk_card_last_frame.png"
```

注意：sleep card 推完后**不**写这个文件，所以 last_frame 反映的是 widget 视图，不是真实屏上画面。

---

## 加一个新 widget 类型

1. **写 schema**：`plugin/skills/card-widget/schemas/<name>.schema.json`（参考 weather）
2. **加到白名单**：`daemon/card_daemon.py:84` 的 `WIDGET_TYPES` 元组
3. **写 painter**：`daemon/card_render.py` 加一个 `paint_<name>(d, rect, data, stale)` 函数 + 注册到 `PAINTERS` dict
4. **加 README 给 agent 看**：`flows/05_push.md` 的 widget 类型表加一行
5. **测试**：`curl -X POST /widgets/preview` 看效果，先不要推真机
6. **glyph 检查**：你用的所有 unicode 字符都在 PingFang 里吗？（不在的话用 ASCII 替代或选另一个字体）

不需要改固件 —— 服务端渲染，固件只 blit 像素。

---

## 改架构时注意

- **新 cmd 加在哪**：`src/main.cpp` 的 `dispatchCmd()` 里 if-else。daemon 通过 `send_line({"cmd": ...})` 推。daemon 一侧不需要专门 hook，cmd 本身是 fire-and-forget 的；如果要 ack，firmware 在 cmd 处理结尾 `Serial.print` + `bleWrite` 发回去
- **新 daemon endpoint**：`CardHandler.do_POST` / `do_GET` 里加 path 分支。loopback only 是约定（127.0.0.1 bind），别破坏
- **状态加字段**：`DEVICE_TELEMETRY` 是单字典，全局可读；写要小心多线程（telemetry_listener 在 RX 线程，render_and_push 在 push_loop 线程）
- **renderer 改动**：`card_render.py` 用 `importlib.reload` 热加载，每次 render_and_push 都重新 import；改了 daemon 不用重启，但 import 时间不能太长（建议 <100ms）
- **新 transport**：继承 `Transport` 基类，实现 `start(on_byte, on_connect)` / `write(bytes)` / `connected() -> bool`。push_frame_bytes 有 isinstance 分支判断 fast path
- **新 flow**：`flows/0X_<name>.md` 加文件 → SKILL.md 决策表加一行 → state.sh 探测必要字段
- **改 chip 布局**：`daemon/card_render.py:paint_bottom_bar` 改 chip 文案 / rect / action。daemon 自动把新 rect 通过 `cmd:set_chips` 推给 firmware；firmware 自动 hit-test。**别去固件里 hard-code chip 位置**

---

## 性能数字（实测，M5Paper V1.1）

| 操作 | 时间 |
|---|---|
| Wi-Fi HTTP push 全帧 (259200B) | 1.96-2.30 s |
| Wi-Fi HTTP push region (144×33) | 0.09-0.27 s |
| USB serial push 全帧 (chunked 2KB) | 32.62 s |
| USB serial push region (144×33) | <1 s |
| BLE 唤醒 Wi-Fi (架构 C) | 5-6 s |
| Wi-Fi mDNS advertise after reboot | ~5-6 s |
| GT911 一次 I2C poll | ~1 ms |
| Touch press → flashChipAck (A2 partial) | ~150 ms |
| EPD UpdateFull GC16 settling | ~700 ms（sleep_now 用 2500ms 保险）|
| daemon render_image + 4bpp pack | ~50 ms |
| Battery push cost (架构 C, 一次完整唤醒+推) | ~0.2 mAh |

---

## 历史决策（为什么不是别的设计）

**为什么服务端渲染而不是设备端**
设备端要支持任意字号 + 任意 unicode + 美观字体，固件 FreeType + 几兆字体常驻 RAM，光栈就难维护。Server-side 用 Python PIL，行业里 inkbird/Visionect 都这么做。代价是每帧要传 ~100-260KB，Wi-Fi 下没问题，BLE 慢但是 architecture C 的 burst 模式可接受。

**为什么不直接拉开源 EPDGUI 框架**
M5Paper_FactoryTest 的 EPDGUI ~2200 行 MIT 开源，提供完整 GUI 框架。最早想直接拉，但发现：（a）M5Paper V1.1 没侧键，他们的 BtnP 触发器不适用；（b）我们是 server-driven，不需要 GUI 框架；（c）他们的字号策略不适合 30-50cm 桌边瞥一眼场景。最后只借用了几个图标资源。

**为什么 16 个 widget 而不是用户可自定义**
开放 widget 自定义意味着 schema / 渲染 / 版本兼容都要做。先固定 16 个能覆盖 80% 用例的，后续按需扩展。

**为什么不用 OTA**
USB 烧固件 ~1min，Wi-Fi OTA 流程要做 manifest 校验 + sha256 + rollback，复杂度对一个 hobby 项目过高。需要时再做。

**为什么 plugin/ 和 SKILL.md 共存**
SKILL.md 是 agent-agnostic 主入口（Codex/Gemini/Aider 都能识别）。plugin/ 留着是为了 Claude Code 用户的 slash 命令便利（`/card-start` `/card-wifi-setup` 比 "ask agent" 直接）。两层共用底层 scripts，不重复。

---

## 安全 / 隐私

- daemon 绑 **127.0.0.1**（loopback only）。LAN 上的设备 → daemon 回程仅通过 USB serial 侧通道，不开 LAN 端口
- Wi-Fi 密码 → daemon → 设备 NVS 的链路上，**不写任何日志**（grep `daemon/card_daemon.py` 确认）
- 没有任何 telemetry / phone-home。daemon 不联外网（设备的 mDNS 是 LAN broadcast）
- `~/.ai-desk-card/interests.yaml` 包含用户偏好（city / repo path），**不要 commit 到 git**

---

## 下一个版本可能要做的

- **Plan C 硬件关机拦截**：长按旋钮 → 拦 ISR → 推名片 → deep sleep
- **BLE frame-data 修复**：找 NimBLE 长包重组那段 bug，让 architecture C 在 BLE-only 下也能推帧
- **Multi-device sync**：多块 M5Paper 共享 widget cache，不同物理位置显示不同视图
- **Captive portal Wi-Fi setup**：第一次开机起 SoftAP + 网页表单，不用 daemon
- **Inkplate / Waveshare 支持**：抽象掉 panel driver，partition 大小 + 触屏 API 差异隔离
- **Widget marketplace**：让用户提交 widget schema → 审 → 合并

---

## 联系

- Issue / PR: https://github.com/op7418/ai-desk-card
- 原作者: [@op7418](https://github.com/op7418)
