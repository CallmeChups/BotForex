# Zone Layout Redesign — Bots & Backtest Forms Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a 5-zone expander layout (General / Entry / Order Settings / Risk & Sizing / Exit) to `pages/1_Bots.py` and `pages/5_Backtest.py` as a parallel option alongside the existing classic layout, switchable via a radio selector at the bottom of each page.

**Architecture:** The existing `use_compact` toggle controls classic vs compact rendering. A new `layout_version` radio (session-only, per-page) gates whether the new 5-zone layout or the existing layout renders. The new layout is purely additive — classic layout code is not modified. Both share all variable names, session state keys, and the same `start_bot()`/`run_backtest()` call at the end.

**Tech Stack:** Python 3.11, Streamlit. No backend changes.

## Global Constraints

- New layout session state key: `"bots_layout_version"` in `1_Bots.py`, `"backtest_layout_version"` in `5_Backtest.py`
- Layout selector default: `"New"` (resets on page refresh — session only)
- Zone names (exact strings): `"General"`, `"Entry"`, `"Order Settings"`, `"Risk & Sizing"`, `"Exit"`
- `General` and `Entry` expanders: `expanded=True`; other three: `expanded=False`
- All session state keys (`{sk}_*`) must remain identical — no renames
- Classic layout code (lines 485–906 in `1_Bots.py`, lines 117–553 in `5_Backtest.py`) must NOT be modified
- `Entry` zone hidden entirely when `not is_pattern` (Master Candle)
- `Limit Order Candles` only in Entry zone when `is_feg_stop_order`
- `Entry Mode` + `Entry %` only in Entry zone when `not is_feg_stop_order` (FEG EMA21)
- `Test Mode` + `Interval` only in Bots form
- `Start Date`, `End Date`, `Starting Equity` only in Backtest form
- Layout version selector placed at bottom of page, after `st.divider()`, before the `start_bot`/`run_backtest` button

---

## File Structure

| File | Change |
|---|---|
| `pages/1_Bots.py` | Add `_render_new_layout_bots()` function + layout selector + call gate |
| `pages/5_Backtest.py` | Add `_render_new_layout_backtest()` function + layout selector + call gate |

No new files created. Both functions defined locally in their respective page files, directly above `show_create_bot()` / the backtest form block.

---

## Task 1: Layout selector + gate in `pages/1_Bots.py`

**Files:**
- Modify: `pages/1_Bots.py` — add selector radio + gate around existing layout block

**Interfaces:**
- Produces: `layout_version` variable (`"New"` or `"Classic"`) available to Task 2

The layout selector goes **after** the `st.divider()` at line 907 but **before** `sl_pips = ...` at line 910. The gate wraps the existing `if use_compact: ... else: ...` block (lines 485–906).

- [ ] **Step 1: Read the file to confirm exact line numbers**

Open `pages/1_Bots.py`. Confirm:
- Line 409: `use_compact = st.toggle(...)`
- Line 485: `if use_compact:`
- Line 907: `st.divider()` (after non-compact lot size block)
- Line 910: `sl_pips = None if is_pattern else ...`

- [ ] **Step 2: Add layout version selector at bottom of form (after line 907 divider)**

Find this block in `pages/1_Bots.py`:
```python
        st.divider()

    # sl_pips not used for pattern strategies (SL from candle + buffer_k)
    sl_pips = None if is_pattern else int(params.get('sl_pips', 30))
```

Replace with:
```python
        st.divider()

    # Layout version selector — session only, resets to "New" on refresh
    st.divider()
    layout_version = st.radio(
        "Layout version",
        ["New", "Classic"],
        index=["New", "Classic"].index(st.session_state.get("bots_layout_version", "New")),
        horizontal=True,
        key="bots_layout_version",
        help="New: 5-zone layout. Classic: original layout. Resets to New on page refresh.",
    )

    # sl_pips not used for pattern strategies (SL from candle + buffer_k)
    sl_pips = None if is_pattern else int(params.get('sl_pips', 30))
```

- [ ] **Step 3: Wrap existing layout block with Classic gate**

Find the existing layout gate at line 485:
```python
    if use_compact:
        # ── COMPACT LAYOUT ────────────────────
```

Replace the outer condition so the whole block only renders when `layout_version == "Classic"`:
```python
    if layout_version == "Classic":
        if use_compact:
            # ── COMPACT LAYOUT ────────────────────
```

And find the matching `else:` that starts non-compact (around line 734):
```python
    else:
        # ── OLD LAYOUT (Non-Compact) ───────────
```

Change to:
```python
        else:
            # ── OLD LAYOUT (Non-Compact) ───────────
```

Close the outer `if layout_version == "Classic":` block after line 907's `st.divider()`:
```python
            st.divider()
    # end Classic layout
```

- [ ] **Step 4: Verify syntax**

```powershell
cd e:\Project\BotForex
python -m py_compile pages/1_Bots.py
```
Expected: no output (success).

- [ ] **Step 5: Smoke test in browser**

Run: `streamlit run Home.py`  
Navigate to Bots page → Create Bot section.  
Verify: radio "Layout version: New | Classic" appears at bottom. Selecting "Classic" shows existing layout. Selecting "New" currently shows nothing (Task 2 will add it). No errors in terminal.

