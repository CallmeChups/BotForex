# Time Window Filter & Backtest History Columns Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `entry_start_time`/`entry_end_time` time-window gating to both backtest engine and live bot (both strategies), and reorder Backtest History columns to a new priority order with new Start Time / End Time columns.

**Architecture:** `_in_time_window()` helper added to `src/utils.py` (shared); backtest engine + bot runner import it. Time params flow: UI `st.time_input` → `run_backtest()` → `_run_feg_backtest()` / master candle loop; live bot: argparse → `run_feg_bot()` / `run_master_candle_bot()`. History column redesign is purely in `src/backtest_history.py` + `pages/5_Backtest.py`. No YAML changes.

**Tech Stack:** Python 3.10+ (`zoneinfo` built-in), Streamlit `st.time_input`, pandas, pytest

## Global Constraints

- Timezone for all time comparisons: `Asia/Ho_Chi_Minh` via `ZoneInfo("Asia/Ho_Chi_Minh")`
- Default `entry_start_time = time(0, 0)`, `entry_end_time = time(23, 59)` → no-op (backward-compat)
- Active trade holds through window end; window only gates NEW entries
- UI-only params (not in strategy YAML)
- History core columns order (exact): `Date Range`, `Start Time`, `End Time`, `Trades`, `Win Rate %`, `Total Pips`, `Total USD`, `Lot Mode`, `RR Ratio`
- `_in_time_window` must handle inclusive boundary: `start <= local_time <= end`
- All existing 25 tests must still pass (default = no filter)
- No new files created (except test additions to existing test files)

---

### Task 1: Add `_in_time_window()` to `src/utils.py`

**Files:**
- Modify: `src/utils.py` (append at bottom)
- Test: `tests/test_utils.py` (create if not exists, or add to existing)

**Interfaces:**
- Produces: `_in_time_window(ts, start, end) -> bool` where `ts` is `pd.Timestamp` or `datetime` with tzinfo, `start`/`end` are `datetime.time` objects

- [ ] **Step 1: Check if test_utils.py exists**

Run: `dir tests\test_utils.py` (Windows) or check for the file. If absent, create it in step 2.

- [ ] **Step 2: Write the failing tests**

Create/append to `tests/test_utils.py`:

```python
import pytest
from datetime import time
import pandas as pd
from zoneinfo import ZoneInfo

from src.utils import _in_time_window

_TZ = ZoneInfo("Asia/Ho_Chi_Minh")


def _ts(hour, minute):
    """Helper: pd.Timestamp at given HCM local hour:minute."""
    return pd.Timestamp(f"2026-01-15 {hour:02d}:{minute:02d}:00", tz=_TZ)


def test_in_time_window_inside():
    assert _in_time_window(_ts(10, 30), time(9, 0), time(12, 0)) is True


def test_in_time_window_before_start():
    assert _in_time_window(_ts(8, 59), time(9, 0), time(12, 0)) is False


def test_in_time_window_after_end():
    assert _in_time_window(_ts(12, 1), time(9, 0), time(12, 0)) is False


def test_in_time_window_at_start_boundary():
    assert _in_time_window(_ts(9, 0), time(9, 0), time(12, 0)) is True


def test_in_time_window_at_end_boundary():
    assert _in_time_window(_ts(12, 0), time(9, 0), time(12, 0)) is True


def test_in_time_window_default_no_filter():
    # Default 00:00–23:59 should pass any time
    assert _in_time_window(_ts(0, 0), time(0, 0), time(23, 59)) is True
    assert _in_time_window(_ts(23, 58), time(0, 0), time(23, 59)) is True
    assert _in_time_window(_ts(23, 59), time(0, 0), time(23, 59)) is True


def test_in_time_window_utc_input_converts_to_hcm():
    # 02:00 UTC = 09:00 HCM (UTC+7) — should be inside 09:00–12:00 window
    ts_utc = pd.Timestamp("2026-01-15 02:00:00", tz="UTC")
    assert _in_time_window(ts_utc, time(9, 0), time(12, 0)) is True
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `pytest tests/test_utils.py -v`
Expected: ImportError or AttributeError — `_in_time_window` not found

- [ ] **Step 4: Implement `_in_time_window` in `src/utils.py`**

Append to the end of `src/utils.py`:

```python
from datetime import time as _time
from zoneinfo import ZoneInfo as _ZoneInfo

_TZ_HCM = _ZoneInfo("Asia/Ho_Chi_Minh")


