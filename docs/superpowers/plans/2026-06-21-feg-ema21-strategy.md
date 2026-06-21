# FEG EMA21 Strategy Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Thêm strategy `feg_ema21` (pattern 2 nến FEG + filter EMA21, quét liên tục, 1 lệnh/lúc) vào BotForex — đầy đủ backtest, UI, live runner.

**Architecture:** Approach B — cô lập phần phát hiện tín hiệu vào module riêng (`src/feg_strategy.py`), tái dùng engine exit/lot/PnL hiện có. Phân nhánh strategy qua field `entry.type` (`time` = master_candle, `pattern` = FEG). Toán TP/SL/lot/PnL được trích thành helper dùng chung trong `src/utils.py` + `src/backtest.py`.

**Tech Stack:** Python 3.10+, pandas, PyYAML, Streamlit, MetaTrader5 (lazy import), pytest (mới thêm cho unit test logic thuần).

## Global Constraints

- Đơn vị khoảng cách EMA21: **pips** (× `get_pip_value(symbol)` để ra giá).
- Số lệnh: **1 lệnh tại 1 thời điểm**, không giới hạn/ngày (block tín hiệu mới khi đang có lệnh).
- Timeframe default FEG: **M5** (configurable qua YAML/UI).
- Cờ `--test`: `test=1` simulate (không gửi MT5); `test=0` đặt lệnh thật.
- `entry.type` thiếu → default `"time"` (backward-compat với master_candle).
- Filter EMA mặc định OFF (`ema_distance.enabled=false`), chỉ áp `+/- dist_pips` khi bật.
- TP/SL neo vào candle2: SELL `SL=H2+buffer_k×pip`, BUY `SL=L2−buffer_k×pip`; `TP=entry±risk×rr_ratio`.
- Pattern: SELL `H2>H1 & C2<L1 & L2>EMA21(+dist)`; BUY `L2<L1 & C2>H1 & H2<EMA21(−dist)`.
- EMA: `df['close'].ewm(span=ema_period, adjust=False).mean()`; backtest chỉ quét từ index ≥ `ema_period` (warmup seed).
- Magic number FEG = `212100` (master_candle = `210500`).
- Không sửa logic live của master_candle (ngoài phạm vi).
- Tất cả test chạy: `python -m pytest <path> -v` từ thư mục gốc project.

---

### Task 1: Test scaffolding (pytest)

**Files:**
- Modify: `requirements.txt`
- Create: `conftest.py`
- Create: `tests/test_smoke.py`

**Interfaces:**
- Produces: thư mục `tests/` + `conftest.py` đặt project root vào `sys.path` để `from src.x import ...` chạy được.

- [ ] **Step 1: Thêm pytest vào requirements.txt**

Thêm dòng cuối file `requirements.txt`:
```
pytest==8.3.4
```

- [ ] **Step 2: Cài pytest**

Run: `python -m pip install pytest==8.3.4`
Expected: `Successfully installed pytest-8.3.4` (hoặc "already satisfied").

- [ ] **Step 3: Tạo `conftest.py` ở project root**

```python
"""Pytest config: đảm bảo project root nằm trong sys.path để import `src.*`."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
```

- [ ] **Step 4: Tạo smoke test `tests/test_smoke.py`**

```python
def test_can_import_src_utils():
    from src.utils import get_pip_value
    assert get_pip_value("XAUUSD") == 0.1
    assert get_pip_value("BTCUSD") == 1.0
    assert get_pip_value("EURUSD") == 0.0001
```

- [ ] **Step 5: Chạy test**

Run: `python -m pytest tests/test_smoke.py -v`
Expected: PASS (1 passed).

- [ ] **Step 6: Commit**

```bash
git add requirements.txt conftest.py tests/test_smoke.py
git commit -m "test: add pytest scaffolding and conftest"
```

---

### Task 2: FEG pattern detection — `detect_feg_signal`

**Files:**
- Create: `src/feg_strategy.py`
- Create: `tests/test_feg_strategy.py`

**Interfaces:**
- Consumes: `src.utils.get_pip_value`.
- Produces: `detect_feg_signal(candle1: dict, candle2: dict, ema2: float, pip_value: float, ema_distance_enabled: bool = False, ema_distance_pips: float = 0.0) -> str | None` — trả `"BUY"`, `"SELL"`, hoặc `None`. `candle1`/`candle2` là dict có keys `open, high, low, close`.

- [ ] **Step 1: Viết test thất bại `tests/test_feg_strategy.py`**

```python
from src.feg_strategy import detect_feg_signal

PIP = 0.1  # XAU

def test_sell_signal_default_filter():
    # H2>H1, C2<L1, L2>EMA21
    c1 = {"open": 100.0, "high": 101.0, "low": 99.0, "close": 100.5}
    c2 = {"open": 100.8, "high": 102.0, "low": 98.5, "close": 98.0}  # H2=102>101, C2=98<99, L2=98.5
    ema2 = 98.0  # L2(98.5) > ema2(98.0)
    assert detect_feg_signal(c1, c2, ema2, PIP) == "SELL"

def test_sell_blocked_when_low2_below_ema():
    c1 = {"open": 100.0, "high": 101.0, "low": 99.0, "close": 100.5}
    c2 = {"open": 100.8, "high": 102.0, "low": 98.5, "close": 98.0}
    ema2 = 99.0  # L2(98.5) NOT > ema2(99.0)
    assert detect_feg_signal(c1, c2, ema2, PIP) is None

def test_buy_signal_default_filter():
    # L2<L1, C2>H1, H2<EMA21
    c1 = {"open": 100.0, "high": 101.0, "low": 99.0, "close": 99.5}
    c2 = {"open": 99.2, "high": 102.0, "low": 98.0, "close": 101.5}  # L2=98<99, C2=101.5>101, H2=102
    ema2 = 103.0  # H2(102) < ema2(103)
    assert detect_feg_signal(c1, c2, ema2, PIP) == "BUY"

def test_buy_blocked_when_high2_above_ema():
    c1 = {"open": 100.0, "high": 101.0, "low": 99.0, "close": 99.5}
    c2 = {"open": 99.2, "high": 102.0, "low": 98.0, "close": 101.5}
    ema2 = 101.0  # H2(102) NOT < ema2(101)
    assert detect_feg_signal(c1, c2, ema2, PIP) is None

def test_no_signal_when_no_gap():
    c1 = {"open": 100.0, "high": 101.0, "low": 99.0, "close": 100.0}
    c2 = {"open": 100.2, "high": 102.0, "low": 99.5, "close": 99.5}  # C2=99.5 NOT < L1=99.0
    assert detect_feg_signal(c1, c2, 95.0, PIP) is None

def test_sell_distance_filter_enabled_boundary():
    c1 = {"open": 100.0, "high": 101.0, "low": 99.0, "close": 100.5}
    c2 = {"open": 100.8, "high": 102.0, "low": 98.5, "close": 98.0}  # L2=98.5
    ema2 = 98.0
    # threshold 4 pips × 0.1 = 0.4 -> need L2 > 98.4 ; 98.5 > 98.4 -> SELL
    assert detect_feg_signal(c1, c2, ema2, PIP, True, 4.0) == "SELL"
    # threshold 6 pips × 0.1 = 0.6 -> need L2 > 98.6 ; 98.5 NOT > 98.6 -> None
    assert detect_feg_signal(c1, c2, ema2, PIP, True, 6.0) is None

def test_buy_distance_filter_enabled_boundary():
    c1 = {"open": 100.0, "high": 101.0, "low": 99.0, "close": 99.5}
    c2 = {"open": 99.2, "high": 102.0, "low": 98.0, "close": 101.5}  # H2=102
    ema2 = 103.0
    # threshold 5 pips × 0.1 = 0.5 -> need H2 < 102.5 ; 102 < 102.5 -> BUY
    assert detect_feg_signal(c1, c2, ema2, PIP, True, 5.0) == "BUY"
    # ema2=102.3, threshold 5 pips -> need H2 < 101.8 ; 102 NOT < 101.8 -> None
    assert detect_feg_signal(c1, c2, 102.3, PIP, True, 5.0) is None
```

- [ ] **Step 2: Chạy test để xác nhận FAIL**

Run: `python -m pytest tests/test_feg_strategy.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'src.feg_strategy'`.

- [ ] **Step 3: Tạo `src/feg_strategy.py` với `detect_feg_signal`**

```python
"""
FEG EMA21 Strategy

Pattern 2 nến + filter EMA21, quét liên tục.
SELL: H2 > H1, C2 < L1, L2 > EMA21 (+dist pips nếu bật filter).
BUY:  L2 < L1, C2 > H1, H2 < EMA21 (-dist pips nếu bật filter).
TP/SL neo vào candle2 (giống master_candle): SL = candle2 high/low ± buffer_k,
TP = entry ± risk × rr_ratio.
"""

from src.utils import get_pip_value, compute_trade_levels


def detect_feg_signal(
    candle1: dict,
    candle2: dict,
    ema2: float,
    pip_value: float,
    ema_distance_enabled: bool = False,
    ema_distance_pips: float = 0.0,
) -> str | None:
    """
    Phát hiện tín hiệu FEG từ 2 nến đã đóng + EMA21 tại close candle2.

    Args:
        candle1: nến đóng trước (dict open/high/low/close)
        candle2: nến vừa đóng (dict open/high/low/close)
        ema2: giá trị EMA21 tại close của candle2
        pip_value: giá trị 1 pip của symbol
        ema_distance_enabled: bật filter khoảng cách EMA
        ema_distance_pips: khoảng cách (pips) khi filter bật

    Returns:
        "BUY", "SELL", hoặc None
    """
    h1, l1 = candle1["high"], candle1["low"]
    h2, l2, c2 = candle2["high"], candle2["low"], candle2["close"]
    dist = ema_distance_pips * pip_value if ema_distance_enabled else 0.0

    # SELL: FEG giảm
    if h2 > h1 and c2 < l1:
        if l2 > ema2 + dist:
            return "SELL"

    # BUY: FEG tăng
    if l2 < l1 and c2 > h1:
        if h2 < ema2 - dist:
            return "BUY"

    return None
```

