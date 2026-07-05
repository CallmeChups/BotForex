# Real MT5 Pending Limit Orders Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the fake candle-fill detection logic with real MT5 SELL_LIMIT/BUY_LIMIT pending orders so entry price, SL, and TP are all correct on the broker side.

**Architecture:** `place_limit_order()` places a real `TRADE_ACTION_PENDING` order on MT5; `cancel_pending_order()` cancels it. The `run_feg_bot` loop drops the candle low/high fill detection and instead polls `mt5.orders_get(ticket=...)` each tick — if the pending order disappears, it checks `mt5.positions_get()` to confirm a fill and grabs the actual fill price; if timeout hits, it calls `cancel_pending_order()`.

**Tech Stack:** Python, MetaTrader5 (ORDER_TYPE_SELL_LIMIT / ORDER_TYPE_BUY_LIMIT, TRADE_ACTION_PENDING, TRADE_ACTION_REMOVE), existing project patterns in `src/orders.py` and `src/bot_runner.py`.

## Global Constraints

- Windows-only: MetaTrader5 module available only on Windows, all paths use `os.path`
- No new dependencies — use MetaTrader5 and stdlib only
- Test mode (`args.test == 1`): skip all real MT5 calls, simulate with log output
- `place_limit_order()` returns `(success: bool, message: str, ticket: int | None)` — same shape as `place_order()`
- `cancel_pending_order()` returns `(success: bool, message: str)`
- `pending_orders` list entries gain a `"mt5_ticket"` key (int | None) to track the real MT5 pending order ticket
- Do NOT change `place_order()` (market orders) — it is still used for closes in `close_position()` and is not being replaced
- YAGNI: no UI changes, no database changes, no new files

---

## File Map

| File | Change |
|---|---|
| `src/orders.py` | Add `place_limit_order()` and `cancel_pending_order()` |
| `src/bot_runner.py` | Rewrite `pending_orders` section in `run_feg_bot()`: place real limit on signal, poll ticket, handle fill/expire |

---

### Task 1: Add `place_limit_order()` and `cancel_pending_order()` to `src/orders.py`

**Files:**
- Modify: `src/orders.py` (append after `place_order()`, around line 395)

**Interfaces:**
- Produces:
  ```python
  def place_limit_order(
      symbol: str,
      direction: str,   # "BUY" or "SELL"
      volume: float,
      price: float,     # exact limit price
      sl: float = None,
      tp: float = None,
      credentials: dict = None,
      test: bool = False,
      magic: int = 123456,
      comment: str = "LimitOrder",
  ) -> tuple:           # (success: bool, message: str, ticket: int | None)

  def cancel_pending_order(
      ticket: int,
      credentials: dict = None,
  ) -> tuple:           # (success: bool, message: str)
  ```
- Consumed by: Task 2 (`run_feg_bot` in `src/bot_runner.py`)

- [ ] **Step 1: Add `place_limit_order()` to `src/orders.py`**

  Append this function after the closing `except` block of `place_order()` (after line 394):

  ```python
  def place_limit_order(
      symbol: str,
      direction: str,
      volume: float,
      price: float,
      sl: float = None,
      tp: float = None,
      credentials: dict = None,
      test: bool = False,
      magic: int = 123456,
      comment: str = "LimitOrder",
  ) -> tuple:
      """
      Place a pending limit order (SELL_LIMIT or BUY_LIMIT).

      Returns (success, message, ticket).
      """
      if test:
          return True, f"[TEST] {direction}_LIMIT {symbol} vol={volume} price={price} sl={sl} tp={tp} simulated", None

      mt5, error = get_mt5_connection(credentials)
      if error:
          return False, error, None

      try:
          import MetaTrader5 as mt5_module

          symbol_info = mt5.symbol_info(symbol)
          if symbol_info is None:
              mt5.shutdown()
              return False, f"Symbol {symbol} not found", None

          if not symbol_info.visible:
              if not mt5.symbol_select(symbol, True):
                  mt5.shutdown()
                  return False, f"Failed to select {symbol}", None

          if direction.upper() == "BUY":
              order_type = mt5_module.ORDER_TYPE_BUY_LIMIT
          else:
              order_type = mt5_module.ORDER_TYPE_SELL_LIMIT

          request = {
              "action": mt5_module.TRADE_ACTION_PENDING,
              "symbol": symbol,
              "volume": volume,
              "type": order_type,
              "price": price,
              "deviation": 20,
              "magic": magic,
              "comment": comment,
              "type_time": mt5_module.ORDER_TIME_GTC,
              "type_filling": mt5_module.ORDER_FILLING_RETURN,
          }

          if sl is not None and sl > 0:
              request["sl"] = sl
          if tp is not None and tp > 0:
              request["tp"] = tp

          result = mt5.order_send(request)
          mt5.shutdown()

          if result is None:
              return False, "Limit order failed: No response from MT5", None

          if result.retcode != mt5_module.TRADE_RETCODE_DONE:
              return False, f"Limit order failed: {result.comment} (code: {result.retcode})", None

          return True, f"Limit order placed at {price:.5f}", result.order

      except Exception as e:
          mt5.shutdown()
          return False, str(e), None
  ```

