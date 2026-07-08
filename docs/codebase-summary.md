# BotForex - Tóm Tắt Codebase

**Cập Nhật Lần Cuối**: 2026-07-08
**Phiên Bản**: 0.3.1
**Trạng Thái**: Production-ready (CI/CD + Trace IDs + Full Error Coverage + Layout Redesign)

## Tổng Quan Project

BotForex là ứng dụng Streamlit đa trang cho phép quản lý, backtest và vận hành nhiều bot giao dịch MT5 tự động. Hỗ trợ hai chiến lược: **Master Candle** (vào lệnh theo giờ cố định) và **FEG EMA21** (quét pattern 2 nến liên tục với bộ lọc EMA21, cả 2 nến phải cùng hướng). Layout compacted 2 cột với colored section headers và helper functions. Deploy tự động qua GitHub Actions + Tailscale SSH.

## Cấu Trúc Thư Mục

```
E:\Project\BotForex\
├── app.py                        # Streamlit entry point (auth gateway + home)
├── pages/                        # Multi-page UI
│   ├── 1_Bots.py                 # Quản lý bot (start/stop/restart)
│   ├── 2_Orders.py               # Lịch sử lệnh MT5
│   ├── 3_Signals.py              # Tín hiệu giao dịch
│   ├── 4_Strategies.py           # Xem cấu hình strategy (read-only)
│   ├── 5_Backtest.py             # Backtest engine UI (EMA toggle + run_id)
│   ├── 6_Simulation.py           # Mô phỏng
│   ├── 7_Users.py                # Quản lý người dùng (admin)
│   └── 8_Settings.py             # Cài đặt hệ thống
│
├── src/                          # Core modules
│   ├── auth.py                   # Xác thực (streamlit-authenticator)
│   ├── backtest.py               # Backtest engine (Master Candle + FEG + debug fields)
│   ├── backtest_history.py       # Lưu/đọc lịch sử backtest (JSON + Excel)
│   ├── bot_manager.py            # Quản lý subprocess bot
│   ├── bot_runner.py             # Live bot runner (order IDs, full Telegram errors, auto-restart)
│   ├── calculation.py            # Chỉ báo kỹ thuật (MACD, Stoch, MA, EMA)
│   ├── feg_strategy.py           # FEG pattern detection (same-type candle rule)
│   ├── orders.py                 # Đặt lệnh MT5 (place_order, close_position)
│   ├── strategy.py               # Hàm strategy chung
│   ├── strategy_manager.py       # Đọc YAML strategy → params dict
│   ├── telegram.py               # Gửi thông báo Telegram (main + error channel)
│   └── utils.py                  # Tiện ích: get_pip_value, check_exit, compute_trade_levels
│
├── strategies/                   # Strategy YAML definitions
│   ├── master_candle.yaml        # Master Candle strategy config
│   └── feg_ema21.yaml            # FEG EMA21 strategy config (buffer_k=50)
│
├── scripts/                      # Utility scripts
│   ├── verify_backtest.py        # Phase 1 verification: per-trade trace từ MT5 data
│   ├── start_streamlit.bat       # Windows bat để restart Streamlit qua schtasks
│   └── start_streamlit.ps1       # PS1 alternative (có execution policy issue)
│
├── .github/
│   └── workflows/
│       └── deploy.yml            # CI/CD: GitHub Actions → Tailscale SSH → Windows server
│
├── tests/                        # Pytest test suite (25 tests)
│   ├── test_feg_strategy.py      # 9 tests: detect_feg_signal + analyze_feg (same-type fixtures)
│   ├── test_trade_levels.py      # 3 tests: compute_trade_levels
│   ├── test_backtest_time_characterization.py  # 1 characterization test + debug fields
│   ├── test_backtest_feg.py      # 2 tests: EMA blocks SELL; EMA below L2 → SELL (debug fields)
│   ├── test_strategy_manager_feg.py  # 2 tests: strategy params (buffer_k=50)
│   ├── test_place_order.py       # 2 tests: test/live mode gate
│   ├── test_feg_runner.py        # 2 tests: live runner entry logic (same-type fixtures)
│   ├── test_bot_command.py       # 2 tests: bot_manager command builder
│   ├── test_history_columns.py   # 1 test: EMA columns in history
│   └── test_smoke.py             # 1 test: import sanity
│
├── config/
│   ├── auth.yaml                 # User accounts + MT5 credentials (tracked in git, deployed)
│   └── auth.yaml.example         # Template
│
├── data/
│   └── backtest_history.json     # Lịch sử backtest (auto-created, git-ignored)
│
├── logs/                         # Bot log files (auto-created, git-ignored)
├── conftest.py                   # Pytest sys.path setup
├── requirements.txt              # Python dependencies
└── docs/                         # Tài liệu dự án
```