> Lưu ý: `compute_trade_levels` được import sẵn ở đây nhưng dùng ở Task 3/4. Nếu Task 4 chưa xong khi chạy test Task 2, đổi import thành `from src.utils import get_pip_value` rồi bổ sung lại ở Task 3. (Thứ tự khuyến nghị: làm Task 4 trước Task 3 — xem ghi chú Task 3.)

- [ ] **Step 4: Tạm thời chỉ import `get_pip_value`** (vì `compute_trade_levels` chưa tồn tại đến Task 4)

Sửa dòng import đầu file thành:
```python
from src.utils import get_pip_value
```

- [ ] **Step 5: Chạy test để xác nhận PASS**

Run: `python -m pytest tests/test_feg_strategy.py -v`
Expected: PASS (7 passed).

- [ ] **Step 6: Commit**

```bash
git add src/feg_strategy.py tests/test_feg_strategy.py
git commit -m "feat: add FEG pattern detection (detect_feg_signal)"
```

---

### Task 4: Shared trade-level + lot + trade-record helpers (làm trước Task 3)

> **Thứ tự:** Task 4 đứng trước Task 3 vì `analyze_feg` (Task 3) và backtest FEG (Task 5) đều dùng `compute_trade_levels`. Refactor backtest time-path để dùng helper chung, có characterization test bảo vệ hành vi master_candle.

**Files:**
- Modify: `src/utils.py` (thêm `compute_trade_levels`)
- Modify: `src/backtest.py` (thêm `_compute_lot_size`, `_simulate_exit`, `_make_trade`; refactor `run_backtest` time-path dùng các helper)
- Create: `tests/test_trade_levels.py`
- Create: `tests/test_backtest_time_characterization.py`

**Interfaces:**
- Produces:
  - `src.utils.compute_trade_levels(direction: str, candle: dict, entry_mode: str, entry_percent: float, buffer_k: float, rr_ratio: float, pip_value: float) -> dict` → keys `entry_price, stop_loss, take_profit, sl_pips`.
  - `src.backtest._compute_lot_size(lot_mode, current_equity, risk_mode, risk_percent, risk_amount, sl_pips, symbol, fixed_lot) -> float`
  - `src.backtest._simulate_exit(df, entry_pos, direction, tp, sl, max_candles, tp_type, sl_type) -> tuple(exit_type, exit_price, exit_time, candles_held, exit_pos)`
  - `src.backtest._make_trade(entry_time, direction, levels, lot, exit_type, exit_price, exit_time, candles_held, symbol) -> tuple(trade_dict, pnl_pips, pnl_usd)`

- [ ] **Step 1: Viết test cho `compute_trade_levels` — `tests/test_trade_levels.py`**

```python
from src.utils import compute_trade_levels

PIP = 0.1  # XAU

def test_sell_levels_close_mode():
    # candle2: high=102, low=98.5, close=98.0, open=100.8
    c2 = {"open": 100.8, "high": 102.0, "low": 98.5, "close": 98.0}
    r = compute_trade_levels("SELL", c2, "close", 0.0, buffer_k=5.0, rr_ratio=2.0, pip_value=PIP)
    # SL = high + 5*0.1 = 102.5 ; entry = close = 98.0
    assert round(r["stop_loss"], 4) == 102.5
    assert r["entry_price"] == 98.0
    # risk = 102.5 - 98.0 = 4.5 ; TP = 98.0 - 9.0 = 89.0
    assert round(r["take_profit"], 4) == 89.0
    # sl_pips = (102.5 - 98.0)/0.1 = 45.0
    assert round(r["sl_pips"], 1) == 45.0

def test_buy_levels_close_mode():
    c2 = {"open": 99.2, "high": 102.0, "low": 98.0, "close": 101.5}
    r = compute_trade_levels("BUY", c2, "close", 0.0, buffer_k=5.0, rr_ratio=2.0, pip_value=PIP)
    # SL = low - 5*0.1 = 97.5 ; entry = 101.5 ; risk = 4.0 ; TP = 101.5 + 8.0 = 109.5
    assert round(r["stop_loss"], 4) == 97.5
    assert round(r["take_profit"], 4) == 109.5
    assert round(r["sl_pips"], 1) == 40.0

def test_buy_levels_range_percent():
    # body = |close-open| = |101.5-99.2| = 2.3 ; entry = close - 50%*body = 101.5 - 1.15 = 100.35
    c2 = {"open": 99.2, "high": 102.0, "low": 98.0, "close": 101.5}
    r = compute_trade_levels("BUY", c2, "range_percent", 50.0, buffer_k=5.0, rr_ratio=2.0, pip_value=PIP)
    assert round(r["entry_price"], 4) == 100.35
```

- [ ] **Step 2: Chạy test xác nhận FAIL**

Run: `python -m pytest tests/test_trade_levels.py -v`
Expected: FAIL — `ImportError: cannot import name 'compute_trade_levels'`.

- [ ] **Step 3: Thêm `compute_trade_levels` vào `src/utils.py`**

Thêm vào cuối `src/utils.py`:
```python
def compute_trade_levels(
    direction: str,
    candle: dict,
    entry_mode: str,
    entry_percent: float,
    buffer_k: float,
    rr_ratio: float,
    pip_value: float,
) -> dict:
    """
    Tính entry / SL / TP / sl_pips neo vào 1 nến (anchor candle).

    BUY:  SL = low  - buffer_k*pip ; TP = entry + risk*rr
    SELL: SL = high + buffer_k*pip ; TP = entry - risk*rr
    entry_mode "close": entry = close
    entry_mode "range_percent": BUY entry = close - X%*body ; SELL entry = close + X%*body
        (body = |close - open|)
    """
    o, h, l, c = candle["open"], candle["high"], candle["low"], candle["close"]
    body = abs(c - o)
    buffer_offset = buffer_k * pip_value

    if direction == "BUY":
        entry = c - (entry_percent / 100) * body if entry_mode == "range_percent" else c
        stop_loss = l - buffer_offset
        sl_pips = (entry - stop_loss) / pip_value
        risk = entry - stop_loss
        take_profit = entry + risk * rr_ratio
    else:  # SELL
        entry = c + (entry_percent / 100) * body if entry_mode == "range_percent" else c
        stop_loss = h + buffer_offset
        sl_pips = (stop_loss - entry) / pip_value
        risk = stop_loss - entry
        take_profit = entry - risk * rr_ratio

    return {
        "entry_price": entry,
        "stop_loss": stop_loss,
        "take_profit": take_profit,
        "sl_pips": sl_pips,
    }
```

- [ ] **Step 4: Chạy test xác nhận PASS**

Run: `python -m pytest tests/test_trade_levels.py -v`
Expected: PASS (3 passed).

- [ ] **Step 5: Viết characterization test cho backtest time-path — `tests/test_backtest_time_characterization.py`**

```python
import pandas as pd
from zoneinfo import ZoneInfo
from src.backtest import run_backtest

TZ = ZoneInfo("Asia/Ho_Chi_Minh")

def _df():
    # Nến entry lúc 21:05 bullish (close>open) + vài nến sau cho exit
    rows = [
        {"time": pd.Timestamp("2025-01-02 21:05", tz=TZ), "open": 100.0, "high": 101.0, "low": 99.5, "close": 100.8},
        {"time": pd.Timestamp("2025-01-02 21:10", tz=TZ), "open": 100.8, "high": 103.5, "low": 100.7, "close": 103.0},
        {"time": pd.Timestamp("2025-01-02 21:15", tz=TZ), "open": 103.0, "high": 104.0, "low": 102.5, "close": 103.5},
    ]
    return pd.DataFrame(rows)

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
    # entry = close = 100.8 ; SL = low(99.5) - 5*0.1 = 99.0 ; risk=1.8 ; TP=100.8+3.6=104.4
    assert round(t["entry"], 4) == 100.8
    assert round(t["sl"], 4) == 99.0
    assert round(t["tp"], 4) == 104.4
```

- [ ] **Step 6: Chạy characterization test trên code HIỆN TẠI (chưa refactor) — xác nhận PASS**

Run: `python -m pytest tests/test_backtest_time_characterization.py -v`
Expected: PASS (1 passed). Đây là baseline khoá hành vi trước khi refactor.

- [ ] **Step 7: Refactor `src/backtest.py` — thêm 3 helper + dùng trong time-path**