- [ ] **Step 6: Commit**

```powershell
git add pages/1_Bots.py
git commit -m "feat: add layout version selector to Bots page (Classic gate)"
```

---

## Task 2: New layout implementation in `pages/1_Bots.py`

**Files:**
- Modify: `pages/1_Bots.py` — add `_render_new_layout_bots()` function and call it when `layout_version == "New"`

**Interfaces:**
- Consumes: `layout_version` (Task 1), `sk`, `params`, `is_pattern`, `is_feg_stop_order`, `symbol`, `username` — all already in scope inside `show_create_bot()`
- Produces: all param variables needed by `start_bot()` call at line 917: `test_mode`, `rr_ratio`, `max_candles`, `interval`, `ema_period`, `h2_exceed_pips`, `c2_gap_pips`, `ema_margin_pips`, `c2_wick_filter_enabled`, `c2_wick_max_percent`, `ema_filter_enabled`, `buy_ema_side`, `sell_ema_side`, `entry_start_time`, `entry_end_time`, `entry_mode`, `entry_percent`, `limit_order_candles`, `buffer_k`, `re_entry_after_sl`, `lot_mode`, `lot_size`, `risk_mode`, `risk_percent`, `risk_amount`, `tp_type`, `sl_type`, `be_enabled`, `be_r`

- [ ] **Step 1: Add the new layout rendering block inside `show_create_bot()`**

After the `if layout_version == "Classic": ... # end Classic layout` block (from Task 1), and before `sl_pips = ...`, add:

