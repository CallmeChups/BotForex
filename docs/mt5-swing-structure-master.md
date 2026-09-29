# Swing Structure Master cho MT5

## Mục đích

`SwingStructureMaster.mq5` là indicator cho MetaTrader 5, dùng để xác định
đỉnh/đáy và cấu trúc swing trên biểu đồ. Indicator hiện hiển thị swing bằng
dấu chấm màu, tùy chọn nối các swing bằng đường.

Mã nguồn:

- [SwingStructureMaster.mq5](../indicators/SwingStructureMaster.mq5)

## Cài đặt

1. Mở MT5 Exness.
2. Chọn **File → Open Data Folder**.
3. Mở thư mục:

   ```text
   MQL5\Indicators\
   ```

4. Có thể đặt file trong thư mục con, ví dụ:

   ```text
   MQL5\Indicators\Homemade Indicators\
   ```

5. Mở MetaEditor bằng `F4`.
6. Mở file `SwingStructureMaster.mq5`.
7. Nhấn `F7` để biên dịch.
8. Kết quả mong muốn:

   ```text
   0 errors, 0 warnings
   ```

9. Quay lại MT5, nhấp phải vào **Navigator → Indicators → Refresh**.
10. Kéo indicator vào biểu đồ.

MetaEditor sẽ tự tạo file `.ex5`; không cần tự tạo file này.

## Giao diện hiển thị

- Dấu chấm màu đỏ/cam: đỉnh.
- Dấu chấm xanh: đáy.
- Đường màu xám: đường nối swing, có thể tắt.
- Indicator không hiển thị chữ `Đỉnh cao hơn`, `Đỉnh thấp hơn`, `Đáy cao hơn`
  hoặc `Đáy thấp hơn` trong phiên bản tối giản hiện tại.

Các điểm gần giá hiện tại chỉ xuất hiện sau khi đủ số nến xác nhận. Vì vậy điểm
mới có thể trễ một số nến tùy chế độ và thông số.

## Các chế độ xác định swing

### Đường nối đỉnh đáy

Phù hợp khi muốn lọc các swing lớn hơn. Chế độ này dùng độ sâu và khoảng đảo
chiều tối thiểu. Nếu khoảng đảo chiều đặt bằng `0`, indicator tự dùng ATR.

Thông số:

- `Độ sâu`: số nến dùng để xác định một swing.
- `Đảo chiều tối thiểu`: khoảng giá tối thiểu, tính theo point.
- `Chiều dài ATR`: số nến dùng để tính ATR khi tự động lọc.
- `Hệ số ATR`: nhân với ATR để tạo ngưỡng lọc.

### Nến mẫu

Một đỉnh được xác nhận khi giá cao hơn các nến ở bên trái và bên phải. Một đáy
được xác nhận khi giá thấp hơn các nến ở hai bên.

Thông số:

- `Số nến phía bên trái`.
- `Số nến phía bên phải`.
- `Khoảng cách giá tối thiểu`.

Giá trị `2` và `2` là cấu hình fractal phổ biến. Tăng số nến sẽ lọc nhiều
nhiễu hơn nhưng tín hiệu xuất hiện trễ hơn.

### Tùy chỉnh

Cho phép kiểm soát chi tiết hơn:

- Số nến bên trái/phải.
- Khoảng cách giá tối thiểu giữa các swing cùng loại.
- Số nến tối thiểu giữa hai điểm.
- Bộ lọc ATR bổ sung.

Đây là chế độ phù hợp để thử nghiệm và tinh chỉnh theo từng mã giao dịch,
khung thời gian.

## Cấu hình hiển thị

- `Hiển thị đường nối`: bật/tắt đường nối giữa các swing.
- `Màu đỉnh`: màu dấu chấm tại đỉnh.
- `Màu đáy`: màu dấu chấm tại đáy.
- `Màu đường nối`: màu đường nối.
- `Độ rộng đường nối`: độ dày đường nối.

