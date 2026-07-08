# BotForex - Kiến Trúc Hệ Thống

**Cập Nhật Lần Cuối**: 2026-07-08
**Phiên Bản**: 0.3.1

## Tổng Quan

BotForex là ứng dụng giao dịch tự động đa chiến lược trên MT5, gồm ba thành phần chính:

1. **Dashboard (Streamlit)** — UI đa trang với layout 2 cột compacted, colored section headers cho quản lý bot, backtest, cài đặt.
2. **Bot Runner (subprocess)** — Live trading loop chạy tách biệt với MT5.
3. **CI/CD Pipeline** — GitHub Actions + Tailscale SSH tự động deploy lên Windows server.

Các thành phần giao tiếp qua: `data/running_bots.json` (state), file log, và Telegram.

## Kiến Trúc Tổng Quát

```
┌──────────────────────────────────────────────────────────────┐
│                      GitHub Actions                          │
│   (push → manual trigger → Tailscale SSH → PowerShell)      │
│   git pull + pip install + schtasks restart Streamlit        │
└────────────────────────┬─────────────────────────────────────┘
                         │ SSH via Tailscale VPN
                         ▼
┌─────────────────────────────────────────────────────────────┐
│              Windows Server (home, Tailscale IP)            │
│                                                             │
│  ┌──────────────────────────────────────────────────────┐   │
│  │         Streamlit Dashboard (2-col layout)           │   │
│  │  app.py (auth) → pages/ (Bots, Backtest, …)         │   │
│  │  Layout: [left 58% | divider 2% | right 40%]        │   │
│  │  Headers: _section_header() + colors (indigo/...)    │   │
│  │                                                      │   │
│  │  ┌────────────┐  ┌──────────────┐  ┌─────────────┐  │   │
│  │  │ 1_Bots.py  │  │ 5_Backtest  │  │4_Strategies │  │   │
│  │  │ Start/Stop │  │ Run + Chart  │  │ Read-only   │  │   │
│  │  │ (2-col)    │  │ (2-col)      │  │  (2-col)    │  │   │
│  │  └─────┬──────┘  └──────┬──────┘  └─────────────┘  │   │
│  └────────┼────────────────┼──────────────────────────┘   │
│           │ subprocess     │ MT5 historical data            │
│           ▼                ▼                                │
│  ┌──────────────┐   ┌──────────────────┐                   │
│  │ bot_runner.py│   │ backtest.py      │                   │
│  │ (live loop)  │   │ _run_feg_backtest│                   │
│  │              │   │ run_backtest     │                   │
│  │ ┌──────────┐ │   └──────────────────┘                   │
│  │ │feg_bot   │ │                                           │
│  │ │master_bot│ │                                           │
│  │ └────┬─────┘ │                                           │
│  └──────┼────────┘                                          │
│         │ MT5 order_send / copy_rates                       │
│         ▼                                                   │
│  ┌──────────────────┐                                       │
│  │ MetaTrader5      │                                       │
│  │ (Windows API)    │                                       │
│  └──────────────────┘                                       │
└──────────────────────────────┬──────────────────────────────┘
                               │ trade confirmation + errors
                               ▼
                   ┌──────────────────────┐
                   │ Telegram             │
                   │ main chat: trades    │
                   │ error chat: all errs │
                   └──────────────────────┘
```

## Layer Chi Tiết

### 1. CI/CD Layer (`.github/workflows/deploy.yml`)

Manual trigger qua GitHub Actions. Steps:

```
GitHub Actions Runner (ubuntu-latest)
    │
    ├─ tailscale/github-action@v2 → join tailnet (TAILSCALE_AUTHKEY)
    ├─ SSH key setup (DEPLOY_SSH_PRIVATE_KEY)
    ├─ SSH → hyperion@100.110.182.114
    │    PowerShell: git pull + pip install -r requirements.txt
    └─ [optional] Restart Streamlit:
         Check port 8501 → stop old process
         schtasks /Create /Run → start_streamlit.bat (detached)
         Wait 12s → verify port 8501 or fail workflow
```

**Tailscale**: WireGuard-based VPN, ephemeral key, runner join tailnet tạm thời. Không cần mở port forward trên router.

**SSH + Windows**: User `hyperion` trong Administrators group → public key phải ở `C:\ProgramData\ssh\administrators_authorized_keys` (không phải `~\.ssh\authorized_keys`).

**schtasks detach**: `Start-Process` chết khi SSH session đóng. `schtasks /Run` spawn process độc lập với SSH lifecycle.

