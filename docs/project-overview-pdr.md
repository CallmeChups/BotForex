# MT5 Forex Trading Bot - Tổng Quan & PDR

**Tên Project**: MT5 Forex Trading Bot - Giao dịch Forex Tự Động
**Phiên Bản**: 0.1.0 (Early-Stage PoC)
**Cập Nhật Lần Cuối**: 2026-01-17
**Trạng Thái**: Phát Triển Sớm
**Repository**: E:\Project\BotForex

## Tóm Tắt Điều Hành

MT5 Forex Trading Bot là một bot giao dịch tự động kết nối với MetaTrader 5 để thực hiện các giao dịch forex dựa trên chiến lược kỹ thuật đa timeframe. Bot sử dụng Python 3.10+, thực hiện phân tích kỹ thuật (MACD, Stochastic, Moving Average), gửi thông báo qua Telegram, và hiện tại ở giai đoạn proof-of-concept với một triển khai tham chiếu hoạt động tốt.

## Mục Đích Project

### Tầm Nhìn
Tự động hóa giao dịch forex với các chiến lược đa timeframe đáng tin cậy, kết hợp các chỉ báo kỹ thuật và quản lý rủi ro.

### Sứ Mệnh
Cung cấp bot giao dịch:
- Kết nối MT5 với khả năng gửi lệnh tự động
- Phân tích kỹ thuật đa timeframe (H4, M30, M5)
- Thông báo Telegram thời gian thực
- Dashboard Streamlit để giám sát và điều khiển
- Logging và phân tích giao dịch

### Giá Trị Đề Xuất
- **Chiến Lược Đa Timeframe**: MACD (H4) + Stochastic (M30) + MA Crossover (M5)
- **Quản Lý Rủi Ro**: SL/TP dựa trên ATR (1.5x)
- **Thông Báo Real-Time**: Telegram cho đầu vào/ra và lỗi
- **Sẽ Có**: Dashboard để start/stop, chỉnh cấu hình, xem lịch sử

## Phạm Vi Project

### Đã Triển Khai (Hiện Tại)
- Tính toán chỉ báo: MACD, Stochastic, MA, EMA (src/calculation.py - 70 dòng)
- Gửi thông báo Telegram với retry logic (src/telegram.py - 58 dòng)
- Chiến lược tham chiếu đa timeframe hoạt động (test/ref.py - 164 dòng)
- Kết nối MT5 và thực hiện lệnh (test/ref.py)
- Công cụ tiện ích: non_zero_range (src/utils.py)

### Sẽ Triển Khai (Phase 1-2)
- Hoàn thành main.py entry point
- Hoàn thành app.py dashboard Streamlit
- Ngoài hóa thông tin xác thực (MT5 & Telegram)
- Cấu hình YAML chuẩn
- Logging toàn diện
- Bộ test chính thức

### Ngoài Phạm Vi
- Backtesting toàn diện
- Phân tích tối ưu hóa thông số
- Triển khai đám mây
- Xác thực đa người dùng

## Yêu Cầu Chức Năng

**FR1: Kết Nối MT5**
- Kết nối đến tài khoản MT5 (demo/live)
- Lấy dữ liệu OHLC real-time
- Gửi lệnh BUY/SELL với SL/TP
- Xử lý lỗi kết nối

**FR2: Phân Tích Kỹ Thuật**
- Tính toán MACD (12, 26, 9) trên khung H4
- Tính toán Stochastic(7,5,3) & Stochastic(13,13,5) trên khung M30
- Tính toán MA10/MA20 trên khung M5
- Kiểm tra tín hiệu cross giữa các chỉ báo

**FR3: Chiến Lược Giao Dịch**
- Entry BUY: MACD cross up (H4) + Stoch < 20 (M30) + Price > MA (M5)
- Entry SELL: MACD cross down (H4) + Stoch > 80 (M30) + Price < MA (M5)
- SL/TP: 1.5x ATR từ mức vào

