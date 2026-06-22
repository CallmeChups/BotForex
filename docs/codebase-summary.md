# BotForex - Tóm Tắt Codebase

**Cập Nhật Lần Cuối**: 2026-06-21
**Phiên Bản**: 0.2.0
**Trạng Thái**: Production-ready (multi-strategy)

## Tổng Quan Project

BotForex là ứng dụng Streamlit đa trang cho phép quản lý, backtest và vận hành nhiều bot giao dịch MT5 tự động. Hỗ trợ hai chiến lược: **Master Candle** (vào lệnh theo giờ cố định) và **FEG EMA21** (quét pattern 2 nến liên tục với bộ lọc EMA21).

## Cấu Trúc Thư Mục

```
E:\Project\BotForex\
├── app.py                        # Streamlit entry point (auth gateway + home)
├── pages/                        # Multi-page UI
│   ├── 1_Bots.py                 # Quản lý bot (start/stop/restart)
│   ├── 2_Orders.py               # Lịch sử lệnh MT5
│   ├── 3_Signals.py              # Tín hiệu giao dịch
│   ├── 4_Strategies.py           # Xem cấu hình strategy (read-only)
│   ├── 5_Backtest.py             # Backtest engine UI
│   ├── 6_Simulation.py           # Mô phỏng
│   ├── 7_Users.py                # Quản lý người dùng (admin)
│   └── 8_Settings.py             # Cài đặt hệ thống
│
├── src/                          # Core modules
│   ├── auth.py                   # Xác thực (streamlit-authenticator)
│   ├── backtest.py               # Backtest engine (Master Candle + FEG)
│   ├── backtest_history.py       # Lưu/đọc lịch sử backtest (JSON + Excel)
│   ├── bot_manager.py            # Quản lý subprocess bot
│   ├── bot_runner.py             # Live bot runner (MT5 loop, argparse entry)
│   ├── calculation.py            # Chỉ báo kỹ thuật (MACD, Stoch, MA, EMA)
│   ├── feg_strategy.py           # FEG pattern detection + signal builder
│   ├── orders.py                 # Đặt lệnh MT5 (place_order, close_position)
│   ├── strategy.py               # Hàm strategy chung
│   ├── strategy_manager.py       # Đọc YAML strategy → params dict
│   ├── telegram.py               # Gửi thông báo Telegram
│   └── utils.py                  # Tiện ích: get_pip_value, check_exit, compute_trade_levels
│
├── strategies/                   # Strategy YAML definitions
│   ├── master_candle.yaml        # Master Candle strategy config
│   └── feg_ema21.yaml            # FEG EMA21 strategy config
│
├── tests/                        # Pytest test suite (25 tests)
│   ├── test_feg_strategy.py      # 9 tests: detect_feg_signal + analyze_feg
│   ├── test_trade_levels.py      # 3 tests: compute_trade_levels
│   ├── test_backtest_time_characterization.py  # 1 characterization test
│   ├── test_backtest_feg.py      # 2 tests: FEG backtest path
│   ├── test_strategy_manager_feg.py  # 2 tests: strategy params
│   ├── test_place_order.py       # 2 tests: test/live mode gate
│   ├── test_feg_runner.py        # 2 tests: live runner entry logic
│   ├── test_bot_command.py       # 2 tests: bot_manager command builder
│   ├── test_history_columns.py   # 1 test: EMA columns in history
│   └── test_smoke.py             # 1 test: import sanity
│
├── config/
│   ├── auth.yaml                 # User accounts (streamlit-authenticator)
│   └── auth.yaml.example         # Template
│
├── data/
│   └── backtest_history.json     # Lịch sử backtest (auto-created)
│
├── logs/                         # Bot log files (auto-created)
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
- `calculate_flex_lot_size()`: tính lot theo risk %.

### `src/backtest_history.py`
Lưu/đọc kết quả backtest vào `data/backtest_history.json`.
- `save_backtest_result()`, `get_history()`, `delete_history_record()`.
- `history_to_dataframe()`: chuyển sang DataFrame với cột EMA (Entry Type, EMA Period, EMA Dist).
- `create_excel_export()`: xuất Excel 2 sheet (Config+Summary, Trades).
- `HISTORY_COLUMNS`: dict định nghĩa nhóm cột cho UI.

### `src/bot_manager.py`
Quản lý subprocess bot. Bot state lưu trong `data/running_bots.json`.
- `start_bot()`: build command → subprocess.
- `stop_bot()`, `restart_bot()`.
- `build_bot_command()`: tổng hợp args (bao gồm `--ema_period`, `--ema_distance_enabled`, `--ema_distance_pips`).

### `src/bot_runner.py`
Live runner chạy như subprocess (argparse entry point). Dispatch theo `entry_type`:
- Master Candle: `run_master_candle_bot()`.
- FEG: `run_feg_bot()` — vòng lặp liên tục, lấy 2 nến đóng gần nhất + EMA, gọi `analyze_feg`, gate `active_trade`, `place_order(test=...)`.
- `get_recent_candles()`: lấy N nến từ MT5, bỏ nến đang chạy.
- `feg_entry_decision()`: trả None nếu đang có lệnh.

### `src/feg_strategy.py`
Logic phát hiện FEG pattern:
- `detect_feg_signal(candle1, candle2, ema2, pip_value, ema_distance_enabled, ema_distance_pips) -> "BUY"|"SELL"|None`
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
`send_message(msg, chat_id, ...)` với retry tối đa 5 lần. Token đọc từ env `TELEGRAM_BOT_TOKEN`.

## Strategies YAML

### `strategies/master_candle.yaml`
```yaml
entry:
  type: time         # discriminator
  timeframe: M5
  time: "21:05"
  timezone: "Asia/Ho_Chi_Minh"