```python
    if layout_version == "New":
        _pip_caption_fn = _pip_caption  # local alias

        # ── ZONE 1: GENERAL ──────────────────────────────────────────────
        with st.expander("General", expanded=True):
            gc1, gc2, gc3, gc4, gc5, gc6 = st.columns([2, 1, 1, 1, 1, 1])
            strategy_symbols = params.get('symbols', [])
            with gc1:
                use_custom_symbol = st.checkbox("Custom symbol", value=False, key=f"{sk}_custom_sym")
                if use_custom_symbol:
                    symbol = st.text_input("Symbol*", value=os.getenv("SYMBOL", "XAUUSD"), key=f"{sk}_symbol")
                elif strategy_symbols:
                    symbol = st.selectbox("Symbol*", options=strategy_symbols, key=f"{sk}_symbol")
                else:
                    symbol = st.text_input("Symbol*", value=os.getenv("SYMBOL", "XAUUSD"), key=f"{sk}_symbol")
            with gc2:
                test_mode = st.checkbox("Test Mode", value=st.session_state.get(f"{sk}_test", True), key=f"{sk}_test",
                                        help="Test mode: no real orders placed")
            with gc3:
                rr_ratio = st.number_input("RR Ratio", value=float(st.session_state.get(f"{sk}_rr", params.get('rr_ratio', 2.0))),
                                           min_value=0.1, max_value=20.0, step=0.1, format="%.1f", key=f"{sk}_rr")
            with gc4:
                _use_mc = st.checkbox("Limit candles", value=st.session_state.get(f"{sk}_use_mc", True), key=f"{sk}_use_mc")
                if _use_mc:
                    max_candles = st.number_input("Max Candles", value=int(st.session_state.get(f"{sk}_mc", params.get('max_candles', 7))),
                                                  min_value=1, max_value=500, key=f"{sk}_mc")
                else:
                    max_candles = None
                    st.caption("No candle limit")
            with gc5:
                interval = st.number_input("Interval (s)", value=int(st.session_state.get(f"{sk}_iv", 60)),
                                           min_value=5, max_value=3600, step=5, key=f"{sk}_iv",
                                           help="Bot scan interval in seconds")
                strategy_timeframe = params.get('timeframe', 'M1')
                st.caption(f"TF: {strategy_timeframe}")

        # ── ZONE 2: ENTRY ─────────────────────────────────────────────────
        if is_pattern:
            with st.expander("Entry", expanded=True):
                # Sub-section: FEG Margins
                st.caption("**FEG Margins**")
                em1, em2, em3, em4, em5, em6 = st.columns(6)
                with em1:
                    ema_period = st.number_input("EMA Period",
                                                 value=int(st.session_state.get(f"{sk}_ema", params.get('ema_period', 21))),
                                                 min_value=2, max_value=200, key=f"{sk}_ema")
                with em2:
                    h2_exceed_pips = st.number_input("H2 > H1 + N pips",
                                                     value=float(st.session_state.get(f"{sk}_h2x", params.get('h2_exceed_pips', 0.0))),
                                                     min_value=0.0, step=1.0, key=f"{sk}_h2x",
                                                     help="SELL: H2 phải vượt H1 thêm N pips | BUY: L2 phải thấp hơn L1 thêm N pips")
                    st.caption(_pip_caption_fn(h2_exceed_pips, symbol))
                with em3:
                    c2_gap_pips = st.number_input("C2 vượt L1/H1 + N pips",
                                                  value=float(st.session_state.get(f"{sk}_c2g", params.get('c2_gap_pips', 0.0))),
                                                  min_value=0.0, step=1.0, key=f"{sk}_c2g",
                                                  help="SELL: C2 phải đóng thấp hơn L1 thêm N pips | BUY: C2 phải đóng cao hơn H1 thêm N pips")
                    st.caption(_pip_caption_fn(c2_gap_pips, symbol))
                with em4:
                    ema_margin_pips = st.number_input("L2/H2 cách EMA + N pips",
                                                      value=float(st.session_state.get(f"{sk}_emam", params.get('ema_margin_pips', 0.0))),
                                                      min_value=0.0, step=1.0, key=f"{sk}_emam",
                                                      help="SELL: L2 phải cách EMA ≥ N pips | BUY: H2 phải cách EMA ≥ N pips")
                    st.caption(_pip_caption_fn(ema_margin_pips, symbol))
                with em5:
                    c2_wick_filter_enabled = st.checkbox("C2 Wick Filter",
                                                         value=bool(st.session_state.get(f"{sk}_c2_wick_filter_enabled", False)),
                                                         key=f"{sk}_c2_wick_filter_enabled",
                                                         help="Râu nến C2 phải nhỏ hơn n% body C2.")
                with em6:
                    c2_wick_max_percent = st.number_input("Wick Max % of Body",
                                                          value=float(st.session_state.get(f"{sk}_c2_wick_max_percent", 30.0)),
                                                          min_value=1.0, max_value=200.0, step=1.0, format="%.0f",
                                                          key=f"{sk}_c2_wick_max_percent",
                                                          disabled=not c2_wick_filter_enabled)

                st.divider()
                # Sub-section: EMA Direction
                st.caption("**EMA Direction**")
                ed1, ed2, ed3 = st.columns(3)
                with ed1:
                    ema_filter_enabled = st.checkbox("EMA Filter",
                                                     value=bool(st.session_state.get(f"{sk}_ema_filter", params.get('ema_filter_enabled', True))),
                                                     key=f"{sk}_ema_filter",
                                                     help="Bật/tắt điều kiện EMA cho tín hiệu entry")
                with ed2:
                    _ema_side_opts = ["above_ema", "below_ema"]
                    buy_ema_side = st.selectbox("BUY EMA side", options=_ema_side_opts,
                                                index=_ema_side_opts.index(st.session_state.get(f"{sk}_buy_ema_side", params.get('buy_ema_side', 'below_ema'))),
                                                format_func=lambda x: "H2 > EMA (above)" if x == "above_ema" else "H2 < EMA (below)",
                                                key=f"{sk}_buy_ema_side",
                                                disabled=not ema_filter_enabled)
                with ed3:
                    sell_ema_side = st.selectbox("SELL EMA side", options=_ema_side_opts,
                                                 index=_ema_side_opts.index(st.session_state.get(f"{sk}_sell_ema_side", params.get('sell_ema_side', 'above_ema'))),
                                                 format_func=lambda x: "L2 > EMA (above)" if x == "above_ema" else "L2 < EMA (below)",
                                                 key=f"{sk}_sell_ema_side",
                                                 disabled=not ema_filter_enabled)

                st.divider()
                # Sub-section: Time Window
                st.caption("**Time Window**")
                tw1, tw2 = st.columns(2)
                with tw1:
                    entry_start_time = st.time_input("Window Start (HCM)", value=time(0, 0),
                                                     key=f"{sk}_tw_start",
                                                     help="Gate entries from this time. 00:00 = no filter.")
                with tw2:
                    entry_end_time = st.time_input("Window End (HCM)", value=time(23, 59),
                                                   key=f"{sk}_tw_end",
                                                   help="Gate entries until this time. 23:59 = no filter.")

                st.divider()
                # Sub-section: Entry Mode
                st.caption("**Entry Mode**")
                if not is_feg_stop_order:
                    enm1, enm2 = st.columns(2)
                    with enm1:
                        _em_opts = ["close", "range_percent"]
                        _em_default = st.session_state.get(f"{sk}_entry_mode", params.get('entry_mode', 'close'))
                        entry_mode = st.radio("Entry Mode", options=_em_opts,
                                              index=_em_opts.index(_em_default),
                                              format_func=lambda x: "Market (close)" if x == "close" else "Limit (body%)",
                                              horizontal=True, key=f"{sk}_entry_mode")
                    with enm2:
                        if entry_mode == "range_percent":
                            entry_percent = st.number_input("Entry %",
                                                            value=float(st.session_state.get(f"{sk}_entry_pct", params.get('entry_percent', 10.0))),
                                                            min_value=0.0, max_value=100.0, step=1.0, format="%.0f",
                                                            key=f"{sk}_entry_pct")
                        else:
                            entry_percent = 0.0
                    limit_order_candles = 1
                else:
                    entry_mode = "close"
                    entry_percent = 0.0
                    limit_order_candles = st.number_input("Limit Order Candles",
                                                          value=int(st.session_state.get(f"{sk}_loc", 1)),
                                                          min_value=1, max_value=50, key=f"{sk}_loc",
                                                          help="Số nến tối đa để chờ stop order fill")
        else:
            # Master Candle — no Entry zone, set defaults
            ema_period = None
            h2_exceed_pips = 0.0
            c2_gap_pips = 0.0
            ema_margin_pips = 0.0
            c2_wick_filter_enabled = False
            c2_wick_max_percent = 30.0
            ema_filter_enabled = True
            buy_ema_side = "below_ema"
            sell_ema_side = "above_ema"
            entry_start_time = time(0, 0)
            entry_end_time = time(23, 59)
            entry_mode = "close"
            entry_percent = 0.0
            limit_order_candles = 1

        # ── ZONE 3: ORDER SETTINGS ────────────────────────────────────────
        with st.expander("Order Settings", expanded=False):
            os1, os2 = st.columns(2)
            with os1:
                buffer_k = st.number_input("Buffer K (pips)",
                                           value=float(st.session_state.get(f"{sk}_buffer_k", params.get('buffer_k', 5))),
                                           min_value=0.0, max_value=200.0, step=1.0, key=f"{sk}_buffer_k",
                                           help="SL = candle body + k pips")
            with os2:
                re_entry_after_sl = st.checkbox("Re-Entry After SL",
                                                value=bool(st.session_state.get(f"{sk}_re_entry_after_sl", False)),
                                                key=f"{sk}_re_entry_after_sl",
                                                help="Trong lúc lệnh đang chạy, bot vẫn scan signal. "
                                                     "Nếu SL hit đúng tại candle2 của signal mới → vào lệnh tiếp ngay.")

        # ── ZONE 4: RISK & SIZING ─────────────────────────────────────────
        with st.expander("Risk & Sizing", expanded=False):
            lot_mode = st.radio("Lot Mode", options=["fixed", "flex"],
                                format_func=lambda x: "Fixed" if x == "fixed" else "Flex (Risk-based)",
                                horizontal=True, key=f"{sk}_lot_mode")
            if lot_mode == "fixed":
                rs1, rs2 = st.columns(2)
                with rs1:
                    lot_size = st.number_input("Lot Size",
                                               value=float(st.session_state.get(f"{sk}_lot", params.get('lot_size', 0.01))),
                                               min_value=0.01, max_value=10.0, step=0.01, format="%.2f",
                                               key=f"{sk}_lot")
                risk_mode = "percent"
                risk_percent = 0.5
                risk_amount = 0.0
            else:
                rs1, rs2, rs3 = st.columns(3)
                with rs1:
                    _rm_opts = ["percent", "fixed_amount"]
                    _rm_default = st.session_state.get(f"{sk}_risk_mode", "percent")
                    risk_mode = st.radio("Risk Mode", options=_rm_opts,
                                        index=_rm_opts.index(_rm_default),
                                        format_func=lambda x: "%" if x == "percent" else "Fixed $",
                                        horizontal=True, key=f"{sk}_risk_mode")
                with rs2:
                    if risk_mode == "percent":
                        risk_percent = st.number_input("Risk %",
                                                       value=float(st.session_state.get(f"{sk}_risk_pct", 0.5)),
                                                       min_value=0.1, max_value=5.0, step=0.1, format="%.1f",
                                                       key=f"{sk}_risk_pct")
                        risk_amount = 0.0
                    else:
                        risk_amount = st.number_input("Risk $",
                                                      value=float(st.session_state.get(f"{sk}_risk_amt", 5.0)),
                                                      min_value=1.0, max_value=1000.0, step=1.0, format="%.2f",
                                                      key=f"{sk}_risk_amt")
                        risk_percent = 0.0
                lot_size = 0.01

        # ── ZONE 5: EXIT ──────────────────────────────────────────────────
        with st.expander("Exit", expanded=False):
            ex1, ex2, ex3, ex4 = st.columns(4)
            with ex1:
                _tp_opts = ["price_based", "close_based"]
                tp_type = st.radio("TP Exit", options=_tp_opts,
                                   index=_tp_opts.index(st.session_state.get(f"{sk}_tp_type", params.get('tp_type', 'price_based'))),
                                   format_func=lambda x: "Price-based (wick)" if x == "price_based" else "Close-based",
                                   horizontal=True, key=f"{sk}_tp_type")
            with ex2:
                _sl_opts = ["price_based", "close_based"]
                sl_type = st.radio("SL Exit", options=_sl_opts,
                                   index=_sl_opts.index(st.session_state.get(f"{sk}_sl_type", params.get('sl_type', 'close_based'))),
                                   format_func=lambda x: "Price-based (wick)" if x == "price_based" else "Close-based",
                                   horizontal=True, key=f"{sk}_sl_type")
            with ex3:
                be_enabled = st.checkbox("Break-Even (BE)",
                                         value=bool(st.session_state.get(f"{sk}_be_enabled", False)),
                                         key=f"{sk}_be_enabled",
                                         help="Dời SL về entry khi lời đủ be_r × SL distance")
            with ex4:
                be_r = st.number_input("BE Trigger (R)",
                                       value=float(st.session_state.get(f"{sk}_be_r", 1.0)),
                                       min_value=0.1, max_value=10.0, step=0.1, format="%.1f",
                                       key=f"{sk}_be_r",
                                       help="BE kích hoạt khi lời đạt be_r × SL distance",
                                       disabled=not be_enabled)
    # end New layout
```

