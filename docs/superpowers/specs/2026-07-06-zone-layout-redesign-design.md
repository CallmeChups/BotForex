# Zone Layout Redesign — Bots & Backtest Forms

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Reorganize all strategy param forms (pages/1_Bots.py + pages/5_Backtest.py) into 5 clearly named zones using `st.expander`, replacing the current ad-hoc multi-row grid + partial-expander structure.

**Architecture:** Each zone is an `st.expander`. Compact layout uses multi-column grids inside each expander. Non-compact uses stack-dọc with sub-headers. Both layouts share the same 5-zone structure and session state keys (no key renames).

**Tech Stack:** Python, Streamlit, PyYAML. No backend changes — UI only.

## Global Constraints

- Zone names (exact): `General`, `Entry`, `Order Settings`, `Risk & Sizing`, `Exit`
- `General` and `Entry` default `expanded=True`; remaining 3 default `expanded=False`
- All existing session state keys (`{sk}_*`) must remain unchanged — only widget render positions change
- No logic changes: all conditional visibility rules preserved as-is
- Master Candle strategy: no `Entry` zone (no pattern params)
- Apply to BOTH `pages/1_Bots.py` AND `pages/5_Backtest.py`
- Apply to BOTH compact and non-compact layouts within each page

---

## Zone Definitions

### Zone 1 — General (expanded=True)

| Param | Bots | Backtest | Notes |
|---|---|---|---|
| Symbol + Custom checkbox | ✅ | ✅ | |
| Timeframe | ✅ | ✅ | |
| Test Mode | ✅ | ❌ | Bots only |
| RR Ratio | ✅ | ✅ | |
| Max Candles + toggle | ✅ | ✅ | |
| Interval (s) | ✅ | ❌ | Bots only |
| Start Date / End Date | ❌ | ✅ | Backtest only |

**Compact layout:** single row, 6 cols (Bots) / 6 cols (Backtest).
**Non-compact layout:** 2 rows of 3 cols each.

---

### Zone 2 — Entry (expanded=True)

Only shown for FEG EMA21 and FEG Stop Order. Hidden entirely for Master Candle.

#### Sub-section: FEG Margins
| Param | Bots | Backtest | Notes |
|---|---|---|---|
| EMA Period | ✅ | ✅ | |
| H2 Exceed Pips | ✅ | ✅ | |
| C2 Gap Pips | ✅ | ✅ | |
| EMA Margin Pips | ✅ | ✅ | |
| C2 Wick Filter (checkbox) | ✅ | ✅ | |
| Wick Max % of Body | ✅ | ✅ | disabled when filter=False |

#### Sub-section: EMA Direction
| Param | Bots | Backtest | Notes |
|---|---|---|---|
| EMA Filter (checkbox) | ✅ | ✅ | |
| BUY EMA side | ✅ | ✅ | visible only when EMA Filter=True |
| SELL EMA side | ✅ | ✅ | visible only when EMA Filter=True |

#### Sub-section: Time Window
| Param | Bots | Backtest | Notes |
|---|---|---|---|
| Entry Start Time (HCM) | ✅ | ✅ | |
| Entry End Time (HCM) | ✅ | ✅ | |

#### Sub-section: Entry Mode
| Param | Bots | Backtest | Notes |
|---|---|---|---|
| Entry Mode (close / range_percent) | ✅ | ✅ | FEG EMA21 only |
| Entry % | ✅ | ✅ | visible only when Entry Mode=range_percent |
| Limit Order Candles | ✅ | ✅ | FEG Stop Order only |

**Compact layout:** Row 1 = FEG Margins (6 cols). Row 2 = EMA Direction + Entry Mode (6 cols). Row 3 = Time Window (2 cols).
**Non-compact layout:** Sub-headers (`st.caption` or `st.markdown`) separate the 4 sub-sections, stacked vertically.

---

### Zone 3 — Order Settings (expanded=False)

| Param | Bots | Backtest | Notes |
|---|---|---|---|
| Buffer K (pips) | ✅ | ✅ | |
| Re-Entry After SL | ✅ | ✅ | |

**Compact layout:** 2 cols.
**Non-compact layout:** 2 cols.

---

### Zone 4 — Risk & Sizing (expanded=False)

| Param | Bots | Backtest | Notes |
|---|---|---|---|
| Lot Mode (fixed / flex) | ✅ | ✅ | |
| Lot Size (fixed_lot) | ✅ | ✅ | when Lot Mode=fixed |
| Risk Mode (percent / fixed_amount) | ✅ | ✅ | when Lot Mode=flex |
| Risk % | ✅ | ✅ | when Risk Mode=percent |
| Risk $ | ✅ | ✅ | when Risk Mode=fixed_amount |
| Starting Equity | ❌ | ✅ | Backtest only, when Lot Mode=flex |

**Compact layout:** Lot Mode radio + conditional fields in 3 cols.
**Non-compact layout:** Lot Mode radio full width, then conditional fields in 2–3 cols.

---

### Zone 5 — Exit (expanded=False)

| Param | Bots | Backtest | Notes |
|---|---|---|---|
| TP Type (price_based / close_based) | ✅ | ✅ | |
| SL Type (price_based / close_based) | ✅ | ✅ | |
| BE Enabled (checkbox) | ✅ | ✅ | |
| BE Trigger R | ✅ | ✅ | disabled when BE=False |

**Compact layout:** 4 cols (TP Type, SL Type, BE, BE Trigger R).
**Non-compact layout:** Row 1 = TP Type + SL Type (2 cols). Row 2 = BE + BE Trigger R (2 cols).

---

## Behavior Rules (preserved from current code)

- `Entry %` visible only when `Entry Mode = range_percent`
- `BUY/SELL EMA side` visible only when `EMA Filter = True`
- `Wick Max %` disabled when `C2 Wick Filter = False`
- `BE Trigger R` disabled when `BE Enabled = False`
- `Risk %` / `Risk $` conditional on `Risk Mode`
- `Starting Equity` only in Backtest, only when `Lot Mode = flex`
- Entire `Entry` zone hidden when strategy = Master Candle
- `Limit Order Candles` only in Entry zone when strategy = FEG Stop Order
- `Entry Mode` + `Entry %` only when strategy = FEG EMA21
- `Test Mode`, `Interval` only in Bots form
- `Start Date`, `End Date`, `Starting Equity` only in Backtest form

---

## What Does NOT Change

- Session state keys: all `{sk}_*` keys remain identical
- Widget types: same `st.checkbox`, `st.number_input`, `st.radio`, `st.selectbox`, `st.time_input`
- Backend calls: `start_bot(...)` and `run_backtest(...)` signatures unchanged
- Strategy YAML files: unchanged
- Any file outside `pages/1_Bots.py` and `pages/5_Backtest.py`