## Module Chi Tiết

### `src/auth.py`
Xác thực người dùng qua `streamlit-authenticator`. Đọc `config/auth.yaml`, expose `get_authenticator()`, `check_auth()`, `get_user_role()`, `is_admin()`.

### `src/backtest.py`
Engine backtest MT5. Entry point: `run_backtest(df, symbol, ..., entry_type)`.
- `entry_type="time"` → Master Candle (tìm nến theo giờ, loop độc lập).
- `entry_type="pattern"` → `_run_feg_backtest()` (while loop tuần tự, 1 lệnh/lúc).
- Helpers dùng chung: `_compute_lot_size`, `_simulate_exit`, `_make_trade`.
- `fetch_historical_data()`: lấy OHLC từ MT5.
- **EMA column**: `df[f"ema{ema_period}"] = ema` — lưu vào `ohlc_data` để chart render EMA overlay.
- **Debug fields per trade** (underscore prefix, trace-only):
  - Master Candle: `_candle: {open, high, low, close}`
  - FEG: `_c1`, `_c2` (OHLC + time), `_ema: float`, `_exit_pos: int`
- **Trace ID**: `run_id = "BT-YYMMDD-HHMMSS-SYMBOL-XXXX"` trong `stats["run_id"]`.

### `src/backtest_history.py`
Lưu/đọc kết quả backtest vào `data/backtest_history.json`.
- `save_backtest_result()`, `get_history()`, `delete_history_record()`.
- `history_to_dataframe()`: chuyển sang DataFrame với cột EMA (Entry Type, EMA Period, EMA Dist).
- `create_excel_export()`: xuất Excel 2 sheet (Config+Summary, Trades).
- `HISTORY_COLUMNS`: dict định nghĩa nhóm cột cho UI.

### `src/bot_manager.py`
Quản lý subprocess bot. Bot state lưu trong `data/running_bots.json` (git-ignored).
- `start_bot()`: build command → subprocess.
- `stop_bot()`, `restart_bot()`.
- `build_bot_command()`: tổng hợp args (bao gồm `--ema_period`, `--ema_distance_enabled`, `--ema_distance_pips`).

### `src/bot_runner.py`
Live runner chạy như subprocess (argparse entry point). Dispatch theo `entry_type`:
- Master Candle: `run_master_candle_bot()`.
- FEG: `run_feg_bot()` — vòng lặp liên tục, lấy 2 nến đóng gần nhất + EMA, gọi `analyze_feg`, gate `active_trade`, `place_order(test=...)`.
- **Order Trace ID**: `order_id = "ORD-YYMMDD-HHMMSS-SYMBOL-XXXX"` — prefix mọi log line, gửi kèm Telegram.
- **Full Telegram error coverage**: mọi lỗi (startup, candle fetch, MT5 loop, signal, order fail, close fail, crash + traceback) đều gửi về `TELEGRAM_ERROR_CHAT_ID`.
- **Auto-restart loop**: `while True` trong `__main__` — catch crash, log, sleep 30s, restart `run_bot()`. Chỉ dừng khi `KeyboardInterrupt`.
- `get_recent_candles()`: lấy N nến từ MT5, bỏ nến đang chạy.
- `feg_entry_decision()`: trả None nếu đang có lệnh.