def _in_time_window(ts, start: _time, end: _time) -> bool:
    """True if ts (converted to Asia/Ho_Chi_Minh) falls within [start, end] inclusive."""
    local = ts.astimezone(_TZ_HCM).time().replace(second=0, microsecond=0)
    if start <= end:
        return start <= local <= end
    # overnight window (e.g. 22:00–02:00)
    return local >= start or local <= end
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/test_utils.py -v`
Expected: 8 passed

- [ ] **Step 6: Run full suite to verify no regressions**

Run: `pytest tests/ -v`
Expected: all existing 25 tests + 8 new = 33 passed

- [ ] **Step 7: Commit**

```bash
git add src/utils.py tests/test_utils.py
git commit -m "feat: add _in_time_window helper to utils (Asia/HCM timezone)"
```

---

### Task 2: Add time window filter to backtest engine (`src/backtest.py`)

**Files:**
- Modify: `src/backtest.py`
- Test: `tests/test_backtest_feg.py` (add 2 new tests)

**Interfaces:**
- Consumes: `_in_time_window(ts, start, end) -> bool` from `src/utils` (Task 1)
- Produces: `run_backtest(..., entry_start_time=time(0,0), entry_end_time=time(23,59))` — 2 new optional params; `_run_feg_backtest(..., entry_start_time=time(0,0), entry_end_time=time(23,59))` — same

- [ ] **Step 1: Write failing tests in `tests/test_backtest_feg.py`**

Add these two tests at the end of `tests/test_backtest_feg.py`:

```python
from datetime import time as _time
from zoneinfo import ZoneInfo

def _make_feg_df_with_time(signal_hour=10, signal_minute=0):
    """Build minimal FEG dataframe where C1+C2 form a valid SELL signal at given HCM hour."""
    import pandas as pd
    import numpy as np
    from zoneinfo import ZoneInfo
    _TZ = ZoneInfo("Asia/Ho_Chi_Minh")

    rows = []
    base_time = pd.Timestamp("2026-01-15 00:00:00", tz="UTC").tz_convert(_TZ)

    # Pad 25 warmup candles (neutral, EMA settles)
    for i in range(25):
        t = base_time + pd.Timedelta(minutes=i)
        rows.append({"time": t, "open": 100.0, "high": 100.5, "low": 99.5, "close": 100.0})

    # Place SELL signal candles at signal_hour:signal_minute HCM
    signal_base = pd.Timestamp(f"2026-01-15 {signal_hour:02d}:{signal_minute:02d}:00", tz=_TZ)
    # C1 bearish: open=101, close=100.5
    rows.append({"time": signal_base, "open": 101.0, "high": 101.0, "low": 99.0, "close": 100.5})
    # C2 bearish: H2>H1, C2<L1(99.0), L2 well above EMA (~100)
    rows.append({"time": signal_base + pd.Timedelta(minutes=1), "open": 100.8, "high": 102.0, "low": 100.1, "close": 98.0})

    # Exit candle (hits TP direction doesn't matter here, just needs data)
    rows.append({"time": signal_base + pd.Timedelta(minutes=2), "open": 98.0, "high": 98.2, "low": 95.0, "close": 96.0})

    return pd.DataFrame(rows)


def test_feg_backtest_time_window_allows_signal():
    """Signal inside window → trade is taken."""
    from src.backtest import run_backtest
    df = _make_feg_df_with_time(signal_hour=10, signal_minute=0)
    results = run_backtest(
        df=df, symbol="XAUUSD", entry_type="pattern", ema_period=21,
        buffer_k=50.0, rr_ratio=2.0, max_candles=5,
        entry_start_time=_time(9, 0), entry_end_time=_time(11, 0),
    )
    assert results["total_trades"] >= 1


