# Backtest Verification Script — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Create `scripts/verify_backtest.py` to print a per-trade trace (signal conditions, SL/TP math, exit info, running equity) for both Master Candle and FEG EMA21 backtests using real MT5 historical data.

**Architecture:** Two tasks. Task 1 extends each trade dict in `src/backtest.py` with underscore-prefixed debug fields (`_candle` for Master Candle; `_c1`, `_c2`, `_ema`, `_exit_pos` for FEG) — these give the verify script all OHLC and EMA data it needs without re-running the signal detection. Task 2 writes the verify script: parse args, load MT5 credentials from `config/auth.yaml`, fetch M5 data, call `run_backtest()` for each strategy, and format each trade as a labeled trace block.

**Tech Stack:** Python 3.10+, pandas, PyYAML, `src.backtest`, `src.strategy_manager`, `src.utils`

## Global Constraints

- Python 3.10+ — use `zoneinfo` (stdlib), not `pytz`
- MT5 operations are Windows-only — `fetch_historical_data` calls MT5; script must be run on Windows with MT5 terminal open
- Debug fields use `_` prefix to mark them as trace-only (not core trade record, not persisted)
- Script does `sys.path.insert(0, …)` — no package installation or `PYTHONPATH` changes needed
- `get_pip_value("XAUUSD")` returns `0.1` — all SL/TP math in trace uses this
- No new test file for `scripts/verify_backtest.py` — the script itself is the verification artifact
- `config/auth.yaml` structure: `credentials.usernames.<user>.mt5` → dict with `login`, `password`, `server`
- Run all tests from project root: `pytest tests/ -v`
- `run_backtest` signature (src/backtest.py:252): `entry_type="time"` or `"pattern"` kwarg controls dispatch

---

### Task 1: Add per-trade debug fields to backtest.py

**Files:**
- Modify: `src/backtest.py` lines 363–367 (master candle path, after `trades.append(trade)`)
- Modify: `src/backtest.py` lines 426–432 (FEG path, after `trades.append(trade)`)
- Modify: `tests/test_backtest_time_characterization.py` (extend existing test)
- Modify: `tests/test_backtest_feg.py` (extend existing test)

**Interfaces:**
- Consumes: `_make_trade()` return value (already has `direction`, `entry`, `sl`, `tp`, `exit_type`, `exit_price`, `exit_time`, `candles`, `pnl_pips`, `pnl_usd`)
- Produces: each trade dict gains these extra keys:
  - Master Candle path: `_candle: {"open": float, "high": float, "low": float, "close": float}`
  - FEG path: `_c1: {"open":…, "high":…, "low":…, "close":…, "time": pd.Timestamp}`, `_c2: same`, `_ema: float`, `_exit_pos: int`
- Task 2 reads these fields by key access.

- [ ] **Step 1: Write failing assertions in test_backtest_time_characterization.py**

Open `tests/test_backtest_time_characterization.py`. After the existing asserts in `test_time_backtest_produces_one_bullish_trade`, add:

```python
def test_time_backtest_produces_one_bullish_trade():
    df = _df()
    res = run_backtest(
        df=df, symbol="XAUUSD", entry_hour=21, entry_minute=5,
        rr_ratio=2.0, max_candles=7, lot_mode="fixed", fixed_lot=0.01,
        buffer_k=5.0, tp_type="price_based", sl_type="close_based",
        entry_mode="close",
    )
    assert res["total_trades"] == 1
    t = res["trades"][0]
    assert t["direction"] == "BUY"
    assert round(t["entry"], 4) == 100.8
    assert round(t["sl"], 4) == 99.0
    assert round(t["tp"], 4) == 104.4
    # debug fields (Task 1)
    assert "_candle" in t
    assert t["_candle"] == {"open": 100.0, "high": 101.0, "low": 99.5, "close": 100.8}
```

- [ ] **Step 2: Write failing assertions in test_backtest_feg.py**

Open `tests/test_backtest_feg.py`. In `test_feg_backtest_sell_when_ema_below_low2`, after `assert round(t["tp"], 4) == 89.0`, add:

```python
    # debug fields (Task 1)
    assert "_c1" in t
    assert "_c2" in t
    assert "_ema" in t
    assert "_exit_pos" in t
    assert set(t["_c1"].keys()) >= {"open", "high", "low", "close", "time"}
    assert t["_c1"]["high"] == 101.0    # candle1 high from fixture
    assert t["_c2"]["close"] == 98.0    # candle2 close from fixture
    assert t["_ema"] < 98.5             # EMA < L2 (that's why SELL fired)
    assert isinstance(t["_exit_pos"], int)
    assert t["_exit_pos"] >= 32         # exit candle is after candle2 at index 31
```

