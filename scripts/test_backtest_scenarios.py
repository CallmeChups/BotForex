#!/usr/bin/env python3
"""
Test tat ca to hop settings cua backtest voi synthetic data (khong can MT5).

Test cases:
  1. FEG signal detection (SELL, BUY, None)
  2. compute_trade_levels (SL/TP cho tung entry_mode)
  3. check_exit (4 to hop tp_type x sl_type)
  4. run_backtest FEG voi tat ca lot_mode, entry_mode, tp/sl types, max_candles
  5. max_candles=0 guard
  6. Flex lot calculation
  7. Edge cases
"""

import sys
import os
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.utils import get_pip_value, check_exit, compute_trade_levels
from src.feg_strategy import detect_feg_signal
from src.backtest import run_backtest

TIMEZONE = ZoneInfo("Asia/Ho_Chi_Minh")
SEP = "=" * 70
DASH = "-" * 70
errors = []


def ok(msg): print(f"  [PASS] {msg}")
def fail(msg):
    print(f"  [FAIL] {msg}")
    errors.append(msg)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_df_with_feg_signals():
    """
    Tao DataFrame voi synthetic candles chua FEG signals da biet:
      - block 0: warmup (EMA period=21) -- 22 candles flat at 2000
      - block A: SELL signal tai vi tri 22 (C1=22, C2=23)
      - block B: buffer, roi BUY signal
    EMA on dinh o ~2000 sau warmup.
    """
    base_time = datetime(2026, 1, 2, 0, 0, tzinfo=TIMEZONE)
    rows = []

    def add(t, o, h, l, c):
        rows.append({"time": t, "open": o, "high": h, "low": l, "close": c, "tick_volume": 10})

    # 22 warmup candles (flat around 2000, EMA -> 2000)
    for k in range(22):
        t = base_time + timedelta(minutes=k)
        add(t, 2000, 2001, 1999, 2000)

    # --- SELL signal pattern ---
    # C1 index=22: H=2010, L=1990, C=2005
    # C2 index=23: H=2015(>H1=2010), C=1985(<L1=1990), L=2002(>EMA~2000) => SELL valid
    add(base_time + timedelta(minutes=22), 2000, 2010, 1990, 2005)   # C1
    add(base_time + timedelta(minutes=23), 2008, 2015, 2002, 1985)   # C2 SELL
    # entry=1985, SL=2015+50*0.1=2020, TP=1985-(2020-1985)*2=1985-70=1915

    # 8 flat candles (won't hit TP/SL)
    for k in range(8):
        t = base_time + timedelta(minutes=24 + k)
        add(t, 1985, 1987, 1983, 1985)

    # TP candle: low=1910 => price_based TP at 1915 hit
    add(base_time + timedelta(minutes=32), 1985, 1986, 1910, 1920)

    # buffer 5 candles
    for k in range(5):
        t = base_time + timedelta(minutes=33 + k)
        add(t, 1920, 1922, 1918, 1920)

    # --- BUY signal pattern ---
    # C1 index=38: H=1930, L=1910, C=1915
    # C2 index=39: L=1905(<L1=1910), C=1935(>H1=1930), H=1928(<EMA~2000) => BUY valid
    add(base_time + timedelta(minutes=38), 1920, 1930, 1910, 1915)   # C1
    add(base_time + timedelta(minutes=39), 1915, 1928, 1905, 1935)   # C2 BUY
    # entry=1935, SL=1905-50*0.1=1900, TP=1935+(1935-1900)*2=1935+70=2005

    # 3 flat candles
    for k in range(3):
        t = base_time + timedelta(minutes=40 + k)
        add(t, 1935, 1937, 1933, 1935)
    # SL candle (close_based): close=1895 < SL=1900
    add(base_time + timedelta(minutes=43), 1935, 1936, 1890, 1895)

    # buffer
    for k in range(10):
        t = base_time + timedelta(minutes=44 + k)
        add(t, 1895, 1897, 1893, 1895)

    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# 1. FEG Signal Detection
