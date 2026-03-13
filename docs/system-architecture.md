# BotForex - System Architecture

**Last Updated**: 2026-02-26
**Version**: 2.0.0
**Status**: Production Ready

---

## Overview

BotForex is an automated Forex trading bot that executes the Master Candle strategy using MetaTrader5 (MT5) API. It runs multiple independent bot processes, each monitoring a specific trading symbol and executing trades based on configurable parameters.

### Architecture Pattern: Process-Based Multi-Bot System

```
┌─────────────────────────────────────────────────────────────────┐
│                    Streamlit UI (app.py)                        │
│  Dashboard for starting/stopping bots, config, monitoring       │
└────────────────────┬────────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────────┐
│              Bot Manager (src/bot_manager.py)                    │
│  Start/Stop/List bot processes, track running instances         │
└────────────────────┬────────────────────────────────────────────┘
                     │ (spawns subprocess)
                     ▼
┌─────────────────────────────────────────────────────────────────┐
│           Bot Runner (src/bot_runner.py) - Per Bot Process      │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │ 1. INIT: Load strategy, credentials, validate config    │   │
│  └──────────────────────────────────────────────────────────┘   │
│                     │                                            │
│  ┌──────────────────▼──────────────────────────────────────┐   │
│  │ 2. MAIN LOOP: Wait for entry time (checks every 1s)    │   │
│  └──────────────────┬──────────────────────────────────────┘   │
│                     │                                            │
│  ┌──────────────────▼──────────────────────────────────────┐   │
│  │ 3. ENTRY: Connect to MT5 at entry time, fetch candle   │   │
│  │    Analyze candle (bullish=BUY, bearish=SELL)          │   │
│  │    Calculate SL, TP, Lot size                          │   │
│  └──────────────────┬──────────────────────────────────────┘   │
│                     │                                            │
│  ┌──────────────────▼──────────────────────────────────────┐   │
│  │ 4. ORDER: Place order (MARKET or LIMIT pending)        │   │
│  │    Retry LIMIT order for N candles if rejected        │   │
│  │    Cancel LIMIT if not filled after N candles         │   │
│  └──────────────────┬──────────────────────────────────────┘   │
│                     │                                            │
│  ┌──────────────────▼──────────────────────────────────────┐   │
│  │ 5. MANAGEMENT: Move SL to breakeven at N% profit       │   │
│  │    Check exit conditions (TP/SL/Time limit)            │   │
│  │    Close position on exit                              │   │
│  └──────────────────┬──────────────────────────────────────┘   │
│                     │                                            │
│  ┌──────────────────▼──────────────────────────────────────┐   │
│  │ 6. NOTIFICATIONS: Send Telegram alerts                 │   │
│  │    Logging to file (logs/bot_*.log)                    │   │
│  └──────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
                     │ (calls)
                     ▼
        ┌────────────────────────────────┐
        │   MetaTrader5 Terminal (MT5)   │
        │   - Order execution            │
        │   - Real-time price feeds      │
        │   - Position/tick info         │
        └────────────────────────────────┘
```

---

## Core Components

### 1. Application Layer (app.py)

**Purpose**: Streamlit web dashboard for user interaction

**Responsibilities**:
- Display bot status and controls
- Allow users to start/stop bots with parameters
- Configure MT5 credentials and strategy settings
- View order history and backtest results
- Pages: 1_Bots.py through 8_Settings.py

**Key Features**:
- Real-time bot status monitoring
- Configuration UI with validation
- Historical data export
- Backtest engine integration

---

### 2. Bot Manager (src/bot_manager.py)

**Purpose**: Process lifecycle management

**Key Functions**:

| Function | Purpose |
|----------|---------|
| `start_bot()` | Launch bot_runner.py as subprocess with parameters |
| `stop_bot()` | Terminate bot process gracefully |
| `list_bots()` | Retrieve all running bot processes |
| `is_process_running()` | Check if bot process is alive |
| `load_bots()` / `save_bots()` | Persist bot state to `data/running_bots.json` |

**Bot State Storage**:
```json
{
  "bot_id": "master_candle_ETHUSDm_admin_12345",
  "strategy": "master_candle",
  "symbol": "ETHUSDm",
  "user": "admin",
  "pid": 12345,
  "status": "running",
  "started_at": "2026-02-26T10:30:00",
  "params": { ... }
}
```

---

### 3. Bot Runner (src/bot_runner.py) - Main Trading Loop

**Purpose**: Core bot logic - monitors entry conditions, executes trades, manages positions

**Entry Point**:
```bash
python src/bot_runner.py \
  --strategy master_candle \
  --symbol ETHUSDm \
  --user admin \
  --timeframe M5 \
  --entry_time 21:05 \
  --entry_mode close \
  --rr_ratio 2.0 \
  --max_candles 7 \
  [... more parameters]
```

**Main Loop Stages**:

