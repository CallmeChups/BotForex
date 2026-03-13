# BotForex - Bot Runner Parameters

**Last Updated**: 2026-02-26
**Version**: 2.0.0

---

## Overview

This document details all command-line parameters for `src/bot_runner.py`. Each parameter maps to a UI field in the Streamlit dashboard.

---

## Parameter Reference

### Required Parameters

#### --strategy
- **Type**: `string`
- **Required**: Yes
- **Default**: None
- **Example**: `master_candle`
- **Description**: Strategy ID to load from `strategies/` directory
- **UI Field**: Strategy Selector dropdown
- **Notes**: Strategy must exist in `strategies/{name}.yaml`

#### --symbol
- **Type**: `string`
- **Required**: Yes
- **Default**: None
- **Example**: `ETHUSDm`, `EURUSD`, `XAUUSD`
- **Description**: Trading symbol (must be available in MT5 terminal)
- **UI Field**: Symbol input field
- **Validation**: Checked against MT5 broker symbols

#### --user
- **Type**: `string`
- **Required**: Yes
- **Default**: None
- **Example**: `admin`
- **Description**: Username for MT5 credentials lookup
- **UI Field**: User selector dropdown
- **Notes**: Credentials must be configured in Settings page

---

### Entry Configuration Parameters

#### --timeframe
- **Type**: `string`
- **Default**: From strategy config (usually `M5`)
- **Choices**: `M1`, `M5`, `M15`, `M30`, `H1`, `H4`, `D1`
- **Example**: `M5`
- **Description**: Candle timeframe to analyze
- **UI Field**: Timeframe selector in bot config
- **Notes**: Entry time must be aligned to timeframe (e.g., M5 entry at :05, :10, :15, etc.)

#### --entry_time
- **Type**: `string` (HH:MM format)
- **Default**: From strategy config (usually `21:05`)
- **Example**: `21:05`, `14:30`
- **Description**: Time when to check for trade signals (candle OPEN time)
- **UI Field**: Entry Time picker in bot config
- **Notes**: Bot triggers at entry_time + timeframe (when candle CLOSES)
  - Entry time "21:05" + M5 → Bot triggers at 21:10
  - Entry time "21:05" + H1 → Bot triggers at 22:05

#### --entry_mode
- **Type**: `string`
- **Default**: From strategy config (usually `close`)
- **Choices**: `close`, `range_percent`, `signal`
- **Example**: `range_percent`
- **Description**: How to place entry order
  - `close`: Market order at candle close price
  - `range_percent`: Pending LIMIT order at X% of candle range
  - `signal`: Alias for `close` (legacy)
- **UI Field**: Entry Mode selector in bot config
- **Notes**:
  - "close" mode: Executes immediately at market price
  - "range_percent" mode: May fail if price doesn't reach limit (requires retry logic)

#### --entry_percent
- **Type**: `float` (0-100)
- **Default**: `30.0`
- **Example**: `50`, `30`, `75`
- **Description**: Entry price as % of candle range (for range_percent mode)
- **UI Field**: Entry Percent slider in bot config
- **Formula**:
  - For BUY: `entry_price = candle_low + (candle_range × entry_percent / 100)`
  - For SELL: `entry_price = candle_high - (candle_range × entry_percent / 100)`
- **Notes**: Only used when entry_mode="range_percent"
  - 0% = at candle low/high (unlikely to fill)
  - 50% = midpoint of candle range (medium probability)
  - 100% = at candle high/low (very likely to fill)

---

### Risk & Money Management Parameters

#### --sl_pips
- **Type**: `float`
- **Default**: From strategy config (usually `30`)
- **Example**: `20`, `30`, `50`
- **Description**: Stop loss distance in pips
- **UI Field**: SL Pips input in bot config
- **Formula**:
  - For BUY: `SL_price = candle_low - (sl_pips × pip_value)`
  - For SELL: `SL_price = candle_high + (sl_pips × pip_value)`
- **Notes**: Pip value varies by symbol (see utils.py for details)

#### --rr_ratio
- **Type**: `float`
- **Default**: From strategy config (usually `2.0`)
- **Example**: `1.5`, `2.0`, `3.0`
- **Description**: Risk:Reward ratio for take profit calculation
- **UI Field**: RR Ratio input in bot config
- **Formula**: `TP = Entry ± (Risk × rr_ratio)`
  - Risk = Entry price - SL price
  - TP = Entry + (Risk × rr_ratio) for BUY
  - TP = Entry - (Risk × rr_ratio) for SELL