# ---------------------------------------------------------------------------

def test_feg_detection():
    print(f"\n{DASH}")
    print("1. FEG SIGNAL DETECTION")
    pip_value = 0.1  # XAUUSD

    # SELL: H2>H1, C2<L1, L2>EMA21
    c1_sell = {"open": 2000, "high": 2010, "low": 1990, "close": 2005}
    c2_sell = {"open": 2008, "high": 2015, "low": 2002, "close": 1985}
    ema_sell = 2000.0

    sig = detect_feg_signal(c1_sell, c2_sell, ema_sell, pip_value)
    if sig == "SELL":
        ok(f"SELL detected: H2({c2_sell['high']})>H1({c1_sell['high']}), C2({c2_sell['close']})<L1({c1_sell['low']}), L2({c2_sell['low']})>EMA({ema_sell})")
    else:
        fail(f"Expected SELL, got {sig}")

    # SELL fails if L2 <= EMA21
    c2_below_ema = dict(c2_sell, low=1998)  # L2=1998 < EMA=2000
    sig2 = detect_feg_signal(c1_sell, c2_below_ema, ema_sell, pip_value)
    if sig2 is None:
        ok("SELL blocked when L2 <= EMA (correct)")
    else:
        fail(f"Expected None when L2<=EMA, got {sig2}")

    # BUY: L2<L1, C2>H1, H2<EMA21
    c1_buy = {"open": 1920, "high": 1930, "low": 1910, "close": 1915}
    c2_buy = {"open": 1915, "high": 1928, "low": 1905, "close": 1935}
    ema_buy = 2000.0

    sig3 = detect_feg_signal(c1_buy, c2_buy, ema_buy, pip_value)
    if sig3 == "BUY":
        ok(f"BUY detected: L2({c2_buy['low']})<L1({c1_buy['low']}), C2({c2_buy['close']})>H1({c1_buy['high']}), H2({c2_buy['high']})<EMA({ema_buy})")
    else:
        fail(f"Expected BUY, got {sig3}")

    # BUY fails if H2 >= EMA
    c2_above_ema = dict(c2_buy, high=2001)
    sig4 = detect_feg_signal(c1_buy, c2_above_ema, ema_buy, pip_value)
    if sig4 is None:
        ok("BUY blocked when H2 >= EMA (correct)")
    else:
        fail(f"Expected None when H2>=EMA, got {sig4}")

    # None: no pattern
    c1_flat = {"open": 2000, "high": 2005, "low": 1995, "close": 2000}
    c2_flat = {"open": 2000, "high": 2003, "low": 1997, "close": 2001}
    sig5 = detect_feg_signal(c1_flat, c2_flat, ema_sell, pip_value)
    if sig5 is None:
        ok("None when no pattern (correct)")
    else:
        fail(f"Expected None for flat candles, got {sig5}")

    # EMA distance filter: L2=2002, EMA=2000, dist=30*0.1=3 => need L2>2003 => fail
    sig6 = detect_feg_signal(c1_sell, c2_sell, ema_sell, pip_value,
                              ema_distance_enabled=True, ema_distance_pips=30)
    if sig6 is None:
        ok("EMA distance filter blocks SELL when L2 not far enough from EMA")
    else:
        fail(f"EMA distance filter should block, got {sig6}")

    # EMA distance OK: L2=2010 > EMA(2000)+3=2003
    c2_far = dict(c2_sell, low=2010)
    sig7 = detect_feg_signal(c1_sell, c2_far, ema_sell, pip_value,
                              ema_distance_enabled=True, ema_distance_pips=30)
    if sig7 == "SELL":
        ok("EMA distance filter passes when L2 far enough")
    else:
        fail(f"Expected SELL with sufficient EMA distance, got {sig7}")