def test_feg_backtest_time_window_blocks_signal():
    """Signal outside window → no trade taken."""
    from src.backtest import run_backtest
    df = _make_feg_df_with_time(signal_hour=10, signal_minute=0)
    results = run_backtest(
        df=df, symbol="XAUUSD", entry_type="pattern", ema_period=21,
        buffer_k=50.0, rr_ratio=2.0, max_candles=5,
        entry_start_time=_time(14, 0), entry_end_time=_time(18, 0),
    )
    assert results["total_trades"] == 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_backtest_feg.py::test_feg_backtest_time_window_allows_signal tests/test_backtest_feg.py::test_feg_backtest_time_window_blocks_signal -v`
Expected: TypeError — `run_backtest()` got unexpected keyword argument `entry_start_time`

- [ ] **Step 3: Add import to `src/backtest.py`**

In `src/backtest.py`, change the import line from:
```python
from src.utils import get_pip_value, check_exit, compute_trade_levels
```
to:
```python
from src.utils import get_pip_value, check_exit, compute_trade_levels, _in_time_window
```

Also add `from datetime import time as _time` to the imports block (below `from datetime import datetime, timedelta`):
```python
from datetime import datetime, timedelta, time as _time
```

- [ ] **Step 4: Add params to `run_backtest()` signature**

In `src/backtest.py`, in the `run_backtest()` function signature (line ~253), add two new parameters at the end of the parameter list (before the closing `)`):

```python
def run_backtest(
    df: pd.DataFrame,
    symbol: str,
    entry_hour: int = 21,
    entry_minute: int = 5,
    sl_pips: float = 0,
    rr_ratio: float = 2.0,
    max_candles: int = 7,
    lot_mode: str = "fixed",
    fixed_lot: float = 0.01,
    risk_percent: float = 0.5,
    risk_amount: float = 0.0,
    risk_mode: str = "percent",
    buffer_k: float = 5.0,
    starting_equity: float = 1000.0,
    tp_type: str = "price_based",
    sl_type: str = "close_based",
    entry_mode: str = "close",
    entry_percent: float = 0.0,
    entry_type: str = "time",
    ema_period: int = 21,
    ema_distance_enabled: bool = False,
    ema_distance_pips: float = 0.0,
    entry_start_time: _time = _time(0, 0),
    entry_end_time: _time = _time(23, 59),
) -> dict:
```

- [ ] **Step 5: Pass new params to `_run_feg_backtest()` call inside `run_backtest()`**

Find the call to `_run_feg_backtest(...)` inside `run_backtest()` (around line 310). Replace it to pass the new params:

```python
    if entry_type == "pattern":
        result = _run_feg_backtest(
            df=df, symbol=symbol, rr_ratio=rr_ratio, max_candles=max_candles,
            lot_mode=lot_mode, fixed_lot=fixed_lot, risk_percent=risk_percent,
            risk_amount=risk_amount, risk_mode=risk_mode, buffer_k=buffer_k,
            starting_equity=starting_equity, tp_type=tp_type, sl_type=sl_type,
            entry_mode=entry_mode, entry_percent=entry_percent, ema_period=ema_period,
            ema_distance_enabled=ema_distance_enabled, ema_distance_pips=ema_distance_pips,
            entry_start_time=entry_start_time, entry_end_time=entry_end_time,
        )
        result["run_id"] = run_id
        return result
```

- [ ] **Step 6: Add time window gate in master candle path inside `run_backtest()`**

Find the master candle loop (around line ~338):
```python
    for idx, entry_row in entry_candles.iterrows():
        entry_time = entry_row['time']
```

Add a time window check right after `entry_time = entry_row['time']`:
```python
    for idx, entry_row in entry_candles.iterrows():
        entry_time = entry_row['time']
        if not _in_time_window(entry_time, entry_start_time, entry_end_time):
            continue
```

- [ ] **Step 7: Add params to `_run_feg_backtest()` signature**

Find the `_run_feg_backtest()` function definition (around line 389). Add two new params at end of parameter list:

```python
def _run_feg_backtest(
    df, symbol, rr_ratio, max_candles, lot_mode, fixed_lot, risk_percent,
    risk_amount, risk_mode, buffer_k, starting_equity, tp_type, sl_type,
    entry_mode, entry_percent, ema_period, ema_distance_enabled, ema_distance_pips,
    entry_start_time: _time = _time(0, 0),
    entry_end_time: _time = _time(23, 59),
):
```

- [ ] **Step 8: Add time window gate in `_run_feg_backtest()` while loop**

Inside `_run_feg_backtest()`, find the `while i < n:` loop (around line 408). Add the gate check as the first thing after getting the candle position (before building c1/c2):

```python
    while i < n:
        candle_time = df.at[i, "time"]
        if not _in_time_window(candle_time, entry_start_time, entry_end_time):
            i += 1
            continue
        c1 = {"open": df.at[i - 1, "open"], "high": df.at[i - 1, "high"],
              "low": df.at[i - 1, "low"], "close": df.at[i - 1, "close"]}
        # ... rest of existing code unchanged
