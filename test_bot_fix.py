"""
Test script to verify bot order placement fix

This will:
1. Connect to MT5 using user's credentials
2. Create a test signal based on current XAUUSD price
3. Attempt to place an order with the fixed logic
4. Verify that the order is placed successfully
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.orders import get_mt5_connection, place_order, close_position
from src.utils import get_pip_value

def test_bot_order_placement():
    """Test the order placement with recalculated stops"""

    print("=" * 80)
    print("BOT ORDER PLACEMENT TEST")
    print("=" * 80)

    # Use credentials from config/auth.yaml
    print(f"\n1. Loading credentials for user: 'user'")
    credentials = {
        'login': '279448057',
        'password': 'Hang1970@',
        'server': 'Exness-MT5Trial8'
    }

    print(f"   Login: {credentials['login']}")
    print(f"   Server: {credentials['server']}")

    # Connect to MT5
    print(f"\n2. Connecting to MT5...")
    mt5, error = get_mt5_connection(credentials)
    if error:
        print(f"   [FAIL] Connection failed: {error}")
        return False

    print(f"   [OK] Connected successfully")

    # Get current XAUUSD price
    symbol = "XAUUSD"
    tick = mt5.symbol_info_tick(symbol)
    if not tick:
        print(f"   [FAIL] Failed to get price for {symbol}")
        mt5.shutdown()
        return False

    print(f"\n3. Current {symbol} price:")
    print(f"   Bid: {tick.bid:.2f}")
    print(f"   Ask: {tick.ask:.2f}")

    # Simulate a SELL signal (like the bot does)
    # Calculate theoretical entry/SL/TP based on "closed candle"
    theoretical_entry = tick.bid - 0.50  # Simulate old candle close (50 cents below current)

    pip_value = get_pip_value(symbol)
    sl_pips = 30
    rr_ratio = 2.0

    # For SELL: SL above entry, TP below entry
    sl_distance = sl_pips * pip_value
    theoretical_sl = theoretical_entry + sl_distance
    theoretical_tp = theoretical_entry - (sl_distance * rr_ratio)

    print(f"\n4. Simulating SELL signal (like bot does):")
    print(f"   Theoretical Entry: {theoretical_entry:.2f} (from 'closed candle')")
    print(f"   Theoretical SL: {theoretical_sl:.2f} (+{sl_pips} pips)")
    print(f"   Theoretical TP: {theoretical_tp:.2f} (-{sl_pips * rr_ratio:.0f} pips)")
    print(f"   RR Ratio: {rr_ratio}")

    print(f"\n5. Market has moved since signal was calculated:")
    print(f"   Current Bid: {tick.bid:.2f}")
    print(f"   Difference: {tick.bid - theoretical_entry:.2f} ({(tick.bid - theoretical_entry) / pip_value:.1f} pips)")

    if theoretical_sl - tick.bid < 0.20:
        print(f"   [WARN]  WARNING: SL too close to current price!")
        print(f"   [WARN]  Old logic would fail with 'Invalid stops'")

    # Test the fixed place_order function
    print(f"\n6. Testing FIXED place_order (with recalculation)...")

    mt5.shutdown()  # Close connection before place_order (it will reconnect)

    success, msg, ticket = place_order(
        symbol=symbol,
        direction="SELL",
        volume=0.01,
        sl=theoretical_sl,
        tp=theoretical_tp,
        credentials=credentials,
        theoretical_entry=theoretical_entry  # NEW: Pass theoretical entry
    )

    if success:
        print(f"   [OK] Order placed successfully!")
        print(f"   {msg}")
        print(f"   Ticket: {ticket}")

        # Verify the order
        mt5, _ = get_mt5_connection(credentials)
        positions = mt5.positions_get(ticket=ticket)
        if positions and len(positions) > 0:
            pos = positions[0]
            print(f"\n7. Verifying order details:")
            print(f"   Actual Entry: {pos.price_open:.2f}")
            print(f"   Actual SL: {pos.sl:.2f}")
            print(f"   Actual TP: {pos.tp:.2f}")
            print(f"   SL Distance: {(pos.sl - pos.price_open) / pip_value:.1f} pips")
            print(f"   TP Distance: {(pos.price_open - pos.tp) / pip_value:.1f} pips")

            # Close the test position
            print(f"\n8. Closing test position...")
            close_success, close_msg = close_position(ticket, credentials=credentials)
            if close_success:
                print(f"   [OK] Test position closed: {close_msg}")
            else:
                print(f"   [WARN]  Failed to close: {close_msg}")

        mt5.shutdown()

        print(f"\n" + "=" * 80)
        print("[OK] TEST PASSED: Order placement fix is working correctly!")
        print("=" * 80)
        return True
    else:
        print(f"   [FAIL] Order failed: {msg}")
        print(f"\n" + "=" * 80)
        print("[FAIL] TEST FAILED: Order placement still has issues")
        print("=" * 80)
        return False

if __name__ == "__main__":
    try:
        success = test_bot_order_placement()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n[FAIL] Test error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
