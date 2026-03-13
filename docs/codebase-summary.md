# BotForex - Codebase Summary

**Last Updated**: 2026-02-26
**Version**: 2.0.0
**Status**: Production Ready

---

## Project Overview

BotForex is an automated Forex trading bot that executes the Master Candle strategy using MetaTrader5 (MT5) API. It provides a Streamlit dashboard for configuration and monitoring, supports multiple concurrent trading bots, and includes backtesting capabilities.

**Key Stats**:
- 13 core Python modules (~2000+ LOC)
- 8 Streamlit dashboard pages
- Multi-bot process management
- Real-time Telegram notifications
- Historical data tracking

---

## Directory Structure

```
BotForex/
├── src/                              # Core business logic
│   ├── bot_runner.py                 # Main trading loop (1850+ lines)
│   ├── bot_manager.py                # Process management
│   ├── orders.py                     # MT5 order operations
│   ├── backtest.py                   # Backtesting engine
│   ├── strategy.py                   # Master Candle strategy logic
│   ├── strategy_manager.py           # Strategy loading from YAML
│   ├── auth.py                       # Credential management
│   ├── utils.py                      # Utility functions (pip/point values)
│   ├── calculation.py                # Technical indicators
│   ├── telegram.py                   # Telegram notifications
│   ├── symbol_validator.py           # Symbol validation
│   ├── backtest_history.py           # Backtest persistence
│   └── bot_config_history.py         # Bot config snapshots
│
├── pages/                            # Streamlit dashboard
│   ├── 1_Bots.py                     # Bot management UI
│   ├── 2_Orders.py                   # Order history viewer
│   ├── 3_Signals.py                  # Signal monitoring
│   ├── 4_Strategies.py               # Strategy editor
│   ├── 5_Backtest.py                 # Backtest executor
│   ├── 6_Simulation.py               # Simulation tools
│   ├── 7_Users.py                    # User management
│   └── 8_Settings.py                 # Configuration settings
│
├── strategies/                       # Strategy configs
│   └── master_candle.yaml            # Master Candle strategy definition
│
├── config/                           # Application configuration
│   └── auth.yaml                     # MT5 credentials per user
│
├── data/                             # Runtime data storage
│   ├── running_bots.json             # Active bot processes
│   ├── orders.csv                    # Trade history
│   ├── bot_config_history.json       # Config snapshots
│   └── backtest_history.json         # Backtest results
│
├── logs/                             # Bot execution logs
│   └── bot_*.log                     # Per-bot logs with timestamps
│
├── app.py                            # Streamlit entry point
├── requirements.txt                  # Python dependencies
├── README.md                         # Project overview (Vietnamese)
├── CLAUDE.md                         # Claude Code instructions
└── docs/                             # Project documentation
    ├── codebase-summary.md           # This file
    ├── system-architecture.md        # Architecture design
    ├── bot-parameters.md             # Parameter reference
    ├── developer-guide.md            # Developer onboarding
    ├── code-standards.md             # Code standards
    ├── project-overview-pdr.md       # PDR document
    └── project-roadmap.md            # Future roadmap
```

---

## Core Modules

### 1. bot_runner.py (Main Trading Loop)

**Lines**: ~1850+
**Purpose**: Core bot logic - monitors entry conditions, executes trades, manages positions

**Key Functions**:

| Function | Lines | Purpose |
|----------|-------|---------|
| `get_args()` | 51-126 | Parse command-line parameters (45 parameters total) |
| `setup_logging()` | 29-48 | Initialize file logging with UTF-8 encoding |
| `log()` | 129-149 | Timestamp logging to console and file |
| `get_mt5_connection()` | 180-203 | MT5 login and initialization |
| `check_entry_time()` | 218-241 | Detect candle close time for entry signal |
| `get_current_candle()` | 244-286 | Fetch last closed candle from MT5 |
| `run_bot()` | 289-800+ | Main bot execution loop |