### 2. Authentication Layer (`src/auth.py` + `app.py`)

- `streamlit-authenticator` với `config/auth.yaml`.
- Role-based: `admin` / `user`.
- `check_auth()` → gate toàn bộ app.
- Admin-only pages: 7_Users, 8_Settings.

### 3. Strategy Definition Layer (`strategies/*.yaml`)

Strategy được định nghĩa hoàn toàn bằng YAML. Discriminator: `entry.type`.

| `entry.type` | Strategy | Entry Trigger |
|---|---|---|
| `time` | Master Candle | Nến M5 lúc 21:05 HCM |
| `pattern` | FEG EMA21 | Pattern 2 nến (cùng hướng) + EMA21 filter |

`src/strategy_manager.py::get_strategy_parameters()` đọc YAML → trả unified dict params.

### 4. Backtest Engine (`src/backtest.py`)

```
run_backtest(df, symbol, ..., entry_type)
    │
    ├─ entry_type="time"  → Master Candle path
    │    find entry candles by hour:minute
    │    for each candle: compute levels → simulate exit → record trade
    │    trade["_candle"] = {open, high, low, close}  # debug field
    │
    └─ entry_type="pattern" → _run_feg_backtest()
         EMA series = df['close'].ewm(span=ema_period).mean()
         df[f"ema{ema_period}"] = ema  # saved to ohlc_data for chart
         i = max(1, ema_period)        # EMA warmup
         while i < n:
             detect_feg_signal(c1, c2, ema[i]) → direction
             if direction:
                 open trade → simulate exit → i = exit_pos + 1
                 trade["_c1"] = {**c1, "time": ...}  # debug fields
                 trade["_c2"] = {**c2, "time": ...}
                 trade["_ema"] = ema[i]
                 trade["_exit_pos"] = exit_pos
             else: i += 1
    │
    └─ run_id = "BT-YYMMDD-HHMMSS-SYMBOL-XXXX"  # trace ID
```

Shared helpers:
- `_compute_lot_size()` — fixed / flex (risk %)
- `_simulate_exit()` — check_exit per candle, TIME exit fallback
- `_make_trade()` — build trade dict + pnl

Data fetched via `fetch_historical_data(symbol, start, end, credentials, timeframe)` từ MT5.

**Wick formula fix (v0.3.1)**:
- SELL: Use true upper wick = `(h2 - o2)` for bearish candle
- BUY: Use true lower wick = `(o2 - l2)` for bullish candle

### 5. FEG Signal Layer (`src/feg_strategy.py`)

```
detect_feg_signal(candle1, candle2, ema2, pip_value, ema_distance_enabled, ema_distance_pips)

    bullish1 = c1 > o1
    bullish2 = c2 > o2

    # Same-type rule (v0.3.0): cả 2 nến phải cùng hướng
    # Wick formula fix (v0.3.1): true wick not close-based
    SELL (not bullish1 and not bullish2):
        H2>H1, C2<L1, L2 > ema2 + dist
        wick = h2 - o2  # true upper wick for bearish
    BUY (bullish1 and bullish2):
        L2<L1, C2>H1, H2 < ema2 - dist
        wick = o2 - l2  # true lower wick for bullish

    → "SELL" | "BUY" | None

analyze_feg(...) → dict | None
    compute_trade_levels(direction, candle2, ...) → entry/SL/TP
    return full signal dict
```

### 6. Exit Engine (`src/utils.py::check_exit`)

```
check_exit(direction, candle, tp, sl, tp_type, sl_type)
    tp_type="price_based" → check wick immediately (high/low)
    tp_type="close_based" → check close only
    sl_type="close_based" → check close only
    sl_type="price_based" → check wick immediately
    → ("TP"|"SL"|None, exit_price)
```

### 7. Trade Level Computation (`src/utils.py::compute_trade_levels`)

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

### 8. Live Bot Layer (`src/bot_runner.py`)

Entry point: `python src/bot_runner.py --strategy <id> --symbol <sym> --test 1 ...`

```
__main__:
    RESTART_DELAY = 30
    while True:                          # auto-restart loop
        try:
            run_bot(args)
            break
        except KeyboardInterrupt: break
        except Exception as e:
            log crash + send_telegram(traceback, is_error=True)
            sleep(RESTART_DELAY)

run_bot(args):
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
            closed_ok, close_msg = close_position(...)
            if not closed_ok: send_telegram(error, is_error=True)
        else:
            signal = feg_entry_decision(active_trade, c1, c2, ema2, ...)
            if signal:
                order_id = "ORD-YYMMDD-HHMMSS-SYMBOL-XXXX"
                place_order(..., test=test, magic=212100, comment="FEG")
                send_telegram(f"... ID: <code>{order_id}</code>")
                active_trade = {**signal, "order_id": order_id}
        sleep(interval)
```

