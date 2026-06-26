# FEG EMA21 Strategy — Design Spec

**Ngày:** 2026-06-21
**Trạng thái:** Approved (chờ user review spec)
**Bot mới:** `feg_ema21`

## 1. Mục tiêu

Thêm strategy mới **FEG EMA21** vào hệ thống BotForex hiện có (đang chạy `master_candle`). Khác biệt căn bản: master_candle vào lệnh theo **giờ cố định** (21:05, 1 lệnh/ngày); FEG vào lệnh theo **pattern 2 nến quét liên tục** kèm filter EMA21.

Phạm vi: **toàn bộ cùng lúc** — backtest engine + UI backtest + live runner + strategy YAML + bot manager/UI.

## 2. Logic vào lệnh (FEG pattern)

`candle1` = nến đóng trước đó; `candle2` = nến vừa đóng. `ema2` = giá trị EMA21 tại thời điểm close của candle2. `pip` = `get_pip_value(symbol)`.

### SELL (cặp nến FEG giảm)
- `H2 > H1`
- `C2 < L1`
- Filter EMA (mặc định): `L2 > ema2`
- Filter EMA (khi bật flag "Xét"): `L2 > ema2 + dist_pips × pip`

### BUY (cặp nến FEG tăng)
- `L2 < L1`
- `C2 > H1`
- Filter EMA (mặc định): `H2 < ema2`
- Filter EMA (khi bật flag "Xét"): `H2 < ema2 − dist_pips × pip`

Không thỏa → không có tín hiệu.

**Tham số khoảng cách EMA21:** `ema_distance.enabled` (default `false`), `ema_distance.pips` (đơn vị **pips**). UI chỉ cho nhập `pips` khi tick flag.

## 3. Đặt TP / SL (giống bot cũ, neo vào candle2)

Vì pattern đảm bảo candle2 là cực trị ở phía cần đặt SL (SELL: `H2>H1`; BUY: `L2<L1`), SL luôn neo vào candle2.

- **Entry**: tái dùng `entry_mode` hiện có (`close` / `range_percent`) + `entry_percent`.
- **SELL**: `SL = H2 + buffer_k × pip`; `risk = SL − entry`; `TP = entry − risk × rr_ratio`.
- **BUY**: `SL = L2 − buffer_k × pip`; `risk = entry − SL`; `TP = entry + risk × rr_ratio`.

Tái dùng nguyên engine exit: `check_exit()` (`tp_type`/`sl_type`), `max_candles`, lot fixed/flex (`calculate_flex_lot_size`), tính P&L pips/USD.

## 4. EMA21

- Dùng `df['close'].ewm(span=ema_period, adjust=False).mean()` → series align index với df.
- `ema_period` mặc định 21 (configurable).
- **Warmup**: fetch thêm ~50 nến trước `start_date` (backtest) / lấy đủ history (runner) để EMA21 ổn định trước nến đầu tiên được xét.

## 5. Quy tắc "1 lệnh tại 1 thời điểm"

- **Backtest**: vòng lặp tuần tự theo nến — khi `flat` và phát hiện pattern → mở lệnh; khi đang giữ lệnh → chỉ check exit; exit xong → quét tiếp từ nến kế tiếp. (Khác master_candle: các lệnh master không chồng nhau nên duyệt độc lập.)
- **Runner**: bỏ qua mọi tín hiệu mới khi còn `active_trade`. Không giới hạn số lệnh/ngày.

## 6. Test mode vs Live (cờ `--test`)

Cờ `--test` quyết định chế độ (KHÔNG phải luôn test):
- `test=1` → simulate: log signal + gửi Telegram, **không** gửi lệnh MT5.
- `test=0` → **live**: gọi `src/orders.py::place_order()` (uncomment `mt5.order_send`) đặt lệnh thật; đóng lệnh thật khi exit (`close_position_by_ticket`).

> ⚠️ **Rủi ro tiền thật**: bước này lần đầu bật đường gửi lệnh MT5 thật cho FEG. Cần test kỹ trên tài khoản demo trước. Master_candle giữ nguyên hiện trạng (không đụng), chỉ FEG wire live.

## 7. Kiến trúc (Approach B — cô lập signal detector, dùng chung engine exit)

Discriminator: thêm `entry.type` vào YAML (`time` cho master_candle, `pattern` cho FEG). Thiếu field → mặc định `time` (backward-compat).

