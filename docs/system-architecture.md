# BotForex - Kiến Trúc Hệ Thống

**Cập Nhật Lần Cuối**: 2026-06-21
**Phiên Bản**: 0.2.0

## Tổng Quan

BotForex là ứng dụng giao dịch tự động đa chiến lược trên MT5, gồm hai thành phần chính:

1. **Dashboard (Streamlit)** — UI đa trang cho quản lý bot, backtest, cài đặt.
2. **Bot Runner (subprocess)** — Live trading loop chạy tách biệt với MT5.

Hai thành phần giao tiếp qua: `data/running_bots.json` (state), file log, và Telegram.

## Kiến Trúc Tổng Quát

```
┌─────────────────────────────────────────────────────────┐
│                   Streamlit Dashboard                   │
│   app.py (auth) → pages/ (Bots, Backtest, Strategies…) │
│                                                         │
│  ┌────────────┐  ┌──────────────┐  ┌─────────────────┐ │
│  │ 1_Bots.py  │  │ 5_Backtest  │  │ 4_Strategies.py │ │
│  │ Start/Stop │  │ Run + View  │  │ Read-only YAML  │ │
│  └─────┬──────┘  └──────┬──────┘  └─────────────────┘ │
└────────┼────────────────┼─────────────────────────────┘
         │ subprocess     │ MT5 historical data
         ▼                ▼
┌──────────────┐   ┌──────────────────┐
│ bot_runner.py│   │ backtest.py      │
│ (live loop)  │   │ _run_feg_backtest│
│              │   │ run_backtest     │
│ ┌──────────┐ │   └──────────────────┘
│ │feg_bot   │ │
│ │master_bot│ │
│ └────┬─────┘ │
└──────┼────────┘
       │ MT5 order_send / copy_rates
       ▼
┌──────────────────┐
│ MetaTrader5      │
│ (Windows API)    │
└──────────────────┘
       │ trade confirmation
       ▼
┌──────────────────┐
│ Telegram         │
│ (notifications)  │
└──────────────────┘
```

## Layer Chi Tiết

### 1. Authentication Layer (`src/auth.py` + `app.py`)

- `streamlit-authenticator` với `config/auth.yaml`.
- Role-based: `admin` / `user`.
- `check_auth()` → gate toàn bộ app.
- Admin-only pages: 7_Users, 8_Settings.

### 2. Strategy Definition Layer (`strategies/*.yaml`)

Strategy được định nghĩa hoàn toàn bằng YAML. Discriminator: `entry.type`.

| `entry.type` | Strategy | Entry Trigger |
|---|---|---|
| `time` | Master Candle | Nến M5 lúc 21:05 HCM |
| `pattern` | FEG EMA21 | Pattern 2 nến + EMA21 filter |

`src/strategy_manager.py::get_strategy_parameters()` đọc YAML → trả unified dict params.

### 3. Backtest Engine (`src/backtest.py`)

```
run_backtest(df, symbol, ..., entry_type)
    │
    ├─ entry_type="time"  → Master Candle path
    │    find entry candles by hour:minute
    │    for each candle: compute levels → simulate exit → record trade
    │
    └─ entry_type="pattern" → _run_feg_backtest()
         EMA series = df['close'].ewm(span=ema_period).mean()
         i = max(1, ema_period)  # EMA warmup
         while i < n:
             detect_feg_signal(c1, c2, ema[i]) → direction
             if direction: open trade → simulate exit → i = exit_pos + 1
             else: i += 1
```

Shared helpers:
- `_compute_lot_size()` — fixed / flex (risk %)
- `_simulate_exit()` — check_exit per candle, TIME exit fallback
- `_make_trade()` — build trade dict + pnl

Data fetched via `fetch_historical_data(symbol, start, end, credentials, timeframe)` từ MT5.

### 4. FEG Signal Layer (`src/feg_strategy.py`)

```
detect_feg_signal(candle1, candle2, ema2, pip_value, ema_distance_enabled, ema_distance_pips)
    SELL: H2>H1, C2<L1, L2 > ema2 + dist
    BUY:  L2<L1, C2>H1, H2 < ema2 - dist
    → "SELL" | "BUY" | None

analyze_feg(...) → dict | None
    compute_trade_levels(direction, candle2, ...) → entry/SL/TP
    return full signal dict
```

### 5. Exit Engine (`src/utils.py::check_exit`)

```
check_exit(direction, candle, tp, sl, tp_type, sl_type)
    tp_type="price_based" → check wick immediately (high/low)
    tp_type="close_based" → check close only
    sl_type="close_based" → check close only
    sl_type="price_based" → check wick immediately
    → ("TP"|"SL"|None, exit_price)
```

### 6. Trade Level Computation (`src/utils.py::compute_trade_levels`)

```
compute_trade_levels(direction, candle, entry_mode, entry_percent, buffer_k, rr_ratio, pip_value)
    BUY:
        entry = close (hoặc close - entry_percent% × body nếu range_percent)
        SL = low - buffer_k × pip
        risk = entry - SL
        TP = entry + risk × rr_ratio
    SELL:
        entry = close (hoặc close + entry_percent% × body)
        SL = high + buffer_k × pip
        risk = SL - entry
        TP = entry - risk × rr_ratio
    → {entry_price, stop_loss, take_profit, sl_pips}
```