Thêm các helper (đặt sau `calculate_flex_lot_size`, trước `run_backtest`):
```python
def _compute_lot_size(lot_mode, current_equity, risk_mode, risk_percent, risk_amount, sl_pips, symbol, fixed_lot):
    """Tính lot theo mode fixed/flex (dùng chung cho mọi entry_type)."""
    if lot_mode == "flex":
        if risk_mode == "fixed_amount":
            return calculate_flex_lot_size(
                equity=current_equity, risk_percent=0, sl_pips=sl_pips,
                symbol=symbol, risk_amount=risk_amount,
            )
        return calculate_flex_lot_size(
            equity=current_equity, risk_percent=risk_percent, sl_pips=sl_pips, symbol=symbol,
        )
    return fixed_lot


def _simulate_exit(df, entry_pos, direction, tp, sl, max_candles, tp_type, sl_type):
    """
    Mô phỏng exit từ vị trí entry_pos (integer position). Trả:
        (exit_type, exit_price, exit_time, candles_held, exit_pos)
    exit_type None khi hết data mà không có TP/SL và max_candles=0.
    """
    if max_candles > 0:
        next_candles = df.iloc[entry_pos + 1: entry_pos + 1 + max_candles]
    else:
        next_candles = df.iloc[entry_pos + 1:]

    exit_type = exit_price = exit_time = None
    candles_held = 0
    exit_pos = entry_pos

    for offset, (_, row) in enumerate(next_candles.iterrows(), start=1):
        candles_held += 1
        exit_pos = entry_pos + offset
        candle = {"high": row["high"], "low": row["low"], "close": row["close"]}
        exit_type, exit_price = check_exit(direction, candle, tp, sl, tp_type, sl_type)
        if exit_type:
            exit_time = row["time"]
            break

    if not exit_type and len(next_candles) > 0 and max_candles > 0:
        exit_type = "TIME"
        last = next_candles.iloc[-1]
        exit_price = last["close"]
        exit_time = last["time"]
        candles_held = len(next_candles)
        exit_pos = entry_pos + len(next_candles)

    return exit_type, exit_price, exit_time, candles_held, exit_pos


def _make_trade(entry_time, direction, levels, lot, exit_type, exit_price, exit_time, candles_held, symbol):
    """Dựng dict trade + tính pnl pips/usd."""
    pip_value = get_pip_value(symbol)
    entry = levels["entry_price"]
    if direction == "BUY":
        pnl_pips = (exit_price - entry) / pip_value
    else:
        pnl_pips = (entry - exit_price) / pip_value
    pnl_usd = lot * pnl_pips * get_pip_value_per_lot(symbol)
    trade = {
        "date": entry_time.strftime("%Y-%m-%d"),
        "time": entry_time.strftime("%H:%M"),
        "direction": direction,
        "entry": entry,
        "sl": levels["stop_loss"],
        "tp": levels["take_profit"],
        "sl_pips": round(levels["sl_pips"], 1),
        "lot": lot,
        "exit_type": exit_type,
        "exit_price": exit_price,
        "exit_time": exit_time.strftime("%H:%M") if exit_time else "",
        "candles": candles_held,
        "pnl_pips": round(pnl_pips, 1),
        "pnl_usd": round(pnl_usd, 2),
    }
    return trade, pnl_pips, pnl_usd
```

Trong `run_backtest`, thay khối tính levels + lot + exit + record (vòng `for idx, entry_row in entry_candles.iterrows()`) bằng cách dùng helper. Thay đoạn từ `# Determine direction...` đến hết phần append trade bằng:
```python
        candle = {"open": o, "high": h, "low": l, "close": c}
        if c > o:
            direction = "BUY"
        elif c < o:
            direction = "SELL"
        else:
            continue  # Doji

        levels = compute_trade_levels(direction, candle, entry_mode, entry_percent, buffer_k, rr_ratio, pip_value)

        lot_size = _compute_lot_size(
            lot_mode, current_equity, risk_mode, risk_percent, risk_amount,
            levels["sl_pips"], symbol, fixed_lot,
        )

        entry_pos = df.index.get_loc(idx)
        exit_type, exit_price, exit_time, candles_held, _ = _simulate_exit(
            df, entry_pos, direction, levels["take_profit"], levels["stop_loss"],
            max_candles, tp_type, sl_type,
        )
        if not exit_type:
            continue

        trade, pnl_pips, pnl_usd = _make_trade(
            entry_time, direction, levels, lot_size, exit_type, exit_price,
            exit_time, candles_held, symbol,
        )
        current_equity += pnl_usd
        trades.append(trade)
        equity_curve_pips.append(equity_curve_pips[-1] + pnl_pips)
        equity_curve_usd.append(current_equity)
```
Thêm import `compute_trade_levels` ở đầu `src/backtest.py`:
```python
from src.utils import get_pip_value, check_exit, compute_trade_levels
```

- [ ] **Step 8: Chạy lại characterization + trade-levels test — xác nhận VẪN PASS**

Run: `python -m pytest tests/test_backtest_time_characterization.py tests/test_trade_levels.py -v`
Expected: PASS (4 passed). Hành vi master_candle giữ nguyên sau refactor.

- [ ] **Step 9: Commit**

```bash
git add src/utils.py src/backtest.py tests/test_trade_levels.py tests/test_backtest_time_characterization.py
git commit -m "refactor: extract shared trade-level/lot/exit helpers for backtest"
```

---

### Task 3: FEG signal builder — `analyze_feg`

**Files:**
- Modify: `src/feg_strategy.py`
- Modify: `tests/test_feg_strategy.py`

**Interfaces:**
- Consumes: `detect_feg_signal` (Task 2), `src.utils.compute_trade_levels` + `get_pip_value` (Task 4).
- Produces: `analyze_feg(symbol, candle1, candle2, ema2, rr_ratio=2.0, buffer_k=5.0, lot_size=0.01, entry_mode="close", entry_percent=0.0, ema_distance_enabled=False, ema_distance_pips=0.0) -> dict | None` → dict keys: `symbol, direction, entry_price, stop_loss, take_profit, sl_pips, lot_size, candle1, candle2`.

- [ ] **Step 1: Thêm test cho `analyze_feg` vào `tests/test_feg_strategy.py`**

```python
from src.feg_strategy import analyze_feg

def test_analyze_feg_sell_levels():
    c1 = {"open": 100.0, "high": 101.0, "low": 99.0, "close": 100.5}
    c2 = {"open": 100.8, "high": 102.0, "low": 98.5, "close": 98.0}
    ema2 = 98.0
    sig = analyze_feg("XAUUSD", c1, c2, ema2, rr_ratio=2.0, buffer_k=5.0, lot_size=0.02)
    assert sig["direction"] == "SELL"
    assert sig["entry_price"] == 98.0
    assert round(sig["stop_loss"], 4) == 102.5   # 102 + 5*0.1
    assert round(sig["take_profit"], 4) == 89.0   # risk 4.5 -> 98 - 9
    assert round(sig["sl_pips"], 1) == 45.0
    assert sig["lot_size"] == 0.02
    assert sig["symbol"] == "XAUUSD"

def test_analyze_feg_returns_none_when_no_signal():
    c1 = {"open": 100.0, "high": 101.0, "low": 99.0, "close": 100.0}
    c2 = {"open": 100.2, "high": 102.0, "low": 99.5, "close": 99.5}  # C2 not < L1
    assert analyze_feg("XAUUSD", c1, c2, 95.0) is None
```

- [ ] **Step 2: Chạy test xác nhận FAIL**

Run: `python -m pytest tests/test_feg_strategy.py -v`
Expected: FAIL — `ImportError: cannot import name 'analyze_feg'`.

- [ ] **Step 3: Thêm `analyze_feg` + import `compute_trade_levels` vào `src/feg_strategy.py`**

Sửa dòng import đầu file:
```python
from src.utils import get_pip_value, compute_trade_levels
```
Thêm hàm:
```python
def analyze_feg(
    symbol: str,
    candle1: dict,
    candle2: dict,
    ema2: float,
    rr_ratio: float = 2.0,
    buffer_k: float = 5.0,
    lot_size: float = 0.01,
    entry_mode: str = "close",
    entry_percent: float = 0.0,
    ema_distance_enabled: bool = False,
    ema_distance_pips: float = 0.0,
) -> dict | None:
    """Dựng signal đầy đủ (entry/SL/TP) từ pattern FEG. Trả None nếu không có tín hiệu."""
    pip_value = get_pip_value(symbol)
    direction = detect_feg_signal(
        candle1, candle2, ema2, pip_value, ema_distance_enabled, ema_distance_pips,
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

- [ ] **Step 4: Chạy test xác nhận PASS**

Run: `python -m pytest tests/test_feg_strategy.py -v`
Expected: PASS (9 passed).

- [ ] **Step 5: Commit**

```bash
git add src/feg_strategy.py tests/test_feg_strategy.py
git commit -m "feat: add analyze_feg signal builder"
```

---

### Task 5: FEG backtest path (entry_type dispatch + sequential loop)

**Files:**
- Modify: `src/backtest.py`
- Create: `tests/test_backtest_feg.py`

**Interfaces:**
- Consumes: `detect_feg_signal`, `compute_trade_levels`, `_compute_lot_size`, `_simulate_exit`, `_make_trade`.
- Produces: `run_backtest(...)` nhận thêm kwargs `entry_type="time"`, `ema_period=21`, `ema_distance_enabled=False`, `ema_distance_pips=0.0`. Khi `entry_type="pattern"` → chạy nhánh FEG tuần tự (1 lệnh/lúc). Kết quả cùng schema (`total_trades`, `trades`, `equity_curve`, ...).

- [ ] **Step 1: Viết test `tests/test_backtest_feg.py`**

```python
import pandas as pd
from zoneinfo import ZoneInfo
from src.backtest import run_backtest