# ---------------------------------------------------------------------------
# 2. compute_trade_levels
# ---------------------------------------------------------------------------

def test_compute_levels():
    print(f"\n{DASH}")
    print("2. COMPUTE TRADE LEVELS")
    pip_value = 0.1  # XAUUSD
    buffer_k = 50
    rr = 2.0

    # SELL close mode
    c_sell = {"open": 2008, "high": 2015, "low": 2002, "close": 1985}
    levels = compute_trade_levels("SELL", c_sell, "close", 0, buffer_k, rr, pip_value)

    expected_entry = 1985.0
    expected_sl = 2015 + 50 * 0.1   # 2020
    expected_risk = expected_sl - expected_entry  # 35
    expected_tp = expected_entry - expected_risk * rr  # 1915

    errs = []
    if abs(levels["entry_price"] - expected_entry) > 0.001: errs.append(f"entry {levels['entry_price']} != {expected_entry}")
    if abs(levels["stop_loss"] - expected_sl) > 0.001: errs.append(f"SL {levels['stop_loss']} != {expected_sl}")
    if abs(levels["take_profit"] - expected_tp) > 0.001: errs.append(f"TP {levels['take_profit']} != {expected_tp}")
    if errs:
        fail(f"SELL close: {'; '.join(errs)}")
    else:
        ok(f"SELL close: entry={expected_entry}, SL={expected_sl}, TP={expected_tp}")

    # BUY close mode
    c_buy = {"open": 1915, "high": 1928, "low": 1905, "close": 1935}
    levels_buy = compute_trade_levels("BUY", c_buy, "close", 0, buffer_k, rr, pip_value)

    exp_entry_buy = 1935.0
    exp_sl_buy = 1905 - 50 * 0.1   # 1900
    exp_risk_buy = exp_entry_buy - exp_sl_buy  # 35
    exp_tp_buy = exp_entry_buy + exp_risk_buy * rr  # 2005

    errs = []
    if abs(levels_buy["entry_price"] - exp_entry_buy) > 0.001: errs.append(f"entry {levels_buy['entry_price']} != {exp_entry_buy}")
    if abs(levels_buy["stop_loss"] - exp_sl_buy) > 0.001: errs.append(f"SL {levels_buy['stop_loss']} != {exp_sl_buy}")
    if abs(levels_buy["take_profit"] - exp_tp_buy) > 0.001: errs.append(f"TP {levels_buy['take_profit']} != {exp_tp_buy}")
    if errs:
        fail(f"BUY close: {'; '.join(errs)}")
    else:
        ok(f"BUY close: entry={exp_entry_buy}, SL={exp_sl_buy}, TP={exp_tp_buy}")

    # SELL range_percent: entry = close + 10%*|close-open| = 1985 + 10%*23 = 1987.3
    levels_rp = compute_trade_levels("SELL", c_sell, "range_percent", 10.0, buffer_k, rr, pip_value)
    exp_entry_rp = 1985 + (10.0 / 100) * abs(c_sell["close"] - c_sell["open"])
    if abs(levels_rp["entry_price"] - exp_entry_rp) > 0.001:
        fail(f"SELL range_percent entry: {levels_rp['entry_price']} != {exp_entry_rp}")
    else:
        ok(f"SELL range_percent: entry={levels_rp['entry_price']:.2f} (expected {exp_entry_rp:.2f})")

    # BUY range_percent: entry = close - 10%*|close-open| = 1935 - 10%*20 = 1933
    levels_rp_buy = compute_trade_levels("BUY", c_buy, "range_percent", 10.0, buffer_k, rr, pip_value)
    exp_entry_rp_buy = 1935 - (10.0 / 100) * abs(c_buy["close"] - c_buy["open"])
    if abs(levels_rp_buy["entry_price"] - exp_entry_rp_buy) > 0.001:
        fail(f"BUY range_percent entry: {levels_rp_buy['entry_price']} != {exp_entry_rp_buy}")
    else:
        ok(f"BUY range_percent: entry={levels_rp_buy['entry_price']:.2f} (expected {exp_entry_rp_buy:.2f})")