- [ ] **Step 2: Verify syntax**

```powershell
cd e:\Project\BotForex
python -m py_compile pages/1_Bots.py
```
Expected: no output.

- [ ] **Step 3: Smoke test in browser**

Navigate to Bots page → Create Bot.  
Select "New" layout:
- Verify 5 expanders appear: General (open), Entry (open for FEG strategies, hidden for Master Candle), Order Settings (closed), Risk & Sizing (closed), Exit (closed).
- Switch strategy to Master Candle → Entry expander disappears.
- Start a test bot → verify `start_bot()` receives correct values (check terminal logs or bot info).

- [ ] **Step 4: Commit**

```powershell
git add pages/1_Bots.py
git commit -m "feat: add 5-zone new layout to Bots page"
```

---

## Task 3: Layout selector + gate in `pages/5_Backtest.py`

**Files:**
- Modify: `pages/5_Backtest.py` — add selector radio + gate around existing layout block

**Interfaces:**
- Produces: `layout_version` variable (`"New"` or `"Classic"`) available to Task 4

The existing compact toggle is at line 109. The layout block spans lines 117–553. The `run_backtest()` call is at line 579.

- [ ] **Step 1: Read the file to confirm exact structure**

Open `pages/5_Backtest.py`. Confirm:
- Line 109: `use_compact = st.toggle("Compact layout", ...)`
- Line 117: `if use_compact:`
- Line 346: `else:` (full layout branch)
- Line 553: end of full layout (last `st.divider()`)
- Line 555: `if st.button("Run Backtest", ...)`