- **Example**: If Risk=30 pips and RR=2.0, then TP=60 pips away

#### --buffer_k
- **Type**: `float` (points)
- **Default**: `0` (no buffer)
- **Example**: `5`, `10`
- **Description**: Additional buffer added to SL in points
- **UI Field**: Buffer K input in bot config
- **Notes**:
  - 1 pip = 10 points on 5-digit brokers (for most instruments)
  - Slightly widens SL for more realistic rejection handling

#### --lot_size
- **Type**: `float`
- **Default**: From strategy config (usually `0.01`)
- **Example**: `0.01`, `0.1`, `1.0`
- **Description**: Fixed lot size for fixed mode
- **UI Field**: Lot Size input in bot config (fixed mode tab)
- **Notes**: Only used when lot_mode="fixed"

#### --lot_mode
- **Type**: `string`
- **Default**: From strategy config (usually `fixed`)
- **Choices**: `fixed`, `flex`
- **Description**: Lot calculation method
  - `fixed`: Use --lot_size directly
  - `flex`: Calculate based on risk (see risk_percent, risk_amount)
- **UI Field**: Lot Mode selector in bot config
- **Notes**:
  - "flex" requires risk_mode, risk_percent or risk_amount
  - Lot calculated as: `lot = risk_amount / (sl_pips × pip_value_per_lot)`

#### --starting_equity
- **Type**: `float` (USD)
- **Default**: `1000.0`
- **Example**: `1000`, `10000`
- **Description**: Reference equity for risk calculation (flex mode)
- **UI Field**: Starting Equity input in bot config
- **Notes**: Used for risk_compounding=0 (fixed reference)

#### --risk_mode
- **Type**: `string`
- **Default**: From strategy config (usually `percent`)
- **Choices**: `percent`, `amount`, `fixed_amount`
- **Description**: Risk calculation method
  - `percent`: % of current/starting equity
  - `amount`: Fixed USD amount (legacy name)
  - `fixed_amount`: Fixed USD amount per trade
- **UI Field**: Risk Mode selector in bot config (flex mode)
- **Notes**:
  - "percent" mode: Uses --risk_percent
  - "fixed_amount" mode: Uses --risk_amount

#### --risk_percent
- **Type**: `float` (0-100)
- **Default**: `1.0`
- **Example**: `0.5`, `1.0`, `2.0`
- **Description**: Risk % per trade (for percent mode)
- **UI Field**: Risk % input in bot config
- **Formula**:
  - If risk_compounding=1: `risk_amount = current_equity × risk_percent / 100`
  - If risk_compounding=0: `risk_amount = starting_equity × risk_percent / 100`
  - Then: `lot = risk_amount / (sl_pips × pip_value_per_lot)`
- **Example**: Equity=$1000, risk_percent=1.0, SL=30 pips on EURUSD
  - Risk amount = $1000 × 1% = $10
  - Lot = $10 / (30 × $0.1) = 0.33 lots

#### --risk_amount
- **Type**: `float` (USD)
- **Default**: `10.0`
- **Example**: `5`, `10`, `50`
- **Description**: Fixed risk amount in USD (for fixed_amount mode)
- **UI Field**: Risk Amount input in bot config
- **Formula**: `lot = risk_amount / (sl_pips × pip_value_per_lot)`
- **Example**: risk_amount=$10, SL=30 pips on EURUSD
  - Lot = $10 / (30 × $0.1) = 0.33 lots

#### --risk_compounding
- **Type**: `integer` (0 or 1)
- **Default**: `1` (True)
- **Choices**: `0` (use starting equity), `1` (use current equity)
- **Example**: `1`
- **Description**: Whether to use compound equity for risk calculation
  - `1` (True): Risk based on current account equity (grows with profits)
  - `0` (False): Risk based on starting equity (fixed reference)
- **UI Field**: Risk Compounding checkbox in bot config
- **Notes**: Important for long-running bots with multiple trades

---

### Exit Configuration Parameters

#### --tp_type
- **Type**: `string`
- **Default**: From strategy config (usually `price_based`)
- **Choices**: `price_based`, `close_based`
- **Description**: Take profit exit trigger type
  - `price_based`: Exit immediately when price touches TP level
  - `close_based`: Exit when candle CLOSES beyond TP level
- **UI Field**: TP Type selector in bot config
- **Notes**: "price_based" is more common for TP (takes profits immediately)