### Files thêm mới
- `strategies/feg_ema21.yaml` — config strategy (xem §9).
- `src/feg_strategy.py`:
  - `detect_feg_signal(candle1, candle2, ema2, params) -> dict | None` — trả direction hoặc None.
  - `analyze_feg(symbol, candle1, candle2, ema2, params) -> dict | None` — dựng signal đầy đủ (entry/SL/TP) cho runner.

### Files sửa
- `src/strategy_manager.py` — `get_strategy_parameters()` đọc `entry.type`, `ema_period`, `ema_distance.{enabled,pips}`, `pattern`; vẫn trả các key cũ cho master.
- `src/backtest.py` — tách helper dùng chung:
  - `_compute_levels(direction, anchor_candle, entry_mode, entry_percent, buffer_k, rr_ratio, pip)` → (entry, sl, tp, sl_pips).
  - `_simulate_exit(df, entry_idx, direction, tp, sl, max_candles, tp_type, sl_type)` → (exit_type, exit_price, exit_time, candles_held).
  - `run_backtest()` dispatch theo `entry_type`: `time` → logic cũ; `pattern` → vòng lặp tuần tự FEG dùng `detect_feg_signal` + EMA series + 2 helper trên.
- `src/bot_runner.py` — dispatch theo `entry_type`: `pattern` → vòng lặp lấy 2 nến đóng gần nhất + EMA21, gọi `analyze_feg`, áp dụng "1 lệnh/lúc", gating test flag (live đặt lệnh thật).
- `pages/5_Backtest.py` — UI điều kiện theo `entry_type` của strategy chọn:
  - `pattern`: ẩn Entry Time; hiện EMA Period, checkbox **"Xét khoảng cách EMA21"** + ô nhập `dist_pips` (chỉ khi tick). Giữ nguyên các control Entry mode / Exit types / Lot / buffer_k / RR / max_candles.
  - Bổ sung EMA params vào `backtest_config` (cho history/export).
- `src/bot_manager.py` — `start_bot()` nhận thêm tham số FEG (`ema_distance_enabled`, `ema_distance_pips`, `ema_period`), truyền vào process args; lưu vào `running_bots.json`.
- `src/bot_runner.py` argparse — thêm `--ema_period`, `--ema_distance_enabled`, `--ema_distance_pips`.
- `pages/1_Bots.py` — form tạo bot: khi strategy `pattern`, hiện input EMA + flag; ẩn thông tin entry_time.
- `pages/4_Strategies.py` — hiển thị FEG **read-only** (chưa cần full edit UI).
- `strategies/master_candle.yaml` — thêm `entry.type: time`.

## 8. Dữ liệu / tương thích

- `backtest_history`: thêm cột config EMA (`ema_period`, `ema_dist_enabled`, `ema_dist_pips`) — optional columns, không phá history cũ.
- `orders.csv`: tái dùng format hiện có; magic number riêng cho FEG (vd `212100`) để phân biệt với MasterCandle (`210500`).

## 9. YAML đề xuất (`strategies/feg_ema21.yaml`)

```yaml
id: feg_ema21
name: FEG EMA21 Strategy
version: "1.0"
description: |
  FEG 2-candle pattern + EMA21 filter. Quét liên tục mọi nến.
  SELL: H2>H1, C2<L1, L2>EMA21(+dist). BUY: L2<L1, C2>H1, H2<EMA21(-dist).
  TP/SL neo vào candle2 (giống master_candle): SL = candle2 high/low ± buffer_k,
  TP = entry ± risk × rr_ratio. 1 lệnh tại 1 thời điểm.
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

## 10. Quyết định đã chốt

- Phạm vi: toàn bộ cùng lúc (backtest + runner + YAML + UI).
- Số lệnh: 1 lệnh tại 1 thời điểm, không giới hạn/ngày.
- Đơn vị khoảng cách EMA: **pips**.
- Timeframe default: **M5** (configurable).
- Test mode: theo cờ `--test`; `test=0` đặt lệnh thật.
- Entry mode: tái dùng `close` / `range_percent`.
- EMA: `ewm(span=21, adjust=False)` + warmup.
- Page 4_Strategies: read-only cho FEG.

## 11. Câu hỏi tồn đọng

- Chưa có. (Live order cho master_candle giữ nguyên hiện trạng, ngoài phạm vi.)
