#!/usr/bin/env python3
"""Backtest verification script - prints per-trade trace for manual inspection.

Usage:
    python scripts/verify_backtest.py --symbol XAUUSD --days 90
    python scripts/verify_backtest.py --symbol XAUUSD --days 90 --strategy feg
    python scripts/verify_backtest.py --symbol XAUUSD --days 7 --strategy master_candle
"""

import argparse
import os
import sys
from datetime import datetime, timedelta, timezone

import yaml

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.backtest import fetch_historical_data, run_backtest
from src.strategy_manager import get_strategy_parameters
from src.utils import get_pip_value

SEP = "=" * 62


def _load_credentials(user="admin"):
    config_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "config", "auth.yaml",
    )
    with open(config_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)
    users = config.get("credentials", {}).get("usernames", {})
    if user not in users:
        raise ValueError(f"user '{user}' not in config/auth.yaml")
    mt5 = users[user].get("mt5", {})
    if not mt5:
        raise ValueError(f"no mt5 section for user '{user}' in config/auth.yaml")
    return mt5


def _fmt_time(ts):
    return ts.strftime("%Y-%m-%d %H:%M") if hasattr(ts, "strftime") else str(ts)


def _print_mc_trace(trades, pip_value, buffer_k, rr_ratio):
    equity = 1000.0
    for n, t in enumerate(trades, 1):
        c = t.get("_candle", {})
        o, h, l, cl = c.get("open", 0.0), c.get("high", 0.0), c.get("low", 0.0), c.get("close", 0.0)
        direction = t["direction"]
        entry, sl, tp = t["entry"], t["sl"], t["tp"]
        sl_dist = abs(entry - sl)

        print(f"\n[TRADE #{n}]")
        print(f"  Candle  : {t['date']} {t['time']} | O={o:.2f} H={h:.2f} L={l:.2f} C={cl:.2f}")
        if direction == "BUY":
            print(f"  Signal  : C({cl:.2f}) > O({o:.2f}) -> BUY")
            print(f"  SL calc : L({l:.2f}) - {buffer_k}x{pip_value:.2f} = {l - buffer_k * pip_value:.2f}")
            print(f"  TP calc : E({entry:.2f}) + SL_dist({sl_dist:.2f}) x {rr_ratio:.1f} = {entry + sl_dist * rr_ratio:.2f}")
        else:
            print(f"  Signal  : C({cl:.2f}) < O({o:.2f}) -> SELL")
            print(f"  SL calc : H({h:.2f}) + {buffer_k}x{pip_value:.2f} = {h + buffer_k * pip_value:.2f}")
            print(f"  TP calc : E({entry:.2f}) - SL_dist({sl_dist:.2f}) x {rr_ratio:.1f} = {entry - sl_dist * rr_ratio:.2f}")
        print(f"  Entry   : {entry:.2f}  |  SL={sl:.2f}  |  TP={tp:.2f}")
        print(f"  Exit    : {t['exit_type']} | {t['exit_time']} | price={t['exit_price']:.2f} | {t['candles']} candles")
        equity += t["pnl_usd"]
        print(f"  PnL     : {t['pnl_pips']:+.1f} pips | equity ${equity:.2f}")