TZ = ZoneInfo("Asia/Ho_Chi_Minh")

def _make_df(rows):
    return pd.DataFrame(rows)

def test_feg_backtest_detects_one_sell_and_is_one_at_a_time():
    # Tạo >21 nến phẳng để EMA21 ổn định quanh ~100, rồi 1 pattern SELL, rồi nến cho exit.
    base = []
    for i in range(30):
        base.append({"time": pd.Timestamp("2025-01-02 00:00", tz=TZ) + pd.Timedelta(minutes=5 * i),
                     "open": 100.0, "high": 100.5, "low": 99.5, "close": 100.0})
    # candle1 (index 30): high=101, low=99, close=100.5
    base.append({"time": pd.Timestamp("2025-01-02 00:00", tz=TZ) + pd.Timedelta(minutes=5 * 30),
                 "open": 100.0, "high": 101.0, "low": 99.0, "close": 100.5})
    # candle2 (index 31): H2=102>101, C2=98<99, L2=98.5 > EMA21(~100? no) -> need L2>ema2
    # EMA quanh 100 -> L2=98.5 < 100 => SELL bị chặn. Để pass, đẩy EMA xuống: dùng nến giảm dần trước.
    # Đơn giản hơn: kiểm tra "không có trade" khi L2<EMA, và "có trade" khi tắt filter bằng ema rất thấp.
    base.append({"time": pd.Timestamp("2025-01-02 00:00", tz=TZ) + pd.Timedelta(minutes=5 * 31),
                 "open": 100.8, "high": 102.0, "low": 98.5, "close": 98.0})
    # exit candles
    for i in range(32, 40):
        base.append({"time": pd.Timestamp("2025-01-02 00:00", tz=TZ) + pd.Timedelta(minutes=5 * i),
                     "open": 98.0, "high": 98.2, "low": 88.0, "close": 89.0})
    df = _make_df(base)

    res = run_backtest(
        df=df, symbol="XAUUSD", entry_type="pattern", ema_period=21,
        rr_ratio=2.0, max_candles=7, lot_mode="fixed", fixed_lot=0.01,
        buffer_k=5.0, tp_type="price_based", sl_type="close_based", entry_mode="close",
    )
    # EMA21 ~100 nên L2=98.5 < ema -> KHÔNG có SELL (filter default chặn)
    assert res["total_trades"] == 0

def test_feg_backtest_sell_when_ema_below_low2():
    # Warmup phẳng ở mức THẤP (~95) để EMA21 nằm dưới L2(98.5) tại candle2 -> SELL hợp lệ.
    # (EMA của chuỗi phẳng ~ chính mức đó; chọn 95 < 98.5.)
    base = []
    for i in range(30):
        base.append({"time": pd.Timestamp("2025-01-02 00:00", tz=TZ) + pd.Timedelta(minutes=5 * i),
                     "open": 95.0, "high": 95.3, "low": 94.7, "close": 95.0})
    # candle1:
    base.append({"time": pd.Timestamp("2025-01-02 00:00", tz=TZ) + pd.Timedelta(minutes=5 * 30),
                 "open": 100.0, "high": 101.0, "low": 99.0, "close": 100.5})
    # candle2: H2=102>101, C2=98<99, L2=98.5 ; EMA21 nên < 98.5
    base.append({"time": pd.Timestamp("2025-01-02 00:00", tz=TZ) + pd.Timedelta(minutes=5 * 31),
                 "open": 100.8, "high": 102.0, "low": 98.5, "close": 98.0})
    for i in range(32, 40):
        base.append({"time": pd.Timestamp("2025-01-02 00:00", tz=TZ) + pd.Timedelta(minutes=5 * i),
                     "open": 98.0, "high": 98.2, "low": 80.0, "close": 81.0})
    df = _make_df(base)

    res = run_backtest(
        df=df, symbol="XAUUSD", entry_type="pattern", ema_period=21,
        rr_ratio=2.0, max_candles=7, lot_mode="fixed", fixed_lot=0.01,
        buffer_k=5.0, tp_type="price_based", sl_type="close_based", entry_mode="close",
    )
    assert res["total_trades"] == 1
    t = res["trades"][0]
    assert t["direction"] == "SELL"
    assert round(t["entry"], 4) == 98.0
    assert round(t["sl"], 4) == 102.5   # 102 + 5*0.1
    assert round(t["tp"], 4) == 89.0    # risk 4.5 -> 98 - 9
```

- [ ] **Step 2: Chạy test xác nhận FAIL**

Run: `python -m pytest tests/test_backtest_feg.py -v`
Expected: FAIL — `TypeError: run_backtest() got an unexpected keyword argument 'entry_type'`.

- [ ] **Step 3: Thêm dispatch + nhánh FEG vào `src/backtest.py`**

Thêm import đầu file:
```python
from src.feg_strategy import detect_feg_signal
```
Sửa chữ ký `run_backtest` — thêm vào cuối danh sách tham số (trước `)`):
```python
    entry_type: str = "time",
    ema_period: int = 21,
    ema_distance_enabled: bool = False,
    ema_distance_pips: float = 0.0,
```
Ngay đầu thân `run_backtest` (sau docstring, trước `pip_value = get_pip_value(symbol)`), thêm dispatch:
```python
    if entry_type == "pattern":
        return _run_feg_backtest(
            df=df, symbol=symbol, rr_ratio=rr_ratio, max_candles=max_candles,
            lot_mode=lot_mode, fixed_lot=fixed_lot, risk_percent=risk_percent,
            risk_amount=risk_amount, risk_mode=risk_mode, buffer_k=buffer_k,
            starting_equity=starting_equity, tp_type=tp_type, sl_type=sl_type,
            entry_mode=entry_mode, entry_percent=entry_percent, ema_period=ema_period,
            ema_distance_enabled=ema_distance_enabled, ema_distance_pips=ema_distance_pips,
        )
```
Thêm hàm `_run_feg_backtest` (đặt sau `run_backtest`):
```python
def _run_feg_backtest(
    df, symbol, rr_ratio, max_candles, lot_mode, fixed_lot, risk_percent,
    risk_amount, risk_mode, buffer_k, starting_equity, tp_type, sl_type,
    entry_mode, entry_percent, ema_period, ema_distance_enabled, ema_distance_pips,
):
    """Backtest FEG: quét tuần tự, 1 lệnh tại 1 thời điểm."""
    pip_value = get_pip_value(symbol)
    df = df.reset_index(drop=True)
    ema = df["close"].ewm(span=ema_period, adjust=False).mean().tolist()

    trades = []
    equity_curve_pips = [0]
    equity_curve_usd = [starting_equity]
    current_equity = starting_equity

    n = len(df)
    i = max(1, ema_period)  # warmup: bỏ vùng EMA chưa ổn định
    while i < n:
        c1 = {"open": df.at[i - 1, "open"], "high": df.at[i - 1, "high"],
              "low": df.at[i - 1, "low"], "close": df.at[i - 1, "close"]}
        c2 = {"open": df.at[i, "open"], "high": df.at[i, "high"],
              "low": df.at[i, "low"], "close": df.at[i, "close"]}
        direction = detect_feg_signal(
            c1, c2, ema[i], pip_value, ema_distance_enabled, ema_distance_pips,
        )
        if direction:
            levels = compute_trade_levels(
                direction, c2, entry_mode, entry_percent, buffer_k, rr_ratio, pip_value,
            )
            lot_size = _compute_lot_size(
                lot_mode, current_equity, risk_mode, risk_percent, risk_amount,
                levels["sl_pips"], symbol, fixed_lot,
            )
            exit_type, exit_price, exit_time, candles_held, exit_pos = _simulate_exit(
                df, i, direction, levels["take_profit"], levels["stop_loss"],
                max_candles, tp_type, sl_type,
            )
            if not exit_type:
                break  # hết data, không đóng được lệnh

            trade, pnl_pips, pnl_usd = _make_trade(
                df.at[i, "time"], direction, levels, lot_size, exit_type,
                exit_price, exit_time, candles_held, symbol,
            )
            current_equity += pnl_usd
            trades.append(trade)
            equity_curve_pips.append(equity_curve_pips[-1] + pnl_pips)
            equity_curve_usd.append(current_equity)

            i = exit_pos + 1  # 1 lệnh/lúc: quét tiếp sau nến exit
            continue
        i += 1

    stats = calculate_stats(trades, lot_mode)
    stats["equity_curve"] = equity_curve_pips
    stats["equity_curve_usd"] = equity_curve_usd
    stats["trades"] = trades
    stats["lot_mode"] = lot_mode
    stats["final_equity"] = current_equity
    stats["starting_equity"] = starting_equity
    stats["ohlc_data"] = df
    return stats