#### --sl_type
- **Type**: `string`
- **Default**: From strategy config (usually `close_based`)
- **Choices**: `price_based`, `close_based`
- **Description**: Stop loss exit trigger type
  - `price_based`: Exit immediately when price touches SL level
  - `close_based`: Exit only when candle CLOSES beyond SL level
- **UI Field**: SL Type selector in bot config
- **Notes**: "close_based" is common to avoid false stops on wicks

#### --max_candles
- **Type**: `integer`
- **Default**: From strategy config (usually `7`)
- **Example**: `5`, `7`, `10`
- **Description**: Maximum candles to hold position before forced close
- **UI Field**: Max Candles input in bot config
- **Notes**: If position not exited by TP/SL after N candles, force close

---

### Breakeven Move Feature Parameters

#### --move_sl_to_breakeven
- **Type**: `integer` (0 or 1)
- **Default**: `0` (False)
- **Choices**: `0` (disabled), `1` (enabled)
- **Example**: `1`
- **Description**: Enable automatic move of stop loss to breakeven
- **UI Field**: Move SL to Breakeven checkbox in bot config
- **Notes**:
  - When enabled, SL moves to entry price (or candle close) at breakeven_trigger_percent
  - Protects profits while allowing upside continuation

#### --breakeven_trigger_percent
- **Type**: `float` (0-100)
- **Default**: `50.0`
- **Example**: `25`, `50`, `75`
- **Description**: % of take profit to trigger breakeven move
- **UI Field**: Breakeven Trigger % input in bot config
- **Formula**:
  - Distance_to_TP = TP_price - Entry_price (for BUY)
  - Trigger_distance = Distance_to_TP × breakeven_trigger_percent / 100
  - When current_price reaches (Entry + Trigger_distance), move SL to breakeven
- **Example**: Entry=1.0800, TP=1.0900, SL=1.0700 (RR 1:2)
  - With breakeven_trigger_percent=50:
  - Trigger when price reaches 1.0850 (50% of TP distance)
  - Then move SL from 1.0700 to 1.0800 (entry)
- **Notes**: Only used when move_sl_to_breakeven=1

#### --breakeven_target
- **Type**: `string`
- **Default**: `entry`
- **Choices**: `entry`, `close`
- **Description**: Where to move SL for breakeven
  - `entry`: Move SL to entry price (zero loss)
  - `close`: Move SL to latest candle close price (near breakeven)
- **UI Field**: Breakeven Target selector in bot config
- **Notes**:
  - "entry" = no loss breakeven
  - "close" = tighter SL at candle close (more likely to execute)

---

### Pending Order Retry Feature Parameters

#### --pending_order_max_candles
- **Type**: `integer`
- **Default**: `3`
- **Example**: `0` (no retry), `3`, `5`
- **Description**: Max candles to retry placing LIMIT order when broker rejects
- **UI Field**: Pending Max Candles input in bot config
- **Usage**: For `entry_mode=range_percent` orders that fail
- **Logic**:
  - When LIMIT order fails: Save signal data
  - On next candles: Retry same LIMIT price
  - If retry succeeds: Continue with trade
  - If max candles exceeded: Abandon trade
  - If price moves past SL: Invalidate signal
- **Example**: With max_candles=3
  - Candle 1: LIMIT placed, fails
  - Candle 2: Retry LIMIT (1/3)
  - Candle 3: Retry LIMIT (2/3)
  - Candle 4: Retry LIMIT (3/3)
  - Candle 5: Max exceeded, bot stops

#### --pending_order_expire_candles
- **Type**: `integer`
- **Default**: `0` (wait indefinitely)
- **Example**: `0`, `5`, `10`
- **Description**: Cancel LIMIT order if not filled after N candles
- **UI Field**: Pending Expire Candles input in bot config
- **Usage**: For `entry_mode=range_percent` orders that are placed but not filled
- **Logic**:
  - When LIMIT placed successfully: Start candle counter
  - After N candles without fill: Cancel LIMIT order
  - Trade abandoned for the day
  - Value 0 = never expire (wait indefinitely)
- **Example**: With expire_candles=5
  - Candle 1: LIMIT placed successfully
  - Candle 2-5: Waiting for fill
  - Candle 6: Expire reached, cancel LIMIT order

---

### Bot Control Parameters

#### --test
- **Type**: `integer` (0 or 1)
- **Default**: `1` (test mode)
- **Choices**: `0` (live trading), `1` (test mode)
- **Example**: `0`
- **Description**: Run mode
  - `1` (True): Test mode - no real trades executed
  - `0` (False): Live trading - real orders on broker