```

- [ ] **Step 9: Run new tests to verify they pass**

Run: `pytest tests/test_backtest_feg.py -v`
Expected: all pass (including 2 new)

- [ ] **Step 10: Run full test suite**

Run: `pytest tests/ -v`
Expected: 35 passed (33 from Task 1 + 2 new)

- [ ] **Step 11: Commit**

```bash
git add src/backtest.py tests/test_backtest_feg.py
git commit -m "feat: add entry_start_time/entry_end_time filter to backtest engine"
```

---

### Task 3: Add time window params to `pages/5_Backtest.py`

**Files:**
- Modify: `pages/5_Backtest.py`

**Interfaces:**
- Consumes: `run_backtest(..., entry_start_time=time, entry_end_time=time)` (Task 2)
- No new test: UI testing only via browser

- [ ] **Step 1: Add import for `time` in `pages/5_Backtest.py`**

Find the existing imports block at top of file. `datetime` is already imported. Check if `time` is imported. If not, change the datetime import line from:
```python
from datetime import datetime, timedelta
```
to:
```python
from datetime import datetime, timedelta, time
```

- [ ] **Step 2: Add `st.time_input` widgets for entry window**

Find the "Entry Configuration" section (around line 242, `st.subheader("Entry")`). After the `st.divider()` that precedes this section, and before the `col1, col2 = st.columns(2)` for entry mode, insert the two time inputs as a new row:

```python
    # Time Window Filter
    st.subheader("Entry Time Window")
    tw_col1, tw_col2 = st.columns(2)
    with tw_col1:
        entry_start_time = st.time_input(
            "Entry Start Time (HCM)",
            value=time(0, 0),
            help="Only enter new positions at or after this time (default 00:00 = no filter)",
        )
    with tw_col2:
        entry_end_time = st.time_input(
            "Entry End Time (HCM)",
            value=time(23, 59),
            help="Only enter new positions at or before this time (default 23:59 = no filter)",
        )
    st.caption("Active trade continues holding if window ends. Window only gates new entries.")

    st.divider()
```

Place this block between the `st.divider()` around line 241 and the `st.subheader("Entry")` for entry mode. Specifically, add the subheader "Entry Time Window" as its own section before "Entry".

- [ ] **Step 3: Pass new params to `run_backtest()` call**

Find the `run_backtest(...)` call inside the `if st.button("Run Backtest"):` block (around line 425). Add the two new params:

```python
            results = run_backtest(
                df=df,
                symbol=symbol,
                entry_hour=entry_time.hour,
                entry_minute=entry_time.minute,
                sl_pips=sl_pips,
                rr_ratio=rr_ratio,
                max_candles=max_candles,
                lot_mode=lot_mode,
                fixed_lot=fixed_lot,
                risk_percent=risk_percent,
                risk_amount=risk_amount,
                risk_mode=risk_mode,
                buffer_k=buffer_k,
                starting_equity=starting_equity,
                tp_type=tp_type,
                sl_type=sl_type,
                entry_mode=entry_mode,
                entry_percent=entry_percent,
                entry_type=entry_type,
                ema_period=ema_period,
                ema_distance_enabled=ema_dist_enabled,
                ema_distance_pips=ema_dist_pips,
                entry_start_time=entry_start_time,
                entry_end_time=entry_end_time,
            )
```

- [ ] **Step 4: Save time params to `backtest_config`**

Find the `backtest_config = { ... }` dict (around line 451). Add two new keys:

```python
        backtest_config = {
            'timeframe': timeframe,
            'start_date': str(start_date),
            'end_date': str(end_date),
            'entry_time': entry_time.strftime('%H:%M'),
            'entry_start_time': entry_start_time.strftime('%H:%M'),
            'entry_end_time': entry_end_time.strftime('%H:%M'),
            'entry_mode': entry_mode,
            # ... rest unchanged
        }
