# Điều kiện và tương tác timeframe của Multi Flappy Bird

## 1. Tổng quan Multi Flappy Bird

Multi Flappy Bird là bản clone độc lập của Flappy Bird, dùng:

- Khung hiện hành để tìm mô hình Mẹ/Con/Cha và kiểm tra EMA chính.
- Khung lớn HTF để xác nhận thêm xu hướng.
- Hỗ trợ đồng thời BUY và SELL.
- Magic number mặc định: `212401`.
- Cấu hình mặc định:
  - Khung hiện hành: `M1`.
  - HTF: `M5`.
  - EMA: `13 / 21 / 55`.
  - Số nến Con: `2–5`.
  - Entry offset: `5%` thân Cha.
  - RR: `2R`.
  - Pending expiry: `7` nến.

Cấu hình chính nằm trong [multi_flappy_bird.yaml](../strategies/multi_flappy_bird.yaml).

---

## 2. Điều kiện mô hình Mẹ/Con/Cha

Các điều kiện này được kiểm tra trên **khung hiện hành**.

### BUY

#### Nến Con

- Số lượng Con nằm trong khoảng cấu hình, mặc định `2–5`.
- Có thể thay đổi thành tối đa `7` tùy cấu hình.

#### Nến Mẹ

- Mẹ phải là nến tăng.
- Thân Mẹ lớn hơn thân của tất cả nến Con.
- Nếu bật `mother_coverage_enabled`:
  - `HIGH` của Mẹ phải bao trùm phần thân trên của các nến Con.

#### Nến Cha

- Thân Cha lớn hơn `1.5 ×` thân nến Con cuối cùng.
- Râu trên Cha nhỏ hơn `30%` thân Cha.
- `OPEN Cha >= EMA ngắn`.
- `LOW Cha > EMA trung`.
- `CLOSE Cha > HIGH` cao nhất của các nến Con.
- Thân Cha:
  - Lớn hơn `min_father_body_points`, mặc định `2.0`.
  - Không vượt quá `6.0` price points.

### SELL

Điều kiện đối xứng:

- Mẹ là nến giảm.
- `LOW` Mẹ bao trùm phần thân dưới của các nến Con.
- Thân Cha lớn hơn `1.5 ×` thân nến Con cuối.
- Râu dưới Cha nhỏ hơn `30%` thân Cha.
- `OPEN Cha <= EMA ngắn`.
- `HIGH Cha < EMA trung`.
- `CLOSE Cha < LOW` thấp nhất của các nến Con.
- Thân Cha nằm trong khoảng cho phép.

Logic chi tiết hiện tại nằm trong [flappy_bird_strategy.py](../src/flappy_bird_strategy.py).

---

## 3. EMA trên khung hiện hành

Khung hiện hành có hai mode độc lập:

- **Chim bay**
- **Fallback**

Mỗi mode có một bộ EMA riêng:

```text
EMA ngắn
EMA trung
EMA dài
```

Mặc định cả hai bộ đều là:

```text
13 / 21 / 55
```

### 3.1. Mode Chim bay

#### BUY

```text
EMA ngắn > EMA trung > EMA dài
```

Ví dụ:

```text
EMA13 > EMA21 > EMA55
```

#### SELL

```text
EMA ngắn < EMA trung < EMA dài
```

Nếu mode Chim bay được xác nhận, các điều kiện EMA của Nến Cha dùng bộ EMA Chim bay.

### 3.2. Mode Fallback

Fallback được dùng khi bộ EMA Đồng thuận không thỏa mãn thứ tự đầy đủ.

#### BUY

- EMA ngắn > EMA trung.
- EMA ngắn nằm dưới EMA dài.
- Nến Cha cắt EMA dài theo hướng tăng:

```text
OPEN Cha < EMA dài < CLOSE Cha
```

#### SELL

- EMA ngắn < EMA trung.
- EMA ngắn nằm trên EMA dài.
- Nến Cha cắt EMA dài theo hướng giảm:

```text
OPEN Cha > EMA dài > CLOSE Cha
```

Fallback dùng bộ EMA Fallback riêng, không dùng lại bộ EMA Đồng thuận.

### 3.3. Hai mode có chạy đồng thời không?

Không phải một tín hiệu phải thỏa cả hai mode.

Cách hoạt động là:

```text
Nếu Chim bay hợp lệ
    => tín hiệu thuộc mode Đồng thuận
Nếu không
    => thử Fallback
Nếu Đầu nguồn hợp lệ
    => tín hiệu thuộc mode Fallback
Nếu cả hai không hợp lệ
    => không có tín hiệu
```

Nếu tắt một mode thì mode đó không được phép tạo tín hiệu.

