# Exit Notification Fix - MANUAL/OTHER Closes

## Issue
User reported that MANUAL/OTHER position closes were marked as [FAIL], even though they are not failed trades.

## Fix Applied

### Changed: Exit Notification Logic
**File**: `src/bot_runner.py`

**Old Logic:**
```python
emoji = "[OK]" if pnl_usd > 0 else "[FAIL]"
```
This marked ALL negative P&L as failures, including manual closes.

**New Logic:**
```python
if exit_type == "TP":
    emoji = "[OK]" if pnl_usd > 0 else "[INFO]"
elif exit_type == "SL":
    emoji = "[FAIL]"  # SL is always a failed trade
elif exit_type in ["MANUAL/OTHER", "MANUAL"]:
    emoji = "[INFO]"  # Manual close is neutral (not a failure)
else:
    # TIME or other exits: based on P&L
    emoji = "[OK]" if pnl_usd > 0 else "[INFO]"
```

### Exit Type Indicators

| Exit Type | Tag | Meaning |
|-----------|-----|---------|
| TP (Take Profit) | `[OK]` if profit > 0, `[INFO]` otherwise | Target reached |
| SL (Stop Loss) | `[FAIL]` | Always marked as failed trade |
| MANUAL/OTHER | `[INFO]` | Neutral - user manually closed position |
| TIME | `[OK]` if profit > 0, `[INFO]` otherwise | Max candles reached |

### Example Notifications

**Take Profit:**
```
[OK] Position Closed: TP

📊 Symbol: XAUUSD
🎯 Direction: BUY
💰 Lot: 0.01

📍 Entry: 5250.00
📍 Exit: 5252.00

💵 P&L: 200.0 pips ($200.00)
🕐 Duration: 45.2 min

Bot stopping...
```

**Stop Loss:**
```
[FAIL] Position Closed: SL

📊 Symbol: XAUUSD
🎯 Direction: SELL
💰 Lot: 0.01

📍 Entry: 5255.00
📍 Exit: 5257.00

💵 P&L: -200.0 pips ($-200.00)
🕐 Duration: 12.5 min

Bot stopping...
```

**Manual Close:**
```
[INFO] Position Closed: MANUAL/OTHER

📊 Symbol: XAUUSD
🎯 Direction: BUY
💰 Lot: 0.01

📍 Entry: 5250.00
📍 Exit: 5249.50

💵 P&L: -50.0 pips ($-50.00)
🕐 Duration: 5.0 min

Bot stopping...
```

## Benefits

1. **Clear Exit Reasons**: Users can immediately understand why a position was closed
2. **No False Failures**: Manual closes are not marked as failures
3. **Better Tracking**: Easy to filter notifications by exit type
4. **Consistent Logic**: Same behavior in both TEST and LIVE modes

## Status
✅ Fixed and ready to use
