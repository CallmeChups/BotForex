#!/usr/bin/env python3
"""
P1-P3 Live Order Test Script
  P1: MT5 connection + account info
  P2: Market data + FEG signal scan on real candles
  P3: Place a real demo order -> verify -> close
"""

import sys
import os
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

TIMEZONE = ZoneInfo("Asia/Ho_Chi_Minh")
SYMBOL = "XAUUSDm"
SEP = "=" * 60

errors = []

def ok(msg): print(f"  [PASS] {msg}")
def fail(msg):
    print(f"  [FAIL] {msg}")
    errors.append(msg)
def info(msg): print(f"  [INFO] {msg}")


# ---------- helpers ----------

def _load_creds(user="admin"):
    import yaml
    cfg_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                            "config", "auth.yaml")
    with open(cfg_path, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    return cfg["credentials"]["usernames"][user]["mt5"]


# ==============================================================
# P1: MT5 Connection & Account Info
# ==============================================================

def phase1_connection():
    print(f"\n{SEP}")
    print("P1: MT5 CONNECTION & ACCOUNT INFO")
    print(SEP)

    try:
        import MetaTrader5 as mt5
    except ImportError:
        fail("MetaTrader5 not installed")
        return None

    creds = _load_creds()
    info(f"Login: {creds['login']} @ {creds['server']}")

    if not mt5.initialize():
        fail(f"mt5.initialize() failed: {mt5.last_error()}")
        return None
    ok("mt5.initialize() OK")

    login = int(creds["login"])
    if not mt5.login(login=login, password=creds["password"], server=creds["server"]):
        fail(f"mt5.login() failed: {mt5.last_error()}")
        mt5.shutdown()
        return None
    ok(f"mt5.login({login}) OK")

    acc = mt5.account_info()
    if acc is None:
        fail("account_info() returned None")
        mt5.shutdown()
        return None

    info(f"Name    : {acc.name}")
    info(f"Server  : {acc.server}")
    info(f"Balance : {acc.balance:.2f} {acc.currency}")
    info(f"Equity  : {acc.equity:.2f} {acc.currency}")
    info(f"Leverage: 1:{acc.leverage}")

    if acc.equity <= 0:
        fail(f"Equity={acc.equity} <= 0 — account may be expired")
        mt5.shutdown()
        return None
    ok(f"Account equity OK: {acc.equity:.2f}")

    # Check symbols
    for sym in [SYMBOL, "BTCUSDm", "ETHUSDm"]:
        si = mt5.symbol_info(sym)
        if si:
            ok(f"Symbol {sym}: bid={si.bid:.2f} ask={si.ask:.2f} min_lot={si.volume_min}")
        else:
            fail(f"Symbol {sym} not found")

    mt5.shutdown()
    return creds


# ==============================================================
# P2: Market Data + FEG Signal Scan
# ==============================================================

def phase2_market_data(creds):
    print(f"\n{SEP}")
    print("P2: MARKET DATA + FEG SIGNAL SCAN")
    print(SEP)

    try:
        import MetaTrader5 as mt5
        import pandas as pd
    except ImportError:
        fail("Missing imports")
        return

    from src.utils import get_pip_value
    from src.feg_strategy import detect_feg_signal

    if not mt5.initialize():
        fail("mt5.initialize() failed")
        return
    if not mt5.login(int(creds["login"]), password=creds["password"], server=creds["server"]):
        fail(f"Login failed: {mt5.last_error()}")
        mt5.shutdown()
        return

    # Fetch 120 M1 candles
    rates = mt5.copy_rates_from_pos(SYMBOL, mt5.TIMEFRAME_M1, 0, 121)
    mt5.shutdown()

    if rates is None or len(rates) < 3:
        fail(f"No candle data: {mt5.last_error()}")
        return

    df = pd.DataFrame(rates)
    df = df.iloc[:-1]  # drop live candle
    ok(f"Fetched {len(df)} closed M1 candles for {SYMBOL}")

    # EMA21
    ema = df["close"].ewm(span=21, adjust=False).mean().tolist()
    pip_value = get_pip_value(SYMBOL)

    # Scan last 30 pairs
    scan_start = max(1, len(df) - 30)
    signals_found = []
    for i in range(scan_start, len(df)):
        c1 = {"open": df.at[i-1,"open"], "high": df.at[i-1,"high"],
              "low": df.at[i-1,"low"], "close": df.at[i-1,"close"]}
        c2 = {"open": df.at[i,"open"], "high": df.at[i,"high"],
              "low": df.at[i,"low"], "close": df.at[i,"close"]}
        direction = detect_feg_signal(c1, c2, ema[i], pip_value)
        if direction:
            t = datetime.fromtimestamp(int(df.at[i,"time"]), tz=TIMEZONE)
            signals_found.append((t, direction, c2, ema[i]))

    last = df.iloc[-1]
    last_time = datetime.fromtimestamp(int(last["time"]), tz=TIMEZONE)
    info(f"Last candle: {last_time.strftime('%H:%M:%S')} | O={last['open']:.2f} H={last['high']:.2f} L={last['low']:.2f} C={last['close']:.2f}")
    info(f"EMA21 (last): {ema[-1]:.2f}")

    if signals_found:
        ok(f"Found {len(signals_found)} FEG signal(s) in last 30 candles:")
        for t, d, c2, ema_v in signals_found:
            info(f"  {t.strftime('%H:%M')} {d}: H2={c2['high']:.2f} L2={c2['low']:.2f} C2={c2['close']:.2f} EMA={ema_v:.2f}")
    else:
        info("No FEG signal in last 30 candles (market may be ranging) -- normal")
        ok("Signal scan completed without crash")


# ==============================================================
# P3: Direct Order Place + Close
# ==============================================================

def phase3_order_place_close(creds):
    print(f"\n{SEP}")
    print("P3: DIRECT ORDER PLACE + CLOSE")
    print(SEP)

    from src.orders import place_order, close_position, fetch_open_positions, get_account_info

    # Get current price to set SL/TP
    try:
        import MetaTrader5 as mt5
        if not mt5.initialize():
            fail("mt5.initialize() failed")
            return
        if not mt5.login(int(creds["login"]), password=creds["password"], server=creds["server"]):
            fail(f"Login failed: {mt5.last_error()}")
            mt5.shutdown()
            return
        tick = mt5.symbol_info_tick(SYMBOL)
        sym_info = mt5.symbol_info(SYMBOL)
        mt5.shutdown()
        if tick is None:
            fail("symbol_info_tick returned None")
            return
    except Exception as e:
        fail(f"Price fetch failed: {e}")
        return

    ask = tick.ask
    bid = tick.bid
    min_lot = sym_info.volume_min if sym_info else 0.01
    pip = 0.1  # XAU

    # We'll do a BUY with tight SL (80 pips below ask) and TP (100 pips above ask)
    sl_price = round(ask - 80 * pip, 2)
    tp_price = round(ask + 100 * pip, 2)

    info(f"Current: ask={ask:.2f} bid={bid:.2f}")
    info(f"Placing BUY {SYMBOL} lot={min_lot} SL={sl_price:.2f} TP={tp_price:.2f}")

    # --- Place order ---
    success, msg, ticket = place_order(
        symbol=SYMBOL,
        direction="BUY",
        volume=min_lot,
        sl=sl_price,
        tp=tp_price,
        credentials=creds,
        test=False,
        magic=999999,
        comment="TEST_PLACE",
    )

    if not success:
        fail(f"place_order failed: {msg}")
        return
    ok(f"Order placed: ticket={ticket} | {msg}")

    if ticket is None:
        fail("ticket is None despite success=True")
        return

    # --- Verify position in MT5 ---
    import time
    time.sleep(1)
    positions, err = fetch_open_positions(credentials=creds)
    if err:
        fail(f"fetch_open_positions error: {err}")
    else:
        our_pos = [p for p in positions if p["ticket"] == ticket]
        if our_pos:
            p = our_pos[0]
            ok(f"Position confirmed: ticket={p['ticket']} type={p['type']} vol={p['volume']} open={p['open_price']:.2f} sl={p['sl']:.2f} tp={p['tp']:.2f}")
        else:
            fail(f"Position ticket={ticket} not found in open positions after placement")

    # --- Close position ---
    info(f"Closing position ticket={ticket}...")
    closed, close_msg = close_position(ticket=ticket, credentials=creds)
    if closed:
        ok(f"Position closed: {close_msg}")
    else:
        fail(f"close_position failed: {close_msg}")
        return

    # --- Verify position gone ---
    time.sleep(1)
    positions2, _ = fetch_open_positions(credentials=creds)
    still_open = [p for p in positions2 if p["ticket"] == ticket]
    if not still_open:
        ok("Position no longer in open positions (confirmed closed)")
    else:
        fail(f"Position ticket={ticket} still open after close attempt")

    # Final account check
    acc_info, _ = get_account_info(credentials=creds)
    if acc_info:
        info(f"Post-test equity: {acc_info['equity']:.2f} | profit: {acc_info['profit']:.2f}")


# ==============================================================
# Main
# ==============================================================

def main():
    print(SEP)
    print("LIVE ORDER TEST  --  Demo MT5")
    print(f"Time: {datetime.now(TIMEZONE).strftime('%Y-%m-%d %H:%M:%S')}")
    print(SEP)

    creds = phase1_connection()
    if creds is None:
        print("\n[ABORT] P1 failed -- cannot proceed to P2/P3")
        return 1

    phase2_market_data(creds)
    phase3_order_place_close(creds)

    print(f"\n{SEP}")
    if errors:
        print(f"RESULT: {len(errors)} FAILURE(S)")
        for e in errors:
            print(f"  x {e}")
    else:
        print("RESULT: ALL PASS -- P1/P2/P3 complete")
    print(SEP)
    return len(errors)


if __name__ == "__main__":
    sys.exit(main())