- [ ] **Step 2: Add layout version selector after the compact toggle (line 111)**

Find:
```python
    use_compact = st.toggle("Compact layout", value=st.session_state.get("backtest_compact_layout", True),
                            key="backtest_compact_layout",
                            help="Switch between compact grid and classic expanded layout")

    strategy_options = {s['name']: s['id'] for s in enabled_strategies}
```

Replace with:
```python
    use_compact = st.toggle("Compact layout", value=st.session_state.get("backtest_compact_layout", True),
                            key="backtest_compact_layout",
                            help="Switch between compact grid and classic expanded layout")

    layout_version = st.radio(
        "Layout version",
        ["New", "Classic"],
        index=["New", "Classic"].index(st.session_state.get("backtest_layout_version", "New")),
        horizontal=True,
        key="backtest_layout_version",
        help="New: 5-zone layout. Classic: original layout. Resets to New on page refresh.",
    )

    strategy_options = {s['name']: s['id'] for s in enabled_strategies}
```

- [ ] **Step 3: Wrap existing layout block with Classic gate**

Find `if use_compact:` at line 117 (now slightly shifted). Wrap with:
```python
    if layout_version == "Classic":
        if use_compact:
            # ── COMPACT LAYOUT ─── (existing code untouched)
```

And the matching `else:` for full layout becomes:
```python
        else:
            # ── OLD LAYOUT ─── (existing code untouched)
```

After the last `st.divider()` of the full layout block (end of current `else` branch), close with:
```python
    # end Classic layout
```

- [ ] **Step 4: Verify syntax**

```powershell
cd e:\Project\BotForex
python -m py_compile pages/5_Backtest.py
```
Expected: no output.

- [ ] **Step 5: Smoke test**

Navigate to Backtest page. Select "Classic" → existing layout appears. Select "New" → currently shows nothing (Task 4). No errors.

- [ ] **Step 6: Commit**

```powershell
git add pages/5_Backtest.py
git commit -m "feat: add layout version selector to Backtest page (Classic gate)"
```

---

## Task 4: New layout implementation in `pages/5_Backtest.py`

**Files:**
- Modify: `pages/5_Backtest.py` — add new 5-zone layout block when `layout_version == "New"`

**Interfaces:**
- Consumes: `layout_version` (Task 3), `selected_strategy`, `selected_strategy_name`, `params`, `is_pattern`, `is_feg_stop_order`, `_pf()` helper, `default_start`, `default_end`
- Produces: all variables needed by `run_backtest()` at line 579 and `backtest_config` dict: `symbol`, `timeframe`, `start_date`, `end_date`, `rr_ratio`, `max_candles`, `ema_period`, `h2_exceed_pips`, `c2_gap_pips`, `ema_margin_pips`, `c2_wick_filter_enabled`, `c2_wick_max_percent`, `ema_filter_enabled`, `buy_ema_side`, `sell_ema_side`, `entry_start_time`, `entry_end_time`, `entry_mode`, `entry_percent`, `limit_order_candles`, `buffer_k`, `re_entry_after_sl`, `lot_mode`, `fixed_lot`, `risk_mode`, `risk_percent`, `risk_amount`, `starting_equity`, `tp_type`, `sl_type`, `be_enabled`, `be_r`, `entry_time`

Note: `entry_time` used by `run_backtest()` — for pattern strategies set to `datetime.strptime("00:00", "%H:%M").time()`, for time strategies set by the existing time picker logic (copy from classic layout).

- [ ] **Step 1: Locate insertion point**