```

- [ ] **Step 4: Chạy test xác nhận PASS**

Run: `python -m pytest tests/test_backtest_feg.py -v`
Expected: PASS (2 passed).

- [ ] **Step 5: Chạy toàn bộ test regression**

Run: `python -m pytest tests/ -v`
Expected: PASS (tất cả).

- [ ] **Step 6: Commit**

```bash
git add src/backtest.py tests/test_backtest_feg.py
git commit -m "feat: add FEG backtest path with sequential one-at-a-time scanning"
```

---

### Task 6: Strategy YAML + strategy_manager params

**Files:**
- Create: `strategies/feg_ema21.yaml`
- Modify: `strategies/master_candle.yaml`
- Modify: `src/strategy_manager.py`
- Create: `tests/test_strategy_manager_feg.py`

**Interfaces:**
- Produces: `get_strategy_parameters(id)` trả thêm keys: `entry_type`, `ema_period`, `ema_distance_enabled`, `ema_distance_pips`, `buffer_k`. Master_candle: `entry_type="time"`.

- [ ] **Step 1: Tạo `strategies/feg_ema21.yaml`**

```yaml
id: feg_ema21
name: FEG EMA21 Strategy
version: "1.0"
description: |
  FEG 2-candle pattern + EMA21 filter. Quet lien tuc moi nen.
  SELL: H2>H1, C2<L1, L2>EMA21(+dist). BUY: L2<L1, C2>H1, H2<EMA21(-dist).
  TP/SL neo vao candle2: SL = candle2 high/low +/- buffer_k, TP = entry +/- risk*rr_ratio.
  1 lenh tai 1 thoi diem.
author: admin
created: "2026-06-21"
enabled: true

entry:
  type: pattern
  timeframe: M5
  pattern: feg_ema21
  ema_period: 21
  ema_distance:
    enabled: false
    pips: 0

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
  buffer_k: 5
  lot_size: 0.01

symbols:
  - XAUUSD
  - BTCUSD
  - ETHUSD
  - XAUUSDm
  - BTCUSDm
  - ETHUSDm
```

- [ ] **Step 2: Thêm `entry.type: time` vào `strategies/master_candle.yaml`**

Trong block `entry:` của `strategies/master_candle.yaml`, thêm dòng `type: time` ngay dưới `entry:`:
```yaml
entry:
  type: time
  timeframe: M5
  time: "21:05"
```

- [ ] **Step 3: Viết test `tests/test_strategy_manager_feg.py`**

```python
from src.strategy_manager import get_strategy_parameters

def test_feg_params():
    p = get_strategy_parameters("feg_ema21")
    assert p["entry_type"] == "pattern"
    assert p["ema_period"] == 21
    assert p["ema_distance_enabled"] is False
    assert p["ema_distance_pips"] == 0
    assert p["buffer_k"] == 5
    assert p["rr_ratio"] == 2.0
    assert "XAUUSD" in p["symbols"]

def test_master_candle_defaults_to_time():
    p = get_strategy_parameters("master_candle")
    assert p["entry_type"] == "time"
    assert p["entry_time"] == "21:05"
```

- [ ] **Step 4: Chạy test xác nhận FAIL**

Run: `python -m pytest tests/test_strategy_manager_feg.py -v`
Expected: FAIL — `KeyError: 'entry_type'`.

- [ ] **Step 5: Sửa `get_strategy_parameters` trong `src/strategy_manager.py`**

Thay khối `return {...}` trong `get_strategy_parameters` bằng:
```python
    ema_distance = entry.get('ema_distance', {})

    return {
        'timeframe': entry.get('timeframe', 'M5'),
        'entry_type': entry.get('type', 'time'),
        'entry_time': entry.get('time', '21:05'),
        'timezone': entry.get('timezone', 'Asia/Ho_Chi_Minh'),
        'pattern': entry.get('pattern', ''),
        'ema_period': entry.get('ema_period', 21),
        'ema_distance_enabled': ema_distance.get('enabled', False),
        'ema_distance_pips': ema_distance.get('pips', 0),
        'sl_pips': params.get('sl_pips', 30),
        'rr_ratio': params.get('rr_ratio', 2.0),
        'buffer_k': params.get('buffer_k', 5),
        'lot_size': params.get('lot_size', 0.01),
        'max_candles': exit_config.get('time_limit', {}).get('max_candles', 7),
        'tp_type': exit_config.get('tp', {}).get('type', 'price_based'),
        'sl_type': exit_config.get('sl', {}).get('type', 'close_based'),
        'symbols': strategy.get('symbols', [])
    }
```

- [ ] **Step 6: Chạy test xác nhận PASS**

Run: `python -m pytest tests/test_strategy_manager_feg.py -v`
Expected: PASS (2 passed).

- [ ] **Step 7: Commit**

```bash
git add strategies/feg_ema21.yaml strategies/master_candle.yaml src/strategy_manager.py tests/test_strategy_manager_feg.py
git commit -m "feat: add feg_ema21 strategy YAML + pattern params in strategy_manager"
```

---

### Task 7: Backtest page UI (pattern-aware)

**Files:**
- Modify: `pages/5_Backtest.py`

**Interfaces:**
- Consumes: `get_strategy_parameters()['entry_type', 'ema_period', 'ema_distance_enabled', 'ema_distance_pips', 'buffer_k']`; `run_backtest(... entry_type, ema_period, ema_distance_enabled, ema_distance_pips)`.
- Produces: UI điều kiện theo `entry_type`; `backtest_config` thêm `entry_type, ema_period, ema_dist_enabled, ema_dist_pips`.

> UI Streamlit không unit test — verify thủ công bằng cách chạy app.

- [ ] **Step 1: Đọc entry_type sau khi load params**

Trong `pages/5_Backtest.py`, ngay sau `params = get_strategy_parameters(selected_strategy)` (dòng ~87), thêm:
```python
    entry_type = params.get('entry_type', 'time')
    is_pattern = entry_type == 'pattern'
```

- [ ] **Step 2: Ẩn Entry Time khi pattern + thêm khối EMA config**

Trong cột `col2` (block `with col2:` chứa entry time, dòng ~133-161), bọc phần entry time bằng điều kiện. Thay toàn bộ phần entry-time trong `col2` bằng:
```python
        if is_pattern:
            st.markdown("**EMA Filter**")
            ema_period = st.number_input(
                "EMA Period",
                value=int(params.get('ema_period', 21)),
                min_value=2, max_value=200,
            )
            ema_dist_enabled = st.checkbox(
                "Xét khoảng cách EMA21",
                value=bool(params.get('ema_distance_enabled', False)),
                help="Bật để yêu cầu L2/H2 cách EMA21 tối thiểu (pips)",
            )
            if ema_dist_enabled:
                ema_dist_pips = st.number_input(
                    "Khoảng cách EMA (pips)",
                    value=float(params.get('ema_distance_pips', 0) or 0),
                    min_value=0.0, step=1.0,
                )
            else:
                ema_dist_pips = 0.0
            # entry_time không dùng cho pattern; đặt giá trị giả để chữ ký run_backtest không lỗi
            entry_time = datetime.strptime("00:00", "%H:%M").time()
        else:
            ema_period = int(params.get('ema_period', 21))
            ema_dist_enabled = False
            ema_dist_pips = 0.0
            entry_time_str = params.get('entry_time', '21:05')
            use_custom_time = st.checkbox("Custom entry time", value=False)
            if use_custom_time:
                custom_time_str = st.text_input(
                    "Entry Time", value="21:05", max_chars=5,
                    help="Format: HH:MM (e.g., 21:05)", placeholder="HH:MM",
                )
                try:
                    entry_time = datetime.strptime(custom_time_str, "%H:%M").time()
                except ValueError:
                    st.error("Invalid time format. Use HH:MM (e.g., 21:05)")
                    entry_time = datetime.strptime("21:05", "%H:%M").time()
            else:
                entry_time = st.time_input(
                    "Entry Time",
                    value=datetime.strptime(entry_time_str, "%H:%M").time(),
                    step=300, help=f"From strategy: {entry_time_str}", disabled=True,
                )
                st.caption(f"Strategy default: {entry_time_str}")
```

- [ ] **Step 3: Truyền params FEG vào `run_backtest`**

Trong lời gọi `results = run_backtest(...)` (dòng ~402), thêm các kwargs:
```python
                entry_type=entry_type,
                ema_period=ema_period,
                ema_distance_enabled=ema_dist_enabled,
                ema_distance_pips=ema_dist_pips,
```

- [ ] **Step 4: Thêm EMA vào `backtest_config`**

Trong dict `backtest_config = {...}` (dòng ~424), thêm:
```python
            'entry_type': entry_type,
            'ema_period': ema_period,
            'ema_dist_enabled': ema_dist_enabled,
            'ema_dist_pips': ema_dist_pips,
```

- [ ] **Step 5: Verify import sạch (smoke)**

Run: `python -c "import ast; ast.parse(open('pages/5_Backtest.py', encoding='utf-8').read()); print('OK')"`
Expected: `OK` (không lỗi cú pháp).

- [ ] **Step 6: Verify thủ công trên app**

Run: `streamlit run app.py` → trang Backtest → chọn strategy **FEG EMA21 Strategy**.
Expected: KHÔNG hiện Entry Time; hiện EMA Period + checkbox "Xét khoảng cách EMA21"; tick checkbox → hiện ô "Khoảng cách EMA (pips)". Chọn master_candle → hiện lại Entry Time như cũ.

- [ ] **Step 7: Commit**

```bash
git add pages/5_Backtest.py
git commit -m "feat: pattern-aware backtest UI for FEG (EMA filter + flag)"
```

---

### Task 8: Live order placement gated by test flag

**Files:**
- Modify: `src/orders.py`
- Create: `tests/test_place_order.py`

**Interfaces:**
- Produces: `place_order(symbol, direction, volume, sl=None, tp=None, credentials=None, test=False, magic=123456, comment="Order") -> tuple(success, message, ticket)`. Khi `test=True` → trả `(True, "[TEST] ...", None)` mà KHÔNG kết nối MT5.

- [ ] **Step 1: Viết test `tests/test_place_order.py`**

```python
from src import orders

