# FEG Reverse Strategy Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add FEG Reverse as a new strategy — detects FEG Classic pattern then flips the trade direction (SELL pattern → BUY order, BUY pattern → SELL order).

**Architecture:** New `src/feg_reverse_strategy.py` wraps `detect_feg_signal` from FEG Classic and inverts the returned direction before computing SL/TP for the new direction. `bot_runner.py` gets a `feg_reverse_entry_decision` function + dispatch in the pattern routing block. `backtest.py` gets `_run_feg_reverse_backtest` mirroring `_run_feg_backtest`. Pages need no changes — `is_pattern` already covers any `entry_type: pattern` strategy.

**Tech Stack:** Python 3.11, existing `src/feg_strategy.py`, `src/utils.py` (`get_pip_value`, `compute_trade_levels`), PyYAML for strategy config, pytest.

## Global Constraints

- ID nội bộ: `feg_reverse` — không đổi sau khi tạo
- Wick filter dùng params của **pattern gốc** (c2_sell_* khi SELL pattern, c2_buy_* khi BUY pattern)
- SL/TP tính theo **chiều lệnh mới** (flipped direction), không phải pattern direction
- EMA filter giữ nguyên theo pattern gốc
- Không có stop order variant
- Không sửa `src/feg_strategy.py`

---

## File Map

| File | Action | Responsibility |
|---|---|---|
| `src/feg_reverse_strategy.py` | Create | detect + flip direction + compute levels |
| `strategies/feg_reverse.yaml` | Create | Strategy config |
| `src/bot_runner.py` | Modify | Add `feg_reverse_entry_decision` + dispatch |
| `src/backtest.py` | Modify | Add `_run_feg_reverse_backtest` + dispatch |
| `tests/test_feg_reverse.py` | Create | Unit tests |

---

### Task 1: `src/feg_reverse_strategy.py` + `strategies/feg_reverse.yaml`

**Files:**
- Create: `src/feg_reverse_strategy.py`
- Create: `strategies/feg_reverse.yaml`
- Test: `tests/test_feg_reverse.py`

**Interfaces:**
- Produces:
  - `detect_feg_reverse_signal(candle1, candle2, ema2, pip_value, **wick_ema_params) -> str | None` — returns `"BUY"`, `"SELL"`, or `None`
  - `analyze_feg_reverse(symbol, candle1, candle2, ema2, rr_ratio, buffer_k, lot_size, entry_mode, entry_percent, **wick_ema_params) -> dict | None`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_feg_reverse.py
import pytest
from src.feg_reverse_strategy import detect_feg_reverse_signal, analyze_feg_reverse

# Minimal candle helpers
def _sell_candle(high, low, open_, close):
    return {"high": high, "low": low, "open": open_, "close": close}

def _buy_candle(high, low, open_, close):
    return {"high": high, "low": low, "open": open_, "close": close}

PIP = 0.1  # XAUUSDm pip

# SELL pattern (2 bearish candles) → FEG Reverse should return "BUY"
C1_SELL = _sell_candle(1950, 1940, 1949, 1941)  # bearish body=8
C2_SELL = _sell_candle(1955, 1930, 1954, 1931)  # bearish body=23, H2>H1, C2<L1
EMA_ABOVE = 1960.0  # L2=1930 > EMA=1960? No. Try EMA below candles

def test_sell_pattern_returns_buy():
    """FEG SELL pattern detected → reverse → direction is BUY."""
    c1 = _sell_candle(1950, 1940, 1949, 1941)
    c2 = _sell_candle(1955, 1930, 1954, 1931)
    ema = 1920.0  # L2=1930 > EMA=1920 → sell_ema_side="above_ema" passes
    sig = detect_feg_reverse_signal(c1, c2, ema, PIP, sell_ema_side="above_ema")
    assert sig == "BUY"

def test_buy_pattern_returns_sell():
    """FEG BUY pattern detected → reverse → direction is SELL."""
    c1 = _buy_candle(1950, 1940, 1941, 1949)   # bullish body=8
    c2 = _buy_candle(1970, 1935, 1936, 1969)   # bullish body=33, L2<L1, C2>H1
    ema = 1980.0  # H2=1970 < EMA=1980 → buy_ema_side="below_ema" passes
    sig = detect_feg_reverse_signal(c1, c2, ema, PIP, buy_ema_side="below_ema")
    assert sig == "SELL"

