# Phase 03 — Test, audit và tài liệu

## Tests

Mở rộng `D:\Project\BotForex\tests\test_flappy_bird_strategy.py`:

- Valid no-mother BUY.
- Valid no-mother SELL.
- Reject sai biên High/Low của Con với Cha.
- Reject wick theo nhiều config, gồm boundary và vượt ngưỡng.
- Reject child body theo nhiều `no_mother_child_body_ratio` và
  `no_mother_child_body_max_points`.
- Reject cross theo nhiều `no_mother_cross_window_candles`.
- Verify no-mother SL thay đổi đúng theo `no_mother_sl_buffer_pips`.
- Verify `use_mother_candle=True` giữ toàn bộ test hiện tại.
- Verify `use_mother_candle=False` không yêu cầu Mẹ.
- Verify chọn `flappy_bird` không render no-mother widgets và command không
  chứa no-mother args.
- Verify chọn `multi_flappy_bird` render đúng switch/threshold widgets.
- Verify EMA consensus và higher-timeframe checks vẫn chạy.
- Verify signal levels/SL không dùng dữ liệu Mẹ khi mode tắt.

Mở rộng:

- `D:\Project\BotForex\tests\test_bot_command.py` cho CLI serialization.
- Test backtest/live parity trong `test_flappy_bird_strategy.py` hoặc test mới
  nếu fixture HTF cần tách riêng.

## Validation

- Chạy targeted pytest cho Flappy Bird và bot command.
- Chạy toàn bộ pytest sau khi targeted tests pass.
- Chạy type/syntax/import checks cho các file Python đã sửa.
- Kiểm tra một backtest có Mẹ và một backtest không Mẹ bằng cùng data.
- Smoke test UI theo cả hai strategy, gồm đổi strategy qua lại và load history
  cũ.

## Documentation

Cập nhật:

- `D:\Project\BotForex\README.md`
- `D:\Project\BotForex\docs\codebase-guide-vi.md` nếu còn mô tả logic cũ

Ghi rõ:

- Hai pattern mode.
- Default vẫn dùng Mẹ.
- Công thức entry/SL/TP.
- Ngưỡng wick/body/cross window.
- Sự khác nhau giữa consensus hiện hành và fallback.

## Risks

- Thay đổi số lượng candle trong scan có thể làm lệch index entry/fill.
- HTF chưa đóng có thể gây look-ahead nếu mapping sai.
- Các trade history cũ thiếu field mode; audit phải fallback rõ ràng, không
  silent success.
- No-mother thresholds phải khóa bằng fixture biên và test override để tránh
  tạo tín hiệu sai hàng loạt hoặc rơi về default im lặng.
- Thêm params vào command builder positional không cẩn thận có thể làm bot cũ
  nhận sai giá trị; cần regression test command legacy.

## Unresolved Questions

- Không còn câu hỏi nghiệp vụ bắt buộc trước khi triển khai.