**FR4: Thông Báo Telegram**
- Gửi alert khi có lệnh vào/ra
- Gửi thông báo lỗi kết nối
- Kênh riêng cho dev và user
- Retry tối đa 5 lần

**FR5: Logging & Phân Tích**
- Lưu chi tiết mọi lệnh (symbol, loại, volume, giá, lợi nhuận)
- Xuất dữ liệu cho phân tích
- Debug logging có thể bật tắt

**FR6: Dashboard (Lập Kế Hoạch)**
- Start/Stop bot
- Chỉnh sửa thông số thời gian thực
- Xem trạng thái tài khoản live
- Xem lịch sử lệnh

## Yêu Cầu Không Chức Năng

**NFR1: Hiệu Suất**
- Kiểm tra tín hiệu mỗi 1-5 phút (tùy timeframe)
- Gửi lệnh < 1 giây
- Thông báo Telegram < 5 giây

**NFR2: Độ Tin Cậy**
- Xử lý lỗi kết nối gracefully
- Retry logic cho Telegram
- Logging lỗi chi tiết

**NFR3: Bảo Mật**
- Không hardcode thông tin xác thực
- Sử dụng biến môi trường
- Không log mật khẩu

**NFR4: Có Thể Bảo Trì**
- Python files < 500 dòng
- Cấu trúc modular
- Tài liệu rõ ràng

## Tiêu Chí Thành Công

### Metric Chức Năng
- Bot kết nối MT5 thành công
- Gọi API Telegram thành công
- Chiến lược phát hiện tín hiệu đúng
- Lệnh gửi thành công (demo/live)

### Metric Hiệu Suất
- Thời gian phân tích < 1 giây/vòng lặp
- Thời gian gửi lệnh < 2 giây
- Uptime bot > 95%

### Metric Quá Trình
- Code coverage > 70% (sau phase 1)
- Tài liệu đầy đủ
- Xử lý lỗi toàn diện

## Kiến Trúc Kỹ Thuật

### Công Nghệ Lõi

**Runtime**:
- Python 3.10+
- MetaTrader5 API
- python-telegram-bot
- Streamlit (dashboard)

**Thư Viện**:
- pandas (xử lý dữ liệu)
- numpy (tính toán)
- PyYAML (cấu hình)
- icecream (debug)

### Thành Phần Hệ Thống

```
┌─────────────────────────────────────┐
│   Main Entry Point (main.py)        │
│   - Load config.yaml                │
│   - Initialize MT5 connection       │
│   - Start trading loop              │
└──────────────┬──────────────────────┘
               │
        ┌──────▼──────────────┐
        │ Strategy Engine     │
        │ ├─ Multi-timeframe  │
        │ ├─ Tech indicators  │
        │ └─ Signal detection │
        └──────┬──────────────┘
               │
        ┌──────▼────────┐
        │ MT5 Connector │
        │ ├─ Login      │
        │ ├─ Get rates  │
        │ └─ Send order │
        └──────┬────────┘
               │
        ┌──────▼──────────┐
        │ Notifications   │
        │ └─ Telegram     │
        └─────────────────┘
```

## Dòng Dữ Liệu

```
MT5 Terminal (Real-time rates)
         ↓
   [H4 OHLC] [M30 OHLC] [M5 OHLC]
         ↓         ↓         ↓
   [MACD]    [Stoch]    [MA Cross]
         ↓         ↓         ↓
    ┌────────────────────────────┐
    │   Signal Detection Engine   │
    │   (check_cross_2_list...)   │
    └────────────────────────────┘
                 ↓
        ┌─────────────────┐
        │ Entry Detected? │
        │ BUY / SELL      │
        └────────┬────────┘
                 ↓
        ┌─────────────────┐
        │ Send Order      │
        │ (MT5)           │
        └────────┬────────┘
                 ↓
        ┌─────────────────┐
        │ Notify User     │
        │ (Telegram)      │
        └────────┬────────┘
                 ↓
        ┌─────────────────┐
        │ Log Trade       │
        │ (File/DB)       │
        └─────────────────┘
```

