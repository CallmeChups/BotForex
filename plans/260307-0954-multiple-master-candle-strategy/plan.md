# Multiple Master Candle Strategy — Implementation Plan

**Date:** 2026-03-07
**Branch:** dev
**Status:** Draft

## Summary

Clone Master Candle Strategy into a new "Multiple Master Candle Strategy" — scans a time window for multiple qualifying candles instead of a single entry time. All trade logic (SL/TP/entry mode/breakeven/etc.) identical.

### New Parameters (vs Master Candle)

| Param | Type | Example | Description |
|-------|------|---------|-------------|
| `window_start` | `HH:MM` | `09:00` | Start of scanning window |
| `window_end` | `HH:MM` | `11:00` | End of scanning window |
| `priority_direction` | `BUY`/`SELL`/`auto` | `BUY` | Only candles matching this direction become master candles. `auto` = first candle decides |

### Architecture Decision: Separate Files

User requirement: **"clone ra hoàn toàn, kẻo đụng tới strategy cũ"**

- `bot_runner.py` → **UNTOUCHED** (single-trade, single-entry-time)
- `bot_runner_multi.py` → **NEW** (multi-trade, time-window)
- `backtest.py` → **UNTOUCHED**
- `backtest_multi.py` → **NEW** (multi-trade backtest)
- `bot_manager.py` picks runner script based on strategy type

---

## Phase 1: Strategy Config & Data Layer

### 1.1 — `strategies/multiple_master_candle.yaml`

New YAML file. Identical to `master_candle.yaml` except entry section uses window:

```yaml
id: multiple_master_candle
name: Multiple Master Candle Strategy
entry:
  timeframe: M5
  window_start: "09:00"
  window_end: "11:00"
  priority_direction: auto    # BUY / SELL / auto
  timezone: Asia/Ho_Chi_Minh
  rules:
    match: "candle direction == priority -> ENTER"
    skip: "candle direction != priority -> SKIP"
exit:
  tp: { type: price_based }
  sl: { type: close_based }
  time_limit: { max_candles: 7 }
parameters:
  rr_ratio: 2.0
  lot_size: 0.01
symbols: [XAUUSD, BTCUSDm, ETHUSDm, ...]
```

### 1.2 — `src/strategy_manager.py` — extract new params

Update `get_strategy_parameters()` to also return:
- `window_start` (from `entry.window_start`, default None)
- `window_end` (from `entry.window_end`, default None)
- `priority_direction` (from `entry.priority_direction`, default None)
- Keep returning `entry_time` for backward compatibility (None if window-based)

Detection: if `window_start` is set → multi-candle strategy.

---

## Phase 2: Bot Runner (Multi)

### 2.1 — `src/bot_runner_multi.py` — NEW FILE

Cloned from `bot_runner.py` with these changes:

**New CLI args:**
- `--window_start` (HH:MM)
- `--window_end` (HH:MM)
- `--priority_direction` (BUY/SELL/auto)

**Main loop redesign:**

```
State:
  active_trades = []        # Multiple concurrent trades
  priority_locked = None    # For auto mode
  last_checked_candle = None
  window_done = False

Loop:
  1. If within window AND new candle closed:
     a. Get candle OHLC
     b. Determine direction (C>O → BUY, C<O → SELL)
     c. If auto mode & not locked → lock priority to this direction
     d. If direction matches priority:
        - Calculate entry/SL/TP (same formulas as master_candle)
        - Calculate lot size (flex: use current MT5 equity)
        - Place order (LIMIT or MARKET, same logic as bot_runner)
        - Append to active_trades[]
     e. If direction doesn't match → skip

  2. Monitor ALL active_trades:
     For each trade in active_trades:
       - LIVE pending check (fill/expire/cancel)
       - Breakeven trigger
       - TP/SL/TIME exit check
       - If exited → log, notify, record, remove from list

  3. Exit condition:
     Window ended AND active_trades is empty → bot stops
```

**What's shared with bot_runner.py (copy, not import):**
- `setup_logging()`, `log()`, `send_telegram()`, `send_telegram_async()`
- `get_mt5_connection()`, `get_current_candle()`
- `check_entry_time()` → replaced with `is_within_window()`
- Order placement logic (place_order, place_pending_order calls)
- Breakeven logic
- Exit detection via `check_exit()`

**What's different:**
- `active_trades[]` list instead of single `active_trade`
- Window-based entry detection instead of single time
- Priority direction filtering
- Auto-priority detection from first candle
- Bot doesn't exit after one trade closes — continues until window ends
- Multiple concurrent LIVE positions tracked