- [ ] **Step 3: Run tests to verify they fail**

```
pytest tests/test_backtest_time_characterization.py tests/test_backtest_feg.py -v
```

Expected: both test functions FAIL with `AssertionError: assert '_candle' in {...}` (or `_c1`).

- [ ] **Step 4: Add debug field to master candle path in backtest.py**

In `src/backtest.py`, locate lines 360–367 (the master candle `_make_trade` + `trades.append` block). Add one line after `trades.append(trade)`:

```python
        trade, pnl_pips, pnl_usd = _make_trade(
            entry_time, direction, levels, lot_size, exit_type, exit_price,
            exit_time, candles_held, symbol,
        )
        current_equity += pnl_usd
        trades.append(trade)
        trade["_candle"] = {"open": o, "high": h, "low": l, "close": c}  # trace-only
        equity_curve_pips.append(equity_curve_pips[-1] + pnl_pips)
        equity_curve_usd.append(current_equity)
```

- [ ] **Step 5: Add debug fields to FEG path in backtest.py**

In `src/backtest.py`, locate lines 422–432 (the FEG `_make_trade` + `trades.append` block). Add four lines after `trades.append(trade)`:

```python
            trade, pnl_pips, pnl_usd = _make_trade(
                df.at[i, "time"], direction, levels, lot_size, exit_type,
                exit_price, exit_time, candles_held, symbol,
            )
            current_equity += pnl_usd
            trades.append(trade)
            trade["_c1"] = {**c1, "time": df.at[i - 1, "time"]}   # trace-only
            trade["_c2"] = {**c2, "time": df.at[i, "time"]}        # trace-only
            trade["_ema"] = ema[i]                                   # trace-only
            trade["_exit_pos"] = exit_pos                            # trace-only
            equity_curve_pips.append(equity_curve_pips[-1] + pnl_pips)
            equity_curve_usd.append(current_equity)
```

- [ ] **Step 6: Run tests to verify they pass**

```
pytest tests/test_backtest_time_characterization.py tests/test_backtest_feg.py -v
```

Expected: PASS — 3 tests (1 characterization + 2 FEG).

- [ ] **Step 7: Run full suite to verify no regressions**

```
pytest tests/ -v
```

Expected: 25 passed (all existing tests unchanged).

- [ ] **Step 8: Commit**

```
git add src/backtest.py tests/test_backtest_time_characterization.py tests/test_backtest_feg.py
git commit -m "feat: add per-trade debug fields to backtest trade dicts"
```

---

### Task 2: Write scripts/verify_backtest.py

**Files:**
- Create: `scripts/verify_backtest.py`

**Interfaces:**
- Consumes (from Task 1): `trade["_candle"]`, `trade["_c1"]`, `trade["_c2"]`, `trade["_ema"]`, `trade["_exit_pos"]`
- Consumes: `run_backtest(df, symbol, entry_type=…, **params)` → `dict` with keys `total_trades`, `trades`, `winning_trades`, `losing_trades`, `win_rate`, `profit_factor`, `total_pips`, `final_equity`
- Consumes: `fetch_historical_data(symbol, start_date, end_date, credentials, "M5")` → `(df, error)`
- Consumes: `get_strategy_parameters(strategy_id)` → dict with `entry_time`, `rr_ratio`, `buffer_k`, `lot_size`, `max_candles`, `tp_type`, `sl_type`, `ema_period`, `ema_distance_enabled`, `ema_distance_pips`
- Consumes: `get_pip_value(symbol)` → `float` (0.1 for XAUUSD)
- Produces: stdout trace output for manual verification

- [ ] **Step 1: Create scripts/ directory and write verify_backtest.py**

Create `scripts/verify_backtest.py` with the full content below:

```python
#!/usr/bin/env python3
"""Backtest verification script — prints per-trade trace for manual inspection.

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

SEP = "═" * 62


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
            print(f"  Signal  : C({cl:.2f}) > O({o:.2f}) → BUY")
            print(f"  SL calc : L({l:.2f}) - {buffer_k}×{pip_value:.2f} = {l - buffer_k * pip_value:.2f}")
            print(f"  TP calc : E({entry:.2f}) + SL_dist({sl_dist:.2f}) × {rr_ratio:.1f} = {entry + sl_dist * rr_ratio:.2f}")
        else:
            print(f"  Signal  : C({cl:.2f}) < O({o:.2f}) → SELL")
            print(f"  SL calc : H({h:.2f}) + {buffer_k}×{pip_value:.2f} = {h + buffer_k * pip_value:.2f}")
            print(f"  TP calc : E({entry:.2f}) - SL_dist({sl_dist:.2f}) × {rr_ratio:.1f} = {entry - sl_dist * rr_ratio:.2f}")
        print(f"  Entry   : {entry:.2f}  |  SL={sl:.2f}  |  TP={tp:.2f}")
        print(f"  Exit    : {t['exit_type']} | {t['exit_time']} | price={t['exit_price']:.2f} | {t['candles']} candles")
        equity += t["pnl_usd"]
        print(f"  PnL     : {t['pnl_pips']:+.1f} pips | equity ${equity:.2f}")


def _print_feg_trace(trades, pip_value, buffer_k, rr_ratio):
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
        print(f"  EMA21   : {ema:.2f}")

        if direction == "SELL":
            chk1 = f"H2({h2:.2f})>H1({h1:.2f}){'✓' if h2 > h1 else '✗'}"
            chk2 = f"C2({c2_close:.2f})<L1({l1:.2f}){'✓' if c2_close < l1 else '✗'}"
            chk3 = f"L2({l2:.2f})>EMA({ema:.2f}){'✓' if l2 > ema else '✗'}"
            print(f"  Checks  : {chk1}  {chk2}  {chk3}")
            print(f"  Signal  : SELL")
            print(f"  SL calc : H2({h2:.2f}) + {buffer_k}×{pip_value:.2f} = {h2 + buffer_k * pip_value:.2f}")
            print(f"  TP calc : E({entry:.2f}) - SL_dist({sl_dist:.2f}) × {rr_ratio:.1f} = {entry - sl_dist * rr_ratio:.2f}")
        else:
            chk1 = f"L2({l2:.2f})<L1({l1:.2f}){'✓' if l2 < l1 else '✗'}"
            chk2 = f"C2({c2_close:.2f})>H1({h1:.2f}){'✓' if c2_close > h1 else '✗'}"
            chk3 = f"H2({h2:.2f})<EMA({ema:.2f}){'✓' if h2 < ema else '✗'}"
            print(f"  Checks  : {chk1}  {chk2}  {chk3}")
            print(f"  Signal  : BUY")
            print(f"  SL calc : L2({l2:.2f}) - {buffer_k}×{pip_value:.2f} = {l2 - buffer_k * pip_value:.2f}")
            print(f"  TP calc : E({entry:.2f}) + SL_dist({sl_dist:.2f}) × {rr_ratio:.1f} = {entry + sl_dist * rr_ratio:.2f}")

        print(f"  Entry   : {entry:.2f}  |  SL={sl:.2f}  |  TP={tp:.2f}")
        print(f"  Exit    : {t['exit_type']} | {t['exit_time']} | price={t['exit_price']:.2f} | {t['candles']} candles")
        equity += t["pnl_usd"]
        print(f"  PnL     : {t['pnl_pips']:+.1f} pips | equity ${equity:.2f}")
        print(f"  Next scan from i={exit_pos + 1}")


def _print_summary(label, res):
    print(f"\n{SEP}")
    print(f"{label} SUMMARY")
    print(f"  Trades   : {res['total_trades']}")
    wins = res.get("winning_trades", 0)
    losses = res.get("losing_trades", 0)
    wr = res.get("win_rate", 0.0)
    pf = res.get("profit_factor", 0.0)
    total_pips = res.get("total_pips", 0.0)
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

    print(f"\n{'─' * 62}")
    print(f"MASTER CANDLE  |  {symbol}  |  {days}d lookback")
    print(f"params: entry={p['entry_time']} HCM  buffer_k={buffer_k}  rr={rr_ratio}")
    print(f"        max_candles={p['max_candles']}  tp={p['tp_type']}  sl={p['sl_type']}")
    print(f"{'─' * 62}")

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

    print(f"\n{'─' * 62}")
    print(f"FEG EMA21  |  {symbol}  |  {days}d lookback")
    print(f"params: ema_period={ema_period}  buffer_k={buffer_k}  rr={rr_ratio}")
    print(f"        ema_distance: enabled={ema_dist_enabled}  pips={ema_dist_pips}")
    print(f"        max_candles={p['max_candles']}  tp={p['tp_type']}  sl={p['sl_type']}")
    print(f"{'─' * 62}")

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
        _print_feg_trace(res["trades"], pip_value, buffer_k, rr_ratio)
    _print_summary("FEG EMA21", res)
    return res


def main():
    parser = argparse.ArgumentParser(description="Backtest verification — per-trade trace")
    parser.add_argument("--symbol", default="XAUUSD", help="MT5 symbol (default: XAUUSD)")
    parser.add_argument("--days", type=int, default=90, help="Lookback days (default: 90)")
    parser.add_argument(
        "--strategy", default="all",
        choices=["all", "master_candle", "feg"],
        help="Which strategy to verify (default: all)",
    )
    parser.add_argument("--user", default="admin", help="Auth user for MT5 credentials")
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
    print(f"Fetching M5 data: {args.symbol}  {start_dt.date()} → {end_dt.date()}")
    df, err = fetch_historical_data(args.symbol, start_dt, end_dt, credentials, "M5")
    if err:
        print(f"ERROR fetching data: {err}")
        sys.exit(1)
    if df is None or df.empty:
        print("ERROR: empty DataFrame returned — is MT5 connected?")
        sys.exit(1)
    print(f"Loaded {len(df)} M5 candles")

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
```