## Lưu ý khi sử dụng

- Chỉ nên gắn một instance của indicator trên cùng biểu đồ.
- Sau khi thay đổi mã nguồn, phải biên dịch lại bằng `F7`.
- Nếu biểu đồ còn đối tượng cũ, nhấn `Ctrl+B`, xóa các đối tượng có tiền tố
  `SwingStructureMaster_`, rồi thêm indicator lại.
- Không đánh giá swing chưa đủ nến xác nhận như một tín hiệu hoàn chỉnh.
- Nên kiểm tra trên tài khoản demo trước khi dùng dữ liệu indicator cho EA.

## Buffer vào lệnh của Swing EMA ZigZag

Trong strategy `swing_ema_zigzag`, Stop Order được đặt lệch khỏi pivot để giá
cần đi thêm một khoảng mới kích hoạt lệnh:

- BUY: giá vào lệnh = đỉnh 2 + buffer.
- SELL: giá vào lệnh = đáy 2 - buffer.
- Buffer vào lệnh mặc định là `2.0` pip, cấu hình bằng
  `parameters.entry_buffer_pips` trong
  [`strategies/swing_ema_zigzag.yaml`](../strategies/swing_ema_zigzag.yaml).

Buffer này độc lập với `sl_buffer_pips` (mặc định `5.0` pip), vốn dùng để đặt
Stop Loss ngoài biên nến phát sinh tín hiệu. TP theo R:R được tính từ giá vào
lệnh đã cộng hoặc trừ buffer. Đây là quy tắc của strategy, không phải tham số
của indicator `SwingStructureMaster`.

## Kiểm thử Strategy

- Trang **Bots** và **Backtest** cho phép cấu hình EMA, Depth/Deviation/Back Step,
  khoảng tuổi cấu trúc, giới hạn giao cắt EMA, buffer Entry/SL, thời hạn Stop
  Order và giới hạn số lệnh chờ.
- Backtest mô phỏng Stop Order từ nến sau nến tín hiệu, hủy lệnh hết hạn trước
  khi xét khớp, bỏ tín hiệu nếu Entry đã bị chạm trong nến tạo tín hiệu hoặc SL
  từ nến đó không để lại rủi ro dương, và xét thoát qua TP/SL hoặc EMA thoát lệnh.
- Trong **Trade Analysis → Interactive Chart**, Swing hiển thị EMA ngắn/trung/dài
  cùng ZigZag đã xác nhận. Mở **Swing EMA + ZigZag** để bật/tắt độc lập từng EMA,
  đường ZigZag và dấu pivot. EMA dùng màu xanh ngọc/vàng cam/tím; đường ZigZag
  màu xám; pivot đỉnh màu vàng và đáy màu hồng. Tooltip pivot ghi nến xác nhận;
  điểm được vẽ tại nến pivot, không phải nến xác nhận.
- Chạy kiểm thử tự động bằng `python -m pytest tests\test_backtest_swing_ema.py
  tests\test_swing_ema_runtime.py tests\test_swing_ema_strategy.py
  tests\test_zigzag_swing.py -q`.
- Các kiểm thử tự động không thay thế việc xác minh kết nối MT5. Chưa xác nhận
  luồng giao dịch trên terminal hoặc tài khoản demo; cần kiểm thử riêng trong
  MT5 Test Mode trước khi dùng tài khoản thật.

## Bộ đệm dành cho EA

Indicator có các bộ đệm chính:

- Bộ đệm 0: giá đỉnh.
- Bộ đệm 1: giá đáy.
- Bộ đệm 2: loại swing nội bộ (`1` là đỉnh, `-1` là đáy).
- Bộ đệm 3: giá swing nội bộ.

EA có thể đọc indicator bằng `iCustom()`. Khi triển khai EA, cần xác định rõ
bar nào đã đủ xác nhận và không dùng nến đang chạy làm tín hiệu đã hoàn tất.