**Parameters Supported**: 45 total
- **Required**: --strategy, --symbol, --user
- **Entry**: --timeframe, --entry_time, --entry_mode, --entry_percent
- **Risk**: --sl_pips, --rr_ratio, --lot_size, --buffer_k
- **Money Management**: --lot_mode, --risk_mode, --risk_percent, --risk_amount, --risk_compounding
- **Exit**: --tp_type, --sl_type, --max_candles
- **Breakeven**: --move_sl_to_breakeven, --breakeven_trigger_percent, --breakeven_target
- **Pending Orders**: --pending_order_max_candles, --pending_order_expire_candles
- **Control**: --test, --interval

**Main Loop Stages**:
1. **Init** (lines 289-390): Load strategy, credentials, config
2. **Wait** (lines 438-610): Loop every N seconds, wait for entry time
3. **Entry** (lines 609-760): Connect to MT5, fetch candle, analyze signal
4. **Order** (lines 760-830): Place market or LIMIT order
5. **Management** (lines 830+): Monitor position, manage exits

**Special Features**:
- LIMIT order retry logic (pending_order_max_candles)
- LIMIT order expiration (pending_order_expire_candles)
- Move SL to breakeven at N% profit
- Close-based vs price-based exits
- Asynchronous Telegram notifications
- Real-time trade logging

### 2. bot_manager.py (Process Management)

**Lines**: ~200+
**Purpose**: Start/stop/list trading bot processes

**Key Functions**:

| Function | Purpose |
|----------|---------|
| `load_bots()` | Load running bot state from `data/running_bots.json` |
| `save_bots()` | Persist bot state atomically (prevents corruption) |
| `start_bot()` | Launch bot_runner.py subprocess with parameters |
| `stop_bot()` | Terminate bot process gracefully |
| `is_process_running()` | Check if bot process is alive (Windows/Linux compatible) |
| `list_bots()` | Get all running bots |

**Data Format**:
```json
{
  "bot_id": "strategy_symbol_user_pid",
  "strategy": "master_candle",
  "symbol": "ETHUSDm",
  "user": "admin",
  "pid": 12345,
  "status": "running",
  "started_at": "2026-02-26T10:30:00",
  "params": { ... }
}
```

**Platform Support**:
- Windows: Uses tasklist and psutil
- Linux: Uses ps and signal handling
- Atomic file writes to prevent JSON corruption

### 3. orders.py (MT5 Order Operations)

**Lines**: ~250+
**Purpose**: Execute orders and manage positions in MT5

**Key Functions**:

| Function | Purpose |
|----------|---------|
| `get_mt5_connection()` | Login to MT5 with credentials |
| `fetch_open_positions()` | Get all open positions |
| `close_position()` | Close position by ticket |
| `place_order()` | Market order execution |
| `place_pending_order()` | LIMIT pending order placement |
| `modify_position_sl()` | Update stop loss |
| `modify_position_tp()` | Update take profit |

**Order Management**:
- Market orders with deviation tolerance
- LIMIT pending orders with price specifications
- SL/TP modification for breakeven moves
- Position closing by ticket
- Error handling for broker rejections

### 4. backtest.py (Backtesting Engine)

**Lines**: ~400+
**Purpose**: Simulate trading strategy on historical data

**Key Functions**:

| Function | Purpose |
|----------|---------|
| `calculate_flex_lot_size()` | Calculate lot based on risk % or fixed amount |
| `simulate_trade()` | Execute single trade simulation |
| `simulate_strategy()` | Run full backtest on historical data |
| `backtest_for_symbol()` | Backtest single symbol across date range |
| `backtest_multiple_symbols()` | Backtest multiple symbols in parallel |

**Features**:
- Historical data fetching from MT5
- OHLC-based trade simulation
- LIMIT order retry simulation
- Move SL to breakeven feature
- P&L calculation with commissions
- Statistics generation (win rate, Sharpe ratio, etc.)
- Results persistence to JSON

**Output Format**:
```json
{
  "symbol": "ETHUSDm",
  "date_range": ["2025-01-01", "2025-02-26"],
  "total_trades": 45,
  "winning_trades": 32,
  "losing_trades": 13,
  "win_rate": 71.1,
  "total_pnl": 450.25,
  "average_win": 15.32,
  "average_loss": -8.45,
  "max_drawdown": 2.1,
  "timestamps": { ... }
}
```

### 5. strategy.py (Master Candle Strategy)

**Lines**: ~323
**Purpose**: Master Candle strategy logic and signal generation

**Key Functions**:

| Function | Purpose |
|----------|---------|
| `is_master_candle_time()` | Check if time matches strategy entry window |
| `analyze_master_candle()` | Generate trade signal from OHLC |
| `notify_signal()` | Send signal notification to Telegram |
| `place_order()` | Execute order (test mode only) |
| `close_position_by_ticket()` | Close position (test mode only) |
| `check_and_execute_strategy()` | Main strategy function |

**Strategy Rules**:
```
Entry Time: 21:05 HCM (Asia/Ho_Chi_Minh timezone)
Timeframe: M5 (5-minute candle)

Signal:
- Close > Open: BUY, SL = Low - 30 pips
- Close < Open: SELL, SL = High + 30 pips
- Close == Open: SKIP (Doji, no trade)

Exit:
- TP: price_based (immediate when price touches TP)
- SL: close_based (when candle closes beyond SL)
- Time: max_candles (~35 min for 7 M5 candles)

Risk/Reward: RR 1:2
```

**Return Format**:
```python
{
    "symbol": "ETHUSDm",
    "direction": "BUY",
    "entry_price": 2450.50,
    "stop_loss": 2420.00,
    "take_profit": 2510.00,
    "lot_size": 0.01,
    "candle_time": datetime,
    "master_candle": {
        "open": 2440.00,
        "high": 2460.00,
        "low": 2430.00,
        "close": 2450.50
    }
}
```

### 6. auth.py (Credential Management)

**Lines**: ~150+
**Purpose**: Load/save/validate MT5 credentials

**Key Functions**:

| Function | Purpose |
|----------|---------|
| `load_auth_config()` | Read `config/auth.yaml` |
| `get_user_mt5_credentials()` | Get credentials for specific user |
| `save_user_mt5_credentials()` | Save user credentials |
| `validate_credentials()` | Verify login/password/server format |
| `list_users()` | Get all configured users |

**Credential Storage**:
```yaml
users:
  admin:
    login: "123456789"
    password: "secret_password"
    server: "Exness-MT5Real"
  demo_user:
    login: "987654321"
    password: "demo_password"
    server: "Exness-MT5Demo"
```

**Security**:
- File-based storage (not in code)
- Passwords hashed/masked in logs
- Validation before MT5 connection

### 7. strategy_manager.py (Strategy Loading)

**Lines**: ~200+
**Purpose**: Load strategy configs from YAML files

**Key Functions**:

| Function | Purpose |
|----------|---------|
| `get_strategy()` | Load strategy definition |
| `get_strategy_parameters()` | Get default parameters |
| `list_strategies()` | Get all available strategies |
| `validate_strategy()` | Verify strategy config format |

**Strategy Config Structure**:
```yaml
id: master_candle
name: Master Candle Strategy
version: "1.0"
parameters:
  sl_pips: 30
  rr_ratio: 2.0
  lot_size: 0.01
  max_candles: 7
entry:
  timeframe: M5
  time: "21:05"
  timezone: Asia/Ho_Chi_Minh
exit:
  tp_type: price_based
  sl_type: close_based
symbols:
  - XAUUSD
  - BTCUSD
  - EURUSD
  # ...
```

### 8. utils.py (Utility Functions)

**Lines**: ~300+
**Purpose**: Shared utility functions

**Key Functions**:

| Function | Purpose |
|----------|---------|
| `get_pip_value()` | Get pip size by symbol (0.0001 for forex, 0.01 for metals, 1.0 for crypto) |
| `get_point_value()` | Get smallest price increment (point) for buffer calculations |
| `get_pip_value_per_lot()` | Get dollar value per pip per lot (for risk calculation) |
| `is_mt5_available()` | Check if MT5 is installed |
| `check_exit()` | Verify if position should exit (TP/SL/Time limit) |
| `non_zero_range()` | Handle zero ranges in crypto data |

**Symbol Pip Value Mapping**:
| Symbol Pattern | Pip Value | Example |
|---|---|---|
| XAU*, *GOLD* | 0.01 | XAUUSD: $1 = 100 pips |
| BTC*, *BITCOIN* | 1.0 | BTCUSD: $100 = 100 pips |
| ETH*, *ETHEREUM* | 0.01 | ETHUSD: $1 = 100 pips |
| *JPY | 0.01 | USDJPY: 0.01 = 1 pip |
| Other Forex | 0.0001 | EURUSD: 0.0001 = 1 pip |