In `pages/5_Backtest.py`, find the `# end Classic layout` comment added in Task 3. The new layout block goes immediately after it, before the `if st.button("Run Backtest", ...)` line.

- [ ] **Step 2: Add new layout block**

After `# end Classic layout`, insert:

```python
    if layout_version == "New":
        # ── ZONE 1: GENERAL ──────────────────────────────────────────────
        with st.expander("General", expanded=True):
            gc1, gc2, gc3, gc4, gc5, gc6 = st.columns([2, 2, 1, 1, 1, 1])
            strategy_symbols = params.get('symbols', [])
            strategy_timeframe = params.get('timeframe', 'M5')
            with gc1:
                use_custom_symbol = st.checkbox("Custom symbol", value=False)
                if use_custom_symbol:
                    symbol = st.text_input("Symbol", value=os.getenv("SYMBOL", "XAUUSD"))
                elif strategy_symbols:
                    symbol = st.selectbox("Symbol", options=strategy_symbols)
                else:
                    symbol = st.text_input("Symbol", value=os.getenv("SYMBOL", "XAUUSD"))
            with gc2:
                timeframe_options = ["M1", "M5", "M15", "M30", "H1", "H4", "D1"]
                use_custom_timeframe = st.checkbox("Custom TF", value=False)
                if use_custom_timeframe:
                    timeframe = st.selectbox("Timeframe", options=timeframe_options,
                                             index=timeframe_options.index(strategy_timeframe))
                else:
                    timeframe = strategy_timeframe
                    st.selectbox("Timeframe", options=[strategy_timeframe], disabled=True)
            with gc3:
                start_date = st.date_input("Start Date", value=default_start, max_value=default_end)
            with gc4:
                end_date = st.date_input("End Date", value=default_end, max_value=default_end)
            with gc5:
                rr_ratio = st.number_input("RR Ratio",
                                           value=float(_pf('rr_ratio', params.get('rr_ratio', 2.0))),
                                           min_value=0.1, max_value=20.0, step=0.1, format="%.1f")
            with gc6:
                _use_mc = st.checkbox("Limit candles", value=True)
                if _use_mc:
                    max_candles = st.number_input("Max Candles",
                                                  value=int(_pf('max_candles', params.get('max_candles', 7))),
                                                  min_value=1, max_value=500)
                else:
                    max_candles = None

        # ── ZONE 2: ENTRY ─────────────────────────────────────────────────
        if is_pattern:
            with st.expander("Entry", expanded=True):
                # Sub-section: FEG Margins
                st.caption("**FEG Margins**")
                em1, em2, em3, em4, em5, em6 = st.columns(6)
                with em1:
                    ema_period = st.number_input("EMA Period",
                                                 value=int(_pf('ema_period', params.get('ema_period', 21))),
                                                 min_value=2, max_value=200)
                with em2:
                    h2_exceed_pips = st.number_input("H2 > H1 + N pips",
                                                     value=float(_pf('h2_exceed_pips', params.get('h2_exceed_pips', 0.0))),
                                                     min_value=0.0, step=1.0,
                                                     help="SELL: H2 phải vượt H1 thêm N pips | BUY: L2 phải thấp hơn L1 thêm N pips")
                    st.caption(_pip_caption(h2_exceed_pips, symbol))
                with em3:
                    c2_gap_pips = st.number_input("C2 vượt L1/H1 + N pips",
                                                  value=float(_pf('c2_gap_pips', params.get('c2_gap_pips', 0.0))),
                                                  min_value=0.0, step=1.0,
                                                  help="SELL: C2 phải đóng thấp hơn L1 thêm N pips | BUY: C2 phải đóng cao hơn H1 thêm N pips")
                    st.caption(_pip_caption(c2_gap_pips, symbol))
                with em4:
                    ema_margin_pips = st.number_input("L2/H2 cách EMA + N pips",
                                                      value=float(_pf('ema_margin_pips', params.get('ema_margin_pips', 0.0))),
                                                      min_value=0.0, step=1.0,
                                                      help="SELL: L2 phải cách EMA ≥ N pips | BUY: H2 phải cách EMA ≥ N pips")
                    st.caption(_pip_caption(ema_margin_pips, symbol))
                with em5:
                    c2_wick_filter_enabled = st.checkbox("C2 Wick Filter",
                                                         value=bool(_pf('c2_wick_filter_enabled', False)),
                                                         help="Râu nến C2 phải nhỏ hơn n% body C2.")
                with em6:
                    c2_wick_max_percent = st.number_input("Wick Max % of Body",
                                                          value=float(_pf('c2_wick_max_percent', 30.0)),
                                                          min_value=1.0, max_value=200.0, step=1.0, format="%.0f",
                                                          disabled=not c2_wick_filter_enabled)

                st.divider()
                # Sub-section: EMA Direction
                st.caption("**EMA Direction**")
                ed1, ed2, ed3 = st.columns(3)
                with ed1:
                    ema_filter_enabled = st.checkbox("EMA Filter",
                                                     value=bool(_pf('ema_filter_enabled', params.get('ema_filter_enabled', True))),
                                                     help="Bật/tắt điều kiện EMA cho tín hiệu entry")
                with ed2:
                    _ema_side_opts = ["above_ema", "below_ema"]
                    buy_ema_side = st.selectbox("BUY EMA side", options=_ema_side_opts,
                                                index=_ema_side_opts.index(_pf('buy_ema_side', params.get('buy_ema_side', 'below_ema'))),
                                                format_func=lambda x: "H2 > EMA (above)" if x == "above_ema" else "H2 < EMA (below)",
                                                disabled=not ema_filter_enabled)
                with ed3:
                    sell_ema_side = st.selectbox("SELL EMA side", options=_ema_side_opts,
                                                 index=_ema_side_opts.index(_pf('sell_ema_side', params.get('sell_ema_side', 'above_ema'))),
                                                 format_func=lambda x: "L2 > EMA (above)" if x == "above_ema" else "L2 < EMA (below)",
                                                 disabled=not ema_filter_enabled)

                st.divider()
                # Sub-section: Time Window
                st.caption("**Time Window**")
                tw1, tw2 = st.columns(2)
                with tw1:
                    entry_start_time = st.time_input("Entry Start (HCM)", value=time(0, 0),
                                                     help="Gate entries from this time. 00:00 = no filter.")
                with tw2:
                    entry_end_time = st.time_input("Entry End (HCM)", value=time(23, 59),
                                                   help="Gate entries until this time. 23:59 = no filter.")
                entry_time = datetime.strptime("00:00", "%H:%M").time()

                st.divider()
                # Sub-section: Entry Mode
                st.caption("**Entry Mode**")
                if not is_feg_stop_order:
                    enm1, enm2 = st.columns(2)
                    with enm1:
                        _em_opts = ["close", "range_percent"]
                        entry_mode = st.radio("Entry Mode", options=_em_opts,
                                              index=_em_opts.index(_pf('entry_mode', params.get('entry_mode', 'close'))),
                                              format_func=lambda x: "Market (close)" if x == "close" else "Limit (body%)",
                                              horizontal=True)
                    with enm2:
                        if entry_mode == "range_percent":
                            entry_percent = st.number_input("Entry %",
                                                            value=float(_pf('entry_percent', params.get('entry_percent', 10.0))),
                                                            min_value=0.0, max_value=100.0, step=1.0, format="%.0f")
                        else:
                            entry_percent = 0.0
                    limit_order_candles = 1
                else:
                    entry_mode = "close"
                    entry_percent = 0.0
                    limit_order_candles = st.number_input("Limit Order Candles",
                                                          value=int(_pf('limit_order_candles', 1)),
                                                          min_value=1, max_value=50,
                                                          help="Số nến tối đa để chờ stop order fill")
        else:
            # Master Candle — no Entry zone
            ema_period = int(params.get('ema_period', 21))
            h2_exceed_pips = 0.0
            c2_gap_pips = 0.0
            ema_margin_pips = 0.0
            c2_wick_filter_enabled = False
            c2_wick_max_percent = 30.0
            ema_filter_enabled = True
            buy_ema_side = "below_ema"
            sell_ema_side = "above_ema"
            entry_start_time = time(0, 0)
            entry_end_time = time(23, 59)
            entry_mode = "close"
            entry_percent = 0.0
            limit_order_candles = 1
            # time-based entry time picker (Master Candle)
            entry_time_str = params.get('entry_time', '21:05')
            use_custom_time = st.checkbox("Custom entry time", value=False)
            if use_custom_time:
                raw = st.text_input("Entry Time (HH:MM)", value="21:05", max_chars=5)
                try:
                    entry_time = datetime.strptime(raw, "%H:%M").time()
                except ValueError:
                    st.error("Use HH:MM format")
                    entry_time = datetime.strptime("21:05", "%H:%M").time()
            else:
                entry_time = st.time_input("Entry Time", value=datetime.strptime(entry_time_str, "%H:%M").time(),
                                           step=300, disabled=True)
                st.caption(f"Strategy default: {entry_time_str}")

        # ── ZONE 3: ORDER SETTINGS ────────────────────────────────────────
        with st.expander("Order Settings", expanded=False):
            os1, os2 = st.columns(2)
            with os1:
                buffer_k = st.number_input("Buffer K (pips)",
                                           value=float(_pf('buffer_k', params.get('buffer_k', 5))),
                                           min_value=0.0, max_value=200.0, step=1.0,
                                           help="SL = candle body + k pips")
            with os2:
                re_entry_after_sl = st.checkbox("Re-Entry After SL",
                                                value=bool(_pf('re_entry_after_sl', False)),
                                                help="Trong lúc lệnh đang chạy, vẫn scan signal song song. "
                                                     "Nếu SL hit đúng tại candle2 của signal mới → vào lệnh tiếp ngay.")

        # ── ZONE 4: RISK & SIZING ─────────────────────────────────────────
        with st.expander("Risk & Sizing", expanded=False):
            lot_mode = st.radio("Lot Mode", options=["fixed", "flex"],
                                format_func=lambda x: "Fixed" if x == "fixed" else "Flex (Risk-based)",
                                horizontal=True)
            if lot_mode == "fixed":
                rs1, _ = st.columns(2)
                with rs1:
                    fixed_lot = st.number_input("Lot Size",
                                                value=float(_pf('fixed_lot', params.get('lot_size', 0.01))),
                                                min_value=0.01, max_value=10.0, step=0.01, format="%.2f")
                risk_percent = 0.5
                risk_amount = 0.0
                risk_mode = "percent"
                starting_equity = 1000.0
            else:
                rs1, rs2, rs3 = st.columns(3)
                with rs1:
                    starting_equity = st.number_input("Starting Equity ($)",
                                                      value=float(_pf('starting_equity', 1000.0)),
                                                      min_value=100.0, step=100.0)
                with rs2:
                    risk_mode = st.radio("Risk Mode", options=["percent", "fixed_amount"],
                                         format_func=lambda x: "%" if x == "percent" else "Fixed $",
                                         horizontal=True)
                with rs3:
                    if risk_mode == "percent":
                        risk_percent = st.number_input("Risk %",
                                                       value=float(_pf('risk_percent', 0.5)),
                                                       min_value=0.1, max_value=5.0, step=0.1, format="%.1f")
                        risk_amount = 0.0
                        st.caption(f"${starting_equity:.0f} × {risk_percent}% = ${starting_equity * risk_percent / 100:.2f}/trade")
                    else:
                        risk_amount = st.number_input("Risk $",
                                                      value=float(_pf('risk_amount', 5.0)),
                                                      min_value=1.0, max_value=1000.0, step=1.0, format="%.2f")
                        risk_percent = 0.0
                fixed_lot = 0.01

        # ── ZONE 5: EXIT ──────────────────────────────────────────────────
        with st.expander("Exit", expanded=False):
            ex1, ex2 = st.columns(2)
            with ex1:
                _tp_opts = ["price_based", "close_based"]
                tp_type = st.radio("TP Exit", options=_tp_opts,
                                   index=_tp_opts.index(_pf('tp_type', params.get('tp_type', 'price_based'))),
                                   format_func=lambda x: "Price-based (wick)" if x == "price_based" else "Close-based",
                                   horizontal=True)
                st.caption("TP triggers when price TOUCHES TP level" if tp_type == "price_based"
                            else "TP triggers when candle CLOSES past TP level")
            with ex2:
                _sl_opts = ["price_based", "close_based"]
                sl_type = st.radio("SL Exit", options=_sl_opts,
                                   index=_sl_opts.index(_pf('sl_type', params.get('sl_type', 'close_based'))),
                                   format_func=lambda x: "Price-based (wick)" if x == "price_based" else "Close-based",
                                   horizontal=True)
                st.caption("SL triggers when price TOUCHES SL level" if sl_type == "price_based"
                            else "SL triggers when candle CLOSES beyond SL level")
            ex3, ex4 = st.columns(2)
            with ex3:
                be_enabled = st.checkbox("Break-Even (BE)",
                                         value=bool(_pf('be_enabled', False)),
                                         help="Dời SL về entry khi lời đủ be_r × SL distance")
            with ex4:
                be_r = st.number_input("BE Trigger (R)",
                                       value=float(_pf('be_r', 1.0)),
                                       min_value=0.1, max_value=10.0, step=0.1, format="%.1f",
                                       help="BE kích hoạt khi lời đạt be_r × SL distance",
                                       disabled=not be_enabled)
    # end New layout
```

