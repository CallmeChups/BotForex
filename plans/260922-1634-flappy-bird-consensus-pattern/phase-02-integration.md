# Phase 02 — Tích hợp config, live, backtest và UI

## Context

- Config: `D:\Project\BotForex\strategies\multi_flappy_bird.yaml`
- Parameter loader: `D:\Project\BotForex\src\strategy_manager.py`
- Live runner: `D:\Project\BotForex\src\bot_runner.py`
- Backtest engine: `D:\Project\BotForex\src\backtest.py`
- Bot UI: `D:\Project\BotForex\pages\1_Bots.py`
- Backtest UI: `D:\Project\BotForex\pages\5_Backtest.py`

## Strategy selection and compatibility

- `flappy_bird`: legacy strategy, giữ UI, params và behavior hiện tại.
- `multi_flappy_bird`: strategy mới cho M1 + HTF, thêm `use_mother_candle`
  và nhóm `no_mother_*`.
- Dùng `is_multi_flappy_strategy` cho widget/params mới; không đưa controls
  no-mother vào nhánh `is_flappy_strategy` chung.
- Default selector giữ `flappy_bird` để user cũ không bị đổi bot. User chọn
  Multi Flappy Bird một cách chủ động để dùng pattern mới.

## Configuration

Thêm vào `entry` hoặc `parameters` một nhóm có tên nhất quán:

- `use_mother_candle: true` — default bảo toàn hành vi hiện tại.
- `no_mother_father_wick_max_pct: 40.0`.
- `no_mother_child_body_ratio: 1.5`.
- `no_mother_child_body_max_points: 1.5`.
- `no_mother_cross_window_candles: 15` — tuổi cross EMA8/EMA13 trên M1 đến
 Nến Cha.
- `no_mother_sl_buffer_pips: 5.0`.
- `no_mother_child_candles: 2` — số Con bắt buộc ở mode không Mẹ.

Các giá trị trên là config độc lập của mode không Mẹ. UI cho phép chỉnh,
CLI cho phép override khi chạy bot/backtest, YAML là default. Không dùng
`sl_buffer_pips`, `max_child_body_points` hoặc `cross_window_candles` chung
để vô tình thay đổi mode có Mẹ.
- Các cờ M1/M5 giữ độc lập; không tắt ngầm higher-timeframe filter.

`get_strategy_parameters` phải validate kiểu, miền giá trị và trả params cho
mọi caller. Không để stale widget values làm bot khởi động sai.

## Live bot

- Thêm CLI arg và command-builder arg cho switch/thresholds.
- Truyền params vào `run_feg_bot` và `analyze_flappy_bird`.
- Khi không có Mẹ, vòng scan phải lấy đúng 2 Con + Cha, không trừ thêm một
  candle cho vị trí Mẹ.
- Resolve và validate toàn bộ no-mother config một lần lúc startup; log các
  giá trị thực tế cùng strategy label.
- Log/Telegram signal phải ghi pattern mode, EMA mode và HTF validation.

## Backtest

- Truyền params qua `run_backtest` và `_run_flappy_bird_backtest`.
- Giữ shared scan cho consensus/fallback.
- Lưu debug fields tương ứng với mode; chart audit không được giả định luôn
  tồn tại `_mother`.
- Kết quả live/backtest phải dùng cùng bounded EMA window, closed HTF candle,
  entry, SL/TP và pending expiry.

## UI

- `1_Bots.py`: thêm checkbox/selectbox “Sử dụng Nến Mẹ” trong khu vực Chim bay.
- `5_Backtest.py`: cùng widget, default lấy YAML.
- Chỉ render switch/threshold no-mother khi selected strategy là
  `multi_flappy_bird`; Flappy Bird cũ giữ nguyên form.
- Khi tắt Mẹ, hiển thị và cho chỉnh riêng số Con, tỷ lệ body Cha, max body
  Con, wick %, cross window và SL buffer; không tái sử dụng nhầm widget của
  mode có Mẹ.
- Hiển thị ngưỡng thực tế trong signal debug và lưu vào trade metadata.
- Signal Debug hiển thị “Có Nến Mẹ” hoặc “Không có Nến Mẹ” và check list tương ứng.
- Không đổi setting của FEG hoặc Flappy Bird thường ngoài phần dùng chung cần
  thiết.

## Files

- Modify: `D:\Project\BotForex\strategies\multi_flappy_bird.yaml`
- Modify: `D:\Project\BotForex\src\strategy_manager.py`
- Modify: `D:\Project\BotForex\src\bot_runner.py`
- Modify: `D:\Project\BotForex\src\backtest.py`
- Modify: `D:\Project\BotForex\pages\1_Bots.py`
- Modify: `D:\Project\BotForex\pages\5_Backtest.py`
- Modify: `D:\Project\BotForex\src\bot_manager.py` if command serialization requires it

## Existing UI risks

- `is_multi_flappy` hiện là subset của `is_flappy_bird`; thêm widget vào nhánh
  Flappy chung sẽ làm thay đổi UI Flappy Bird cũ.
- `pages/5_Backtest.py` có block Multi Flappy đang bị guard bởi
  `if False and is_multi_flappy`; không bật mù block này. Cần hợp nhất
  defaults và widgets trong nhánh Multi rõ ràng, bảo đảm mọi biến được khởi
  tạo cho cả strategy.
- `bot_manager.build_bot_command` dùng danh sách positional args dài; params
  mới phải ưu tiên keyword hoặc gom config object để không lệch thứ tự.
- Backtest history cũ thiếu no-mother keys; migration fallback về
  `use_mother_candle=true` và config YAML.

## Success Criteria

- Toggle được truyền đúng từ UI đến subprocess.
- Default config tạo command/behavior tương thích hiện tại.
- Backtest no-mother sinh trade và hiển thị audit đúng.
- Live runner không gửi duplicate signal do thay đổi cửa sổ scan.