### 9. calculation.py (Technical Indicators)

**Lines**: ~350+
**Purpose**: Technical indicator calculations

**Key Functions**:

| Function | Purpose |
|----------|---------|
| `calculate_macd()` | MACD (Moving Average Convergence Divergence) |
| `calculate_stochastic()` | Stochastic Oscillator |
| `calculate_ma()` | Simple Moving Average |
| `calculate_ema()` | Exponential Moving Average |
| `check_cross_2_list_updated()` | Detect crossover between two lines |

**Used By**: Backtest engine, potential future signal enhancements

### 10. telegram.py (Notifications)

**Lines**: ~100+
**Purpose**: Send Telegram alerts asynchronously

**Key Functions**:

| Function | Purpose |
|----------|---------|
| `send_telegram()` | Send blocking Telegram message |
| `send_telegram_async()` | Send non-blocking (threaded) message |
| `format_trade_notification()` | Format trade alert message |
| `format_error_notification()` | Format error alert message |

**Channels**:
- `TELEGRAM_ERROR_CHAT_ID`: Dev channel (errors, critical alerts)
- `TELEGRAM_CHAT_ID`: User channel (trade notifications)

### 11. symbol_validator.py (Symbol Validation)

**Lines**: ~150+
**Purpose**: Validate trading symbols against broker availability

**Key Functions**:

| Function | Purpose |
|----------|---------|
| `validate_symbol()` | Check if symbol exists in MT5 |
| `get_symbol_info()` | Get symbol properties (min lot, step, etc.) |
| `get_available_symbols()` | List all symbols from MT5 |
| `validate_symbol_properties()` | Verify lot size/step requirements |

### 12. backtest_history.py (Backtest Persistence)

**Lines**: ~200+
**Purpose**: Store and retrieve backtest results

**Key Functions**:

| Function | Purpose |
|----------|---------|
| `save_backtest_result()` | Persist backtest to JSON |
| `load_backtest_result()` | Retrieve backtest results |
| `list_backtest_history()` | Get all backtest runs |
| `compare_backtests()` | Compare two backtest results |

### 13. bot_config_history.py (Config Snapshots)

**Lines**: ~150+
**Purpose**: Track configuration changes for debugging

**Key Functions**:

| Function | Purpose |
|----------|---------|
| `save_bot_config()` | Save bot parameters at startup |
| `load_bot_config()` | Retrieve config snapshot |
| `get_config_history()` | Get all config versions for a bot |

---

## Streamlit Pages

### 1_Bots.py (Bot Management)
- Start/stop bots
- View running bot status
- Configure bot parameters
- Monitor real-time logs

### 2_Orders.py (Order History)
- View all closed trades
- Filter by symbol/date/P&L
- Export to CSV/Excel
- Calculate statistics

### 3_Signals.py (Signal Monitoring)
- View generated signals
- Signal history
- Signal accuracy tracking

### 4_Strategies.py (Strategy Configuration)
- Load/edit strategy YAML files
- Test strategy logic
- Parameter adjustment UI

### 5_Backtest.py (Backtesting)
- Run backtest on date range
- Compare multiple symbols
- Optimize parameters
- View statistics and equity curves

### 6_Simulation.py (Simulation Tools)
- Market simulation
- "What-if" scenario testing
- Risk analysis

### 7_Users.py (User Management)
- Create/edit user accounts
- Configure MT5 credentials per user
- User permissions

### 8_Settings.py (Configuration)
- Telegram bot configuration
- System settings
- Data storage management
- Backup/restore

---

## Data Storage

| File | Format | Purpose |
|------|--------|---------|
| `config/auth.yaml` | YAML | MT5 credentials (login, password, server) per user |
| `data/running_bots.json` | JSON | Active bot processes (PID, status, params) |
| `data/orders.csv` | CSV | Trade history (symbol, direction, lot, entry, exit, P&L) |
| `data/bot_config_history.json` | JSON | Snapshots of bot parameters at each run |
| `data/backtest_history.json` | JSON | Backtest results with statistics |
| `logs/bot_*.log` | TXT | Per-bot execution logs (timestamped) |
| `strategies/master_candle.yaml` | YAML | Master Candle strategy definition |