def test_no_pattern_returns_none():
    """No FEG pattern → None."""
    c1 = _sell_candle(1950, 1940, 1949, 1941)
    c2 = _buy_candle(1960, 1942, 1943, 1958)   # mixed directions
    sig = detect_feg_reverse_signal(c1, c2, 1970.0, PIP)
    assert sig is None

def test_analyze_feg_reverse_buy_direction():
    """analyze_feg_reverse on SELL pattern returns dict with direction=BUY."""
    c1 = _sell_candle(1950, 1940, 1949, 1941)
    c2 = _sell_candle(1955, 1930, 1954, 1931)
    ema = 1920.0
    result = analyze_feg_reverse(
        "XAUUSDm", c1, c2, ema,
        rr_ratio=2.0, buffer_k=5.0, lot_size=0.01,
        entry_mode="close", entry_percent=0.0,
        sell_ema_side="above_ema",
    )
    assert result is not None
    assert result["direction"] == "BUY"
    # SL must be below entry for BUY
    assert result["stop_loss"] < result["entry_price"]
    assert result["take_profit"] > result["entry_price"]

def test_wick_filter_rejects_on_pattern_side():
    """Wick filter uses pattern params, not flipped-direction params."""
    c1 = _sell_candle(1950, 1940, 1949, 1941)
    c2 = _sell_candle(1955, 1900, 1954, 1931)  # lower wick = 1931-1900 = 31, body=23
    ema = 1880.0  # L2=1900 > EMA=1880 passes above_ema
    # c2_sell_lower_wick_cmp="lt", pct=50 → reject if wick >= 50% body = 11.5 → wick=31 >= 11.5 → reject
    sig = detect_feg_reverse_signal(
        c1, c2, ema, PIP,
        sell_ema_side="above_ema",
        c2_sell_lower_wick_max_pct=50.0,
        c2_sell_lower_wick_cmp="lt",
    )
    assert sig is None
```

- [ ] **Step 2: Run tests to verify they fail**

```
pytest tests/test_feg_reverse.py -v
```
Expected: `ImportError` or `ModuleNotFoundError` — `feg_reverse_strategy` does not exist yet.

- [ ] **Step 3: Implement `src/feg_reverse_strategy.py`**

```python
"""
FEG Reverse Strategy

Detects FEG Classic 2-candle pattern then inverts the trade direction.
SELL pattern → BUY order. BUY pattern → SELL order.

Wick filter uses pattern-side params (c2_sell_* for SELL pattern, c2_buy_* for BUY pattern).
SL/TP computed for the NEW (flipped) direction.
"""

from src.feg_strategy import detect_feg_signal
from src.utils import get_pip_value, compute_trade_levels


_FLIP = {"BUY": "SELL", "SELL": "BUY"}


def detect_feg_reverse_signal(
    candle1: dict,
    candle2: dict,
    ema2: float,
    pip_value: float,
    h2_exceed_pips: float = 0.0,
    c2_gap_pips: float = 0.0,
    ema_margin_pips: float = 0.0,
    ema_filter_enabled: bool = True,
    buy_ema_side: str = "below_ema",
    sell_ema_side: str = "above_ema",
    c2_buy_upper_wick_max_pct: float | None = None,
    c2_buy_lower_wick_max_pct: float | None = None,
    c2_sell_upper_wick_max_pct: float | None = None,
    c2_sell_lower_wick_max_pct: float | None = None,
    c2_buy_upper_wick_cmp: str = "lt",
    c2_buy_lower_wick_cmp: str = "lt",
    c2_sell_upper_wick_cmp: str = "lt",
    c2_sell_lower_wick_cmp: str = "lt",
) -> str | None:
    """
    Phát hiện pattern FEG rồi đảo chiều lệnh.
    SELL pattern → trả "BUY". BUY pattern → trả "SELL". None nếu không có pattern.
    Wick filter dùng params của pattern gốc (không phải chiều lệnh mới).
    """
    pattern = detect_feg_signal(
        candle1, candle2, ema2, pip_value,
        h2_exceed_pips=h2_exceed_pips,
        c2_gap_pips=c2_gap_pips,
        ema_margin_pips=ema_margin_pips,
        ema_filter_enabled=ema_filter_enabled,
        buy_ema_side=buy_ema_side,
        sell_ema_side=sell_ema_side,
        c2_buy_upper_wick_max_pct=c2_buy_upper_wick_max_pct,
        c2_buy_lower_wick_max_pct=c2_buy_lower_wick_max_pct,
        c2_sell_upper_wick_max_pct=c2_sell_upper_wick_max_pct,
        c2_sell_lower_wick_max_pct=c2_sell_lower_wick_max_pct,
        c2_buy_upper_wick_cmp=c2_buy_upper_wick_cmp,
        c2_buy_lower_wick_cmp=c2_buy_lower_wick_cmp,
        c2_sell_upper_wick_cmp=c2_sell_upper_wick_cmp,
        c2_sell_lower_wick_cmp=c2_sell_lower_wick_cmp,
    )
    return _FLIP.get(pattern)  # None stays None


