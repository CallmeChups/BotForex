# BotForex - Developer Guide

**Last Updated**: 2026-02-26
**Version**: 2.0.0
**Target Audience**: New developers joining the project

---

## Getting Started in 15 Minutes

### 1. Clone & Setup (5 min)

```bash
# Clone repository
git clone https://github.com/CallmeChups/BotForex.git
cd BotForex

# Create virtual environment
python -m venv venv
source venv/bin/activate          # Linux/Mac
venv\Scripts\activate             # Windows

# Install dependencies
pip install -r requirements.txt

# Setup environment
cp .env.example .env              # If provided
# Edit .env with your Telegram tokens, MT5 credentials
```

### 2. Run Streamlit Dashboard (5 min)

```bash
streamlit run app.py
# Opens http://localhost:8501
# Go to Settings page to add MT5 credentials
```

### 3. Start Your First Bot (5 min)

```bash
# Via Streamlit UI:
# 1. Go to "Settings" → Add MT5 account for your user
# 2. Go to "Bots" → Create bot with:
#    - Strategy: master_candle
#    - Symbol: ETHUSDm
#    - Test mode: ON
#    - Click "Start Bot"
# 3. View logs in "Orders" page

# Or via command line:
python src/bot_runner.py \
  --strategy master_candle \
  --symbol ETHUSDm \
  --user admin \
  --test 1
```

---

## Project Structure Overview

```
BotForex/
├── app.py                    # Entry point (streamlit run app.py)
├── src/
│   ├── bot_runner.py         # Main trading loop ★ MOST IMPORTANT
│   ├── bot_manager.py        # Process management
│   ├── orders.py             # MT5 order execution
│   ├── backtest.py           # Backtesting engine
│   ├── strategy.py           # Strategy logic
│   └── [other modules...]
├── pages/                    # Streamlit pages (1_Bots.py - 8_Settings.py)
├── strategies/               # Strategy YAML configs
├── config/                   # Configuration files
│   └── auth.yaml             # MT5 credentials
├── data/                     # Runtime data
├── logs/                     # Bot execution logs
└── docs/                     # This documentation
```

---

## Understanding the Bot Flow

### Bot Lifecycle

```
User clicks "Start Bot" in UI
    ↓
bot_manager.start_bot() spawns subprocess
    ↓
bot_runner.py runs (new Python process)
    ↓
run_bot() initializes:
  - Load strategy (strategies/master_candle.yaml)
  - Load credentials (config/auth.yaml)
  - Setup logging (logs/bot_*_*.log)
  - Send startup Telegram alert
    ↓
Main loop begins (checks every 1 second)
    ├─ Wait for entry_time (21:05 by default)
    ├─ Connect to MT5
    ├─ Fetch candle
    ├─ Analyze signal
    ├─ Place order
    ├─ Monitor position
    ├─ Manage exits
    ├─ Send alerts
    └─ Repeat
    ↓
Position closes (TP/SL/Time limit)
    ↓
Send exit alert to Telegram
    ↓
Save to orders.csv
    ↓
Bot continues (waits for tomorrow's entry)
```

### Entry Time Precision

**Important**: Entry time is the candle OPEN time, not trigger time!

Example for M5:
- Entry time: "21:05" (candle OPENS at 21:05)
- Bot trigger: "21:10" (21:05 + 5 minutes = candle CLOSES)
- Why: Bot needs to analyze the COMPLETED candle

---

## How to Add a New Strategy

### Step 1: Create Strategy YAML

Create `strategies/my_strategy.yaml`:

```yaml
id: my_strategy
name: My Custom Strategy
version: "1.0"
description: My awesome trading strategy
author: your_name
created: "2026-02-26"
enabled: true

entry:
  timeframe: M5
  time: "21:05"
  timezone: Asia/Ho_Chi_Minh
  rules:
    rule1: "Some condition"
    rule2: "Another condition"

exit:
  tp:
    type: price_based
    description: "Exit at TP"
  sl:
    type: close_based
    description: "Exit when candle closes past SL"
  time_limit:
    enabled: true
    max_candles: 7

parameters:
  sl_pips: 30
  rr_ratio: 2.0
  lot_size: 0.01

symbols:
  - EURUSD
  - GBPUSD
  - XAUUSD
  - BTCUSD
```

### Step 2: Implement Strategy Logic

Create `src/my_strategy.py`:

```python
def analyze_my_strategy(symbol: str, ohlc_data: dict) -> dict | None:
    """
    Generate trade signal or None if no signal.

    Args:
        symbol: Trading symbol
        ohlc_data: {"open": X, "high": Y, "low": Z, "close": C, "time": datetime}

    Returns:
        Signal dict: {
            "symbol": "...",
            "direction": "BUY" or "SELL",
            "entry_price": X,
            "stop_loss": Y,
            "take_profit": Z,
            "lot_size": 0.01,
            "candle_time": datetime
        }
        Or None if no signal
    """
    # Your strategy logic here
    # Example: Compare indicators, check conditions, generate signal

    if my_signal_condition:
        return {
            "symbol": symbol,
            "direction": "BUY",
            "entry_price": ohlc_data["close"],
            "stop_loss": ohlc_data["low"] - (30 * pip_value),
            "take_profit": ...,
            "lot_size": 0.01,
            "candle_time": ohlc_data["time"]
        }

    return None
```

### Step 3: Integrate with Bot Runner

Update `src/bot_runner.py` to import and use your strategy:

```python
# In run_bot() function, after strategy loading:
if args.strategy == "my_strategy":
    from src.my_strategy import analyze_my_strategy
    signal = analyze_my_strategy(args.symbol, candle_data)
```

### Step 4: Test

```bash
# Test mode
python src/bot_runner.py \
  --strategy my_strategy \
  --symbol EURUSD \
  --user admin \
  --test 1
```

### Step 5: Backtest

Use `pages/5_Backtest.py` to validate performance before going live.

---

## Reading Bot Logs for Debugging

### Log Location

```
logs/bot_<strategy>_<symbol>_<user>_<pid>_<timestamp>.log
Example: logs/bot_master_candle_ETHUSDm_admin_12345_20260226_103000.log
```

### Log Structure

```
[2026-02-26 10:30:00] [INFO] === Bot Logs ===
[2026-02-26 10:30:00] [INFO] Bot ID: master_candle_ETHUSDm_admin_12345
[2026-02-26 10:30:00] [INFO] Started: 2026-02-26 10:30:00
[2026-02-26 10:30:00] [INFO] ============================================================
[2026-02-26 10:30:00] [INFO] [STEP 1/5] Loading strategy: master_candle
[2026-02-26 10:30:00] [INFO] [OK] Strategy loaded: Master Candle Strategy
[2026-02-26 10:30:00] [INFO] [STEP 2/5] Configuration:
[2026-02-26 10:30:00] [INFO]   RR Ratio: 2.0
[2026-02-26 10:30:00] [INFO]   Max Candles: 7
[2026-02-26 10:30:00] [INFO]   Entry Time: 21:05
[2026-02-26 10:30:00] [INFO]   Timeframe: M5
...
```

### Key Sections to Check

**1. Startup Issues**

Look for errors in STEP 1-5:
```
[ERROR] CRITICAL ERROR: Strategy not found: my_strategy
# → Add strategy to strategies/ directory

[ERROR] No credentials found for user: admin
# → Go to Settings page and configure MT5 account

[ERROR] MT5 credentials not configured
# → Check config/auth.yaml
```

**2. Entry Detection**

Check for entry time detection:
```
[Loop 30] [TIME] 21:05:00 | Entry: 21:05 | Active: False | WaitLimit: None
# → Bot is waiting properly

[TIME] CANDLE CLOSE DETECTED!
[TIME] Current Time: 21:10:00
# → Entry signal triggered
```

**3. Order Placement**

Look for order execution details:
```
[1/6] Connecting to MT5...
[OK] MT5 connected successfully
[2/6] Fetching candle data...
[3/6] Analyzing signal...
Direction: BUY
Entry: 2450.50
SL: 2420.00
TP: 2510.00
[4/6] Placing order...
[SUCCESS] Order placed! Ticket: 12345
```

**4. Errors**

Search for `[ERROR]` lines:
```
[ERROR] MT5 connection failed: Login failed
# → Check MT5 credentials

[ERROR] Retry failed: LIMIT order rejected
# → Price moved, entry no longer valid

[ERROR] Price moved past SL! bid=2415.00 <= SL=2420.00
# → Signal invalidated by market movement
```

**5. Exit Events**

Look for position close logs:
```
[TP] Take profit hit at 2510.00
[SUCCESS] Position closed - Profit: +$60.00

[SL] Stop loss triggered
[SUCCESS] Position closed - Loss: -$30.00

[TIME] Max candles reached (7)
[SUCCESS] Position closed at market
```