---

## Dependencies

**Key Libraries**:

| Package | Version | Purpose |
|---------|---------|---------|
| MetaTrader5 | 5.0.5430 | MT5 API (Windows only) |
| Streamlit | 1.52.2 | Web dashboard UI |
| pandas | 2.3.3 | Data manipulation (trades, candles) |
| python-telegram-bot | 22.5 | Telegram notifications |
| PyYAML | 6.0.3 | Configuration files |
| python-dotenv | 1.2.1 | Environment variables (.env) |
| plotly | 6.5.2 | Interactive charts (backtesting) |
| requests | 2.32.5 | HTTP requests (Telegram API) |
| cryptography | 46.0.3 | Credential encryption (future) |

---

## Configuration

### Environment Variables (.env)

```bash
# MT5 (fallback, overridden by config/auth.yaml)
MT5_LOGIN=123456789
MT5_PASSWORD=secret_password
MT5_SERVER=Exness-MT5Real

# Telegram
TELEGRAM_BOT_TOKEN=123456:ABC-DEF1234567890
TELEGRAM_CHAT_ID=123456789        # User alerts
TELEGRAM_ERROR_CHAT_ID=987654321  # Dev errors

# Python
PYTHONIOENCODING=utf-8            # For Windows Unicode
```

### Timezone
- **Default**: Asia/Ho_Chi_Minh (UTC+7)
- **Used for**: Entry time matching, log timestamps, candle time
- **Configurable**: In strategy YAML files

---

## Key Patterns & Conventions

### 1. Entry Time Precision
- **Entry time**: Candle OPEN time (e.g., "21:05")
- **Bot trigger**: Entry time + timeframe (e.g., "21:10" for M5)
- **Why**: Allows analysis of completed candle before placing trade

### 2. Lot Calculation (Flex Mode)
```
Formula: lot_size = risk_amount / (sl_pips × pip_value_per_lot)

Example:
- Equity: $1000
- Risk: 1%
- Risk amount: $10
- SL: 30 pips
- EURUSD pip value per lot: $0.1
- Lot = $10 / (30 × $0.1) = 3.33 lots → 0.33 (rounded down)
```

### 3. LIMIT Order Retry Logic
```
Signal fails (broker rejects LIMIT):
  → Save signal data
  → Next candle: Retry same LIMIT price
  → If still fails: Keep retrying
  → After N candles: Abandon trade
  → If price past SL: Invalidate signal (no loss potential)
  → If price at/past entry: Convert to MARKET
```

### 4. Breakeven Feature
```
When profit reaches N% of TP distance:
  → Move SL from original level to breakeven
  → Breakeven target: Entry price OR candle close price
  → Protects profits, allows upside continuation
  → Example: Entry=1.0800, TP=1.0900, SL=1.0700
             At 50% profit: Move SL to 1.0800
```

### 5. Exit Types
| Type | Behavior |
|------|----------|
| Price-based | Exit immediately when price touches level |
| Close-based | Exit only when candle CLOSES beyond level |

---

## Error Handling Strategy

### Connection Errors
- MT5 login fails → Retry next loop
- Network timeout → Continue with fallback
- Symbol not found → Skip trade, log error

### Validation Errors
- Invalid parameters → Prevent bot start, show error message
- Missing credentials → Stop bot immediately
- Invalid timeframe → Use fallback from strategy

### Graceful Degradation
- Telegram unavailable → Continue trading (non-blocking)
- File write error → Log to console instead
- MT5 disconnect → Reconnect on next loop iteration

---

## Performance Characteristics

| Metric | Value |
|--------|-------|
| Bot loop interval | 1 second (configurable) |
| MT5 connection latency | 100-200ms |
| Entry detection accuracy | <1 second |
| Memory per bot process | 50-100 MB |
| Max concurrent bots | 50+ (system dependent) |
| Order placement latency | 200-500ms |

---

## Future Enhancements

- Multiple strategy support
- Advanced order types (Trailing SL, OCO)
- Position scaling (pyramid entries)
- Correlation-based multi-symbol management
- ML-based signal validation
- API for external integrations
- Mobile app companion