Nếu tắt master toggle của EMA khung hiện hành:

- Bỏ qua điều kiện thứ tự/cắt EMA hiện hành.
- Nhưng vẫn giữ toàn bộ pattern Mẹ/Con/Cha.

---

## 4. Tương tác giữa khung hiện hành và HTF

HTF **không thay thế** khung hiện hành.

HTF chỉ là bộ lọc xác nhận bổ sung.

Luồng chính là:

```text
Khung hiện hành tìm pattern
        ↓
Khung hiện hành xác định mode EMA
        ↓
HTF xác nhận đúng mode đó
        ↓
Đủ điều kiện mới tạo lệnh
```

Ví dụ:

```text
Khung hiện hành xác nhận Đồng thuận
        ↓
HTF cũng phải đạt điều kiện Đồng thuận
        ↓
Mới được tạo tín hiệu
```

Không được xảy ra trường hợp:

```text
Khung hiện hành Đồng thuận
HTF Fallback
```

Mode ở HTF phải cùng tên với mode đã được chọn ở khung hiện hành.

---

## 5. Điều kiện HTF Chim bay

### BUY

HTF phải thỏa đồng thời:

```text
EMA ngắn > EMA trung > EMA dài
```

Và nến HTF hiện hành phải nằm hoàn toàn phía trên EMA dài:

```text
OPEN HTF > EMA dài
CLOSE HTF > EMA dài
```

### SELL

HTF phải thỏa:

```text
EMA ngắn < EMA trung < EMA dài
```

Và:

```text
OPEN HTF < EMA dài
CLOSE HTF < EMA dài
```

Tức là với Chim bay, cả `OPEN` và `CLOSE` của nến HTF đều phải nằm đúng phía EMA dài.

---

## 6. Điều kiện HTF Fallback

### BUY

HTF phải thỏa:

```text
EMA ngắn > EMA trung
CLOSE HTF > EMA dài
```

Không bắt buộc `OPEN HTF > EMA dài`.

### SELL

HTF phải thỏa:

```text
EMA ngắn < EMA trung
CLOSE HTF < EMA dài
```

Không bắt buộc `OPEN HTF < EMA dài`.

Vì vậy HTF Đầu nguồn cho phép nến HTF đang cắt qua EMA dài, miễn là `CLOSE` đã nằm đúng phía.

---

## 7. HTF dùng cây nến nào?

Backtest và Live Bot không dùng HTF candle đang hình thành.

Hệ thống dùng:

```text
Nến HTF đã đóng gần nhất
```

tính đến thời điểm Nến Cha của khung hiện hành.

Mục đích là tránh look-ahead:

- Không dùng dữ liệu tương lai.
- Không lấy `HIGH/LOW/CLOSE` cuối cùng của nến HTF khi nến đó chưa đóng.
- Backtest và Live Bot giữ cùng nguyên tắc này.

---

## 8. Quan hệ timeframe

Bắt buộc:

```text
HTF > Khung hiện hành
```

Thứ tự hợp lệ:

```text
M1 < M5 < M15 < M30 < H1 < H4 < D1
```

Ví dụ hợp lệ:

```text
M1  → M5
M5  → M15
M15 → H1
H1  → H4
```

Ví dụ không hợp lệ:

```text
M5 → M1
M15 → M5
M1 → M1
```

Nếu chọn sai:

- UI hiển thị lỗi.
- Không thể chọn HTF nhỏ hơn hoặc bằng khung hiện hành.
- Nút chạy Backtest bị khóa.
- Nút khởi động Live Bot bị khóa.

Nếu chọn `D1` làm khung hiện hành thì hiện tại không còn timeframe lớn hơn để làm HTF.

---

## 9. Tạo lệnh và thoát lệnh

### BUY

```text
Entry = CLOSE Cha - 5% × thân Cha
SL    = min(LOW Cha, LOW Con cuối) - 5 pips
TP    = Entry + 2R
```

Tạo `BUY LIMIT`.

### SELL

```text
Entry = CLOSE Cha + 5% × thân Cha
SL    = max(HIGH Cha, HIGH Con cuối) + 5 pips
TP    = Entry - 2R
```

Tạo `SELL LIMIT`.

Pending order hết hạn sau mặc định `7` nến nếu chưa được khớp.

EXIT TIME hiện đang tắt cho Flappy/Multi Flappy; vị thế sau khi khớp chủ yếu thoát bằng SL hoặc TP. Khi cùng một nến chạm cả SL và TP, Backtest ưu tiên SL theo hướng bảo thủ.

Tài liệu tổng hợp hiện tại nằm trong [codebase-guide-vi.md](./codebase-guide-vi.md).
