---
title: "Harden Flappy Bird Live Trading"
description: "Make pending-limit handling restart-safe, validate trade levels, and remove the Flappy backtest timeout constant."
status: pending
priority: P1
effort: 5h
branch: main
tags: [bugfix, backend, trading, critical]
created: 2026-09-07
---

# Flappy Bird Live-Trading Hardening

## Scope

Fix four audit findings without redesigning the runner:

1. Accept MT5 `TRADE_RETCODE_PLACED` as a successful pending-limit submission.
2. Treat broker state as authoritative after restart and when an order leaves the pending list.
3. Make Flappy in-trade timeout use the configured value, not literal `7`.
4. Reject invalid levels and duplicate pending signals before sending another order.

`docs/development-rules.md` is absent in this checkout; follow existing Python/pytest conventions in `docs/code-standards.md`.

## Minimal Architecture

- Keep `pending_orders`/`active_trades` in `src/bot_runner.py`; add small reconciliation helpers rather than a new state service.
- Broker is the recovery source of truth. On startup, recover matching Flappy pending orders and open positions by symbol + Flappy magic (`212400`), using ticket/comment metadata. Do not infer state from `data/bot_state.json`; it currently stores counts only.
- When a pending ticket disappears, locate the resulting position by symbol/magic and position identifier/order linkage, not only `positions_get(ticket=pending_ticket)`. If no linkage exists, use the newest matching position and log the ambiguity; never silently create a duplicate.
- Before placement, reject a signal already represented by a local or broker pending order with the same symbol, magic, direction, and normalized entry/SL/TP. This protects repeated scans and restarts.
- Reuse the signal’s computed levels for validation so live and backtest paths cannot disagree.

## Exact Files / Functions

### Modify `D:\Project\BotForex\src\orders.py`

- `place_limit_order()`
  - Define accepted success retcodes as `TRADE_RETCODE_DONE` or `TRADE_RETCODE_PLACED` (guard the optional constant for test doubles/older MT5 bindings).
  - Preserve the existing `(success, message, ticket)` contract and failure logging.

### Modify `D:\Project\BotForex\src\flappy_bird_strategy.py`

- `analyze_flappy_bird()`
  - After calculating levels, validate finite numeric values, positive risk, and directional ordering:
    - BUY: `stop_loss < entry_price < take_profit`
    - SELL: `take_profit < entry_price < stop_loss`
  - Return `None` for invalid levels (or a clearly named validation failure only if existing callers need diagnostics); do not submit malformed MT5 requests.
- Prefer a small private/shared validator (e.g. `_validate_trade_levels`) over duplicating these checks in live and backtest code.

### Modify `D:\Project\BotForex\src\bot_runner.py`

- `run_feg_bot()`
  - Add startup reconciliation immediately after the persistent MT5 connection is available:
    - recover Flappy pending orders from `orders_get()` filtered by symbol/magic and pending order type/comment;
    - recover matching open positions into `active_trades`;
    - derive remaining pending lifetime from `time_setup` and the configured timeframe where available; use a bounded conservative fallback when broker timestamps are missing.
  - Extract pending status handling into focused helpers if needed:
    - `_recover_flappy_state(...)`
    - `_find_filled_position(...)`
    - `_has_duplicate_pending(...)`
  - Replace `positions_get(ticket=mt5_ticket)` in the “pending order disappeared” path with linkage-aware lookup by order/position identifier, then symbol/magic fallback.
  - Gate Flappy placement on `_has_duplicate_pending(...)` across both local lists and current MT5 orders. Keep existing non-Flappy behavior unchanged.
  - Write recovered counts through `_write_bot_state()` after reconciliation.

- `get_args()` / parameter handling
  - Keep existing `--limit_order_candles` and strategy YAML values; ensure validation clamps/rejects non-positive expiry values before the loop.

### Modify `D:\Project\BotForex\src\backtest.py`

- `run_backtest()`
  - Pass `max_candles` into `_run_flappy_bird_backtest()`.
- `_run_flappy_bird_backtest()`
  - Add `max_candles` parameter.
  - Replace both hardcoded `7` values in post-fill exit scanning (`range(... + 7)` and `pos + 7`) with the configured active-trade timeout.
  - Keep `limit_order_candles` exclusively for pending-entry expiry.
  - Preserve SL-before-TP ordering and existing trade/debug output.

### Modify `D:\Project\BotForex\tests\test_place_order.py`

- Add a live mocked `place_limit_order()` case where retcode is `TRADE_RETCODE_PLACED`; assert success and returned ticket.
- Retain the existing `DONE` coverage.

### Modify `D:\Project\BotForex\tests\test_flappy_bird_strategy.py`

- Add BUY and SELL invalid-level cases (bad RR/order, zero/negative risk, non-finite level if practical) and assert no signal.
- Add a backtest fixture proving `max_candles=2` produces `TIME` at two candles rather than the old seven; keep the current `limit_order_candles=7` fill/SL-first assertion.

### Add/extend `D:\Project\BotForex\tests\test_feg_runner.py`

- Unit-test `_has_duplicate_pending()` for same signal, different direction, and different level.
- Mock MT5 startup reconciliation and verify:
  - existing Flappy pending order is recovered;
  - matching open position is recovered;
  - a repeated signal does not call `place_limit_order()`;
  - a filled pending order whose position ticket differs from the order ticket is recognized.
- Test missing/invalid expiry is rejected or safely bounded.

## Implementation Order

1. Add level validator and retcode acceptance; add focused unit tests.
2. Parameterize Flappy backtest timeout; add regression test.
3. Add runner reconciliation and linkage-aware fill detection.
4. Add duplicate gate; test restart/repeat scenarios.
5. Run full suite and manually inspect the generated order request in test doubles.

## Acceptance Criteria

- `PLACED` limit orders enter the tracked pending list and are not reported as failures.
- Restarting with a broker-side Flappy pending order does not place a second order.
- A pending order that fills into a differently-ticketed position becomes one active trade.
- Invalid directional levels never reach `mt5.order_send()`.
- Flappy pending expiry and active-trade timeout are independently configurable.
- Existing FEG, stop-order, reverse, and market-order tests remain green.

## Test Plan

```text
pytest tests/test_place_order.py tests/test_flappy_bird_strategy.py tests/test_feg_runner.py -v
pytest tests/ -v
```

Manual demo-account smoke test:

1. Start Flappy live in a controlled symbol.
2. Confirm broker returns `PLACED`; verify one pending record and Telegram notification.
3. Restart the process while pending; verify recovery and no duplicate.
4. Trigger fill; verify active position tracking and exit handling.
5. Verify expiry cancellation after configured pending candles.

## Risks / Mitigations

- MT5 order/position linkage differs by account mode: prefer explicit identifiers, then symbol/magic + direction + newest timestamp; log ambiguity and avoid duplicate placement.
- Recovery timestamp/timezone gaps can overrun expiry: use conservative remaining-candle calculation and cancel immediately when elapsed lifetime is already at/over the limit.
- Existing generic FEG loops are duplicated in `bot_runner.py`: limit edits to the Flappy branch/helpers unless a shared helper is behavior-neutral.

## Unresolved Questions

- Should recovered pending orders retain their original full `ORD-*` ID, or is a stable `RECOVERED-{ticket}` ID acceptable?
- For ambiguous netting-account position matches, should the bot halt Flappy entry or only log and continue?