- [ ] **Step 2: Add `cancel_pending_order()` to `src/orders.py`**

  Append immediately after `place_limit_order()`:

  ```python
  def cancel_pending_order(
      ticket: int,
      credentials: dict = None,
  ) -> tuple:
      """
      Cancel a pending order by ticket.

      Returns (success, message).
      """
      mt5, error = get_mt5_connection(credentials)
      if error:
          return False, error

      try:
          import MetaTrader5 as mt5_module

          request = {
              "action": mt5_module.TRADE_ACTION_REMOVE,
              "order": ticket,
          }

          result = mt5.order_send(request)
          mt5.shutdown()

          if result is None:
              return False, "Cancel failed: No response from MT5"

          if result.retcode != mt5_module.TRADE_RETCODE_DONE:
              return False, f"Cancel failed: {result.comment} (code: {result.retcode})"

          return True, f"Pending order {ticket} cancelled"

      except Exception as e:
          mt5.shutdown()
          return False, str(e)
  ```

- [ ] **Step 3: Verify the functions are importable**

  Run from the project root (Windows PowerShell):
  ```powershell
  .venv\Scripts\python.exe -c "from src.orders import place_limit_order, cancel_pending_order; print('OK')"
  ```
  Expected output: `OK`

- [ ] **Step 4: Commit**

  ```powershell
  git add src/orders.py
  git commit -m "feat: add place_limit_order and cancel_pending_order to orders.py"
  ```

---

### Task 2: Rewrite pending order handling in `run_feg_bot()` to use real MT5 limit orders

**Files:**
- Modify: `src/bot_runner.py` (inside `run_feg_bot()`, two sections)

**Interfaces:**
- Consumes:
  ```python
  from src.orders import place_order, close_position, place_limit_order, cancel_pending_order
  # place_limit_order(symbol, direction, volume, price, sl, tp, credentials, test, magic, comment)
  #   → (bool, str, int | None)
  # cancel_pending_order(ticket, credentials) → (bool, str)
  ```
- `pending_orders` list entry shape BEFORE this task:
  ```python
  {"signal": dict, "trade_lot": float, "candles_left": int, "order_id": str}
  ```
- `pending_orders` list entry shape AFTER this task:
  ```python
  {"signal": dict, "trade_lot": float, "candles_left": int, "order_id": str, "mt5_ticket": int | None}
  ```
- `active_trades` list entry shape is unchanged:
  ```python
  {"direction": str, "entry": float, "sl": float, "tp": float,
   "ticket": int, "candles": int, "order_id": str, "lot": float}
  ```

**Context for the implementer:**

The file is `src/bot_runner.py`. The function `run_feg_bot()` starts around line 571. There are two code sections to change:

**Section A — Signal detected → place real limit order** (around line 778–801, inside `if signal:` block):

Current code places nothing — just appends to `pending_orders`:
```python
if signal:
    trade_lot = lot_size
    if lot_mode == "flex":
        ...
    import uuid as _uuid
    _candle_dt = ...
    order_id = f"ORD-..."
    log(f"[{order_id}] FEG Signal: ...")
    send_telegram(...)
    pending_orders.append({
        "signal": signal,
        "trade_lot": trade_lot,
        "candles_left": limit_order_candles,
        "order_id": order_id,
    })
```

**Section B — Check pending orders each new candle** (around line 663–710, inside `if is_new_candle:`, step "1. Check pending orders"):

Current code fakes fill by checking `candle["low"] <= entry_price <= candle["high"]` then calls `place_order()` (market order).

- [ ] **Step 1: Update the import at the top of `run_feg_bot()`**

  Find line ~575:
  ```python
  from src.orders import place_order, close_position
  ```
  Replace with:
  ```python
  from src.orders import place_order, close_position, place_limit_order, cancel_pending_order
  ```