### 2.2 — `src/bot_manager.py` — pick runner script

```python
BOT_SCRIPT = "src/bot_runner.py"
BOT_SCRIPT_MULTI = "src/bot_runner_multi.py"
```

In `start_bot()`:
- Accept new params: `window_start`, `window_end`, `priority_direction`
- If `window_start` is set → use `BOT_SCRIPT_MULTI`
- Else → use `BOT_SCRIPT` (unchanged)
- Pass new args to CLI: `--window_start`, `--window_end`, `--priority_direction`

In `restart_bot()`:
- Read `window_start` from saved bot info to pick correct script

---

## Phase 3: Backtest (Multi)

### 3.1 — `src/backtest_multi.py` — NEW FILE

New function `run_backtest_multi()`:

```python
def run_backtest_multi(
    df, symbol,
    window_start_hour, window_start_minute,
    window_end_hour, window_end_minute,
    priority_direction="auto",
    # ... all other params same as run_backtest
) -> dict:
```

**Logic:**

```
For each day in data:
  1. Find all candles within [window_start, window_end]
  2. Determine priority:
     - manual (BUY/SELL) → use as-is
     - auto → first candle's direction
  3. Filter candles matching priority direction
  4. For each qualifying candle (= master candle):
     a. Calculate entry/SL/TP (same formulas)
     b. Run LIMIT fill logic on subsequent candles (same as backtest.py)
     c. Run exit monitoring from next candle after fill
     d. Record trade result
  5. All trades independent (no interaction between them)
```

**Equity tracking for flex mode:**
- Trades within same day share equity
- Each trade calculates lot from current equity at fill time
- Equity updates as trades close (chronological order matters)

Returns same stats format as `run_backtest()` for UI compatibility.

---

## Phase 4: UI Integration

### 4.1 — `pages/1_Bots.py` — Create Bot form

When user selects "Multiple Master Candle Strategy":
- **Hide** single `entry_time` field
- **Show** `window_start` (HH:MM input)
- **Show** `window_end` (HH:MM input)
- **Show** `priority_direction` (selectbox: BUY / SELL / auto)
- All other params remain identical

Detection: `params.get('window_start') is not None` → show window fields.

**Running bots display:** Show window_start/end + priority instead of entry_time.

### 4.2 — `pages/5_Backtest.py` — Backtest config

Same conditional UI as Bots page:
- If multi strategy → show window fields, call `run_backtest_multi()`
- Else → existing flow unchanged

**Batch mode:** For multi strategy, batch = multiple window configs (or just one window per run).

### 4.3 — `src/i18n.py` — Translation keys

```python
"window_start":         {"en": "Window Start",        "vi": "Giờ bắt đầu"},
"window_end":           {"en": "Window End",          "vi": "Giờ kết thúc"},
"priority_direction":   {"en": "Priority Direction",  "vi": "Hướng ưu tiên"},
"priority_auto":        {"en": "Auto (first candle)", "vi": "Tự động (nến đầu tiên)"},
```

---

## Phase 5: Config History & Presets

### 5.1 — `src/bot_config_history.py`

Add `window_start`, `window_end`, `priority_direction` to saved config fields.

### 5.2 — `pages/1_Bots.py` — Preset mapping

Add new fields to `_apply_preset_to_session()` mapping.

---

## File Change Summary

| File | Action | Risk |
|------|--------|------|
| `strategies/multiple_master_candle.yaml` | CREATE | None |
| `src/bot_runner_multi.py` | CREATE (clone+modify) | None — new file |
| `src/backtest_multi.py` | CREATE | None — new file |
| `src/strategy_manager.py` | EDIT — add 3 fields to `get_strategy_parameters()` | Low — additive only |
| `src/bot_manager.py` | EDIT — add params + script selection | Low — additive |
| `pages/1_Bots.py` | EDIT — conditional UI for window params | Medium — UI changes |
| `pages/5_Backtest.py` | EDIT — conditional UI + call backtest_multi | Medium — UI changes |
| `src/i18n.py` | EDIT — add ~6 keys | None |
| `src/bot_config_history.py` | EDIT — add 3 fields | None |
| `src/bot_runner.py` | **UNTOUCHED** | **Zero** |
| `src/backtest.py` | **UNTOUCHED** | **Zero** |

## Execution Order

1. Phase 1 (config + strategy_manager) — foundation
2. Phase 3 (backtest_multi) — can test immediately with UI
3. Phase 2 (bot_runner_multi + bot_manager) — live trading
4. Phase 4 (UI integration) — ties everything together
5. Phase 5 (presets) — polish

## Unresolved Questions

None — all requirements confirmed by user.