```

- [ ] **Step 5: Commit**

```bash
git add pages/5_Backtest.py
git commit -m "feat: add entry time window inputs to Backtest UI"
```

---

### Task 4: Redesign `HISTORY_COLUMNS` and `history_to_dataframe()` in `src/backtest_history.py`

**Files:**
- Modify: `src/backtest_history.py`

**Interfaces:**
- Produces: `HISTORY_COLUMNS['core']` = `['Date Range', 'Start Time', 'End Time', 'Trades', 'Win Rate %', 'Total Pips', 'Total USD', 'Lot Mode', 'RR Ratio']`
- Produces: `history_to_dataframe()` now includes `'Start Time'` and `'End Time'` columns from `config.get('entry_start_time', '00:00')` / `config.get('entry_end_time', '23:59')`

- [ ] **Step 1: Update `HISTORY_COLUMNS` in `src/backtest_history.py`**

Find the `HISTORY_COLUMNS` dict (around line 216). Replace it entirely:

```python
HISTORY_COLUMNS = {
    # Always shown (core) — in this exact order
    'core': [
        'Date Range',
        'Start Time',
        'End Time',
        'Trades',
        'Win Rate %',
        'Total Pips',
        'Total USD',
        'Lot Mode',
        'RR Ratio',
    ],

    # Config columns (optional, shown/hidden via multiselect)
    'config': [
        'Strategy', 'Symbol', 'Timeframe',
        'Entry Time', 'Entry Type', 'EMA Period', 'EMA Dist',
        'Entry Mode', 'Entry %', 'Max Candles', 'Buffer K',
        'TP Type', 'SL Type', 'Fixed Lot', 'Start Equity',
        'Risk Mode', 'Risk %', 'Risk $',
    ],

    # Summary columns (optional)
    'summary': [
        'Wins', 'Losses', 'Avg Pips', 'Best', 'Worst',
        'Max Wins', 'Max Losses', 'TP Exits', 'SL Exits', 'Time Exits',
        'Final Equity',
    ],

    # Default optional columns to show in multiselect
    'default_optional': ['Strategy', 'Symbol', 'Timeframe', 'Entry Type'],
}
```

- [ ] **Step 2: Add `'Start Time'` and `'End Time'` to `history_to_dataframe()`**

Find `history_to_dataframe()` (around line 149). In the `row = { ... }` dict, find where `'Date Range'` is built (around line 172) and add `'Start Time'` and `'End Time'` right after it:

```python
            # Config - Basic
            'Timeframe': config.get('timeframe', ''),
            'Entry Time': config.get('entry_time', ''),
            'Lot Mode': config.get('lot_mode', ''),
            'RR Ratio': config.get('rr_ratio', ''),

            # Config - Optional
            'Date Range': f"{config.get('start_date', '')} ~ {config.get('end_date', '')}",
            'Start Time': config.get('entry_start_time', '00:00'),
            'End Time': config.get('entry_end_time', '23:59'),