- [ ] **Step 2: Verify the script runs without import errors (no MT5 needed)**

Run with `--help` only (no data fetch, no MT5):

```
python scripts/verify_backtest.py --help
```

Expected output:
```
usage: verify_backtest.py [-h] [--symbol SYMBOL] [--days DAYS]
                          [--strategy {all,master_candle,feg}] [--user USER]
...
```

If you see `ModuleNotFoundError`, check that `sys.path.insert` points to project root and `requirements.txt` packages are installed.

- [ ] **Step 3: Run full test suite to confirm no regressions**

```
pytest tests/ -v
```

Expected: 25 passed (the script file itself does not add test files).

- [ ] **Step 4: Commit**

```
git add scripts/verify_backtest.py
git commit -m "feat: add scripts/verify_backtest.py for Phase 1 backtest verification"
```

---

## Phase 2 — Live Demo Testing Runbook

No code to write. These are manual steps after Phase 1 passes. Checklist embedded here for reference.

### Pre-condition

Update `config/auth.yaml` with new demo account credentials under the `mt5:` key for the `admin` user:

```yaml
credentials:
  usernames:
    admin:
      mt5:
        login: "<new_demo_login>"
        password: "<new_demo_password>"
        server: "<broker_server>"
```

Verify connection:
```python
python -c "
import yaml; from src.orders import get_account_info
creds = yaml.safe_load(open('config/auth.yaml'))['credentials']['usernames']['admin']['mt5']
info, err = get_account_info(creds)
print(info or err)
"
```

### Step 2 — Test Mode (`--test 1`)

```bash
python src/bot_runner.py --strategy feg_ema21 --symbol XAUUSDm --user admin --test 1 --interval 60
```

- [ ] MT5 connects and login OK (log in console)
- [ ] `get_recent_candles` returns DataFrame, no live candle
- [ ] EMA21 computed without error
- [ ] FEG pattern detected → log signal + `[TEST] simulated`
- [ ] Telegram receives `[TEST] BUY/SELL XAUUSDm …`
- [ ] `active_trade` set after signal; subsequent signals skipped
- [ ] TP/SL/TIME → log exit + Telegram exit message

### Step 3 — Live Mode (`--test 0`)

```bash
python src/bot_runner.py --strategy feg_ema21 --symbol XAUUSDm --user admin --test 0 --interval 60
```

- [ ] `place_order` calls MT5 → returns ticket number in log
- [ ] Order visible in MT5 terminal with `magic=212100`, `comment="FEG"`
- [ ] SL/TP on the order match the trace output from `scripts/verify_backtest.py`
- [ ] Telegram reports "Order placed at {price}"
- [ ] Exit condition triggers `close_position_by_ticket`; Telegram reports exit type + PnL

**Safety:** demo account only; `fixed_lot=0.01`.

### Step 4 — Master Candle Smoke Test

```bash
python src/bot_runner.py --strategy master_candle --symbol XAUUSDm --user admin --test 1 --interval 60
```

- [ ] Dispatches to `run_master_candle_bot` (not FEG path)
- [ ] Bot waits until 21:05 HCM and logs "waiting for entry candle"
- [ ] No crash on startup

### Fail Conditions

| Condition | Action |
|---|---|
| Step 2 fails | Do not proceed to Step 3 |
| Step 3 fails (place_order) | Log the specific error; manually close any open orders via MT5 terminal or `pages/2_Orders.py` |
| Bot crash while order is open | Close manually from MT5 terminal |

---

## Unresolved Questions

- Demo account credentials will be provided by user after Phase 1 passes
- Confirm symbol suffix for demo account (assumed `XAUUSDm` — verify when credentials are provided)