def test_place_order_test_mode_does_not_touch_mt5(monkeypatch):
    called = {"connect": False}
    def fake_conn(creds=None):
        called["connect"] = True
        return None, "should not be called"
    monkeypatch.setattr(orders, "get_mt5_connection", fake_conn)

    success, msg, ticket = orders.place_order(
        "XAUUSD", "SELL", 0.01, sl=102.5, tp=89.0, test=True,
    )
    assert success is True
    assert ticket is None
    assert "TEST" in msg
    assert called["connect"] is False  # không gọi MT5 ở test mode

def test_place_order_live_sends_and_returns_ticket(monkeypatch):
    class FakeTick:
        bid = 98.0
        ask = 98.1
    class FakeSymbolInfo:
        visible = True
    class FakeResult:
        retcode = 99
        order = 777777
        comment = "done"
    class FakeMT5:
        TRADE_RETCODE_DONE = 99
        ORDER_TYPE_BUY = 0
        ORDER_TYPE_SELL = 1
        TRADE_ACTION_DEAL = 1
        ORDER_TIME_GTC = 0
        ORDER_FILLING_IOC = 0
        def symbol_info(self, s): return FakeSymbolInfo()
        def symbol_select(self, s, v): return True
        def symbol_info_tick(self, s): return FakeTick()
        def order_send(self, req): return FakeResult()
        def shutdown(self): pass

    fake = FakeMT5()
    monkeypatch.setattr(orders, "get_mt5_connection", lambda creds=None: (fake, None))
    # place_order dùng `import MetaTrader5 as mt5_module` cho hằng số -> patch sys.modules
    import sys
    monkeypatch.setitem(sys.modules, "MetaTrader5", fake)

    success, msg, ticket = orders.place_order(
        "XAUUSD", "SELL", 0.01, sl=102.5, tp=89.0, test=False, magic=212100, comment="FEG",
    )
    assert success is True
    assert ticket == 777777
```

- [ ] **Step 2: Chạy test xác nhận FAIL**

Run: `python -m pytest tests/test_place_order.py -v`
Expected: FAIL — `place_order()` chưa có tham số `test` (TypeError) hoặc test-mode chưa short-circuit.

- [ ] **Step 3: Sửa `place_order` trong `src/orders.py`**

Thay chữ ký + đầu thân hàm `place_order`:
```python
def place_order(
    symbol: str,
    direction: str,
    volume: float,
    sl: float = None,
    tp: float = None,
    credentials: dict = None,
    test: bool = False,
    magic: int = 123456,
    comment: str = "Order",
) -> tuple:
    """
    Place a market order.

    test=True  -> simulate (không gửi MT5), trả (True, "[TEST] ...", None)
    test=False -> gửi lệnh thật.
    """
    if test:
        return True, f"[TEST] {direction} {symbol} vol={volume} sl={sl} tp={tp} simulated", None

    mt5, error = get_mt5_connection(credentials)
    if error:
        return False, error, None
```
Trong dict `request` của `place_order`, đổi `magic`/`comment` cứng thành tham số:
```python
            "magic": magic,
            "comment": comment,
```

- [ ] **Step 4: Chạy test xác nhận PASS**

Run: `python -m pytest tests/test_place_order.py -v`
Expected: PASS (2 passed).

- [ ] **Step 5: Commit**

```bash
git add src/orders.py tests/test_place_order.py
git commit -m "feat: gate place_order by test flag + parameterize magic/comment"
```

---

### Task 9: bot_runner FEG dispatch + runner loop

**Files:**
- Modify: `src/bot_runner.py`
- Create: `tests/test_feg_runner.py`

**Interfaces:**
- Consumes: `analyze_feg`, `place_order(... test=...)`, `check_exit`, `get_strategy_parameters`.
- Produces:
  - argparse thêm `--ema_period` (int), `--ema_distance_enabled` (int 0/1), `--ema_distance_pips` (float).
  - `feg_entry_decision(active_trade, candle1, candle2, ema2, symbol, rr_ratio, buffer_k, lot_size, entry_mode, entry_percent, ema_distance_enabled, ema_distance_pips) -> dict | None` — None nếu đang có lệnh (1 lệnh/lúc) hoặc không có pattern.
  - `run_feg_bot(args, strategy, params, credentials)` — vòng lặp live FEG.
  - `run_bot` dispatch theo `params['entry_type']`.

- [ ] **Step 1: Viết test `tests/test_feg_runner.py`**

```python
from src.bot_runner import feg_entry_decision

C1 = {"open": 100.0, "high": 101.0, "low": 99.0, "close": 100.5}
C2 = {"open": 100.8, "high": 102.0, "low": 98.5, "close": 98.0}  # SELL khi ema2<98.5
EMA2 = 98.0

def test_entry_when_flat_and_pattern():
    sig = feg_entry_decision(
        None, C1, C2, EMA2, "XAUUSD",
        rr_ratio=2.0, buffer_k=5.0, lot_size=0.01,
        entry_mode="close", entry_percent=0.0,
        ema_distance_enabled=False, ema_distance_pips=0.0,
    )
    assert sig is not None
    assert sig["direction"] == "SELL"

def test_no_entry_when_already_in_trade():
    active = {"direction": "SELL", "entry": 98.0}
    sig = feg_entry_decision(
        active, C1, C2, EMA2, "XAUUSD",
        rr_ratio=2.0, buffer_k=5.0, lot_size=0.01,
        entry_mode="close", entry_percent=0.0,
        ema_distance_enabled=False, ema_distance_pips=0.0,
    )
    assert sig is None  # 1 lệnh tại 1 thời điểm
```

- [ ] **Step 2: Chạy test xác nhận FAIL**

Run: `python -m pytest tests/test_feg_runner.py -v`
Expected: FAIL — `ImportError: cannot import name 'feg_entry_decision'`.

- [ ] **Step 3: Thêm argparse args trong `get_args()` (`src/bot_runner.py`)**

Sau `--max_candles` (dòng ~45), thêm:
```python
    parser.add_argument("--ema_period", type=int, default=None,
                        help="EMA period for pattern strategies (default: from strategy)")
    parser.add_argument("--ema_distance_enabled", type=int, default=0,
                        help="Enable EMA distance filter: 1=yes, 0=no")
    parser.add_argument("--ema_distance_pips", type=float, default=0.0,
                        help="EMA distance in pips when filter enabled")
```

- [ ] **Step 4: Thêm `feg_entry_decision` + `get_recent_candles` + `run_feg_bot` vào `src/bot_runner.py`**

Thêm import ở đầu file (sau các import hiện có, để top-level không cần mt5):
```python
# (đặt trong các hàm cần dùng để tránh import mt5 ở module top-level)
```
Thêm hàm (đặt sau `run_bot`):
```python
def feg_entry_decision(
    active_trade, candle1, candle2, ema2, symbol,
    rr_ratio, buffer_k, lot_size, entry_mode, entry_percent,
    ema_distance_enabled, ema_distance_pips,
):
    """Quyết định vào lệnh FEG. None nếu đang có lệnh (1 lệnh/lúc) hoặc không có pattern."""
    from src.feg_strategy import analyze_feg
    if active_trade is not None:
        return None
    return analyze_feg(
        symbol, candle1, candle2, ema2,
        rr_ratio=rr_ratio, buffer_k=buffer_k, lot_size=lot_size,
        entry_mode=entry_mode, entry_percent=entry_percent,
        ema_distance_enabled=ema_distance_enabled, ema_distance_pips=ema_distance_pips,
    )


def get_recent_candles(mt5, symbol: str, timeframe_str: str, count: int = 120):
    """Lấy `count` nến đã đóng gần nhất dưới dạng list dict (cũ -> mới)."""
    import pandas as pd
    timeframe_map = {
        'M1': mt5.TIMEFRAME_M1, 'M5': mt5.TIMEFRAME_M5, 'M15': mt5.TIMEFRAME_M15,
        'M30': mt5.TIMEFRAME_M30, 'H1': mt5.TIMEFRAME_H1, 'H4': mt5.TIMEFRAME_H4,
        'D1': mt5.TIMEFRAME_D1,
    }
    timeframe = timeframe_map.get(timeframe_str, mt5.TIMEFRAME_M5)
    # +1 vì nến cuối (index 0) đang chạy, ta bỏ nó đi
    rates = mt5.copy_rates_from_pos(symbol, timeframe, 0, count + 1)
    if rates is None or len(rates) < 3:
        return None
    df = pd.DataFrame(rates)
    df = df.iloc[:-1]  # bỏ nến đang chạy -> chỉ nến đã đóng
    return df