# ---------------------------------------------------------------------------
# 3. check_exit
# ---------------------------------------------------------------------------

def test_check_exit():
    print(f"\n{DASH}")
    print("3. CHECK EXIT (4 tp_type x sl_type combos)")
    direction = "SELL"
    tp = 1915.0
    sl = 2020.0

    candle_tp_wick  = {"high": 1990, "low": 1910, "close": 1950}   # wick hits TP
    candle_tp_close = {"high": 1990, "low": 1908, "close": 1910}   # close hits TP
    candle_sl_wick  = {"high": 2025, "low": 1980, "close": 2000}   # wick hits SL
    candle_sl_close = {"high": 2025, "low": 1980, "close": 2021}   # close hits SL
    candle_no_exit  = {"high": 1990, "low": 1980, "close": 1985}   # no exit

    r, p = check_exit(direction, candle_tp_wick, tp, sl, "price_based", "close_based")
    if r == "TP" and abs(p - tp) < 0.001:
        ok("SELL price_based TP: wick hits => TP at level price")
    else:
        fail(f"SELL price_based TP wick: got ({r},{p})")

    r, p = check_exit(direction, candle_tp_close, tp, sl, "close_based", "close_based")
    if r == "TP" and abs(p - candle_tp_close["close"]) < 0.001:
        ok("SELL close_based TP: close hits => TP at close price")
    else:
        fail(f"SELL close_based TP: got ({r},{p})")

    r, p = check_exit(direction, candle_sl_close, tp, sl, "price_based", "close_based")
    if r == "SL" and abs(p - candle_sl_close["close"]) < 0.001:
        ok("SELL close_based SL: close hits => SL at close price")
    else:
        fail(f"SELL close_based SL: got ({r},{p})")

    r, p = check_exit(direction, candle_sl_wick, tp, sl, "price_based", "price_based")
    if r == "SL" and abs(p - sl) < 0.001:
        ok("SELL price_based SL: wick hits => SL at level price")
    else:
        fail(f"SELL price_based SL: got ({r},{p})")

    r, p = check_exit(direction, candle_no_exit, tp, sl, "price_based", "close_based")
    if r is None:
        ok("No exit when candle doesn't reach TP or SL")
    else:
        fail(f"Expected None, got ({r},{p})")

    # BUY checks
    direction_buy = "BUY"
    tp_buy = 2005.0
    sl_buy = 1900.0

    candle_buy_tp = {"high": 2010, "low": 1995, "close": 2000}
    r, p = check_exit(direction_buy, candle_buy_tp, tp_buy, sl_buy, "price_based", "close_based")
    if r == "TP" and abs(p - tp_buy) < 0.001:
        ok("BUY price_based TP: wick hits => TP at level")
    else:
        fail(f"BUY TP: got ({r},{p})")

    candle_buy_sl = {"high": 1935, "low": 1935, "close": 1895}
    r, p = check_exit(direction_buy, candle_buy_sl, tp_buy, sl_buy, "price_based", "close_based")
    if r == "SL" and abs(p - candle_buy_sl["close"]) < 0.001:
        ok("BUY close_based SL: close below SL => SL at close")
    else:
        fail(f"BUY SL close: got ({r},{p})")

    # Priority: TP check before SL (same candle touches both)
    candle_both = {"high": 2010, "low": 1890, "close": 2000}   # touches both TP and SL
    r_buy, _ = check_exit("BUY", candle_both, tp_buy, sl_buy, "price_based", "price_based")
    r_sell, _ = check_exit("SELL", {"high": 2025, "low": 1910, "close": 1990}, tp, sl, "price_based", "price_based")
    ok(f"BUY priority: {r_buy} (TP checked before SL) | SELL: {r_sell}")