def analyze_feg_reverse(
    symbol: str,
    candle1: dict,
    candle2: dict,
    ema2: float,
    rr_ratio: float = 2.0,
    buffer_k: float = 5.0,
    lot_size: float = 0.01,
    entry_mode: str = "close",
    entry_percent: float = 0.0,
    h2_exceed_pips: float = 0.0,
    c2_gap_pips: float = 0.0,
    ema_margin_pips: float = 0.0,
    ema_filter_enabled: bool = True,
    buy_ema_side: str = "below_ema",
    sell_ema_side: str = "above_ema",
    c2_buy_upper_wick_max_pct: float | None = None,
    c2_buy_lower_wick_max_pct: float | None = None,
    c2_sell_upper_wick_max_pct: float | None = None,
    c2_sell_lower_wick_max_pct: float | None = None,
    c2_buy_upper_wick_cmp: str = "lt",
    c2_buy_lower_wick_cmp: str = "lt",
    c2_sell_upper_wick_cmp: str = "lt",
    c2_sell_lower_wick_cmp: str = "lt",
) -> dict | None:
    """Dựng signal đầy đủ (entry/SL/TP) cho FEG Reverse. None nếu không có pattern."""
    pip_value = get_pip_value(symbol)
    direction = detect_feg_reverse_signal(
        candle1, candle2, ema2, pip_value,
        h2_exceed_pips=h2_exceed_pips,
        c2_gap_pips=c2_gap_pips,
        ema_margin_pips=ema_margin_pips,
        ema_filter_enabled=ema_filter_enabled,
        buy_ema_side=buy_ema_side,
        sell_ema_side=sell_ema_side,
        c2_buy_upper_wick_max_pct=c2_buy_upper_wick_max_pct,
        c2_buy_lower_wick_max_pct=c2_buy_lower_wick_max_pct,
        c2_sell_upper_wick_max_pct=c2_sell_upper_wick_max_pct,
        c2_sell_lower_wick_max_pct=c2_sell_lower_wick_max_pct,
        c2_buy_upper_wick_cmp=c2_buy_upper_wick_cmp,
        c2_buy_lower_wick_cmp=c2_buy_lower_wick_cmp,
        c2_sell_upper_wick_cmp=c2_sell_upper_wick_cmp,
        c2_sell_lower_wick_cmp=c2_sell_lower_wick_cmp,
    )
    if direction is None:
        return None

    levels = compute_trade_levels(
        direction, candle2, entry_mode, entry_percent, buffer_k, rr_ratio, pip_value,
    )
    return {
        "symbol": symbol,
        "direction": direction,
        "entry_price": levels["entry_price"],
        "stop_loss": levels["stop_loss"],
        "take_profit": levels["take_profit"],
        "sl_pips": levels["sl_pips"],
        "lot_size": lot_size,
        "candle1": candle1,
        "candle2": candle2,
    }
```

- [ ] **Step 4: Create `strategies/feg_reverse.yaml`**

```yaml
id: feg_reverse
name: FEG Reverse
version: "1.0"
description: |
  FEG 2-candle pattern + flipped direction. SELL pattern → BUY order. BUY pattern → SELL order.
  Wick filter dung params cua pattern goc. SL/TP neo theo chieu lenh moi.
author: admin
created: "2026-07-09"
enabled: true

entry:
  type: pattern
  timeframe: M1
  pattern: feg_reverse
  ema_period: 21
  h2_exceed_pips: 0.0
  c2_gap_pips: 0.0
  ema_filter_enabled: true
  buy_ema_side: below_ema
  sell_ema_side: above_ema
  ema_margin_pips: 0.0

exit:
  tp:
    type: price_based
  sl:
    type: close_based
  time_limit:
    enabled: true
    max_candles: 7

parameters:
  rr_ratio: 2.0
  buffer_k: 50
  lot_size: 0.01
  entry_mode: close
  entry_percent: 10
  re_entry_after_sl: false

symbols:
  - XAUUSD
  - BTCUSD
  - ETHUSD
  - XAUUSDm
  - BTCUSDm
  - ETHUSDm
  - EURUSDm
  - GBPUSDm
  - AUDUSDm
