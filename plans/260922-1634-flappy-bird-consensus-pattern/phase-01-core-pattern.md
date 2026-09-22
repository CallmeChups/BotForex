# Phase 01 — Chuẩn hóa model và điều kiện pattern

## Context

- Core detector: `D:\Project\BotForex\src\flappy_bird_strategy.py`
- Current tests: `D:\Project\BotForex\tests\test_flappy_bird_strategy.py`
- Current implementation bắt buộc `mother`, kiểm tra Mẹ bao phủ Con,
  wick Cha `<30%`, EMA13/EMA21, child body tối đa `2.0`.

## Requirements

### Pattern mode

Thêm tham số rõ nghĩa, ví dụ `use_mother_candle: bool = True`, truyền xuyên
qua `diagnose_flappy_bird`, `detect_flappy_bird_signal`, `analyze_flappy_bird`.

- `True`: giữ pattern hiện tại.
- `False`: dùng chính xác 2 Nến Con + 1 Nến Cha; không kiểm tra hướng/body/
  coverage của Mẹ.

Không ép kiểu hoặc dựng Mẹ giả. Các field debug phải có `mother=None` hoặc
không có field Mẹ và ghi `pattern_mode=without_mother`.

### Shared conditions

Giữ chung cho cả hai mode:

- EMA đồng thuận trên khung hiện hành:
  - BUY: `EMA13 > EMA21 > EMA55`.
  - SELL: `EMA13 < EMA21 < EMA55`.
- Nến Cha cùng hướng với tín hiệu nếu đây là yêu cầu của hình/đặc tả cuối.
- Mức wick, EMA Cha, child containment, child body cap và cross window phải
  là tham số dùng chung, không hard-code riêng live/backtest.

### No-mother conditions from image

Khi tắt Nến Mẹ, triển khai các check độc lập và có key debug ổn định:

- Đúng 2 Nến Con.
- High/Low của hai Con nằm trong biên tương ứng của Cha theo hướng BUY/SELL.
- Wick Cha theo `no_mother_father_wick_max_pct`, mặc định `40%`.
- Điều kiện OPEN Cha với EMA theo đặc tả đã chốt.
- Mỗi body Con `< body Cha / no_mother_child_body_ratio` và
  `< no_mother_child_body_max_points`.
- Tuổi giao cắt EMA8/EMA13 trên M1 từ cross đến Cha `<=
  no_mother_cross_window_candles`.

Tách helper cho geometry của pattern để tránh lặp BUY/SELL và để backtest,
live, audit gọi cùng một logic.

### Trade levels

Giữ `analyze_flappy_bird` trả signal chuẩn. Khi không có Mẹ:

- BUY: `min(LOW hai Con, LOW Cha) -
  no_mother_sl_buffer_pips * pip_value`.
- SELL: `max(HIGH hai Con, HIGH Cha) +
  no_mother_sl_buffer_pips * pip_value`.

Mọi tham số no-mother phải được validate ở boundary:

- Ratio > 0.
- Wick/body percentages trong miền hợp lệ.
- Cross window là số nguyên không âm.
- Buffer không âm.

Detector nhận tham số đã resolve, không tự đọc YAML để giữ pure logic và
đảm bảo live/backtest parity.
- Entry, RR, pending expiry giữ nguyên nếu không có yêu cầu thay đổi.

## Files

- Modify: `D:\Project\BotForex\src\flappy_bird_strategy.py`
- Modify: `D:\Project\BotForex\tests\test_flappy_bird_strategy.py`

## Success Criteria

- Detector trả `valid=True` cho fixture có Mẹ và fixture không Mẹ.
- Detector trả reason/key cụ thể cho từng điều kiện hình bị fail.
- BUY/SELL đối xứng, không thay đổi kết quả test pattern cũ khi bật Mẹ.