### `src/feg_strategy.py` (Updated v0.3.1)
Logic phát hiện FEG pattern:
- `detect_feg_signal(candle1, candle2, ema2, pip_value, ema_distance_enabled, ema_distance_pips) -> "BUY"|"SELL"|None`
- **Same-type candle rule (v0.3.0)**: C1 và C2 phải cùng hướng (cả 2 tăng hoặc cả 2 giảm). Mixed-type pair → `None`.
- **Wick formula fix (v0.3.1)**:
  - SELL upper wick: `(h2 - o2)` instead of `(h2 - c2)` — correct for bearish candle
  - BUY lower wick: `(o2 - l2)` instead of `(c2 - l2)` — correct for bullish candle
  - SELL: `not bullish1 and not bullish2` → H2>H1, C2<L1, L2>EMA+dist, wick=(h2-o2)
  - BUY: `bullish1 and bullish2` → L2<L1, C2>H1, H2<EMA-dist, wick=(o2-l2)
- `analyze_feg(...) -> dict | None`: dựng signal đầy đủ (entry/SL/TP) dùng `compute_trade_levels`.

### `src/orders.py`
- `place_order(symbol, direction, volume, sl, tp, credentials, test, magic, comment)`:
  - `test=True` → simulate, không gọi MT5.
  - `test=False` → gọi `mt5.order_send()` thật.
- `close_position_by_ticket()`: đóng lệnh mở bằng ticket.

### `src/strategy_manager.py`
Đọc YAML strategy file → trả dict params đầy đủ:
- `entry_type`, `ema_period`, `ema_distance_enabled`, `ema_distance_pips`, `pattern`.
- `entry_time`, `tp_type`, `sl_type`, `max_candles`, `rr_ratio`, `buffer_k`, `lot_size`, `symbols`.

### `src/utils.py`
- `get_pip_value(symbol)`: pip size (0.01 cho XAU/BTC, 0.0001 cho Forex).
- `check_exit(direction, candle, tp, sl, tp_type, sl_type) -> (exit_type, exit_price)`.
- `compute_trade_levels(direction, candle, entry_mode, entry_percent, buffer_k, rr_ratio, pip_value) -> dict`: tính entry/SL/TP/sl_pips.

### `src/calculation.py`
Chỉ báo kỹ thuật: `calculate_macd()`, `calculate_stoch()`, `calculate_ma()`, `calculate_ema()`, `check_cross_2_list_updated()`.

### `src/telegram.py`
`send_message(msg, chat_id, is_error=False, ...)` với retry tối đa 5 lần. Token đọc từ env `TELEGRAM_BOT_TOKEN`. `is_error=True` → gửi về `TELEGRAM_ERROR_CHAT_ID` thay vì main chat.

## Layout Helpers (v0.3.1)

### `_section_header(title, color)`
HTML-based colored section header (replaces `st.expander`):
- `color` options: `"indigo"` (General), `"emerald"` (Entry), `"amber"` (Order Settings & Risk), `"red"` (Exit)
- Renders: `<h3 style="color: {color}; border-bottom: 2px solid {color}; padding-bottom: 8px">{title}</h3>`

### `_vdivider()`
Vertical CSS divider for 2-column layout:
- Renders: `<div style="width: 100%; height: 100%; border-left: 2px solid #ccc"></div>`

### Main Page Layout (v0.3.1)
2-column structure: `left, _div, right = st.columns([0.58, 0.02, 0.40])`
- **Left (58%)**: General zone + Entry zone
- **Right (40%)**: Order Settings & Risk + Exit zone
- **Entry zone internal split**: FEG Margins + Wick Filter (left) | EMA + Time Window + Entry Mode (right)