- [ ] **Step 2: Rewrite Section A — place real limit order when signal detected**

  Find the `if signal:` block (around line 778). Replace the `pending_orders.append(...)` call with the block below. Keep everything before it (lot calculation, order_id generation, log/telegram) unchanged. Only replace the `pending_orders.append(...)` at the end:

  ```python
  if signal:
      trade_lot = lot_size
      if lot_mode == "flex":
          trade_lot = _calc_flex_lot(
              mt5, args.symbol, risk_mode, risk_percent, risk_amount,
              signal["entry_price"], signal["stop_loss"],
          )
      import uuid as _uuid
      _candle_dt = datetime.fromtimestamp(int(last['time']), tz=TIMEZONE)
      order_id = f"ORD-{_candle_dt.strftime('%y%m%d-%H%M%S')}-{args.symbol}-{_uuid.uuid4().hex[:4].upper()}"
      log(f"[{order_id}] FEG Signal: {signal['direction']} @ {signal['entry_price']:.2f}, "
          f"SL={signal['stop_loss']:.2f}, TP={signal['take_profit']:.2f}, lot={trade_lot}, "
          f"limit_timeout={limit_order_candles}c")

      # Place real MT5 pending limit order
      ok_limit, msg_limit, mt5_ticket = place_limit_order(
          args.symbol, signal["direction"], trade_lot, signal["entry_price"],
          sl=signal["stop_loss"], tp=signal["take_profit"],
          credentials=credentials, test=bool(args.test),
          magic=212100, comment=f"FEG-{order_id[-4:]}",
      )
      if not ok_limit:
          log(f"[{order_id}] Failed to place limit order: {msg_limit}", "ERROR")
          send_telegram(f"❌ Limit order failed\nID: <code>{order_id}</code>\nReason: {msg_limit}", is_error=True)
      else:
          log(f"[{order_id}] Limit order placed on MT5 ticket={mt5_ticket}")
          send_telegram(f"<b>FEG Signal (pending): {signal['direction']}</b>\n"
                        f"ID: <code>{order_id}</code>\n"
                        f"Symbol: {args.symbol}\nEntry: {signal['entry_price']:.2f}\n"
                        f"SL: {signal['stop_loss']:.2f} TP: {signal['take_profit']:.2f}\n"
                        f"Lot: {trade_lot} | Ticket: {mt5_ticket} | Chờ: {limit_order_candles} nến")
          pending_orders.append({
              "signal": signal,
              "trade_lot": trade_lot,
              "candles_left": limit_order_candles,
              "order_id": order_id,
              "mt5_ticket": mt5_ticket,
          })
  ```

  Note: the original `send_telegram` for signal was BEFORE the append. In the new code, the telegram is sent only after a successful limit placement (inside `else:`). Remove the original `send_telegram` call that was before `pending_orders.append`.

- [ ] **Step 3: Rewrite Section B — poll MT5 ticket instead of fake candle fill detection**

  Find the block starting with `# 1. Check pending orders — khớp nếu giá nến chạm entry price` (around line 663). Replace the entire inner body (from `still_pending = []` through `pending_orders = still_pending`) with:

  ```python
  # 1. Check pending orders — poll MT5 ticket each candle
  still_pending = []
  for order in pending_orders:
      oid = order["order_id"]
      mt5_ticket = order.get("mt5_ticket")
      _sig = order["signal"]

      # Test mode: simulate fill by candle low/high (unchanged behaviour)
      if args.test or mt5_ticket is None:
          filled = candle["low"] <= _sig["entry_price"] <= candle["high"]
          if filled:
              log(f"[{oid}] [TEST] Limit order filled @ {_sig['entry_price']:.2f}")
              send_telegram(f"<b>FEG Limit Filled (TEST): {_sig['direction']}</b>\n"
                            f"ID: <code>{oid}</code>\nEntry: {_sig['entry_price']:.2f}\n"
                            f"SL: {_sig['stop_loss']:.2f} TP: {_sig['take_profit']:.2f}\n"
                            f"Lot: {order['trade_lot']}")
              active_trades.append({
                  "direction": _sig["direction"],
                  "entry": _sig["entry_price"],
                  "sl": _sig["stop_loss"],
                  "tp": _sig["take_profit"],
                  "ticket": None, "candles": 0, "order_id": oid,
                  "lot": order.get("trade_lot", lot_size),
              })
          else:
              order["candles_left"] -= 1
              if order["candles_left"] > 0:
                  still_pending.append(order)
              else:
                  log(f"[{oid}] [TEST] Limit order expired (no fill)")
                  send_telegram(
                      f"⏰ <b>Limit order hết hạn (không khớp) [TEST]</b>\n"
                      f"ID: <code>{oid}</code>\nSymbol: {args.symbol}\n"
                      f"Direction: {_sig['direction']}\nEntry: {_sig['entry_price']:.2f}\n"
                      f"SL: {_sig['stop_loss']:.2f} TP: {_sig['take_profit']:.2f}"
                  )
          continue  # skip live logic below

      # Live: poll MT5 pending orders by ticket
      pending_on_mt5 = mt5.orders_get(ticket=mt5_ticket)
      if pending_on_mt5:
          # Still pending on broker — decrement counter
          order["candles_left"] -= 1
          if order["candles_left"] > 0:
              still_pending.append(order)
          else:
              # Timeout — cancel the pending order on MT5
              log(f"[{oid}] Limit order timed out (ticket={mt5_ticket}) — cancelling")
              ok_cancel, cancel_msg = cancel_pending_order(mt5_ticket, credentials=credentials)
              log(f"[{oid}] Cancel result: {cancel_msg}")
              send_telegram(
                  f"⏰ <b>Limit order hết hạn (không khớp)</b>\n"
                  f"ID: <code>{oid}</code>\nSymbol: {args.symbol}\n"
                  f"Direction: {_sig['direction']}\nEntry: {_sig['entry_price']:.2f}\n"
                  f"SL: {_sig['stop_loss']:.2f} TP: {_sig['take_profit']:.2f}"
              )
      else:
          # Order gone from MT5 pending list — check if it became a position (filled)
          pos = mt5.positions_get(ticket=mt5_ticket)
          if pos:
              position = pos[0]
              fill_price = position.price_open
              log(f"[{oid}] Limit order filled by broker @ {fill_price:.5f} (ticket={mt5_ticket})")
              send_telegram(f"<b>FEG Limit Filled: {_sig['direction']}</b>\n"
                            f"ID: <code>{oid}</code>\nFill: {fill_price:.2f}\n"
                            f"SL: {_sig['stop_loss']:.2f} TP: {_sig['take_profit']:.2f}\n"
                            f"Lot: {order['trade_lot']} | Ticket: {mt5_ticket}")
              active_trades.append({
                  "direction": _sig["direction"],
                  "entry": fill_price,          # actual fill price from MT5
                  "sl": _sig["stop_loss"],
                  "tp": _sig["take_profit"],
                  "ticket": mt5_ticket, "candles": 0, "order_id": oid,
                  "lot": order.get("trade_lot", lot_size),
              })
          else:
              # Disappeared without becoming a position — cancelled externally or rejected
              log(f"[{oid}] Pending order {mt5_ticket} no longer on MT5 (cancelled externally or rejected)")
              send_telegram(f"⚠️ Pending order removed externally\nID: <code>{oid}</code>\nTicket: {mt5_ticket}")
  pending_orders = still_pending
  ```