#### Stage 1: Initialization
- Load strategy config from `strategies/master_candle.yaml`
- Fetch MT5 credentials for user from `config/auth.yaml`
- Validate all parameters
- Setup logging to `logs/bot_{id}_{timestamp}.log`
- Send startup notification to Telegram

#### Stage 2: Entry Detection Loop
- Sleep for `--interval` seconds (default: 1s)
- Check if current time matches candle close time
  - Entry time: "21:05" (candle OPEN)
  - Trigger: 21:05 + timeframe (e.g., M5 → 21:10, H1 → 22:05)
- Verify not already traded today (`last_entry_date != today`)

#### Stage 3: Candle Analysis
- Connect to MT5 with credentials
- Fetch last CLOSED candle (not current open)
- Analyze direction:
  - **Bullish** (close > open): BUY signal
  - **Bearish** (close < open): SELL signal
  - **Doji** (close == open): No trade
- Calculate trade parameters:
  - Entry price (from candle close)
  - Stop Loss: Low - (SL_PIPS × pip_value) for BUY
  - Take Profit: Entry ± (Risk × RR_Ratio)
  - Lot size: Fixed or risk-based calculation

#### Stage 4: Order Placement
- **Entry Mode: "close"** (Market Order)
  - Place market order at candle close price
- **Entry Mode: "range_percent"** (Pending LIMIT Order)
  - Calculate LIMIT entry price at X% of candle range
  - Place pending LIMIT order
  - If rejected: Retry for `--pending_order_max_candles` (default: 3)
  - If not filled after `--pending_order_expire_candles`: Cancel

**Pending Order Retry Logic**:
- Saves signal data when LIMIT fails
- Retries same LIMIT price on next candles
- Converts to MARKET if price moves to/past entry
- Cancels if max candles exceeded
- Skips if price moved past SL (trade invalidated)

#### Stage 5: Position Management
- **Move SL to Breakeven** (if enabled):
  - When trade reaches `--breakeven_trigger_percent` of TP
  - Move SL to: Entry price OR latest candle close price
  - Prevents further losses on winning trades
- **Exit Conditions**:
  - TP hit: Price-based (immediate exit)
  - SL hit: Close-based (candle closes beyond SL)
  - Time limit: Close after `--max_candles` candles

#### Stage 6: Notifications & Logging
- Send Telegram alerts:
  - Startup confirmation
  - Order placed
  - SL/TP moved
  - Exit executed
  - Errors
- Log all events to file for debugging

---

### 4. Strategy Module (src/strategy.py)

**Purpose**: Master Candle strategy logic

**Key Function**: `analyze_master_candle()`
- Input: OHLC candle data
- Output: Trade signal (direction, entry, SL, TP) or None

**Strategy Rules**:
```
Time: 21:05 HCM (Asia/Ho_Chi_Minh timezone)
- Bullish (Close > Open): BUY, SL = Low - 30 pips
- Bearish (Close < Open): SELL, SL = High + 30 pips
- Doji (Close == Open): Skip (no trade)

Risk/Reward: RR 1:2
- Risk = Entry - SL
- Reward = Risk × 2
- TP = Entry + Reward

Time Limit: 7 candles (~35 min for M5)
```

---

### 5. Order Management (src/orders.py)

**Purpose**: Execute MT5 orders and fetch position data

**Key Functions**:

| Function | Purpose |
|----------|---------|
| `get_mt5_connection()` | Initialize MT5 and login |
| `fetch_open_positions()` | Get all open positions |
| `close_position()` | Close position by ticket |
| `place_order()` | Market order |
| `place_pending_order()` | Pending LIMIT order |

---

### 6. Backtest Engine (src/backtest.py)

**Purpose**: Simulate strategy on historical data

**Key Components**:
- Historical data fetching from MT5
- Trade simulation with OHLC data
- Lot size calculation (fixed or risk-based)
- P&L tracking
- Statistics generation

**Backtesting Features**:
- Entry mode: Market or LIMIT with retry logic
- Exit types: Price-based (TP), Close-based (SL), Time limit
- Move SL to breakeven feature
- Risk compounding option

---

### 7. Data Storage

| File | Purpose |
|------|---------|
| `data/running_bots.json` | Active bot processes |
| `data/orders.csv` | Trade history (symbol, direction, lot, entry, exit, P&L) |
| `data/bot_config_history.json` | Config snapshots for each bot run |
| `data/backtest_history.json` | Backtest result history |
| `config/auth.yaml` | MT5 credentials per user |
| `logs/bot_*.log` | Per-bot execution logs |

---

### 8. Supporting Modules

#### src/utils.py
- `get_pip_value()`: Symbol-specific pip size (0.0001 for forex, 0.01 for metals, 1.0 for crypto)
- `get_point_value()`: Point size for broker (usually 1/10 of pip for 5-digit brokers)
- `get_pip_value_per_lot()`: Value per pip per lot (for risk calculation)
- `check_exit()`: Verify if position should exit (TP/SL/Time limit)
- `non_zero_range()`: Handle zero-value ranges in crypto data