- [ ] **Step 2: Verify syntax**

```powershell
cd e:\Project\BotForex
python -m py_compile pages/5_Backtest.py
```
Expected: no output.

- [ ] **Step 3: Smoke test in browser**

Navigate to Backtest page. Select "New" layout:
- 5 expanders appear: General (open), Entry (open for FEG, hidden for Master Candle), Order Settings / Risk & Sizing / Exit (closed).
- Run a backtest with FEG EMA21 → verify results match Classic layout with same params.
- Switch to Master Candle → Entry zone disappears, entry time picker appears standalone.

- [ ] **Step 4: Commit**

```powershell
git add pages/5_Backtest.py
git commit -m "feat: add 5-zone new layout to Backtest page"
```

---

## Self-Review

**Spec coverage:**
- ✅ 5 zones with exact names: General, Entry, Order Settings, Risk & Sizing, Exit
- ✅ General + Entry expanded=True, rest expanded=False
- ✅ All session state keys preserved (`{sk}_*` in Bots, no-key in Backtest compact matching `_pf()`)
- ✅ Entry zone hidden for Master Candle
- ✅ Limit Order Candles only for Stop Order, Entry Mode/% only for EMA21
- ✅ Test Mode + Interval only in Bots
- ✅ Start/End Date + Starting Equity only in Backtest
- ✅ Layout selector per-page, session-only, default "New"
- ✅ Classic layout code untouched (wrapped in `if layout_version == "Classic":`)
- ✅ Both compact and non-compact gated under Classic (existing toggle preserved)
- ✅ `start_bot()` and `run_backtest()` signatures unchanged

**Placeholder scan:** No TBD, TODO, or vague steps. All code blocks are complete.

**Type consistency:** All variable names match what `start_bot()` (line 917) and `run_backtest()` (line 579) expect exactly.