def _print_feg_trace(trades, pip_value, buffer_k, rr_ratio, ema_period=21):
    equity = 1000.0
    for n, t in enumerate(trades, 1):
        c1 = t.get("_c1", {})
        c2 = t.get("_c2", {})
        ema = t.get("_ema", 0.0)
        exit_pos = t.get("_exit_pos", 0)
        direction = t["direction"]
        entry, sl, tp = t["entry"], t["sl"], t["tp"]
        sl_dist = abs(entry - sl)

        h1, l1 = c1.get("high", 0.0), c1.get("low", 0.0)
        h2 = c2.get("high", 0.0)
        l2 = c2.get("low", 0.0)
        c2_close = c2.get("close", 0.0)
        c1_time = _fmt_time(c1.get("time", ""))
        c2_time = _fmt_time(c2.get("time", ""))

        print(f"\n[TRADE #{n}]")
        print(f"  C1      : {c1_time} | H={h1:.2f} L={l1:.2f}")
        print(f"  C2      : {c2_time} | H={h2:.2f} L={l2:.2f} C={c2_close:.2f}")
        print(f"  EMA{ema_period:<3} : {ema:.2f}")

        if direction == "SELL":
            chk1 = f"H2({h2:.2f})>H1({h1:.2f}){'[ok]' if h2 > h1 else '[!!]'}"
            chk2 = f"C2({c2_close:.2f})<L1({l1:.2f}){'[ok]' if c2_close < l1 else '[!!]'}"
            chk3 = f"L2({l2:.2f})>EMA({ema:.2f}){'[ok]' if l2 > ema else '[!!]'}"
            print(f"  Checks  : {chk1}  {chk2}  {chk3}")
            print(f"  Signal  : SELL")
            print(f"  SL calc : H2({h2:.2f}) + {buffer_k}x{pip_value:.2f} = {h2 + buffer_k * pip_value:.2f}")
            print(f"  TP calc : E({entry:.2f}) - SL_dist({sl_dist:.2f}) x {rr_ratio:.1f} = {entry - sl_dist * rr_ratio:.2f}")
        else:
            chk1 = f"L2({l2:.2f})<L1({l1:.2f}){'[ok]' if l2 < l1 else '[!!]'}"
            chk2 = f"C2({c2_close:.2f})>H1({h1:.2f}){'[ok]' if c2_close > h1 else '[!!]'}"
            chk3 = f"H2({h2:.2f})<EMA({ema:.2f}){'[ok]' if h2 < ema else '[!!]'}"
            print(f"  Checks  : {chk1}  {chk2}  {chk3}")
            print(f"  Signal  : BUY")
            print(f"  SL calc : L2({l2:.2f}) - {buffer_k}x{pip_value:.2f} = {l2 - buffer_k * pip_value:.2f}")
            print(f"  TP calc : E({entry:.2f}) + SL_dist({sl_dist:.2f}) x {rr_ratio:.1f} = {entry + sl_dist * rr_ratio:.2f}")

        print(f"  Entry   : {entry:.2f}  |  SL={sl:.2f}  |  TP={tp:.2f}")
        print(f"  Exit    : {t['exit_type']} | {t['exit_time']} | price={t['exit_price']:.2f} | {t['candles']} candles")
        equity += t["pnl_usd"]
        print(f"  PnL     : {t['pnl_pips']:+.1f} pips | equity ${equity:.2f}")
        print(f"  Next scan from i={exit_pos + 1}")


def _print_summary(label, res):
    print(f"\n{SEP}")
    print(f"{label} SUMMARY")
    print(f"  Trades   : {res['total_trades']}")
    wins = res.get("wins", 0)
    losses = res.get("losses", 0)
    wr = res.get("win_rate", 0.0)
    pf = res.get("profit_factor", 0.0)
    total_pips = res.get("total_pnl", 0.0)
    final_eq = res.get("final_equity", 1000.0)
    print(f"  Win/Loss : {wins}/{losses} ({wr:.1f}%)")
    print(f"  P/F      : {pf:.2f}")
    print(f"  Total    : {total_pips:+.1f} pips")
    print(f"  Equity   : ${final_eq:.2f}")
    print(SEP)


def _run_master_candle(df, symbol, days):
    p = get_strategy_parameters("master_candle")
    if not p:
        print("ERROR: master_candle strategy not found in strategies/")
        return None
    pip_value = get_pip_value(symbol)
    hour, minute = [int(x) for x in p["entry_time"].split(":")]
    buffer_k = float(p["buffer_k"])
    rr_ratio = float(p["rr_ratio"])

    print(f"\n{'-' * 62}")
    print(f"MASTER CANDLE  |  {symbol}  |  {days}d lookback")
    print(f"params: entry={p['entry_time']} HCM  buffer_k={buffer_k}  rr={rr_ratio}")
    print(f"        max_candles={p['max_candles']}  tp={p['tp_type']}  sl={p['sl_type']}")
    print(f"{'-' * 62}")

    try:
        res = run_backtest(
            df=df.copy(),
            symbol=symbol,
            entry_hour=hour,
            entry_minute=minute,
            rr_ratio=rr_ratio,
            max_candles=int(p["max_candles"]),
            lot_mode="fixed",
            fixed_lot=float(p["lot_size"]),
            buffer_k=buffer_k,
            tp_type=p["tp_type"],
            sl_type=p["sl_type"],
            entry_mode="close",
            starting_equity=1000.0,
        )
    except Exception as exc:
        print(f"ERROR running master_candle backtest: {exc}")
        return None

    if res["total_trades"] == 0:
        print("  [no trades found in this period]")
    else:
        _print_mc_trace(res["trades"], pip_value, buffer_k, rr_ratio)
    _print_summary("MASTER CANDLE", res)
    return res