### Removed
- **Classic layout variants** — No more separate Compact + Verbose layouts
- **`st.expander` form zones** — Replaced with `_section_header()` HTML colored headers

## Pages Chi Tiết

### `pages/1_Bots.py` (Updated v0.3.1)
- 2-column compacted form layout với colored section headers
- Entry zone: FEG Margins + Wick Filter split horizontally
- Main button: "🚀 Khởi động Bot", caption: "KHỞI ĐỘNG NHANH (TEST)"
- Flash success message via `_flash_success` session state

### `pages/5_Backtest.py` (Updated v0.3.1)
- Hiển thị `run_id` dạng copyable code block sau mỗi backtest.
- **EMA indicator toggle**: detect cột `ema*` trong `ohlc_data`, render expander "Indicators" với checkbox per EMA period. EMA21 = màu #FF6B00.
- `buffer_k` max_value=200.0, default=float(params.get('buffer_k', 5)).
- 2-column layout consistency

## Scripts

### `scripts/verify_backtest.py`
Phase 1 verification: fetch MT5 historical data, chạy backtest cả 2 strategy, in per-trade trace với signal conditions, SL/TP math, exit info. Dùng debug fields (`_c1`, `_c2`, `_ema`, `_exit_pos`) từ backtest engine.
```bash
python scripts/verify_backtest.py --symbol XAUUSD --days 90 --strategy feg
```

### `scripts/start_streamlit.bat`
Được gọi bởi Windows Task Scheduler (`schtasks /Run`) để start/restart Streamlit **tách biệt với SSH session**. Tạo `logs/` nếu chưa có, redirect stdout/stderr vào `logs/streamlit.log`.

## CI/CD Pipeline

### `.github/workflows/deploy.yml`
Manual trigger (`workflow_dispatch`) với input `restart_streamlit` (true/false).

**Steps:**
1. **Tailscale connect** — join tailnet tạm thời (ephemeral auth key từ secret `TAILSCALE_AUTHKEY`)
2. **SSH key setup** — private key từ `DEPLOY_SSH_PRIVATE_KEY` secret
3. **Deploy** — SSH vào `hyperion@100.110.182.114`, PowerShell: `git pull` + `pip install -r requirements.txt`
4. **Restart Streamlit** (nếu chọn): kiểm tra port 8501, dừng process cũ, tạo schtask chạy `start_streamlit.bat`, verify port 8501 sau 12s (fail workflow nếu không lên)

**Secrets cần thiết:**
- `TAILSCALE_AUTHKEY` — ephemeral Tailscale auth key
- `DEPLOY_SSH_PRIVATE_KEY` — SSH private key (public key đặt ở `C:\ProgramData\ssh\administrators_authorized_keys` trên server vì user trong Administrators group)

## Strategies YAML

### `strategies/master_candle.yaml`
```yaml
entry:
  type: time         # discriminator
  timeframe: M5
  time: "21:05"
  timezone: "Asia/Ho_Chi_Minh"
parameters:
  buffer_k: 30
  rr_ratio: 2.0
  lot_size: 0.01
```

### `strategies/feg_ema21.yaml`
```yaml
entry:
  type: pattern      # discriminator
  timeframe: M1
  pattern: feg_ema21
  ema_period: 21
  ema_distance: {enabled: false, pips: 0}
exit:
  tp: {type: price_based}
  sl: {type: close_based}
  time_limit: {enabled: true, max_candles: 7}
parameters:
  rr_ratio: 2.0
  buffer_k: 50        # 50 pips = $5 buffer cho XAUUSD
  lot_size: 0.01
symbols: [XAUUSD, BTCUSD, ETHUSD, XAUUSDm, BTCUSDm, ETHUSDm]
```

## Trace ID System