#### src/calculation.py
- Technical indicator calculations (MACD, Stochastic, MA, EMA)
- Crossover detection

#### src/telegram.py
- Send Telegram notifications asynchronously
- Separate channels for dev (errors) and user (trades)

#### src/auth.py
- Load/save MT5 credentials per user
- Credential validation

#### src/strategy_manager.py
- Load strategy config from YAML files
- Get strategy parameters

#### src/symbol_validator.py
- Validate trading symbols against broker's available symbols
- Check symbol properties (min lot, step, etc.)

#### src/backtest_history.py & bot_config_history.py
- Persist historical backtest results
- Track configuration changes for debugging

---

## Data Flow

### Order Entry Flow
```
User clicks "Start Bot" in UI
    ↓
Bot Manager spawns bot_runner.py subprocess
    ↓
Bot Runner waits for entry_time
    ↓
Entry time arrives → Connect to MT5
    ↓
Fetch candle data
    ↓
Analyze direction (bullish/bearish)
    ↓
Calculate SL, TP, Lot size
    ↓
Place order (Market or LIMIT)
    ↓
Send Telegram alert
    ↓
Log to file
```

### Position Management Flow
```
Position opened
    ↓
Loop: Check every N seconds
    ├─ TP hit? → Market close order
    ├─ SL hit? → Market close order
    ├─ Time limit? → Market close order
    ├─ Move SL to BE? (if enabled at N% profit)
    │   └─ Modify SL to entry or candle close price
    └─ Repeat
    ↓
Position closed
    ↓
Log exit details + P&L
    ↓
Send Telegram alert
    ↓
Save to orders.csv
```

---

## Key Parameters & Features

### Entry Configuration
- **entry_time**: Candle open time (e.g., "21:05") - bot triggers at close
- **timeframe**: M5, M15, H1, H4, D1
- **entry_mode**: "close" (market), "range_percent" (LIMIT)
- **entry_percent**: Entry price % of candle range (for range_percent mode)

### Order Management
- **pending_order_max_candles**: Retry LIMIT order for N candles (default: 3)
- **pending_order_expire_candles**: Cancel LIMIT if not filled after N candles (default: 0 = wait)

### Risk Management
- **rr_ratio**: Risk:Reward ratio (default: 2.0)
- **sl_pips**: Stop loss distance in pips
- **lot_size**: Fixed lot (fixed mode)
- **risk_percent**: Risk % per trade (flex mode)
- **risk_amount**: Fixed USD risk per trade
- **risk_compounding**: Use current equity (1) or starting equity (0)

### Exit Configuration
- **tp_type**: "price_based" (immediate exit) or "close_based" (wait for candle close)
- **sl_type**: "price_based" or "close_based"
- **max_candles**: Close position after N candles if not exited
- **move_sl_to_breakeven**: Enable SL movement to entry price
- **breakeven_trigger_percent**: TP % to trigger breakeven move
- **breakeven_target**: Move SL to "entry" price or latest "close" price

### Control Parameters
- **test**: 1 (test mode, no real trades), 0 (live trading)
- **interval**: Check frequency in seconds (default: 1)

---

## Error Handling & Resilience

### Connection Errors
- MT5 login fails → Retry on next loop iteration
- Symbol not found → Log error, skip trade
- Broker rejected order → Retry LIMIT for pending_order_max_candles

### Data Errors
- Invalid candle data → Skip and wait for next candle
- Missing credentials → Stop bot immediately with error alert

### Telegram Failures
- Non-blocking async sends (doesn't block trading loop)
- Timeout after 3 seconds

### Logging
- UTF-8 encoded file logs with line buffering
- Timestamped console output
- Separate error, warning, and info levels

---

## Security Considerations

- MT5 credentials stored in `config/auth.yaml` (not in code)
- Passwords logged as asterisks
- Telegram errors sent to dev channel only
- Trade alerts sent to user channel only
- Bot runs in test mode by default

---

## Performance

- Bot loop interval: 1 second (configurable)
- MT5 connection: ~100-200ms per call
- Entry detection latency: <1 second (precise minute matching)
- Candle fetch latency: 100-200ms
- Max concurrent bots: Limited only by system resources
- Each bot process: ~50-100 MB RAM

---

## Deployment

**Single Bot Example**:
```bash
python src/bot_runner.py \
  --strategy master_candle \
  --symbol ETHUSDm \
  --user admin \
  --test 0 \
  --entry_mode close
```

**Multi-Bot Deployment**:
- Use Streamlit UI to start multiple bots
- Each bot runs in separate subprocess
- Independent MT5 connections per bot
- Shared data directory for history tracking

---

## Future Enhancements

- Multiple strategy support (templates)
- Advanced order types (Trailing SL, OCO)
- Position scaling (pyramid entries)
- Correlation-based multi-symbol management
- ML-based entry signal validation
- Mobile app integration
