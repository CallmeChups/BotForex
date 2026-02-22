# Move SL to Breakeven - Backtest Integration

## ✅ COMPLETED

Tính năng "Move SL to Breakeven" đã được apply vào **Backtest Page** để bạn có thể test strategy trước khi chạy live.

---

## 🎯 Changes Made

### 1. Backend - `src/backtest.py`

**Added Parameters:**
```python
def run_backtest(
    ...
    move_sl_to_breakeven: bool = False,
    breakeven_trigger_percent: float = 50.0
) -> dict:
```

**Added Logic:**
```python
# During trade monitoring
sl_moved_to_breakeven = False
current_sl = stop_loss  # Track current SL

for candle in next_candles:
    # Check if should move SL to breakeven
    if move_sl_to_breakeven and not sl_moved_to_breakeven:
        if direction == "BUY":
            trigger_price = entry + (tp_distance × trigger_percent / 100)
            if candle_high >= trigger_price:
                current_sl = entry  # Move to breakeven
                sl_moved_to_breakeven = True
        else:  # SELL
            trigger_price = entry - (tp_distance × trigger_percent / 100)
            if candle_low <= trigger_price:
                current_sl = entry  # Move to breakeven
                sl_moved_to_breakeven = True

    # Use current_sl (not original stop_loss) for exit check
    exit_type, exit_price = check_exit(..., current_sl, ...)
```

**Trade Record:**
```python
trades.append({
    ...
    "sl_moved_to_breakeven": sl_moved_to_breakeven,
    "final_sl": current_sl
})
```

### 2. Frontend - `pages/5_Backtest.py`

**Added UI Controls:**
```python
move_sl_to_breakeven = st.checkbox(
    "Move SL to Breakeven",
    value=False,
    help="Automatically move SL to entry when price reaches % of TP"
)

if move_sl_to_breakeven:
    breakeven_trigger_percent = st.number_input(
        "Breakeven Trigger (%)",
        value=50.0,
        min_value=10.0,
        max_value=90.0,
        step=5.0
    )
```

**Pass to Backtest:**
```python
results = run_backtest(
    ...
    move_sl_to_breakeven=move_sl_to_breakeven,
    breakeven_trigger_percent=breakeven_trigger_percent
)
```

**Save to Config:**
```python
backtest_config = {
    ...
    'move_sl_to_breakeven': move_sl_to_breakeven,
    'breakeven_trigger_percent': breakeven_trigger_percent,
}
```

**Results Display:**
```python
# Trades table: Show "✓ BE" indicator
if 'sl_moved_to_breakeven' in trades_df.columns:
    trades_df['SL Moved'] = trades_df['sl_moved_to_breakeven'].apply(
        lambda x: '✓ BE' if x else ''
    )

# Summary metrics: Show count
if config.get('move_sl_to_breakeven', False):
    sl_moved_count = sum(1 for t in trades if t.get('sl_moved_to_breakeven'))
    st.metric("SL Moved to BE", f"{sl_moved_count}/{total_trades}")
```

---

## 📊 How to Use in Backtest

### Step 1: Configure Backtest
1. Go to **Backtest Page**
2. Set up normal parameters (symbol, date range, timeframe, etc.)
3. Scroll to **Exit Configuration** section

### Step 2: Enable Feature
1. Check ✓ **"Move SL to Breakeven"**
2. Set **"Breakeven Trigger (%)"** (default: 50%)
   - 25-35%: Aggressive (move SL early)
   - 40-60%: Balanced (recommended)
   - 65-80%: Conservative (move SL late)

### Step 3: Run Backtest
1. Click **"Run Backtest"** button
2. Wait for results

### Step 4: Analyze Results
**Trades Table:**
- New column: **"SL Moved"**
- Shows "✓ BE" for trades where SL was moved to breakeven
- Empty for trades where SL stayed at original level

**Summary Metrics:**
- New metric: **"SL Moved to BE: X/Y"**
- X = Number of trades with SL moved
- Y = Total trades
- Only shows when feature is enabled

---

## 📈 Example Results

### Without Move SL to Breakeven
```
Total Trades: 20
Wins: 12
Losses: 8
Win Rate: 60%
```

### With Move SL to Breakeven (50% Trigger)
```
Total Trades: 20
Wins: 14
Losses: 4
Win Rate: 70%
SL Moved to BE: 6/20
```

**Why Win Rate Increased?**
- 6 trades reached 50% TP → SL moved to breakeven
- 2 of those 6 would have been losses (hit original SL)
- But with moved SL, they became breakeven (not counted as losses)
- Result: Losses reduced from 8 → 4, Wins increased from 12 → 14

### Trades Table Example

