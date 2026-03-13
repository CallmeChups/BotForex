# Changelog - 2026-01-28

## Critical Bug Fix: "Invalid stops" / Immediate Exit Issue

### Issue
- Bot was exiting trades immediately after entry
- Broker error: "Invalid stops"
- Orders failing to place with retcode 10016

### Root Cause
Bot calculated SL/TP from closed candle price but placed MARKET orders at current price. When market moved between calculation and execution, stops became invalid.

### Fix Applied
**Modified Files:**
1. `src/orders.py` - Added automatic SL/TP recalculation based on actual execution price
2. `src/bot_runner.py` - Pass theoretical entry price to enable recalculation

**How It Works:**
- Bot calculates signal from closed candle (e.g., entry=5255.81, SL=5256.67)
- When placing order, gets actual market price (e.g., ask=5256.50)
- Recalculates SL/TP to maintain same pip distances from actual entry
- Result: Order placed successfully with valid stops

### Test Results
- ✅ Test 1: Simulated order with 50-pip market movement - PASSED
- ✅ Test 2: Live bot with XAUUSD demo account - ORDER PLACED (Ticket: 1654167327)
- ✅ All open positions verified and closed

### Additional Changes
- Fixed unicode encoding errors in console logs (removed emojis from print statements)
- Added broker stop level validation
- Improved error messages for debugging

### Status
**VERIFIED AND READY FOR USE**

All tests passed. Bot now handles market movement correctly and places orders successfully.