- **UI Field**: Test Mode toggle in bot config
- **WARNING**: Set to 0 ONLY after testing thoroughly on demo account
- **Notes**: All orders logged but not sent to MT5 in test mode

#### --interval
- **Type**: `integer` (seconds)
- **Default**: `1`
- **Example**: `1`, `5`, `60`
- **Description**: Check interval in seconds (entry time checking frequency)
- **UI Field**: Check Interval input in bot config (advanced)
- **Notes**:
  - Lower value = more responsive (1s is typical)
  - Higher value = less CPU usage but less precise timing
  - Minimum 1s recommended

---

## Example Configurations

### Conservative Setup (Fixed Lot, Market Entry)
```bash
python src/bot_runner.py \
  --strategy master_candle \
  --symbol ETHUSDm \
  --user admin \
  --timeframe M5 \
  --entry_time 21:05 \
  --entry_mode close \
  --lot_mode fixed \
  --lot_size 0.01 \
  --rr_ratio 2.0 \
  --sl_pips 30 \
  --max_candles 7 \
  --test 1
```

### Aggressive Setup (Risk-Based, LIMIT Entry with Retry)
```bash
python src/bot_runner.py \
  --strategy master_candle \
  --symbol ETHUSDm \
  --user admin \
  --timeframe M5 \
  --entry_time 21:05 \
  --entry_mode range_percent \
  --entry_percent 50 \
  --pending_order_max_candles 5 \
  --pending_order_expire_candles 10 \
  --lot_mode flex \
  --risk_mode percent \
  --risk_percent 2.0 \
  --risk_compounding 1 \
  --rr_ratio 3.0 \
  --sl_pips 25 \
  --max_candles 10 \
  --move_sl_to_breakeven 1 \
  --breakeven_trigger_percent 50 \
  --breakeven_target entry \
  --test 1
```

### Multi-Symbol Live Trading
```bash
# Bot 1: EURUSD
python src/bot_runner.py --strategy master_candle --symbol EURUSD --user admin --test 0 &

# Bot 2: XAUUSD
python src/bot_runner.py --strategy master_candle --symbol XAUUSD --user admin --test 0 &

# Bot 3: BTCUSD
python src/bot_runner.py --strategy master_candle --symbol BTCUSD --user admin --test 0 &
```

---

## UI Field Mapping

| UI Section | Parameter(s) |
|-----------|--------------|
| Strategy Selector | --strategy |
| Symbol Input | --symbol |
| User Selector | --user |
| **Entry Configuration Tab** | |
| Timeframe | --timeframe |
| Entry Time | --entry_time |
| Entry Mode | --entry_mode |
| Entry Percent | --entry_percent |
| **Money Management Tab** | |
| Lot Mode | --lot_mode |
| Lot Size | --lot_size (fixed) |
| Risk Mode | --risk_mode (flex) |
| Risk % | --risk_percent (flex) |
| Risk Amount | --risk_amount (flex) |
| Risk Compounding | --risk_compounding |
| **Risk Parameters Tab** | |
| SL Pips | --sl_pips |
| RR Ratio | --rr_ratio |
| Buffer K | --buffer_k |
| Max Candles | --max_candles |
| **Exit Configuration Tab** | |
| TP Type | --tp_type |
| SL Type | --sl_type |
| **Breakeven Feature Tab** | |
| Move SL to Breakeven | --move_sl_to_breakeven |
| Breakeven Trigger % | --breakeven_trigger_percent |
| Breakeven Target | --breakeven_target |
| **Pending Order Feature Tab** | |
| Pending Max Candles | --pending_order_max_candles |
| Pending Expire Candles | --pending_order_expire_candles |
| **Control Tab** | |
| Test Mode | --test |
| Check Interval | --interval |

---

## Notes

1. **Entry Time Precision**: Entry time specifies candle OPEN time. Bot triggers at candle CLOSE (open time + timeframe).
2. **Lot Calculation**: In flex mode, lot is calculated daily based on current/starting equity and SL distance.
3. **Pending Orders**: LIMIT orders may fail due to broker restrictions. Retry logic attempts to place again.
4. **Breakeven Safety**: Move SL to breakeven only when position is profitable (no downside protection needed).
5. **Risk Compounding**: Enable for long-term bots to benefit from profit growth; disable for fixed risk targets.
6. **Test Mode**: Always test thoroughly on demo account before going live (test=0).