### 7. Live Bot Layer (`src/bot_runner.py`)

Entry point: `python src/bot_runner.py --strategy <id> --symbol <sym> --test 1 ...`

```
run_bot(args)
    params = get_strategy_parameters(strategy)
    if params['entry_type'] == 'pattern':
        run_feg_bot(args, strategy, params, credentials)
        return
    run_master_candle_bot(...)

run_feg_bot():
    active_trade = None
    while True:
        df = get_recent_candles(mt5, symbol, timeframe)
        ema = df['close'].ewm(span=ema_period).mean()
        c1, c2 = df.iloc[-2], df.iloc[-1]
        ema2 = ema.iloc[-1]
        if active_trade:
            check_exit → close if hit TP/SL/TIME
        else:
            signal = feg_entry_decision(active_trade, c1, c2, ema2, ...)
            if signal:
                place_order(..., test=test, magic=212100, comment="FEG")
                active_trade = signal
        sleep(interval)
```

### 8. Order Execution (`src/orders.py`)

```
place_order(symbol, direction, volume, sl, tp, credentials, test, magic, comment)
    if test:
        return True, "[TEST] simulated", None
    mt5 = get_mt5_connection(credentials)
    request = {action, symbol, type, volume, price, sl, tp, magic, comment}
    result = mt5.order_send(request)
    return success, message, ticket
```

### 9. Bot Manager (`src/bot_manager.py`)

UI → `start_bot()` → `build_bot_command()` → `subprocess.Popen()`.

State lưu: `data/running_bots.json`

```json
{
  "bot_id": {
    "strategy": "feg_ema21",
    "symbol": "XAUUSD",
    "test": true,
    "ema_period": 21,
    "ema_distance_enabled": false,
    "ema_distance_pips": 0.0,
    "pid": 12345,
    ...
  }
}
```

### 10. Backtest History (`src/backtest_history.py`)

```
save_backtest_result(config, results, strategy_name, symbol)
    → data/backtest_history.json (append)

history_to_dataframe(history)
    → pd.DataFrame with columns:
       core: Date, Strategy, Symbol, Trades, Win Rate%, P/F, Total Pips
       config: Timeframe, Entry Type, EMA Period, EMA Dist, ...
       summary: Wins, Losses, Avg Pips, Total USD, ...

create_excel_export(config, results, trades_df)
    → BytesIO (Sheet1: Config+Summary, Sheet2: Trades)
```

## Data Flow: Backtest

```
User chọn Strategy + Symbol + Date Range + Params
    ↓ (5_Backtest.py)
fetch_historical_data(MT5)
    ↓
run_backtest(df, ..., entry_type)
    ↓ [pattern]
_run_feg_backtest → trades list + equity curve
    ↓
calculate_stats → win_rate, profit_factor, ...
    ↓
Hiển thị UI (metrics, chart, trades table)
    ↓ (optional)
save_backtest_result → data/backtest_history.json
```

## Data Flow: Live Bot

```
User click "Start Bot" (1_Bots.py)
    ↓
build_bot_command → ["python", "src/bot_runner.py", "--strategy", ...]
    ↓
subprocess.Popen → pid lưu vào running_bots.json
    ↓ (subprocess vòng lặp)
get_recent_candles(MT5) → c1, c2, EMA
feg_entry_decision → signal dict | None
    ↓ (có signal)
place_order(test=True/False)
    ↓
Telegram notify
    ↓ (có active_trade)
check_exit → close_position_by_ticket
```

## Module Dependency

```
app.py
└── src/auth.py

pages/5_Backtest.py
├── src/backtest.py
│   ├── src/utils.py (get_pip_value, check_exit, compute_trade_levels)
│   └── src/feg_strategy.py (detect_feg_signal)
├── src/strategy_manager.py (get_strategy_parameters)
└── src/backtest_history.py

pages/1_Bots.py
├── src/bot_manager.py (start/stop/restart)
└── src/strategy_manager.py

src/bot_runner.py
├── src/feg_strategy.py (analyze_feg)
├── src/orders.py (place_order)
├── src/utils.py (check_exit)
├── src/strategy_manager.py
└── src/telegram.py
```

## Quy Tắc Entry Type

Mỗi file YAML phải có `entry.type`. Backward-compat: thiếu `entry.type` → mặc định `"time"`.

| Field YAML | Python kwarg | Default |
|---|---|---|
| `entry.type` | `entry_type` | `"time"` |
| `entry.ema_period` | `ema_period` | `21` |
| `entry.ema_distance.enabled` | `ema_distance_enabled` | `False` |
| `entry.ema_distance.pips` | `ema_distance_pips` | `0.0` |

## Tài Liệu Liên Quan

- [Project Overview & PDR](./project-overview-pdr.md)
- [Codebase Summary](./codebase-summary.md)
- [Project Roadmap](./project-roadmap.md)
- [Code Standards](./code-standards.md)