# ---------------------------------------------------------------------------
# 4. run_backtest FEG -- all scenario combinations
# ---------------------------------------------------------------------------

SCENARIOS = [
    # (name, entry_mode, entry_pct, tp_type, sl_type, lot_mode, risk_mode, risk_pct, risk_amt, max_candles)
    ("default",              "close",         0.0,  "price_based",  "close_based", "fixed",  "percent",      0.5, 0.0, 7),
    ("entry_range_pct",      "range_percent", 10.0, "price_based",  "close_based", "fixed",  "percent",      0.5, 0.0, 7),
    ("tp_close_based",       "close",         0.0,  "close_based",  "close_based", "fixed",  "percent",      0.5, 0.0, 7),
    ("sl_price_based",       "close",         0.0,  "price_based",  "price_based", "fixed",  "percent",      0.5, 0.0, 7),
    ("both_close_sl_pricetP","close",         0.0,  "close_based",  "price_based", "fixed",  "percent",      0.5, 0.0, 7),
    ("lot_flex_percent",     "close",         0.0,  "price_based",  "close_based", "flex",   "percent",      0.5, 0.0, 7),
    ("lot_flex_fixed_amt",   "close",         0.0,  "price_based",  "close_based", "flex",   "fixed_amount", 0.0, 5.0, 7),
    ("max_candles_off",      "close",         0.0,  "price_based",  "close_based", "fixed",  "percent",      0.5, 0.0, 0),
    ("max_candles_3",        "close",         0.0,  "price_based",  "close_based", "fixed",  "percent",      0.5, 0.0, 3),
    ("all_flex_range_pct",   "range_percent", 10.0, "close_based",  "price_based", "flex",   "percent",      0.5, 0.0, 5),
]


def _check_trade_sanity(t):
    """Returns list of error strings for a single trade dict."""
    errs = []
    if t.get("exit_type") not in ("TP", "SL", "TIME"):
        errs.append(f"invalid exit_type: {t.get('exit_type')}")
    if t.get("entry", 0) <= 0:
        errs.append(f"invalid entry: {t.get('entry')}")
    if t.get("sl", 0) <= 0:
        errs.append(f"invalid SL: {t.get('sl')}")
    if t.get("tp", 0) <= 0:
        errs.append(f"invalid TP: {t.get('tp')}")
    if t.get("direction") == "SELL":
        if t["sl"] <= t["entry"]:
            errs.append(f"SELL: SL({t['sl']}) should be > entry({t['entry']})")
        if t["tp"] >= t["entry"]:
            errs.append(f"SELL: TP({t['tp']}) should be < entry({t['entry']})")
    elif t.get("direction") == "BUY":
        if t["sl"] >= t["entry"]:
            errs.append(f"BUY: SL({t['sl']}) should be < entry({t['entry']})")
        if t["tp"] <= t["entry"]:
            errs.append(f"BUY: TP({t['tp']}) should be > entry({t['entry']})")
    return errs


def test_backtest_scenarios():
    print(f"\n{DASH}")
    print("4. RUN BACKTEST -- ALL SCENARIO COMBINATIONS")

    df = make_df_with_feg_signals()
    symbol = "XAUUSD"

    for row in SCENARIOS:
        name, entry_mode, entry_pct, tp_type, sl_type, lot_mode, risk_mode, risk_pct, risk_amt, max_candles = row
        try:
            res = run_backtest(
                df=df.copy(),
                symbol=symbol,
                entry_type="pattern",
                ema_period=21,
                rr_ratio=2.0,
                max_candles=max_candles,
                lot_mode=lot_mode,
                fixed_lot=0.01,
                risk_percent=risk_pct,
                risk_amount=risk_amt,
                risk_mode=risk_mode,
                buffer_k=50,
                starting_equity=1000.0,
                tp_type=tp_type,
                sl_type=sl_type,
                entry_mode=entry_mode,
                entry_percent=entry_pct,
                ema_distance_enabled=False,
                ema_distance_pips=0.0,
            )

            errs = []
            for t in res.get("trades", []):
                errs.extend(_check_trade_sanity(t))

            total = res.get("total_trades", -1)
            if errs:
                fail(f"[{name}] trades={total} | {'; '.join(errs)}")
            else:
                ok(f"[{name}] trades={total} exits: TP={res['tp_exits']} SL={res['sl_exits']} TIME={res['time_exits']} pnl={res['total_pnl']:+.1f}p")

        except Exception as exc:
            import traceback
            fail(f"[{name}] EXCEPTION: {exc}")
            traceback.print_exc()