| Date | Time | Direction | Entry | SL | TP | Exit | Exit Price | P&L (pips) | SL Moved |
|------|------|-----------|-------|----|----|------|------------|------------|----------|
| 2024-01-15 | 21:05 | BUY | 5000 | 4990 | 5020 | TP | 5020 | +200 | ✓ BE |
| 2024-01-16 | 21:05 | SELL | 5010 | 5020 | 4990 | SL | 5010 | 0 | ✓ BE |
| 2024-01-17 | 21:05 | BUY | 5005 | 4995 | 5025 | SL | 4995 | -100 | |
| 2024-01-18 | 21:05 | SELL | 5000 | 5010 | 4980 | TP | 4980 | +200 | ✓ BE |

**Observations:**
- Row 1: SL moved, hit TP → Profit
- Row 2: SL moved, price reversed and hit new SL (breakeven) → No loss!
- Row 3: SL not moved (price didn't reach trigger) → Loss
- Row 4: SL moved, hit TP → Profit

---

## 🧪 Testing Strategy

### Test 1: Compare With/Without Feature
1. Run backtest WITHOUT Move SL to Breakeven
2. Save results (Win Rate, P&L, Max DD)
3. Run same backtest WITH Move SL to Breakeven (50%)
4. Compare results

**Expected:**
- Win Rate: Should increase by 5-15%
- Max Drawdown: Should decrease
- Profit Factor: Should increase
- Some losses → breakeven trades

### Test 2: Trigger Sensitivity
Run backtest with different trigger %:
- 25% (Aggressive)
- 50% (Balanced)
- 75% (Conservative)

**Expected:**
- Lower % = More trades get SL moved, but some might exit early at breakeven
- Higher % = Fewer trades get SL moved, but those that do are safer

### Test 3: Market Conditions
Test with different market conditions:
- Trending market: Feature helps protect profits
- Range-bound market: Feature might cause more breakeven exits

---

## 💡 Recommendations

### When to Enable in Backtest

✅ **Enable when testing:**
- High volatility pairs (XAUUSD, BTC, etc.)
- RR ratio ≥ 2:1
- Scalping strategies
- News-based strategies

❌ **Disable when testing:**
- Low volatility pairs
- RR ratio < 1.5:1
- Mean reversion strategies (need full stop loss distance)

### Optimal Trigger %

| Market Type | Recommended Trigger |
|-------------|---------------------|
| High Volatility (XAUUSD) | 40-50% |
| Medium Volatility (EURUSD) | 50-60% |
| Low Volatility (USDJPY) | 60-70% |
| Scalping (M1-M5) | 30-40% |
| Swing Trading (H4-D1) | 50-60% |

---

## 🔍 Analysis Tips

### 1. Check SL Moved Rate
```
SL Moved Rate = (SL Moved Count / Total Trades) × 100%

Good Rate: 20-40%
- Too Low (<10%): Trigger % might be too high, or strategy doesn't reach trigger often
- Too High (>60%): Trigger % might be too low, or market is very favorable
```

### 2. Compare Breakeven vs Loss
Look at trades where SL was moved:
- How many hit TP? (full profit)
- How many hit breakeven? (no loss, protected capital)
- Calculate: Would those breakeven trades be losses without the feature?

### 3. Impact on Win Rate
```
Original Win Rate = 60%
With Move SL = 70%

Impact = +10% (significant improvement)

If Impact > 15%: Feature is very effective
If Impact < 5%: Feature has minimal effect (might not need it)
```

---

## 🚀 Next Steps

After backtesting:

1. **If Results Improved:**
   - Note the best trigger %
   - Enable feature when creating live bots
   - Monitor real trades to confirm

2. **If Results Similar:**
   - Feature might not be needed for this strategy
   - Market conditions might not suit the feature
   - Try different trigger %

3. **If Results Worse:**
   - Feature causing premature exits at breakeven
   - Disable feature for this strategy
   - Or try higher trigger % (70-80%)

---

## 📁 Files Modified

1. `src/backtest.py` - Added logic and parameters
2. `pages/5_Backtest.py` - Added UI and integration
3. `src/backtest_history.py` - Already supports arbitrary config fields

---

## ✅ Status

**COMPLETED AND READY TO USE**

Feature is now available in both:
- ✅ Backtest Page (for testing)
- ✅ Bot Page (for live/test trading)

You can now:
1. Test the strategy in Backtest with Move SL to Breakeven
2. Find optimal trigger %
3. Create bots with the same settings
4. Monitor performance in live trading

---

## 🎯 Summary

Move SL to Breakeven is now fully integrated into Backtest:
- ✅ Same logic as live bots
- ✅ Visual indicators in trades table
- ✅ Statistics in summary
- ✅ Saved in backtest history
- ✅ Compare results with/without feature

**Ready for testing! 🚀**