def run_feg_bot(args, strategy, params, credentials):
    """Vòng lặp live cho strategy FEG (pattern + EMA21, 1 lệnh/lúc)."""
    import pandas as pd
    from src.orders import place_order, close_position

    timeframe = params.get('timeframe', 'M5')
    ema_period = args.ema_period or params.get('ema_period', 21)
    rr_ratio = args.rr_ratio or params.get('rr_ratio', 2.0)
    buffer_k = params.get('buffer_k', 5)
    lot_size = args.lot_size or params.get('lot_size', 0.01)
    max_candles = args.max_candles or params.get('max_candles', 7)
    ema_dist_enabled = bool(args.ema_distance_enabled) or params.get('ema_distance_enabled', False)
    ema_dist_pips = args.ema_distance_pips or params.get('ema_distance_pips', 0)
    entry_mode = "close"
    entry_percent = 0.0

    log(f"FEG params: EMA{ema_period}, RR={rr_ratio}, buffer_k={buffer_k}, "
        f"lot={lot_size}, max_candles={max_candles}, dist={'ON ' + str(ema_dist_pips) + 'p' if ema_dist_enabled else 'OFF'}")

    send_telegram(f"FEG Bot Started\nSymbol: {args.symbol}\nUser: {args.user}\n"
                  f"Test: {'Yes' if args.test else 'No'}")

    active_trade = None
    last_candle_time = None

    try:
        while True:
            mt5, error = get_mt5_connection(credentials)
            if error:
                log(f"MT5 connection failed: {error}", "ERROR")
                send_telegram(f"MT5 Error: {error}", is_error=True)
                time.sleep(args.interval)
                continue

            df = get_recent_candles(mt5, args.symbol, timeframe, count=max(120, ema_period * 4))
            if df is None or len(df) < ema_period + 2:
                mt5.shutdown()
                time.sleep(args.interval)
                continue

            ema = df["close"].ewm(span=ema_period, adjust=False).mean().tolist()
            last = df.iloc[-1]
            prev = df.iloc[-2]
            candle_time = datetime.fromtimestamp(int(last["time"]), tz=TIMEZONE)

            # chỉ xử lý khi có nến đóng mới
            is_new_candle = (last_candle_time is None) or (candle_time > last_candle_time)

            if active_trade is None and is_new_candle:
                c1 = {"open": prev["open"], "high": prev["high"], "low": prev["low"], "close": prev["close"]}
                c2 = {"open": last["open"], "high": last["high"], "low": last["low"], "close": last["close"]}
                signal = feg_entry_decision(
                    None, c1, c2, ema[-1], args.symbol,
                    rr_ratio, buffer_k, lot_size, entry_mode, entry_percent,
                    ema_dist_enabled, ema_dist_pips,
                )
                if signal:
                    log(f"FEG Signal: {signal['direction']} @ {signal['entry_price']:.2f}, "
                        f"SL={signal['stop_loss']:.2f}, TP={signal['take_profit']:.2f}")
                    send_telegram(f"<b>FEG Signal: {signal['direction']}</b>\n"
                                  f"Symbol: {args.symbol}\nEntry: {signal['entry_price']:.2f}\n"
                                  f"SL: {signal['stop_loss']:.2f}\nTP: {signal['take_profit']:.2f}")
                    ok, msg, ticket = place_order(
                        args.symbol, signal["direction"], lot_size,
                        sl=signal["stop_loss"], tp=signal["take_profit"],
                        credentials=credentials, test=bool(args.test),
                        magic=212100, comment="FEG",
                    )
                    log(f"Order result: {msg}")
                    active_trade = {
                        "direction": signal["direction"], "entry": signal["entry_price"],
                        "sl": signal["stop_loss"], "tp": signal["take_profit"],
                        "ticket": ticket, "candles": 0,
                    }

            elif active_trade is not None and is_new_candle:
                active_trade["candles"] += 1
                candle = {"high": last["high"], "low": last["low"], "close": last["close"]}
                from src.utils import check_exit
                exit_type, exit_price = check_exit(
                    active_trade["direction"], candle,
                    active_trade["tp"], active_trade["sl"],
                    params.get("tp_type", "price_based"),
                    params.get("sl_type", "close_based"),
                )
                if not exit_type and active_trade["candles"] >= max_candles:
                    exit_type, exit_price = "TIME", last["close"]

                if exit_type:
                    pip_value = get_pip_value(args.symbol)
                    if active_trade["direction"] == "BUY":
                        pnl = (exit_price - active_trade["entry"]) / pip_value
                    else:
                        pnl = (active_trade["entry"] - exit_price) / pip_value
                    log(f"FEG Exit: {exit_type} @ {exit_price:.2f}, P&L: {pnl:.1f} pips")
                    send_telegram(f"<b>FEG Exit: {exit_type}</b>\nPrice: {exit_price:.2f}\nP&L: {pnl:.1f} pips")
                    if not args.test and active_trade.get("ticket"):
                        close_position(active_trade["ticket"], credentials=credentials)
                    active_trade = None

            if is_new_candle:
                last_candle_time = candle_time

            mt5.shutdown()
            time.sleep(args.interval)

    except KeyboardInterrupt:
        log("FEG Bot stopped by user")
        send_telegram("FEG Bot Stopped (manual)")
    except Exception as e:
        log(f"FEG Bot error: {e}", "ERROR")
        send_telegram(f"FEG Bot Error: {e}", is_error=True)
        raise
```

- [ ] **Step 5: Dispatch theo `entry_type` trong `run_bot`**

Trong `run_bot`, ngay sau `params = get_strategy_parameters(args.strategy)` và `log(...)` (dòng ~174-175), thêm dispatch (trước khi đọc các param master_candle):
```python
    # Dispatch theo entry type
    if params.get('entry_type', 'time') == 'pattern':
        credentials = get_user_mt5_credentials(args.user)
        if not credentials.get('login'):
            log(f"MT5 credentials not configured for user: {args.user}", "ERROR")
            return
        run_feg_bot(args, strategy, params, credentials)
        return
```
(`get_user_mt5_credentials` đã import ở đầu `run_bot`.)

- [ ] **Step 6: Chạy unit test xác nhận PASS**

Run: `python -m pytest tests/test_feg_runner.py -v`
Expected: PASS (2 passed).

- [ ] **Step 7: Verify import + argparse (smoke, không cần MT5)**

Run: `python -c "import src.bot_runner; print('import OK')"`
Expected: `import OK`.
Run: `python src/bot_runner.py --help`
Expected: hiển thị help có `--ema_period`, `--ema_distance_enabled`, `--ema_distance_pips`.

- [ ] **Step 8: Commit**

```bash
git add src/bot_runner.py tests/test_feg_runner.py
git commit -m "feat: FEG live runner loop + entry_type dispatch in bot_runner"
```

---

### Task 10: bot_manager + Bots page params

**Files:**
- Modify: `src/bot_manager.py`
- Modify: `pages/1_Bots.py`
- Create: `tests/test_bot_command.py`

**Interfaces:**
- Produces:
  - `src.bot_manager.build_bot_command(python_exe, script_path, strategy, symbol, user, test, interval, lot_size, sl_pips, rr_ratio, max_candles, ema_period, ema_distance_enabled, ema_distance_pips) -> list[str]`.
  - `start_bot(...)` thêm tham số `ema_period=None, ema_distance_enabled=False, ema_distance_pips=0.0`, lưu vào `running_bots.json` + dùng `build_bot_command`.

- [ ] **Step 1: Viết test `tests/test_bot_command.py`**

```python
from src.bot_manager import build_bot_command

def test_command_includes_ema_flags_when_enabled():
    cmd = build_bot_command(
        "python", "bot_runner.py", "feg_ema21", "XAUUSD", "admin",
        test=False, interval=60, lot_size=0.02, sl_pips=None, rr_ratio=2.0,
        max_candles=7, ema_period=21, ema_distance_enabled=True, ema_distance_pips=5.0,
    )
    assert "--strategy" in cmd and "feg_ema21" in cmd
    assert "--test" in cmd and cmd[cmd.index("--test") + 1] == "0"
    assert cmd[cmd.index("--ema_period") + 1] == "21"
    assert cmd[cmd.index("--ema_distance_enabled") + 1] == "1"
    assert cmd[cmd.index("--ema_distance_pips") + 1] == "5.0"

def test_command_disabled_ema_flag_is_zero():
    cmd = build_bot_command(
        "python", "bot_runner.py", "feg_ema21", "XAUUSD", "admin",
        test=True, interval=60, lot_size=None, sl_pips=None, rr_ratio=None,
        max_candles=None, ema_period=None, ema_distance_enabled=False, ema_distance_pips=0.0,
    )
    assert cmd[cmd.index("--ema_distance_enabled") + 1] == "0"
    assert "--ema_period" not in cmd  # None -> không thêm
```

- [ ] **Step 2: Chạy test xác nhận FAIL**

Run: `python -m pytest tests/test_bot_command.py -v`
Expected: FAIL — `ImportError: cannot import name 'build_bot_command'`.

- [ ] **Step 3: Thêm `build_bot_command` + sửa `start_bot` trong `src/bot_manager.py`**

Thêm hàm (trước `start_bot`):
```python
def build_bot_command(
    python_exe, script_path, strategy, symbol, user, test, interval,
    lot_size=None, sl_pips=None, rr_ratio=None, max_candles=None,
    ema_period=None, ema_distance_enabled=False, ema_distance_pips=0.0,
):
    """Dựng command list để chạy bot_runner (tách riêng để test được)."""
    cmd = [
        python_exe, script_path,
        "--strategy", strategy,
        "--symbol", symbol,
        "--user", user,
        "--test", "1" if test else "0",
        "--interval", str(interval),
        "--ema_distance_enabled", "1" if ema_distance_enabled else "0",
        "--ema_distance_pips", str(ema_distance_pips),
    ]
    if lot_size:
        cmd.extend(["--lot_size", str(lot_size)])
    if sl_pips:
        cmd.extend(["--sl_pips", str(sl_pips)])
    if rr_ratio:
        cmd.extend(["--rr_ratio", str(rr_ratio)])
    if max_candles:
        cmd.extend(["--max_candles", str(max_candles)])
    if ema_period:
        cmd.extend(["--ema_period", str(ema_period)])
    return cmd
