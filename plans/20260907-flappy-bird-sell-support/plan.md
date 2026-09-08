---
title: "Flappy Bird mirrored SELL support"
description: "Extend the existing Flappy Bird BUY LIMIT flow to detect, backtest, display, and trade the mirrored SELL LIMIT setup."
status: pending
priority: P2
effort: 6h
branch: main
tags: [feature, backend, frontend, testing]
created: 2026-09-07
---

# Flappy Bird mirrored SELL support

## Overview

Add SELL support without creating a second strategy: the existing `flappy_bird` strategy should emit either BUY LIMIT or SELL LIMIT signals from mirrored candle/EMA conditions. Preserve current BUY behavior and public function compatibility.

## Findings / current flow

- **Config:** `strategies/flappy_bird.yaml` is the single strategy definition; `src/strategy_manager.py::list_strategies`, `get_strategy`, and `get_strategy_parameters` discover/read it. YAML currently names the strategy “Flappy Bird BUY”, documents bullish-only rules, and uses magic `212400`.
- **Core:** `src/flappy_bird_strategy.py`
  - `diagnose_flappy_bird()` hard-codes bullish EMA order, mother-high coverage, father upper-wick, EMA filters, and close-above-children.
  - `detect_flappy_bird_signal()` and `analyze_flappy_bird()` are BUY-only; `analyze_flappy_bird()` calculates BUY LIMIT entry, low-based SL, and upward TP.
- **Backtest:** `src/backtest.py::run_backtest()` dispatches `strategy == "flappy_bird"` to `_run_flappy_bird_backtest()`. The helper scans EMA13/21/55, calls `analyze_flappy_bird`, fills only when `low <= entry`, checks BUY SL before TP, records `"BUY"`, and stores `_mother/_children/_father/_ema*` debug fields.
- **Live runner:** `src/bot_runner.py::run_feg_bot()` dispatches Flappy into the generic FEG loop. The Flappy scan calls `analyze_flappy_bird`; pending orders already use generic `place_limit_order()` and direction-based MT5 `BUY_LIMIT`/`SELL_LIMIT`. Exit handling has a Flappy-specific BUY-only branch and otherwise uses `check_exit()`.
- **Order layer:** `src/orders.py::place_limit_order()` already maps direction to `ORDER_TYPE_BUY_LIMIT` or `ORDER_TYPE_SELL_LIMIT`; no new MT5 primitive is needed.
- **Backtest UI:** `pages/5_Backtest.py` has explicit `is_flappy_bird` branches, fixed 7-candle expiry and price-based exits, Flappy help text, and `show_flappy_debug()` which calls `diagnose_flappy_bird(..., include_checks=True)` and hard-codes “upper wick”.
- **Bot UI:** `pages/1_Bots.py` has no Flappy-specific branch; it discovers YAML generically, passes all common parameters through `start_bot()` → `build_bot_command()` → CLI. It will expose the new behavior automatically, but its generic labels/help must not imply BUY-only behavior.
- **Tests:** `tests/test_flappy_bird_strategy.py` covers BUY signal/levels, rejection boundaries, and BUY backtest fill/SL precedence. No Flappy live-runner test exists. Existing order tests cover direction-based order selection. `tests/test_strategy_manager_feg.py` does not cover Flappy YAML.
- **Docs:** `README.md` and `docs/codebase-guide-vi.md` contain BUY-only descriptions. `docs/development-rules.md` requested by the planning instructions is absent; use existing `docs/code-standards.md` and current project conventions, and flag this gap.

## Recommended design

### 1. Generalize the core, retain compatibility

Prefer one direction-aware implementation rather than duplicating BUY/SELL functions:

- Add a `direction` argument (default `"BUY"`) to diagnosis/detection/analysis, or introduce internal direction-aware helpers and keep current BUY signatures as wrappers.
- Keep current default behavior and output keys unchanged for existing callers/tests.
- Return `direction` and `order_type` as `"SELL"` / `"SELL_LIMIT"` for the mirrored path.
- Add direction-specific diagnostic keys/labels while retaining the existing 9-check audit shape where practical.

Mirrored SELL rules to confirm in implementation:

| BUY rule | SELL mirror |
|---|---|
| `EMA13 > EMA21 > EMA55` | `EMA13 < EMA21 < EMA55` |
| Mother `HIGH` covers child bodies | Mother `LOW` covers child bodies |
| Father upper wick `< 30%` body | Father lower wick `< 30%` body |
| Father `OPEN >= EMA13`, `LOW > EMA21` | Father `OPEN <= EMA13`, `HIGH < EMA21` |
| Father `CLOSE >` highest child high | Father `CLOSE <` lowest child low |
| Entry `CLOSE - body%` | Entry `CLOSE + body%` |
| SL below lowest father/child low minus buffer | SL above highest father/child high plus buffer |
| TP `entry + RR*risk` | TP `entry - RR*risk` |

Use direction-aware reason names (for example `father_lower_wick_too_large`, `father_close_not_below_children`) so audit failures are actionable.

### 2. Backtest

- Pass a direction-capable analyzer from `_run_flappy_bird_backtest()`; do not maintain a separate scan loop.
- Evaluate both EMA orderings at each father candle.
- For BUY pending fill: existing `low <= entry`; SL-before-TP.
- For SELL pending fill: `high >= entry`; SL-before-TP (`high >= sl` before `low <= tp`).
- Record the actual signal direction in `_make_trade`, and preserve all debug window fields.
- Keep one trade-at-a-time/scan advancement and progress callback semantics unchanged.

### 3. Live runner