### Debugging Tips

1. **Enable Verbose Mode**: Add logging directly to track variable values
2. **Check Console Output**: Errors also print to console
3. **View Candle Data**: Add logs when fetching candles to verify OHLC
4. **Trace Entry Logic**: Add condition checks before signal generation
5. **Monitor MT5 Sync**: Verify MT5 terminal has correct quotes

---

## Common Development Tasks

### Task 1: Add a New Parameter

**Step 1**: Add argparse argument in `bot_runner.py` (~line 60-120)
```python
parser.add_argument("--my_param", type=float, default=None,
                    help="Description of my parameter")
```

**Step 2**: Add to UI in `pages/1_Bots.py` (streamlit slider/input)
```python
my_param = st.slider("My Parameter", 0.0, 100.0, 50.0)
```

**Step 3**: Use parameter in trading logic
```python
my_param = args.my_param or params.get('my_param', 50.0)
```

### Task 2: Debug Entry Time Issues

**Problem**: Bot never detects entry time

**Debug Steps**:
1. Check log for `[Loop N] [TIME]` entries
2. Verify entry_time in bot config
3. Check timeframe is correct
4. Add log: `print(f"Now: {datetime.now(TIMEZONE).strftime('%H:%M:%S')}")`
5. Manually calculate trigger time: entry_time + timeframe offset

### Task 3: Fix LIMIT Order Retry Logic

**Problem**: LIMIT order keeps failing

**Check**:
1. Entry price is valid (within candle range)
2. pending_order_max_candles >= 3 (enough retries)
3. Price hasn't moved past SL (invalidates signal)
4. Broker supports LIMIT orders for symbol

**Debug**:
- Add logs in `place_pending_order()` in orders.py
- Check broker's rejection message
- Try market order instead (entry_mode="close")

### Task 4: Monitor Position Management

**Problem**: Breakeven never triggers

**Check**:
1. move_sl_to_breakeven = 1 (enabled)
2. Trade reached breakeven_trigger_percent % of TP
3. SL modification call succeeded
4. Add logs in SL modification code

### Task 5: Test Strategy on Historical Data

```bash
# Via Streamlit (recommended)
# Go to pages/5_Backtest.py
# Select: Symbol, Date range, Parameters
# Click "Run Backtest"
# View results with charts

# Via Python
from src.backtest import backtest_for_symbol
results = backtest_for_symbol(
    symbol="EURUSD",
    date_from="2026-01-01",
    date_to="2026-02-26",
    strategy="master_candle",
    **params
)
print(f"Win rate: {results['win_rate']}%")
print(f"Total P&L: ${results['total_pnl']}")
```

---

## Testing Checklist

Before deploying to live trading:

### 1. Configuration Testing
- [ ] MT5 credentials configured in Settings
- [ ] Strategy loads without errors
- [ ] All parameters have valid values
- [ ] Test mode = ON (--test 1)

### 2. Signal Testing
- [ ] Entry time detection works (check logs)
- [ ] Candle data fetches correctly
- [ ] Strategy generates signals (backtest shows trades)
- [ ] No spurious signals (false positives)

### 3. Order Testing
- [ ] Test bot can connect to MT5
- [ ] Entry mode works (market or limit)
- [ ] SL/TP calculated correctly
- [ ] Lot size matches expectations

### 4. Position Management Testing
- [ ] Position updates in real-time
- [ ] SL/TP modifications work
- [ ] Breakeven trigger fires correctly
- [ ] Exit conditions detect TP/SL hits

### 5. Notification Testing
- [ ] Telegram alerts send to correct channel
- [ ] Alert format is readable
- [ ] Errors alert to dev channel
- [ ] No duplicate messages

### 6. Logging Testing
- [ ] Log file created with correct name
- [ ] All important events logged
- [ ] Timestamps are accurate
- [ ] No sensitive data in logs

### 7. Multi-Bot Testing
- [ ] Multiple bots can run simultaneously
- [ ] Each bot has independent log file
- [ ] bots don't interfere with each other
- [ ] Can stop individual bots

### 8. Edge Cases
- [ ] Doji candles (close=open) skip signal
- [ ] Price moves past SL before order → signal invalidates
- [ ] LIMIT order retry exhausted → bot stops gracefully
- [ ] MT5 disconnect → reconnect on next loop
- [ ] Telegram unavailable → trading continues