def _run_feg(df, symbol, days):
    p = get_strategy_parameters("feg_ema21")
    if not p:
        print("ERROR: feg_ema21 strategy not found in strategies/")
        return None
    pip_value = get_pip_value(symbol)
    ema_period = int(p["ema_period"])
    buffer_k = float(p["buffer_k"])
    rr_ratio = float(p["rr_ratio"])
    ema_dist_enabled = bool(p.get("ema_distance_enabled", False))
    ema_dist_pips = float(p.get("ema_distance_pips", 0.0))

    print(f"\n{'-' * 62}")
    print(f"FEG EMA21  |  {symbol}  |  {days}d lookback")
    print(f"params: ema_period={ema_period}  buffer_k={buffer_k}  rr={rr_ratio}")
    print(f"        ema_distance: enabled={ema_dist_enabled}  pips={ema_dist_pips}")
    print(f"        max_candles={p['max_candles']}  tp={p['tp_type']}  sl={p['sl_type']}")
    print(f"{'-' * 62}")

    try:
        res = run_backtest(
            df=df.copy(),
            symbol=symbol,
            entry_type="pattern",
            ema_period=ema_period,
            ema_distance_enabled=ema_dist_enabled,
            ema_distance_pips=ema_dist_pips,
            rr_ratio=rr_ratio,
            max_candles=int(p["max_candles"]),
            lot_mode="fixed",
            fixed_lot=float(p["lot_size"]),
            buffer_k=buffer_k,
            tp_type=p["tp_type"],
            sl_type=p["sl_type"],
            entry_mode="close",
            starting_equity=1000.0,
        )
    except Exception as exc:
        print(f"ERROR running feg backtest: {exc}")
        return None

    if res["total_trades"] == 0:
        print("  [no trades found in this period]")
    else:
        _print_feg_trace(res["trades"], pip_value, buffer_k, rr_ratio, ema_period)
    _print_summary("FEG EMA21", res)
    return res


def main():
    parser = argparse.ArgumentParser(description="Backtest verification - per-trade trace")
    parser.add_argument("--symbol", default="XAUUSD", help="MT5 symbol (default: XAUUSD)")
    parser.add_argument("--days", type=int, default=90, help="Lookback days (default: 90)")
    parser.add_argument(
        "--strategy", default="all",
        choices=["all", "master_candle", "feg"],
        help="Which strategy to verify (default: all)",
    )
    parser.add_argument("--user", default="admin", help="Auth user for MT5 credentials")
    parser.add_argument("--timeframe", default="M1", help="Candle timeframe (default: M1)")
    args = parser.parse_args()

    # credentials
    try:
        credentials = _load_credentials(args.user)
    except (FileNotFoundError, ValueError) as exc:
        print(f"ERROR: {exc}")
        sys.exit(1)

    # fetch data
    end_dt = datetime.now(tz=timezone.utc)
    start_dt = end_dt - timedelta(days=args.days)
    print(f"Fetching {args.timeframe} data: {args.symbol}  {start_dt.date()} -> {end_dt.date()}")
    df, err = fetch_historical_data(args.symbol, start_dt, end_dt, credentials, args.timeframe)
    if err:
        print(f"ERROR fetching data: {err}")
        sys.exit(1)
    if df is None or df.empty:
        print("ERROR: empty DataFrame returned - is MT5 connected?")
        sys.exit(1)
    print(f"Loaded {len(df)} {args.timeframe} candles")

    # run strategies
    results = {}
    if args.strategy in ("all", "master_candle"):
        results["master_candle"] = _run_master_candle(df, args.symbol, args.days)

    if args.strategy in ("all", "feg"):
        results["feg"] = _run_feg(df, args.symbol, args.days)

    # overall summary (only when both ran)
    if args.strategy == "all":
        mc = results.get("master_candle")
        feg = results.get("feg")
        total = (mc["total_trades"] if mc else 0) + (feg["total_trades"] if feg else 0)
        print(f"\n{SEP}")
        print("OVERALL")
        print(f"  Total trades (both strategies): {total}")
        print(SEP)


if __name__ == "__main__":
    main()