```

- [ ] **Step 3: Move `'Total USD'`, `'Lot Mode'`, `'RR Ratio'` to core output position**

The columns `'Total USD'`, `'Lot Mode'`, `'RR Ratio'` are already populated in the `row` dict — they just need to be listed in `HISTORY_COLUMNS['core']`. The `history_to_dataframe()` function already populates them:
- `'Lot Mode'` → `config.get('lot_mode', '')` ✓ (already in row under 'Config - Basic')
- `'RR Ratio'` → `config.get('rr_ratio', '')` ✓ (already in row under 'Config - Basic')
- `'Total USD'` → `summary.get('total_pnl_usd', 0)` ✓ (already in row under 'Summary - Optional')

No change needed to row dict for these — `HISTORY_COLUMNS['core']` listing them is sufficient. The UI builds display order from the column list.

Also remove `'Lot Mode'` and `'RR Ratio'` from `HISTORY_COLUMNS['config']` since they are now in `'core'`. And remove `'Total USD'` from `HISTORY_COLUMNS['summary']` since it's now in `'core'`. The updated `HISTORY_COLUMNS` in Step 1 already does this.

- [ ] **Step 4: Commit**

```bash
git add src/backtest_history.py
git commit -m "feat: redesign HISTORY_COLUMNS with new core order + Start/End Time columns"
```

---

### Task 5: Update Backtest History display in `pages/5_Backtest.py`

**Files:**
- Modify: `pages/5_Backtest.py` (history section only)

**Interfaces:**
- Consumes: updated `HISTORY_COLUMNS` from Task 4

- [ ] **Step 1: Find `show_history_section()` function**

Read `pages/5_Backtest.py` from line ~700 onwards to locate `show_history_section()` and find where `HISTORY_COLUMNS` is used to build the multiselect and column display.

- [ ] **Step 2: Update column display logic**

Find the code in `show_history_section()` that builds `display_cols`. It currently assembles `core` columns + user-selected optional columns. The core set already drives what's always shown. The update needed is:

Ensure the DataFrame column order in the display matches `HISTORY_COLUMNS['core']` first, then optional. Look for where `display_df = history_df[display_cols]` or similar is assembled. The current code assembles columns in `core + selected_optional`. Since `HISTORY_COLUMNS['core']` is now updated (Task 4), and `history_to_dataframe()` now emits `'Start Time'` and `'End Time'`, no logic change needed — just verify columns exist in the df.

If `'Start Time'` / `'End Time'` are in `HISTORY_COLUMNS['core']` but missing from the dataframe (old records), `history_to_dataframe()` will already supply `'00:00'`/`'23:59'` defaults via `config.get(..., default)`. No extra guard needed.

- [ ] **Step 3: Check and update `default_optional` multiselect**

Find where the multiselect for optional columns is defined. Ensure `default_optional` values (`['Strategy', 'Symbol', 'Timeframe', 'Entry Type']`) are still valid column names in `history_to_dataframe()`. They are — no change needed.

Also ensure `'Lot Mode'` and `'RR Ratio'` are NOT in the multiselect options anymore (they moved to core). Since `HISTORY_COLUMNS['config']` no longer contains them, they'll be absent from the multiselect automatically.

- [ ] **Step 4: Run the Streamlit app to verify (manual)**

```bash
streamlit run app.py
```

Navigate to Backtest page → Backtest History section. Verify:
- Default visible columns: Date Range, Start Time, End Time, Trades, Win Rate %, Total Pips, Total USD, Lot Mode, RR Ratio
- Optional multiselect shows: Strategy, Symbol, Timeframe, Entry Type (pre-selected) + others
- Old history records show '00:00'/'23:59' in Start Time/End Time

- [ ] **Step 5: Commit**

```bash
git add pages/5_Backtest.py
git commit -m "feat: update history display for new HISTORY_COLUMNS core order"
```

---

### Task 6: Add time window to live bot (`src/bot_runner.py` + `src/bot_manager.py`)

**Files:**
- Modify: `src/bot_runner.py`
- Modify: `src/bot_manager.py`

**Interfaces:**
- Consumes: `_in_time_window(ts, start, end) -> bool` from `src/utils` (Task 1)
- Produces: `--entry_start_time HH:MM` and `--entry_end_time HH:MM` argparse args
- Produces: `build_bot_command(..., entry_start_time='00:00', entry_end_time='23:59')` updated signature

- [ ] **Step 1: Add argparse args to `get_args()` in `src/bot_runner.py`**

Find `get_args()` function (around line 26). Add two new args at end (before `return parser.parse_args()`):

```python
    parser.add_argument('--entry_start_time', type=str, default='00:00',
                        help='Entry window start HH:MM (Asia/Ho_Chi_Minh). Default 00:00 = no filter.')
    parser.add_argument('--entry_end_time', type=str, default='23:59',
                        help='Entry window end HH:MM (Asia/Ho_Chi_Minh). Default 23:59 = no filter.')
```

- [ ] **Step 2: Import `_in_time_window` and `time` in `src/bot_runner.py`**

Find the imports at the top of `src/bot_runner.py`. Add:

```python
from datetime import datetime, time as _time
```

(change existing `from datetime import datetime` if present, or add separately)

Also add the import of `_in_time_window` — but since `src/bot_runner.py` does `sys.path.insert` and then imports from `src.*`, add:

```python
from src.utils import _in_time_window
```

Place this near the bottom of the top-level imports (after `load_dotenv()`), because `src.*` imports at module level before `sys.path.insert` would fail. Actually `sys.path.insert` is done at module top, so it's fine — add `from src.utils import _in_time_window` to the top-level import block near line 20.

- [ ] **Step 3: Parse time args in `run_bot()` and pass to `run_feg_bot()`**

Find `run_bot()` function (around line 184). After the strategy/params loading, add:

```python
    # Parse time window args
    from datetime import datetime as _dt
    entry_start = _dt.strptime(args.entry_start_time, '%H:%M').time()
    entry_end   = _dt.strptime(args.entry_end_time,   '%H:%M').time()
```

Then update the `run_feg_bot(...)` call in `run_bot()` to pass new params:

```python
        run_feg_bot(args, strategy, params, credentials,
                    entry_start_time=entry_start, entry_end_time=entry_end)
```

- [ ] **Step 4: Add time window params to `run_feg_bot()` signature**

Find `run_feg_bot(args, strategy, params, credentials)` (around line 468). Update signature:

```python
def run_feg_bot(args, strategy, params, credentials,
                entry_start_time: _time = _time(0, 0),
                entry_end_time: _time = _time(23, 59)):