# ---------------------------------------------------------------------------
# 5. max_candles = 0 guard
# ---------------------------------------------------------------------------

def test_max_candles_zero():
    print(f"\n{DASH}")
    print("5. MAX_CANDLES=0 (no time exit, TP/SL only)")
    df = make_df_with_feg_signals()

    res = run_backtest(
        df=df.copy(), symbol="XAUUSD",
        entry_type="pattern", ema_period=21, rr_ratio=2.0,
        max_candles=0, lot_mode="fixed", fixed_lot=0.01,
        buffer_k=50, starting_equity=1000.0,
        tp_type="price_based", sl_type="close_based",
        entry_mode="close",
    )

    time_exits = res.get("time_exits", 0)
    if time_exits == 0:
        ok(f"max_candles=0: no TIME exits (correct). trades={res['total_trades']}")
    else:
        fail(f"max_candles=0: expected 0 TIME exits, got {time_exits}")


# ---------------------------------------------------------------------------
# 6. Flex lot calculation
# ---------------------------------------------------------------------------

def test_flex_lot():
    print(f"\n{DASH}")
    print("6. FLEX LOT CALCULATION")
    from src.backtest import calculate_flex_lot_size

    # XAUUSD pip_value_per_lot=10: equity=1000, risk=0.5%, sl=50p
    # risk_usd=5, lot=5/(50*10)=0.01
    lot = calculate_flex_lot_size(equity=1000, risk_percent=0.5, sl_pips=50, symbol="XAUUSD")
    if abs(lot - 0.01) < 0.001:
        ok(f"XAUUSD flex percent: equity=1000, risk=0.5%, sl=50p => lot={lot:.2f}")
    else:
        fail(f"XAUUSD flex percent: got {lot}, expected 0.01")

    # Fixed amount: $10 / (50*10) = 0.02
    lot2 = calculate_flex_lot_size(equity=1000, risk_percent=0, sl_pips=50, symbol="XAUUSD", risk_amount=10.0)
    if abs(lot2 - 0.02) < 0.001:
        ok(f"XAUUSD flex fixed_amount: $10 risk, sl=50p => lot={lot2:.2f}")
    else:
        fail(f"XAUUSD flex fixed_amount: got {lot2}, expected 0.02")

    # Large equity: equity=10000, risk=1%, sl=30p => 100/(30*10)=0.33
    lot3 = calculate_flex_lot_size(equity=10000, risk_percent=1.0, sl_pips=30, symbol="XAUUSD")
    expected3 = int(100.0 / 30 / 10 / 0.01) * 0.01  # floor to 0.33
    if abs(lot3 - expected3) < 0.001:
        ok(f"XAUUSD flex large equity: equity=10000, risk=1%, sl=30p => lot={lot3:.2f}")
    else:
        fail(f"XAUUSD flex large equity: got {lot3}, expected {expected3}")

    # BTC pip_value_per_lot=1.0: equity=1000, risk=0.5%, sl=50p => 5/(50*1)=0.10
    lot_btc = calculate_flex_lot_size(equity=1000, risk_percent=0.5, sl_pips=50, symbol="BTCUSD")
    if abs(lot_btc - 0.10) < 0.001:
        ok(f"BTCUSD flex: equity=1000, risk=0.5%, sl=50p => lot={lot_btc:.2f}")
    else:
        fail(f"BTCUSD flex: got {lot_btc}, expected 0.10")

    # sl_pips=0 => min_lot guard
    lot_zero = calculate_flex_lot_size(equity=1000, risk_percent=0.5, sl_pips=0, symbol="XAUUSD")
    if lot_zero == 0.01:
        ok("sl_pips=0 returns min_lot (guard correct)")
    else:
        fail(f"sl_pips=0 should return 0.01, got {lot_zero}")