**Error coverage**: mọi exception path đều gọi `send_telegram(..., is_error=True)` về `TELEGRAM_ERROR_CHAT_ID`.

### 9. Order Execution (`src/orders.py`)

```
place_order(symbol, direction, volume, sl, tp, credentials, test, magic, comment)
    if test:
        return True, "[TEST] simulated", None
    mt5 = get_mt5_connection(credentials)
    request = {action, symbol, type, volume, price, sl, tp, magic, comment}
    result = mt5.order_send(request)
    return success, message, ticket
```

### 10. Bot Manager (`src/bot_manager.py`)

UI → `start_bot()` → `build_bot_command()` → `subprocess.Popen()`.

State lưu: `data/running_bots.json` (git-ignored)

```json
{
  "bot_id": {
    "strategy": "feg_ema21",
    "symbol": "XAUUSD",
    "test": true,
    "ema_period": 21,
    "ema_distance_enabled": false,
    "ema_distance_pips": 0.0,
    "pid": 12345
  }
}
```

### 11. Backtest History (`src/backtest_history.py`)

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

### 12. Backtest UI (`pages/5_Backtest.py` - v0.3.1)

```
2-column layout with _section_header() and _vdivider()

display_results(stats, ohlc_data, params):
    st.code(stats["run_id"])           # copyable Trace ID
    show_interactive_chart(ohlc_data):
        # EMA overlay toggle
        ema_cols = [c for c in ohlc_data.columns if c.startswith("ema")]
        with st.expander("Indicators"):
            checkbox per EMA → go.Scatter overlay (EMA21 = #FF6B00)
    show trade table + equity curve

Layout: left (58%) | divider (2%) | right (40%)
- Left: General params, entry controls
- Right: Chart, results summary
- All `st.button()` use width='stretch'
- All `st.dataframe()` use width='content'
```

### 13. Verification Script (`scripts/verify_backtest.py`)

```
python scripts/verify_backtest.py --symbol XAUUSD --days 90 --strategy feg

1. Load credentials from config/auth.yaml
2. fetch_historical_data(MT5) → df
3. run_backtest() → stats with per-trade debug fields
4. Print per-trade trace:
   [TRADE #N]
     C1     : time | H=.. L=..
     C2     : time | H=.. L=.. C=..
     EMA21  : ..
     Checks : H2>H1✓  C2<L1✓  L2>EMA✓
     Signal : SELL
     SL calc: H2 + buffer_k×pip = ..
     TP calc: E - dist × rr = ..
     Exit   : TP | time | price=.. | N candles
     PnL    : +X.X pips | equity $Y
     Next scan from i=N
5. Print SUMMARY block per strategy
```

## Data Flow: Backtest

```
User chọn Strategy + Symbol + Date Range + Params
    ↓ (5_Backtest.py)
fetch_historical_data(MT5)
    ↓
run_backtest(df, ..., entry_type)  → run_id = "BT-..."
    ↓ [pattern]
_run_feg_backtest → trades list + equity curve + ohlc_data (với ema col)
    ↓
calculate_stats → win_rate, profit_factor, ...
    ↓
display_results:
    st.code(run_id)               # Trace ID
    EMA toggle → chart overlay    # Indicators expander
    trade table + equity curve
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
    ↓ (subprocess vòng lặp, auto-restart nếu crash)
get_recent_candles(MT5) → c1, c2, EMA
detect_feg_signal (same-type rule) → direction | None
feg_entry_decision → signal dict | None
    ↓ (có signal)
order_id = "ORD-YYMMDD-HHMMSS-SYMBOL-XXXX"
place_order(test=True/False)
    ↓
Telegram notify (main chat) với order_id
    ↓ (có active_trade)
check_exit → close_position_by_ticket
    ↓ (error bất kỳ)
send_telegram(error, is_error=True) → TELEGRAM_ERROR_CHAT_ID
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

scripts/verify_backtest.py
├── src/backtest.py (run_backtest, fetch_historical_data)
├── src/strategy_manager.py (get_strategy_parameters)
└── src/utils.py (get_pip_value)
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