```

### `strategies/feg_ema21.yaml`
```yaml
entry:
  type: pattern      # discriminator
  timeframe: M5
  pattern: feg_ema21
  ema_period: 21
  ema_distance: {enabled: false, pips: 0}
exit:
  tp: {type: price_based}
  sl: {type: close_based}
  time_limit: {enabled: true, max_candles: 7}
parameters:
  rr_ratio: 2.0
  buffer_k: 5
  lot_size: 0.01
symbols: [XAUUSD, BTCUSD, ETHUSD, XAUUSDm, BTCUSDm, ETHUSDm]
```

## Magic Numbers

| Magic | Strategy |
|-------|----------|
| 210500 | Master Candle |
| 212100 | FEG EMA21 |

## Công Nghệ Stack

| Thành phần | Thư viện | Phiên bản |
|-----------|---------|---------|
| Dashboard | Streamlit | 1.52.2 |
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
25 passed in ~2.2s
```

| File test | Nội dung |
|-----------|---------|
| test_feg_strategy.py | detect_feg_signal (7 cases), analyze_feg (2 cases) |
| test_trade_levels.py | compute_trade_levels BUY/SELL/range_percent |
| test_backtest_feg.py | EMA blocks SELL; EMA below L2 → SELL fires |
| test_backtest_time_characterization.py | Master Candle backward-compat lock |
| test_strategy_manager_feg.py | FEG params + master_candle defaults |
| test_place_order.py | test mode short-circuit; live mode mock |
| test_feg_runner.py | entry when flat+pattern; no entry when active_trade |
| test_bot_command.py | EMA flags in command; disabled EMA = 0 |
| test_history_columns.py | EMA columns in history_to_dataframe |
| test_smoke.py | import sanity |

## Vấn Đề Bảo Mật

| Mức | Vấn đề | Trạng thái |
|-----|--------|-----------|
| ⚠️ Medium | `config/auth.yaml` (MT5 credentials) được track trong git | Cần `git rm --cached` + rotate password |
| ✅ | Telegram token đọc từ env `TELEGRAM_BOT_TOKEN` | OK |
| ✅ | MT5 credentials đọc từ `config/auth.yaml` (không hardcode) | OK |

## Tài Liệu Liên Quan

- [Project Overview & PDR](./project-overview-pdr.md)
- [System Architecture](./system-architecture.md)
- [Project Roadmap](./project-roadmap.md)
- [Code Standards](./code-standards.md)