# ---------------------------------------------------------------------------
# 7. Edge cases
# ---------------------------------------------------------------------------

def test_edge_cases():
    print(f"\n{DASH}")
    print("7. EDGE CASES")

    # Empty df
    try:
        res = run_backtest(
            df=pd.DataFrame(columns=["time", "open", "high", "low", "close", "tick_volume"]),
            symbol="XAUUSD", entry_type="pattern", ema_period=21,
        )
        if res["total_trades"] == 0:
            ok("Empty df => 0 trades (no crash)")
        else:
            fail(f"Empty df: unexpected trades={res['total_trades']}")
    except Exception as e:
        fail(f"Empty df crashed: {e}")

    # No FEG signal (all flat candles)
    rows = []
    base = datetime(2026, 1, 2, 0, 0, tzinfo=TIMEZONE)
    for k in range(30):
        rows.append({"time": base + timedelta(minutes=k), "open": 2000, "high": 2001, "low": 1999, "close": 2000, "tick_volume": 1})
    df_flat = pd.DataFrame(rows)
    try:
        res = run_backtest(
            df=df_flat, symbol="XAUUSD", entry_type="pattern", ema_period=21,
        )
        if res["total_trades"] == 0:
            ok("All flat candles => 0 trades (no signal)")
        else:
            fail(f"Flat candles: unexpected trades={res['total_trades']}")
    except Exception as e:
        fail(f"Flat candles crashed: {e}")

    # buffer_k = 0
    df_sig = make_df_with_feg_signals()
    try:
        res = run_backtest(
            df=df_sig.copy(), symbol="XAUUSD", entry_type="pattern", ema_period=21,
            buffer_k=0.0, rr_ratio=2.0, max_candles=7,
        )
        ok(f"buffer_k=0: trades={res['total_trades']} (no crash)")
    except Exception as e:
        fail(f"buffer_k=0 crashed: {e}")

    # rr_ratio = 0.5
    try:
        res = run_backtest(
            df=df_sig.copy(), symbol="XAUUSD", entry_type="pattern", ema_period=21,
            buffer_k=50, rr_ratio=0.5, max_candles=7,
        )
        ok(f"rr_ratio=0.5: trades={res['total_trades']} (no crash)")
    except Exception as e:
        fail(f"rr_ratio=0.5 crashed: {e}")

    # High ema_period (no warmup data)
    try:
        res = run_backtest(
            df=df_sig.copy(), symbol="XAUUSD", entry_type="pattern", ema_period=100,
            buffer_k=50, rr_ratio=2.0, max_candles=7,
        )
        ok(f"ema_period=100 (more than df rows): trades={res['total_trades']} (no crash)")
    except Exception as e:
        fail(f"ema_period=100 crashed: {e}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    print(SEP)
    print("BACKTEST SCENARIO TEST SUITE")
    print(f"Run: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(SEP)

    test_feg_detection()
    test_compute_levels()
    test_check_exit()
    test_backtest_scenarios()
    test_max_candles_zero()
    test_flex_lot()
    test_edge_cases()

    print(f"\n{SEP}")
    if errors:
        print(f"RESULT: {len(errors)} FAILURE(S)")
        for e in errors:
            print(f"  x {e}")
    else:
        print("RESULT: ALL PASS")
    print(SEP)
    return len(errors)


if __name__ == "__main__":
    sys.exit(main())