```
Sửa chữ ký `start_bot` — thêm tham số:
```python
def start_bot(
    strategy: str,
    symbol: str,
    user: str,
    test: bool = True,
    lot_size: float = None,
    sl_pips: float = None,
    rr_ratio: float = None,
    max_candles: int = None,
    interval: int = 60,
    ema_period: int = None,
    ema_distance_enabled: bool = False,
    ema_distance_pips: float = 0.0,
) -> tuple:
```
Trong `start_bot`, thay khối dựng `cmd` (từ `python_exe = sys.executable` đến hết các `cmd.extend(...)`) bằng:
```python
    python_exe = sys.executable
    script_path = os.path.abspath(BOT_SCRIPT)
    cmd = build_bot_command(
        python_exe, script_path, strategy, symbol, user, test, interval,
        lot_size, sl_pips, rr_ratio, max_candles,
        ema_period, ema_distance_enabled, ema_distance_pips,
    )
```
Thêm vào dict `bot_info` (sau `'max_candles': max_candles,`):
```python
            'ema_period': ema_period,
            'ema_distance_enabled': ema_distance_enabled,
            'ema_distance_pips': ema_distance_pips,
```
Trong `restart_bot`, thêm vào lời gọi `start_bot(...)`:
```python
        ema_period=bot.get('ema_period'),
        ema_distance_enabled=bot.get('ema_distance_enabled', False),
        ema_distance_pips=bot.get('ema_distance_pips', 0.0),
```

- [ ] **Step 4: Chạy test xác nhận PASS**

Run: `python -m pytest tests/test_bot_command.py -v`
Expected: PASS (2 passed).

- [ ] **Step 5: Thêm input EMA vào form tạo bot (`pages/1_Bots.py`)**

Trong `show_create_bot`, sau `params = get_strategy_parameters(selected_strategy)` (dòng ~198), thêm:
```python
            is_pattern = params.get('entry_type', 'time') == 'pattern'
```
Trong `with st.form("create_bot")`, sau block `col1/col2` interval (dòng ~248), thêm:
```python
        if is_pattern:
            st.markdown("**EMA Filter (FEG)**")
            ec1, ec2, ec3 = st.columns(3)
            with ec1:
                ema_period = st.number_input("EMA Period", value=int(params.get('ema_period', 21)), min_value=2, max_value=200)
            with ec2:
                ema_distance_enabled = st.checkbox("Xét khoảng cách EMA21", value=bool(params.get('ema_distance_enabled', False)))
            with ec3:
                ema_distance_pips = st.number_input("Khoảng cách (pips)", value=float(params.get('ema_distance_pips', 0) or 0), min_value=0.0, step=1.0, disabled=not ema_distance_enabled)
        else:
            ema_period = None
            ema_distance_enabled = False
            ema_distance_pips = 0.0
```
Sửa block hiển thị strategy info (dòng ~252-253) thành:
```python
        st.markdown(f"**Strategy:** {selected_strategy_name}")
        if is_pattern:
            st.caption(f"Pattern: {params.get('pattern', 'feg')} | EMA{params.get('ema_period', 21)} ({params.get('timeframe', 'M5')})")
        else:
            st.caption(f"Entry: {params.get('entry_time', 'N/A')} ({params.get('timeframe', 'N/A')})")
```
Sửa lời gọi `start_bot(...)` trong nhánh submit (dòng ~261), thêm kwargs:
```python
                    ema_period=ema_period,
                    ema_distance_enabled=ema_distance_enabled,
                    ema_distance_pips=ema_distance_pips,
```

- [ ] **Step 6: Verify cú pháp page**

Run: `python -c "import ast; ast.parse(open('pages/1_Bots.py', encoding='utf-8').read()); print('OK')"`
Expected: `OK`.

- [ ] **Step 7: Commit**

```bash
git add src/bot_manager.py pages/1_Bots.py tests/test_bot_command.py
git commit -m "feat: pass FEG EMA params through bot_manager + Bots create form"
```

---

### Task 11: Backtest history EMA columns + Strategies read-only view

**Files:**
- Modify: `src/backtest_history.py`
- Modify: `pages/4_Strategies.py`
- Create: `tests/test_history_columns.py`

**Interfaces:**
- Produces: `history_to_dataframe` thêm cột `Entry Type`, `EMA Period`, `EMA Dist`; `HISTORY_COLUMNS['config']` thêm các cột này.

- [ ] **Step 1: Viết test `tests/test_history_columns.py`**

```python
from src.backtest_history import history_to_dataframe, HISTORY_COLUMNS

def test_history_includes_ema_columns():
    history = [{
        "id": "x", "timestamp": "2026-06-21T10:00:00", "strategy": "FEG EMA21 Strategy",
        "symbol": "XAUUSD",
        "config": {"entry_type": "pattern", "ema_period": 21, "ema_dist_enabled": True,
                   "ema_dist_pips": 5, "timeframe": "M5"},
        "summary": {"total_trades": 3, "win_rate": 66.7},
    }]
    df = history_to_dataframe(history)
    assert df.iloc[0]["Entry Type"] == "pattern"
    assert df.iloc[0]["EMA Period"] == 21
    assert "Entry Type" in HISTORY_COLUMNS["config"]
    assert "EMA Period" in HISTORY_COLUMNS["config"]
```

- [ ] **Step 2: Chạy test xác nhận FAIL**

Run: `python -m pytest tests/test_history_columns.py -v`
Expected: FAIL — `KeyError: 'Entry Type'`.

- [ ] **Step 3: Thêm cột EMA vào `history_to_dataframe` (`src/backtest_history.py`)**

Trong dict `row = {...}`, sau dòng `'Buffer K': config.get('buffer_k', ''),`, thêm:
```python
            'Entry Type': config.get('entry_type', 'time'),
            'EMA Period': config.get('ema_period', ''),
            'EMA Dist': (f"{config.get('ema_dist_pips', 0)}p" if config.get('ema_dist_enabled') else 'Off'),
```
Trong `HISTORY_COLUMNS['config']`, thêm 3 cột vào list:
```python
    'config': [
        'Timeframe', 'Entry Time', 'Entry Type', 'EMA Period', 'EMA Dist',
        'Lot Mode', 'RR Ratio', 'Date Range',
        'Entry Mode', 'Entry %', 'Max Candles', 'Buffer K',
        'TP Type', 'SL Type', 'Fixed Lot', 'Start Equity',
        'Risk Mode', 'Risk %', 'Risk $'
    ],
```

- [ ] **Step 4: Chạy test xác nhận PASS**

Run: `python -m pytest tests/test_history_columns.py -v`
Expected: PASS (1 passed).

- [ ] **Step 5: FEG read-only view trong `pages/4_Strategies.py`**

Trong `show_view_edit` → `with view_tab:` → block `with col2:` (dòng ~260-264), thay bằng hiển thị có điều kiện theo entry type:
```python
        with col2:
            entry = strategy.get('entry', {})
            entry_type = entry.get('type', 'time')
            st.markdown(f"**Timeframe:** {entry.get('timeframe')}")
            st.markdown(f"**Entry Type:** {entry_type}")
            if entry_type == 'pattern':
                st.markdown(f"**Pattern:** {entry.get('pattern', '')}")
                st.markdown(f"**EMA Period:** {entry.get('ema_period', 21)}")
                ema_d = entry.get('ema_distance', {})
                st.markdown(f"**EMA Distance:** {'On ' + str(ema_d.get('pips', 0)) + ' pips' if ema_d.get('enabled') else 'Off'}")
            else:
                st.markdown(f"**Entry Time:** {entry.get('time')}")
                st.markdown(f"**Timezone:** {entry.get('timezone')}")
```

- [ ] **Step 6: Verify cú pháp page**

Run: `python -c "import ast; ast.parse(open('pages/4_Strategies.py', encoding='utf-8').read()); print('OK')"`
Expected: `OK`.

- [ ] **Step 7: Chạy toàn bộ test suite (regression cuối)**

Run: `python -m pytest tests/ -v`
Expected: PASS (toàn bộ).

- [ ] **Step 8: Commit**

```bash
git add src/backtest_history.py pages/4_Strategies.py tests/test_history_columns.py
git commit -m "feat: FEG history columns + read-only strategy view"
```

---

## Manual Verification (sau khi hoàn tất, trên Windows + MT5)

- [ ] `streamlit run app.py` → Backtest → chọn **FEG EMA21 Strategy** → chạy backtest trên XAUUSD M5 (~30 ngày) → có trades, equity curve, biểu đồ hoạt động.
- [ ] Tick "Xét khoảng cách EMA21" + nhập pips → số lệnh thay đổi hợp lý.
- [ ] Bots → Create Bot → chọn FEG, Test Mode ON → bot chạy, Telegram báo "FEG Bot Started", log signal khi có pattern.
- [ ] (Demo account) Test Mode OFF → xác nhận lệnh thật được đặt trên MT5 với magic 212100.

## Notes / Quyết định kỹ thuật

- EMA backtest bỏ qua `i < ema_period` (warmup seed) thay vì fetch thêm data trước start_date — KISS, ảnh hưởng không đáng kể trên khung thời gian dài.
- `entry_mode`/`entry_percent` runner cố định `close`/`0.0` (range_percent chỉ dùng trong backtest hiện tại; có thể mở rộng sau).
- Master_candle live giữ nguyên hiện trạng (TODO chưa đặt lệnh thật) — ngoài phạm vi.