```

- [ ] **Step 5: Add time gate in `run_feg_bot()` entry decision**

Inside `run_feg_bot()`, find the block `if active_trade is None and is_new_candle:` (around line 534). Add the time window check inside this block, wrapping the `feg_entry_decision` call:

```python
            if active_trade is None and is_new_candle:
                now_hcm = datetime.now(TIMEZONE)
                if _in_time_window(now_hcm, entry_start_time, entry_end_time):
                    c1 = {"open": prev["open"], "high": prev["high"], "low": prev["low"], "close": prev["close"]}
                    c2 = {"open": last["open"], "high": last["high"], "low": last["low"], "close": last["close"]}
                    signal = feg_entry_decision(
                        None, c1, c2, ema[-1], args.symbol,
                        rr_ratio, buffer_k, lot_size, entry_mode, entry_percent,
                        ema_dist_enabled, ema_dist_pips,
                    )
                    # ... rest of signal handling unchanged
                # else: outside window, skip entry (active_trade continues if held)
```

- [ ] **Step 6: Add time gate in master candle bot path (`run_bot()` for `entry_type == 'time'`)**

In `run_bot()`, find the master candle entry check (around line 258):
```python
            if check_entry_time(entry_time) and last_entry_date != now.date():
```

Update to also check the time window:
```python
            if check_entry_time(entry_time) and last_entry_date != now.date() and _in_time_window(datetime.now(TIMEZONE), entry_start, entry_end):
```

- [ ] **Step 7: Update `build_bot_command()` in `src/bot_manager.py`**

Find `build_bot_command()` (around line 70). Add two new parameters with defaults:

```python
def build_bot_command(
    python_exe, script_path, strategy, symbol, user, test, interval,
    lot_size=None, sl_pips=None, rr_ratio=None, max_candles=None,
    ema_period=None, ema_distance_enabled=False, ema_distance_pips=0.0,
    entry_mode=None, entry_percent=None, tp_type=None, sl_type=None,
    buffer_k=None, lot_mode=None, risk_mode=None, risk_percent=None, risk_amount=None,
    entry_start_time='00:00', entry_end_time='23:59',
):
```

Add the two args to the `cmd` list in `build_bot_command()`. Find where the base cmd is built and always-appended args are added. After `--ema_distance_pips` append, add:

```python
    cmd.extend(["--entry_start_time", str(entry_start_time)])
    cmd.extend(["--entry_end_time", str(entry_end_time)])
```

- [ ] **Step 8: Update `start_bot()` in `src/bot_manager.py`**

Find `start_bot()` function (around line 119). Add two new params:

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
    entry_mode: str = None,
    entry_percent: float = None,
    tp_type: str = None,
    sl_type: str = None,
    buffer_k: float = None,
    lot_mode: str = None,
    risk_mode: str = None,
    risk_percent: float = None,
    risk_amount: float = None,
    entry_start_time: str = '00:00',
    entry_end_time: str = '23:59',
) -> tuple:
```

Update the `build_bot_command(...)` call inside `start_bot()` to pass the new params:

```python
    cmd = build_bot_command(
        python_exe, script_path, strategy, symbol, user, test, interval,
        lot_size, sl_pips, rr_ratio, max_candles,
        ema_period, ema_distance_enabled, ema_distance_pips,
        entry_mode, entry_percent, tp_type, sl_type,
        buffer_k, lot_mode, risk_mode, risk_percent, risk_amount,
        entry_start_time, entry_end_time,
    )
```

- [ ] **Step 9: Run full test suite**

Run: `pytest tests/ -v`
Expected: 35 passed (no regressions — bot_manager tests use default args)

- [ ] **Step 10: Commit**

```bash
git add src/bot_runner.py src/bot_manager.py
git commit -m "feat: add entry time window filter to live bot (FEG + Master Candle)"
```

---

### Task 7: Add time window UI to Bot start form (`pages/1_Bots.py`)

**Files:**
- Modify: `pages/1_Bots.py`

**Interfaces:**
- Consumes: `start_bot(..., entry_start_time='HH:MM', entry_end_time='HH:MM')` (Task 6)

- [ ] **Step 1: Add `time` import to `pages/1_Bots.py`**

Find the imports block. Add:
```python
from datetime import time
```

- [ ] **Step 2: Add time window `st.time_input` widgets in `show_create_bot()`**

