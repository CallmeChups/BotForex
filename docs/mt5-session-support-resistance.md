# Session Support/Resistance MT5 Indicator

Source: [`indicators/SessionSupportResistance.mq5`](../indicators/SessionSupportResistance.mq5)

Indicator chia dữ liệu thành 7 phiên theo giờ server của MT5. Mặc định các
phiên bắt đầu lúc `20:00`, `00:00`, `05:00`, `08:00`, `11:00`, `14:00` và
`18:00`, tương ứng với các phiên trong hình minh họa.

Với mỗi phiên:

- Resistance là `High` cao nhất của các nến trong phiên.
- Support là `Low` thấp nhất của các nến trong phiên.
- Trong phiên kế tiếp, giá hiện hành (`Bid`, fallback `Last`) vượt resistance
  hoặc support sẽ đánh dấu mức đó bị phủ định ngay lập tức.
- Mức bị phủ định vẫn hiển thị trong phiên đang phá cản và được xóa khi phiên
  đó kết thúc.
- Mỗi phiên vẫn tạo một cặp support/resistance riêng.
- Cản chưa bị phủ định được kéo từ đầu phiên tới thời điểm hiện tại. Cản đã bị
  phủ định vẫn hiện trong phiên phá cản, rồi biến mất khi phiên đó kết thúc.
- Chỉ hiển thị cản thuộc `SoPhienHienThi` phiên gần nhất còn ít nhất một cản
  chưa bị phủ định; mặc định là `7`.
- Nhãn `HH:00 R` và `HH:00 S` cho biết giờ bắt đầu phiên và loại cản; có thể
  tắt bằng input `HienThiNhanPhien`.

Các input giờ là giờ server MT5, không phải giờ địa phương của máy tính.
Indicator dùng tick hiện tại để xử lý realtime; khi nạp lại lịch sử, `High` và
`Low` của phiên kế tiếp được dùng để tái dựng trạng thái đã phủ định.
