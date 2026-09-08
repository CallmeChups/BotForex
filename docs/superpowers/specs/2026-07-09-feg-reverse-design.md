# FEG Reverse Strategy — Design Spec

**Date:** 2026-07-09  
**Status:** Approved

---

## Overview

FEG Reverse là variant của FEG Classic. Dùng cùng điều kiện phát hiện pattern 2 nến, nhưng đảo chiều lệnh: SELL pattern → vào BUY order, BUY pattern → vào SELL order.

Use case: pattern FEG SELL xuất hiện với râu dưới dài → có thể là tín hiệu đảo chiều lên, user muốn vào BUY thay vì SELL.

---

## Detection Logic

Tái sử dụng hoàn toàn `detect_feg_signal` từ `src/feg_strategy.py`. Không thay đổi logic detect.

- **SELL pattern** (2 nến giảm, H2>H1, C2<L1) → direction thực tế = `"BUY"`
- **BUY pattern** (2 nến tăng, L2<L1, C2>H1) → direction thực tế = `"SELL"`

---

## Wick Filter

Dùng params của **pattern gốc** (không theo chiều lệnh mới):
- Khi detect SELL pattern → dùng `c2_sell_*_wick_*` params
- Khi detect BUY pattern → dùng `c2_buy_*_wick_*` params

Params giữ nguyên 8 params như FEG Classic:
`c2_buy_upper_wick_max_pct`, `c2_buy_lower_wick_max_pct`, `c2_sell_upper_wick_max_pct`, `c2_sell_lower_wick_max_pct` + 4 cmp tương ứng.

---

## EMA Filter

Giữ nguyên theo pattern gốc. User chọn `buy_ema_side` / `sell_ema_side` tự do (above/below đều hợp lệ). `ema_filter_enabled` bật/tắt được.

---

## SL / TP

Neo vào **chiều lệnh mới** (không phải pattern gốc):

| Pattern detected | Lệnh vào | SL | TP |
|---|---|---|---|
| SELL (nến giảm) | BUY | L2 − buffer_k | entry + risk × RR |
| BUY (nến tăng) | SELL | H2 + buffer_k | entry − risk × RR |

Dùng `compute_trade_levels(direction_mới, candle2, ...)` — hàm hiện có xử lý đúng theo direction.

---

## Entry Mode

- `close` — entry tại close C2
- `range_percent` — limit order tại body%

Giống FEG Classic, không có stop order variant.

---

## Architecture

### New files

**`src/feg_reverse_strategy.py`**
- `detect_feg_reverse_signal(...)` — gọi `detect_feg_signal`, đảo direction trả về
- `analyze_feg_reverse(...)` — gọi `detect_feg_reverse_signal`, tính levels theo direction mới qua `compute_trade_levels`
- Signature params giống hệt `feg_strategy.py`

**`strategies/feg_reverse.yaml`**
- `id: feg_reverse`, `name: FEG Reverse`, `entry_type: pattern`
- Cùng default params với `feg_ema21.yaml`

### Modified files

**`src/bot_runner.py`**
- Thêm argparse handler cho `feg_reverse`
- Hàm `run_feg_reverse_bot` — tương tự `run_feg_bot`, dùng `analyze_feg_reverse`

**`src/bot_manager.py`**
- `build_bot_command` nhận `feg_reverse` strategy ID — không cần thay đổi nếu đã generic
- Kiểm tra và thêm nếu cần

**`src/backtest.py`**
- `_run_feg_reverse_backtest` — tương tự `_run_feg_backtest`, dùng `detect_feg_reverse_signal`
- `run_backtest` dispatch `feg_reverse` → `_run_feg_reverse_backtest`

**`pages/1_Bots.py`**, **`pages/5_Backtest.py`**
- Kiểm tra `is_pattern` detection — nếu đã dùng `entry_type == 'pattern'` thì tự động support, không cần sửa UI.

---

## What is NOT changing

- Logic `detect_feg_signal` trong `feg_strategy.py` — không sửa
- UI Wick Filter, ENTRY section — không sửa (đã generic theo `is_pattern`)
- `feg_stop_order` — không liên quan

---

## Out of scope

- Stop order variant cho FEG Reverse
- Bất kỳ thay đổi nào với FEG Classic hay FEG Stop Order