```

- [ ] **Step 5: Run tests — expect pass**

```
pytest tests/test_feg_reverse.py -v
```
Expected: all 5 tests PASS.

- [ ] **Step 6: Commit**

```bash
git add src/feg_reverse_strategy.py strategies/feg_reverse.yaml tests/test_feg_reverse.py
git commit -m "feat: add FEG Reverse strategy core + yaml config"
```

---

### Task 2: `src/bot_runner.py` — add feg_reverse dispatch

**Files:**
- Modify: `src/bot_runner.py`

**Interfaces:**
- Consumes: `analyze_feg_reverse` from `src/feg_reverse_strategy`
- Produces: `feg_reverse_entry_decision(active_trade, candle1, candle2, ema2, symbol, ...) -> dict | None`

- [ ] **Step 1: Add `feg_reverse_entry_decision` after `feg_entry_decision` (line ~570)**

Find the block ending with `feg_stop_order_entry_decision` and add after it:

```python
def feg_reverse_entry_decision(
    active_trade, candle1, candle2, ema2, symbol,
    rr_ratio, buffer_k, lot_size, entry_mode, entry_percent,
    h2_exceed_pips=0.0, c2_gap_pips=0.0, ema_margin_pips=0.0,
    ema_filter_enabled=True, buy_ema_side="below_ema", sell_ema_side="above_ema",
    c2_buy_upper_wick_max_pct=None, c2_buy_lower_wick_max_pct=None,
    c2_sell_upper_wick_max_pct=None, c2_sell_lower_wick_max_pct=None,
    c2_buy_upper_wick_cmp="lt", c2_buy_lower_wick_cmp="lt",
    c2_sell_upper_wick_cmp="lt", c2_sell_lower_wick_cmp="lt",
):
    """Quyết định vào lệnh FEG Reverse. None nếu đang có lệnh hoặc không có pattern."""
    from src.feg_reverse_strategy import analyze_feg_reverse
    if active_trade is not None:
        return None
    return analyze_feg_reverse(
        symbol, candle1, candle2, ema2,
        rr_ratio=rr_ratio, buffer_k=buffer_k, lot_size=lot_size,
        entry_mode=entry_mode, entry_percent=entry_percent,
        h2_exceed_pips=h2_exceed_pips, c2_gap_pips=c2_gap_pips, ema_margin_pips=ema_margin_pips,
        ema_filter_enabled=ema_filter_enabled, buy_ema_side=buy_ema_side, sell_ema_side=sell_ema_side,
        c2_buy_upper_wick_max_pct=c2_buy_upper_wick_max_pct,
        c2_buy_lower_wick_max_pct=c2_buy_lower_wick_max_pct,
        c2_sell_upper_wick_max_pct=c2_sell_upper_wick_max_pct,
        c2_sell_lower_wick_max_pct=c2_sell_lower_wick_max_pct,
        c2_buy_upper_wick_cmp=c2_buy_upper_wick_cmp,
        c2_buy_lower_wick_cmp=c2_buy_lower_wick_cmp,
        c2_sell_upper_wick_cmp=c2_sell_upper_wick_cmp,
        c2_sell_lower_wick_cmp=c2_sell_lower_wick_cmp,
    )
```

- [ ] **Step 2: Update dispatch block (line ~324) to route `feg_reverse`**

Current code:
```python
if args.strategy == 'feg_stop_order':
    run_feg_stop_order_bot(...)
else:
    run_feg_bot(...)
```

Replace with:
```python
if args.strategy == 'feg_stop_order':
    run_feg_stop_order_bot(args, strategy, params, credentials,
                           entry_start_time=entry_start, entry_end_time=entry_end)
elif args.strategy == 'feg_reverse':
    run_feg_reverse_bot(args, strategy, params, credentials,
                        entry_start_time=entry_start, entry_end_time=entry_end)
else:
    run_feg_bot(args, strategy, params, credentials,
                entry_start_time=entry_start, entry_end_time=entry_end)