In `show_create_bot()` function (around line 172), find the `st.divider()` before the **Entry** section (around line 265). Insert a new "Entry Time Window" section between the EMA Filter divider and Entry section:

```python
    st.divider()

    # --- Entry Time Window ---
    st.subheader("Entry Time Window")
    tw1, tw2 = st.columns(2)
    with tw1:
        entry_start_time = st.time_input(
            "Entry Start Time (HCM)",
            value=time(0, 0),
            help="Only enter new positions at or after this time. Default 00:00 = no filter.",
            key=f"{sk}_tw_start",
        )
    with tw2:
        entry_end_time = st.time_input(
            "Entry End Time (HCM)",
            value=time(23, 59),
            help="Only enter new positions at or before this time. Default 23:59 = no filter.",
            key=f"{sk}_tw_end",
        )
    st.caption("Active trade continues if time window ends. Window only gates new entries.")
```

- [ ] **Step 3: Pass time window to `start_bot()` call**

Find where `start_bot(...)` is called in `show_create_bot()`. Pass the new params as strings:

```python
        success, msg, bot_info = start_bot(
            strategy=selected_strategy,
            symbol=symbol,
            user=username,
            test=test_mode,
            # ... existing params ...
            entry_start_time=entry_start_time.strftime('%H:%M'),
            entry_end_time=entry_end_time.strftime('%H:%M'),
        )
```

- [ ] **Step 4: Commit**

```bash
git add pages/1_Bots.py
git commit -m "feat: add entry time window inputs to Bot start form"
```

---

### Task 8: Final verification

**Files:**
- No file changes — run + verify only

- [ ] **Step 1: Run full test suite one final time**

Run: `pytest tests/ -v`
Expected: 35 passed, 0 failed

- [ ] **Step 2: Start Streamlit app and verify Backtest page**

Run: `streamlit run app.py`

Check Backtest page:
- [ ] "Entry Time Window" section visible with 2 time inputs (default 00:00 / 23:59)
- [ ] Run backtest with default window → same results as before
- [ ] Run backtest with narrow window (e.g. 10:00–11:00) → fewer or 0 trades depending on strategy

- [ ] **Step 3: Verify Backtest History columns**

In Backtest History section:
- [ ] Default columns visible: Date Range, Start Time, End Time, Trades, Win Rate %, Total Pips, Total USD, Lot Mode, RR Ratio (in this order)
- [ ] Old history records show '00:00'/'23:59' in Start Time/End Time
- [ ] Multiselect shows optional columns (Strategy, Symbol, Timeframe, Entry Type pre-selected)
- [ ] Lot Mode and RR Ratio NOT in multiselect (they're in core now)

- [ ] **Step 4: Verify Bot form**

In Bots → Create Bot:
- [ ] "Entry Time Window" section visible with 2 time inputs
- [ ] Starting a bot passes `--entry_start_time 00:00 --entry_end_time 23:59` in command

- [ ] **Step 5: Final commit if any cleanup needed, else done**

```bash
git add .
git commit -m "chore: final cleanup time window filter feature"
```

---

## Implementation Notes

**`_in_time_window` candle time format:** In `_run_feg_backtest`, `df.at[i, "time"]` is a `pd.Timestamp` with `Asia/Ho_Chi_Minh` tzinfo (set in `fetch_historical_data`). In live bot, `datetime.now(TIMEZONE)` is already HCM. Both are compatible with `.astimezone(_TZ_HCM)` inside `_in_time_window`.

**`now_hcm` in live bot:** `datetime.now(TIMEZONE)` already returns HCM-localized datetime. `_in_time_window` will call `.astimezone(HCM)` which is a no-op when already in HCM — safe.

**Candle time in master candle bot:** `check_entry_time(entry_time)` already uses `datetime.now(TIMEZONE)`. The time window check uses the same `datetime.now(TIMEZONE)` — consistent.

**Old history records:** Records saved before this feature have no `entry_start_time`/`entry_end_time` in `config`. `config.get('entry_start_time', '00:00')` returns the default safely — no migration needed.

**`HISTORY_COLUMNS['core']` contains `'Total USD'`, `'Lot Mode'`, `'RR Ratio'`:** These keys must exist in the dataframe produced by `history_to_dataframe()`. Check: `'Total USD'` → `summary.get('total_pnl_usd', 0)` ✓; `'Lot Mode'` → `config.get('lot_mode', '')` ✓; `'RR Ratio'` → `config.get('rr_ratio', '')` ✓. All are already in the row dict — just moved from optional to core display.