- Make the Flappy scan return either direction.
- Replace the Flappy BUY-only exit branch with direction-aware pending-position checks, or route both directions through `check_exit()` after verifying its price-based semantics.
- Preserve pending expiry, broker fill polling, order trace IDs, Telegram messages, magic `212400`, and `FLAPPY-*` comments.
- Validate that SELL SL/TP are on the correct side before submitting.

### 4. YAML and UI

- Update `strategies/flappy_bird.yaml` name/description and add an explicit direction mode only if configuration is required; recommended default is `both` with no new UI toggle (YAGNI).
- Update `pages/5_Backtest.py` help text and debug rendering to describe both directions and show the correct wick/coverage metrics.
- Ensure chart/debug level labels work for either direction.
- Review `pages/1_Bots.py` generic Flappy labels and history-load behavior; no architecture change expected.
- Update `README.md` and `docs/codebase-guide-vi.md` to document mirrored SELL rules, order levels, and magic number.

## Affected files / call sites

### Modify

- `D:\Project\BotForex\src\flappy_bird_strategy.py` — direction-aware detection, diagnostics, level math; compatibility wrappers/defaults.
- `D:\Project\BotForex\src\backtest.py` — Flappy dispatch/helper scan, SELL pending fill and exit simulation.
- `D:\Project\BotForex\src\bot_runner.py` — live signal scan and SELL exit handling.
- `D:\Project\BotForex\strategies\flappy_bird.yaml` — neutral/both-direction metadata and documentation.
- `D:\Project\BotForex\pages\5_Backtest.py` — neutral copy and direction-aware audit display.
- `D:\Project\BotForex\pages\1_Bots.py` — only if generic labels or Flappy-specific defaults need clarification.
- `D:\Project\BotForex\README.md` — strategy table and rules.
- `D:\Project\BotForex\docs\codebase-guide-vi.md` — implementation and architecture references.

### Reuse / verify, likely no code change

- `D:\Project\BotForex\src\orders.py::place_limit_order` — already supports SELL_LIMIT.
- `D:\Project\BotForex\src\strategy_manager.py` — already reads YAML parameters generically.
- `D:\Project\BotForex\src\bot_manager.py::start_bot/build_bot_command` — already forwards common runner arguments.
- `D:\Project\BotForex\src\utils.py::check_exit` and `_make_trade` — verify SELL semantics and P&L; change only if a concrete defect is found.

### Add/extend tests

- `D:\Project\BotForex\tests\test_flappy_bird_strategy.py`
  - valid mirrored SELL signal and exact entry/SL/TP;
  - bearish EMA ordering;
  - lower-wick, mother-low, and father-close boundary failures;
  - BUY regression coverage unchanged.
- Same file or a new `tests/test_flappy_bird_backtest.py`
  - SELL LIMIT fill when high reaches entry;
  - SELL SL-before-TP when one candle touches both;
  - SELL TP, timeout, expiry/no-fill, direction/debug fields.
- Add a focused runner test (new `tests/test_flappy_bird_runner.py` or existing runner test location)
  - mocked Flappy SELL signal reaches `place_limit_order` with `SELL`, correct magic/comment, and exits via SELL rules.
- Extend strategy-manager/config test to assert Flappy YAML parameters, symbols, and neutral name/direction mode if added.
- Extend `tests/test_place_order.py` only if a regression in pending SELL request mapping is exposed.

## Implementation phases

1. **Core contract (1.5h):** settle mirrored rules; refactor diagnosis/analyze with BUY-compatible defaults; add unit tests.
2. **Backtest (1.5h):** direction selection, SELL fill/exit simulation, trade/debug assertions.
3. **Live path (1.5h):** runner scan/exit changes; mocked order/expiry/Telegram regression tests.
4. **UI/config/docs (1h):** YAML metadata, Backtest debug/copy, Bot UI wording if needed, README/codebase guide.
5. **Validation (0.5h):** `pytest tests/ -v`; targeted Flappy tests; syntax/import smoke; manual test-mode runner and Streamlit backtest with synthetic bearish data.

## Acceptance criteria

- Existing BUY tests and BUY backtest output remain unchanged.
- A valid bearish Flappy window produces SELL LIMIT with `entry < SL` and `TP < entry`.
- Backtest fills SELL when price rises to entry, checks SELL SL before TP, handles expiry/time exit, and records `"SELL"`.
- Live test mode submits SELL_LIMIT through the existing order abstraction; live mode retains magic `212400`, trace IDs, Telegram, and pending expiry behavior.
- Backtest UI audit shows PASS/FAIL for the mirrored conditions and correct SELL levels.
- YAML, README, and codebase guide no longer claim Flappy is BUY-only.

## Assumptions / unresolved questions

- “Mirrored SELL” means a strict geometric/EMA inversion of the current BUY rules, not a separate reversal strategy.
- One `flappy_bird` strategy supports both directions automatically; no direction selector is added unless operators need to disable one side.
- SELL mother coverage means mother `LOW` covers the lowest body edge of every child; confirm whether full candle lows should be covered instead.
- SELL father wick means `CLOSE - LOW` (true lower wick for a bearish candle), mirroring the current BUY `HIGH - CLOSE`.
- SELL EMA filter mirror is `OPEN <= EMA13` and `HIGH < EMA21`; confirm inclusive/exclusive boundaries (`>=`/`>` mirrored to `<=`/`<`).
- Existing `limit_order_candles=7`, RR, minimum body, buffer, magic, and one-trade scan behavior remain unchanged.
- `docs/development-rules.md` is missing from the repository; clarify whether it should be restored or whether `docs/code-standards.md` is authoritative.