```

- [ ] **Step 3: Add `run_feg_reverse_bot` function**

Copy `run_feg_bot` (line ~805) and change:
1. Function name: `run_feg_reverse_bot`
2. Log prefix: `"FEG Reverse"` instead of `"FEG"`
3. Entry decision call: `feg_reverse_entry_decision(...)` instead of `feg_entry_decision(...)`
4. Telegram message: `"FEG Reverse Bot Started"` instead of `"FEG Bot Started"`
5. All other logic identical

The `run_feg_bot` function is long (~430 lines). The only lines that change are:
- The log line (~line 862): change `"FEG params:"` → `"FEG Reverse params:"`
- The Telegram line (~line 866): change `"FEG Bot Started"` → `"FEG Reverse Bot Started"`
- Every call to `feg_entry_decision(` → `feg_reverse_entry_decision(`

- [ ] **Step 4: Syntax check**

```
python -c "import ast; ast.parse(open('src/bot_runner.py', encoding='utf-8-sig').read()); print('OK')"
```
Expected: `OK`

- [ ] **Step 5: Commit**

```bash
git add src/bot_runner.py
git commit -m "feat: add feg_reverse dispatch + run_feg_reverse_bot to bot_runner"
```

---

### Task 3: `src/backtest.py` — add feg_reverse backtest

**Files:**
- Modify: `src/backtest.py`

**Interfaces:**
- Consumes: `detect_feg_reverse_signal` from `src/feg_reverse_strategy`
- Produces: `_run_feg_reverse_backtest(df, symbol, ...) -> dict`

- [ ] **Step 1: Add `_run_feg_reverse_backtest` function**

Locate `_run_feg_backtest`. Copy it entirely and:
1. Rename to `_run_feg_reverse_backtest`
2. Change import line inside:
   - `from src.feg_strategy import detect_feg_signal` → `from src.feg_reverse_strategy import detect_feg_reverse_signal as detect_feg_signal`
3. All other logic is identical — `detect_feg_signal` variable now points to the reverse version.

This works because `detect_feg_reverse_signal` has the exact same signature as `detect_feg_signal`.

- [ ] **Step 2: Update `run_backtest` dispatch block (~line 364)**

Current:
```python
if strategy == "feg_stop_order":
    result = _run_feg_stop_order_backtest(...)
else:
    result = _run_feg_backtest(...)
```

Replace with:
```python
if strategy == "feg_stop_order":
    result = _run_feg_stop_order_backtest(
        df=df, symbol=symbol, rr_ratio=rr_ratio, max_candles=max_candles,
        lot_mode=lot_mode, fixed_lot=fixed_lot, risk_percent=risk_percent,
        risk_amount=risk_amount, risk_mode=risk_mode, buffer_k=buffer_k,
        starting_equity=starting_equity, tp_type=tp_type, sl_type=sl_type,
        ema_period=ema_period, h2_exceed_pips=h2_exceed_pips, c2_gap_pips=c2_gap_pips,
        ema_filter_enabled=ema_filter_enabled, buy_ema_side=buy_ema_side,
        sell_ema_side=sell_ema_side, ema_margin_pips=ema_margin_pips,
        entry_start_time=entry_start_time, entry_end_time=entry_end_time,
        limit_order_candles=limit_order_candles,
        be_enabled=be_enabled, be_r=be_r,
        re_entry_after_sl=re_entry_after_sl,
        c2_buy_upper_wick_max_pct=c2_buy_upper_wick_max_pct, c2_buy_lower_wick_max_pct=c2_buy_lower_wick_max_pct,
        c2_sell_upper_wick_max_pct=c2_sell_upper_wick_max_pct, c2_sell_lower_wick_max_pct=c2_sell_lower_wick_max_pct,
        c2_buy_upper_wick_cmp=c2_buy_upper_wick_cmp, c2_buy_lower_wick_cmp=c2_buy_lower_wick_cmp,
        c2_sell_upper_wick_cmp=c2_sell_upper_wick_cmp, c2_sell_lower_wick_cmp=c2_sell_lower_wick_cmp,
    )
elif strategy == "feg_reverse":
    result = _run_feg_reverse_backtest(
        df=df, symbol=symbol, rr_ratio=rr_ratio, max_candles=max_candles,
        lot_mode=lot_mode, fixed_lot=fixed_lot, risk_percent=risk_percent,
        risk_amount=risk_amount, risk_mode=risk_mode, buffer_k=buffer_k,
        starting_equity=starting_equity, tp_type=tp_type, sl_type=sl_type,
        entry_mode=entry_mode, entry_percent=entry_percent, ema_period=ema_period,
        h2_exceed_pips=h2_exceed_pips, c2_gap_pips=c2_gap_pips, ema_margin_pips=ema_margin_pips,
        entry_start_time=entry_start_time, entry_end_time=entry_end_time,
        limit_order_candles=limit_order_candles,
        be_enabled=be_enabled, be_r=be_r,
        ema_filter_enabled=ema_filter_enabled, buy_ema_side=buy_ema_side,
        sell_ema_side=sell_ema_side,
        re_entry_after_sl=re_entry_after_sl,
        c2_buy_upper_wick_max_pct=c2_buy_upper_wick_max_pct, c2_buy_lower_wick_max_pct=c2_buy_lower_wick_max_pct,
        c2_sell_upper_wick_max_pct=c2_sell_upper_wick_max_pct, c2_sell_lower_wick_max_pct=c2_sell_lower_wick_max_pct,
        c2_buy_upper_wick_cmp=c2_buy_upper_wick_cmp, c2_buy_lower_wick_cmp=c2_buy_lower_wick_cmp,
        c2_sell_upper_wick_cmp=c2_sell_upper_wick_cmp, c2_sell_lower_wick_cmp=c2_sell_lower_wick_cmp,
    )
else:
    result = _run_feg_backtest(
        df=df, symbol=symbol, rr_ratio=rr_ratio, max_candles=max_candles,
        lot_mode=lot_mode, fixed_lot=fixed_lot, risk_percent=risk_percent,
        risk_amount=risk_amount, risk_mode=risk_mode, buffer_k=buffer_k,
        starting_equity=starting_equity, tp_type=tp_type, sl_type=sl_type,
        entry_mode=entry_mode, entry_percent=entry_percent, ema_period=ema_period,
        h2_exceed_pips=h2_exceed_pips, c2_gap_pips=c2_gap_pips, ema_margin_pips=ema_margin_pips,
        entry_start_time=entry_start_time, entry_end_time=entry_end_time,
        limit_order_candles=limit_order_candles,
        be_enabled=be_enabled, be_r=be_r,
        ema_filter_enabled=ema_filter_enabled, buy_ema_side=buy_ema_side,
        sell_ema_side=sell_ema_side,
        re_entry_after_sl=re_entry_after_sl,
        c2_buy_upper_wick_max_pct=c2_buy_upper_wick_max_pct, c2_buy_lower_wick_max_pct=c2_buy_lower_wick_max_pct,
        c2_sell_upper_wick_max_pct=c2_sell_upper_wick_max_pct, c2_sell_lower_wick_max_pct=c2_sell_lower_wick_max_pct,
        c2_buy_upper_wick_cmp=c2_buy_upper_wick_cmp, c2_buy_lower_wick_cmp=c2_buy_lower_wick_cmp,
        c2_sell_upper_wick_cmp=c2_sell_upper_wick_cmp, c2_sell_lower_wick_cmp=c2_sell_lower_wick_cmp,
    )
```

- [ ] **Step 3: Syntax check**

```
python -c "import ast; ast.parse(open('src/backtest.py', encoding='utf-8-sig').read()); print('OK')"
```
Expected: `OK`

- [ ] **Step 4: Commit**

```bash
git add src/backtest.py
git commit -m "feat: add _run_feg_reverse_backtest + dispatch to backtest.py"
```

---

### Task 4: Verify UI auto-detects `feg_reverse`

**Files:**
- Read: `pages/1_Bots.py` (check `is_pattern`)
- Read: `pages/5_Backtest.py` (check `is_pattern`)

- [ ] **Step 1: Verify `is_pattern` logic in `1_Bots.py`**

Search for `is_pattern` assignment. Expected to find:
```python
is_pattern = entry_type == 'pattern'
```
If this line exists and `entry_type` comes from `params.get('entry_type', ...)`, then `feg_reverse.yaml` with `entry_type: pattern` auto-shows the ENTRY section. No changes needed.

- [ ] **Step 2: Verify `is_feg_stop_order` guard**

Search for `is_feg_stop_order` in both pages. It should be:
```python
is_feg_stop_order = (selected_strategy == 'feg_stop_order')
```
`feg_reverse` will correctly get `is_feg_stop_order = False` → Entry Mode shows radio with Market/Limit options. Correct.

- [ ] **Step 3: Run strategy list to confirm feg_reverse appears**

```
python -c "from src.strategy_manager import list_strategies; [print(s['id'], '-', s['name']) for s in list_strategies()]"
```
Expected output includes:
```
feg_reverse - FEG Reverse
```

- [ ] **Step 4: Run all tests**

```
pytest tests/ -v
```
Expected: all pass, no regressions.

- [ ] **Step 5: Final commit**

```bash
git add .
git commit -m "feat: FEG Reverse strategy complete — strategy, bot_runner, backtest"
```