## Ràng Buộc & Hạn Chế

### Kỹ Thuật
- Phụ thuộc vào terminal MT5 đang chạy (Windows)
- Thông tin xác thực hiện tại hardcoded (cần ngoài hóa)
- Không hỗ trợ các broker khác (chỉ MT5)
- Xử lý đơn khóa, không có backtest

### Dữ Liệu
- Cần dữ liệu tick real-time từ MT5
- Chỉ hỗ trợ một symbol/bot instance
- Không có lưu trữ dữ liệu lịch sử (hiện tại)

### Vận Hành
- Cần cấu hình thủ công (config.yaml)
- Không tự động khởi động
- Không có monitoring/alert về downtime
- Cần Python environment cài đặt

## Trạng Thái Hiện Tại

### Hoàn Thành
- Core indicators (MACD, Stochastic, MA, EMA) ✅
- Telegram notification module ✅
- Reference multi-timeframe strategy (test/ref.py) ✅
- MT5 connection & order execution ✅

### Đang Làm
- (None - ở giai đoạn PoC)

### Chưa Bắt Đầu
- main.py entry point (stub)
- app.py Streamlit dashboard (stub)
- config.yaml (empty)
- Formal test suite
- Credential externalization
- Comprehensive logging
- Error handling

## Mối Nguy Hiểm & Cảnh Báo

### Bảo Mật
- ⚠️ Thông tin xác thực MT5 hardcoded trong test/ref.py
- ⚠️ Telegram token hardcoded trong src/telegram.py
- ✅ Cần sử dụng biến môi trường/vault

### Rủi Ro Tài Chính
- ⚠️ Bot có thể gây mất tiền nếu chiến lược sai
- ✅ Luôn test trên tài khoản demo trước
- ✅ Bắt đầu với lot nhỏ (0.1)

### Vận Hành
- ⚠️ Terminal MT5 phải mở 24/7 (hoặc tạo scheduler)
- ⚠️ Kết nối mạng bị gián đoạn → lệnh không được gửi
- ✅ Cần giám sát và log toàn diện

## Lộ Trình

### Phase 1 (Hiện Tại)
- Hoàn thành main.py entry point
- Hoàn thành app.py dashboard
- Ngoài hóa thông tin xác thực
- Viết config.yaml chuẩn
- Xây dựng logging
- Bắt đầu test formal

### Phase 2
- Cải thiện chiến lược (thêm filter)
- Thêm kỹ thuật quản lý rủi ro
- Thêm indicator khác
- Backtest & phân tích hiệu suất

### Phase 3 (Tương Lai)
- Dashboard web hoàn chỉnh
- Multiple bot instances
- Database cho lịch sử trade
- API REST

## Tài Liệu Liên Quan

### Nội Bộ
- [Code Standards](./code-standards.md)
- [System Architecture](./system-architecture.md)
- [Codebase Summary](./codebase-summary.md)
- [Project Roadmap](./project-roadmap.md)

### Ngoài
- [MetaTrader5 Python Docs](https://www.mql5.com/en/docs/integration/python_metatrader5)
- [python-telegram-bot Docs](https://python-telegram-bot.readthedocs.io/)
- [Streamlit Docs](https://docs.streamlit.io/)
- [PyYAML Docs](https://pyyaml.org/)

## Các Câu Hỏi Chưa Giải Quyết

1. **Chiến lược giao dịch cuối cùng**: Thêm filter nào khác (volume, trend)?
2. **Quản lý tiền**: Cơ chế sizing lot dựa trên balance?
3. **Scheduler**: Cách để bot chạy 24/7 tự động?
4. **Multiple timeframes**: Kỳ vọng chi tiết từ các timeframe khác?
5. **Backtesting**: Cần công cụ backtesting?