- [ ] **Step 4: Verify syntax — import check**

  ```powershell
  .venv\Scripts\python.exe -c "import py_compile; py_compile.compile('src/bot_runner.py', doraise=True); print('Syntax OK')"
  ```
  Expected: `Syntax OK`

- [ ] **Step 5: Manual smoke test in test mode**

  Start the bot in test mode (no real trades placed):
  ```powershell
  .venv\Scripts\python.exe src/bot_runner.py --strategy feg_ema21 --symbol XAUUSDm --user admin --test 1
  ```

  Watch the log for one new candle. Expected log sequence when a signal fires:
  ```
  [ORD-...] FEG Signal: SELL @ 4051.26, SL=4059.76, TP=4034.27, lot=0.01, limit_timeout=1c
  [ORD-...] [TEST] Limit order placed (simulated)  — OR — limit order expired
  ```

  No Python exceptions in the output.

- [ ] **Step 6: Commit**

  ```powershell
  git add src/bot_runner.py
  git commit -m "feat: use real MT5 SELL_LIMIT/BUY_LIMIT pending orders in run_feg_bot"
  ```

---

## Self-Review

### Spec coverage

| Requirement | Covered by |
|---|---|
| `place_limit_order()` using TRADE_ACTION_PENDING + SELL_LIMIT/BUY_LIMIT | Task 1 Step 1 |
| `cancel_pending_order()` using TRADE_ACTION_REMOVE | Task 1 Step 2 |
| On signal: call `place_limit_order()`, store `mt5_ticket` | Task 2 Step 2 |
| Each tick: `mt5.orders_get(ticket=...)` to check if still pending | Task 2 Step 3 |
| If order gone → `mt5.positions_get(ticket=...)` → use actual fill price | Task 2 Step 3 |
| If timeout: `cancel_pending_order(ticket)` | Task 2 Step 3 |
| Remove fake candle fill detection (`candle["low"] <= entry_price <= candle["high"]`) | Task 2 Step 3 (moved to test-mode only) |
| Test mode still works without real MT5 | Task 2 Step 3 (test-mode branch preserved) |

### Placeholder scan

No TBD, TODO, or vague steps found.

### Type consistency

- `place_limit_order()` returns `(bool, str, int | None)` — matches how Task 2 unpacks: `ok_limit, msg_limit, mt5_ticket`
- `cancel_pending_order()` returns `(bool, str)` — matches `ok_cancel, cancel_msg`
- `mt5_ticket` stored as `order["mt5_ticket"]` — retrieved as `order.get("mt5_ticket")` ✓
- `fill_price = position.price_open` — `price_open` is correct MT5 field for fill price ✓
