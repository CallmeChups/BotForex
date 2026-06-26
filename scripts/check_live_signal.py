#!/usr/bin/env python3
"""One-shot live signal check for FEG EMA21.

Shows exactly what the bot sees on the current candles, whether a signal
would fire, and what the computed SL/TP would be. Useful for Phase 2
pipeline verification without waiting for a live signal.

Usage:
    python scripts/check_live_signal.py
    python scripts/check_live_signal.py --symbol XAUUSDm --user admin
"""

import argparse
import os
import sys
from datetime import datetime
from zoneinfo import ZoneInfo

import yaml

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.strategy_manager import get_strategy_parameters
from src.bot_runner import get_mt5_connection, get_recent_candles, feg_entry_decision

TIMEZONE = ZoneInfo("Asia/Ho_Chi_Minh")


def _load_mt5_credentials(user="admin"):
    config_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "config", "auth.yaml",
    )
    with open(config_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)
    return config["credentials"]["usernames"][user]["mt5"]


def main():
    parser = argparse.ArgumentParser(description="One-shot FEG live signal check")
    parser.add_argument("--symbol", default="XAUUSDm")
    parser.add_argument("--user", default="admin")
    args = parser.parse_args()

    now = datetime.now(TIMEZONE).strftime("%Y-%m-%d %H:%M:%S")
    print(f"\n[check_live_signal] {now}")
    print(f"Symbol: {args.symbol}  User: {args.user}")
    print("-" * 50)

    # Load strategy
    p = get_strategy_parameters("feg_ema21")
    if not p:
        print("ERROR: feg_ema21 strategy not found")
        sys.exit(1)
    ema_period = int(p["ema_period"])
    rr_ratio = float(p["rr_ratio"])
    buffer_k = float(p["buffer_k"])
    lot_size = float(p["lot_size"])
    ema_dist_enabled = bool(p.get("ema_distance_enabled", False))
    ema_dist_pips = float(p.get("ema_distance_pips", 0.0))
    timeframe = p.get("timeframe", "M5")

    print(f"Strategy: EMA{ema_period}  RR={rr_ratio}  buffer_k={buffer_k}  lot={lot_size}")
    print(f"EMA distance: {'ON ' + str(ema_dist_pips) + 'p' if ema_dist_enabled else 'OFF'}")

    # Connect MT5
    creds = _load_mt5_credentials(args.user)
    mt5, err = get_mt5_connection(creds)
    if err:
        print(f"ERROR: MT5 connect failed: {err}")
        sys.exit(1)
    print("MT5: connected OK")

    # Fetch candles
    count = max(120, ema_period * 4)
    df = get_recent_candles(mt5, args.symbol, timeframe, count=count)
    mt5.shutdown()

    if df is None or len(df) < ema_period + 2:
        print(f"ERROR: not enough candles (got {len(df) if df is not None else 0}, need {ema_period + 2})")
        sys.exit(1)
    print(f"Candles fetched: {len(df)}")

    # EMA
    ema = df["close"].ewm(span=ema_period, adjust=False).mean().tolist()
    last = df.iloc[-1]
    prev = df.iloc[-2]
    c1 = {"open": prev["open"], "high": prev["high"], "low": prev["low"], "close": prev["close"]}
    c2 = {"open": last["open"], "high": last["high"], "low": last["low"], "close": last["close"]}
    ema2 = ema[-1]

    c1_time = datetime.fromtimestamp(int(prev["time"]), tz=TIMEZONE).strftime("%Y-%m-%d %H:%M")
    c2_time = datetime.fromtimestamp(int(last["time"]), tz=TIMEZONE).strftime("%Y-%m-%d %H:%M")

    print(f"\nC1 ({c1_time}): H={c1['high']:.2f}  L={c1['low']:.2f}  C={c1['close']:.2f}")
    print(f"C2 ({c2_time}): H={c2['high']:.2f}  L={c2['low']:.2f}  C={c2['close']:.2f}")
    print(f"EMA{ema_period}: {ema2:.2f}")

    # SELL checks
    chk_sell = [
        ("H2>H1", c2["high"] > c1["high"]),
        ("C2<L1", c2["close"] < c1["low"]),
        (f"L2>EMA{ema_period}", c2["low"] > ema2),
    ]
    # BUY checks
    chk_buy = [
        ("L2<L1", c2["low"] < c1["low"]),
        ("C2>H1", c2["close"] > c1["high"]),
        (f"H2<EMA{ema_period}", c2["high"] < ema2),
    ]

    def fmt_checks(checks):
        return "  ".join(f"{name}={'[ok]' if ok else '[!!]'}" for name, ok in checks)

    print(f"\nSELL: {fmt_checks(chk_sell)}  -> {'SELL' if all(ok for _, ok in chk_sell) else 'no'}")
    print(f"BUY:  {fmt_checks(chk_buy)}  -> {'BUY' if all(ok for _, ok in chk_buy) else 'no'}")

    # Actual signal
    signal = feg_entry_decision(
        None, c1, c2, ema2, args.symbol,
        rr_ratio, buffer_k, lot_size, "close", 0.0,
        ema_dist_enabled, ema_dist_pips,
    )

    print()
    if signal:
        print(f"SIGNAL: {signal['direction']}")
        print(f"  Entry : {signal['entry_price']:.2f}")
        print(f"  SL    : {signal['stop_loss']:.2f}  ({abs(signal['entry_price'] - signal['stop_loss']):.2f} dist)")
        print(f"  TP    : {signal['take_profit']:.2f}  ({abs(signal['entry_price'] - signal['take_profit']):.2f} dist)")
        print(f"  Lot   : {lot_size}")
        print(f"\n  -> In test mode: [TEST] {signal['direction']} {args.symbol} @ {signal['entry_price']:.2f} simulated")
    else:
        print("SIGNAL: none (conditions not met on last 2 candles)")

    print("-" * 50)


if __name__ == "__main__":
    main()