---

## Code Standards & Patterns

### Naming Conventions

```python
# Variables
entry_price = 1.0800          # snake_case
stop_loss_pips = 30           # descriptive
is_running = True             # bool prefix with "is_"

# Functions
def check_entry_time():       # verb_noun
def get_mt5_connection():     # get_* for data retrieval
def calculate_lot_size():     # calculate_* for computations

# Classes (if used)
class BotRunner:              # PascalCase
class MT5Connection:
```

### Logging Pattern

```python
# Structured logging with levels
log("Starting new trade", "INFO")
log("Order failed: invalid price", "WARN")
log("MT5 connection error: {error}", "ERROR")
log(f"[STEP 1/5] Loading strategy: {name}")
log(f"{'='*60}")  # Section separators
```

### Error Handling

```python
# Try/except with meaningful messages
try:
    mt5, error = get_mt5_connection(credentials)
    if error:
        log(f"[ERROR] MT5 connection failed: {error}", "ERROR")
        send_telegram_async(f"MT5 Error: {error}", is_error=True)
        return  # Exit gracefully
except Exception as e:
    log(f"[ERROR] Unexpected error: {e}", "ERROR")
    return
```

### Datetime Handling

```python
# Always use timezone-aware datetimes
from datetime import datetime
from zoneinfo import ZoneInfo

TIMEZONE = ZoneInfo("Asia/Ho_Chi_Minh")
now = datetime.now(TIMEZONE)
formatted = now.strftime("%Y-%m-%d %H:%M:%S")
```

---

## Performance Optimization Tips

### 1. Reduce MT5 Connections
- Reuse connections where possible
- Close connections explicitly
- Cache symbol info

### 2. Optimize Candle Fetching
- Fetch only last closed candle (not full history)
- Use `copy_rates_from_pos(symbol, timeframe, 1, 1)`

### 3. Efficient Logging
- Use line buffering: `open(..., buffering=1)`
- Write to file async (non-blocking)

### 4. Minimize Sleep Time
- Check entry time every 1 second (not 60 seconds)
- Improves precision with minimal CPU impact

---

## Troubleshooting Guide

| Problem | Cause | Solution |
|---------|-------|----------|
| Bot never starts | Strategy not found | Check `strategies/` directory |
| | Credentials missing | Go to Settings, add MT5 account |
| | Invalid parameters | Run with `--test 1` first |
| Bot doesn't detect entry | Wrong entry time | Verify entry_time format (HH:MM) |
| | Wrong timeframe | Check timeframe matches strategy |
| | Time zone mismatch | Use Asia/Ho_Chi_Minh (default) |
| Order fails to place | MT5 not logged in | Check credentials in Settings |
| | Symbol not available | Verify symbol exists in MT5 |
| | Lot too small/large | Adjust lot_size parameter |
| Position doesn't close | TP/SL not reached | Check market conditions |
| | Max candles too high | Lower max_candles to force exit |
| | No exit trigger defined | Check tp_type, sl_type settings |

---

## Resources

### Key Files to Review
1. `src/bot_runner.py` - Main bot loop (start here!)
2. `src/strategy.py` - Strategy logic
3. `src/backtest.py` - Backtesting engine
4. `docs/system-architecture.md` - Overall design
5. `docs/bot-parameters.md` - Parameter reference

### Learning Path
1. Read this guide (you are here!)
2. Run Streamlit UI: `streamlit run app.py`
3. Start test bot on demo account
4. Read logs: `logs/bot_*.log`
5. Modify one parameter, test again
6. Review `src/bot_runner.py` line by line
7. Try adding custom strategy
8. Run backtest on your strategy
9. Deploy to live (after thorough testing!)

### Getting Help
- Check logs first: `logs/bot_*.log`
- Search for error in code
- Add debug logging to trace issue
- Post in team chat with logs attached
- Review similar issues in git history

---

## Next Steps

1. **Setup Complete**: You now have a working development environment
2. **Try Example Bot**: Start a test bot on demo account
3. **Read Source Code**: Focus on `bot_runner.py` and `strategy.py`
4. **Write Custom Strategy**: Create your own strategy YAML and logic
5. **Run Backtest**: Validate strategy on historical data
6. **Deploy Carefully**: Test thoroughly before going live

Welcome to BotForex development! Happy coding!