| Loại | Format | Ví dụ |
|------|--------|-------|
| Backtest Run | `BT-YYMMDD-HHMMSS-SYMBOL-XXXX` | `BT-260627-143022-XAUUSD-A3F1` |
| Live Order | `ORD-YYMMDD-HHMMSS-SYMBOL-XXXX` | `ORD-260627-143022-XAUUSD-B7C2` |

Mục đích: expert copy ID → grep log → thấy toàn bộ action tại thời điểm đó.

## Magic Numbers

| Magic | Strategy |
|-------|----------|
| 210500 | Master Candle |
| 212100 | FEG EMA21 |

## Git-tracked vs Server-local Files

| File | Git | Lý do |
|------|-----|-------|
| `config/auth.yaml` | ✅ tracked | Deployed qua CI/CD |
| `.streamlit/config.toml` | ✅ tracked | Deployed qua CI/CD |
| `data/orders.csv` | ❌ ignored | Runtime state, server-local |
| `data/running_bots.json` | ❌ ignored | Runtime state, server-local |
| `logs/` | ❌ ignored | Log files, server-local |

## Công Nghệ Stack

| Thành phần | Thư viện | Phiên bản |
|-----------|---------|---------|
| Dashboard | Streamlit | 1.52.2+ (v0.3.1: deprecated `use_container_width` → `width` param) |
| Auth | streamlit-authenticator | 0.4.2 |
| MT5 API | metatrader5 | 5.0.5430 |
| Telegram | python-telegram-bot | 22.5 |
| Data | pandas | 2.3.3 |
| Charting | plotly | 6.5.2 |
| Excel | openpyxl | 3.1.2 |
| Config | PyYAML | 6.0.3 |
| Test | pytest | 8.3.4 |
| Env | python-dotenv | 1.2.1 |

## Test Suite

Chạy: `pytest tests/ -v`

```
25 passed in ~0.5s
```

| File test | Nội dung |
|-----------|---------|
| test_feg_strategy.py | detect_feg_signal (7 cases), analyze_feg (2 cases) — all same-type fixtures |
| test_trade_levels.py | compute_trade_levels BUY/SELL/range_percent |
| test_backtest_feg.py | EMA blocks SELL; EMA below L2 → SELL fires; debug fields verified |
| test_backtest_time_characterization.py | Master Candle backward-compat + _candle debug field |
| test_strategy_manager_feg.py | FEG params (buffer_k=50) + master_candle defaults |
| test_place_order.py | test mode short-circuit; live mode mock |
| test_feg_runner.py | entry when flat+pattern; no entry when active_trade — same-type fixtures |
| test_bot_command.py | EMA flags in command; disabled EMA = 0 |
| test_history_columns.py | EMA columns in history_to_dataframe |
| test_smoke.py | import sanity |

## Streamlit API Changes (v0.3.1)

All `use_container_width` deprecated parameter replaced:
- `use_container_width=True` → `width='stretch'`
- `use_container_width=False` → `width='content'`

Applied to all widgets across all pages and app.py:
- `st.button()`, `st.form_submit_button()`
- `st.dataframe()`
- `plotly.streamlit.plotly_chart()`

## Vấn Đề Bảo Mật

| Mức | Vấn đề | Trạng thái |
|-----|--------|-----------|
| ✅ | `config/auth.yaml` tracked và deployed qua CI/CD | OK — intended |
| ✅ | Telegram token đọc từ env `TELEGRAM_BOT_TOKEN` | OK |
| ✅ | MT5 credentials đọc từ `config/auth.yaml` (không hardcode) | OK |
| ⚠️ | SSH private key trong GitHub Secrets | Cần rotate định kỳ |
| ℹ️ | `config/auth.yaml` chứa MT5 password trong git history | Cần cân nhắc nếu repo public |

## Tài Liệu Liên Quan

- [Project Overview & PDR](./project-overview-pdr.md)
- [System Architecture](./system-architecture.md)
- [Project Roadmap](./project-roadmap.md)
- [Code Standards](./code-standards.md)
