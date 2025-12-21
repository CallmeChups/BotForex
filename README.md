# MT5 Forex Bot Project

## Giới Thiệu
Project này là một bot trading forex tự động sử dụng Python và MetaTrader 5 (MT5) API. Bot kết nối với terminal MT5 để thực hiện giao dịch dựa trên các chiến lược trading, gửi thông báo qua Telegram, lưu log lệnh giao dịch để phân tích sau này, và cung cấp giao diện web đơn giản bằng Streamlit để người dùng tương tác.

### Tính Năng Chính
- **Tự động giao dịch**: Kết nối MT5, lấy dữ liệu real-time, kiểm tra tín hiệu và gửi lệnh buy/sell.
- **Thông báo Telegram**: Gửi alert khi có lệnh vào/ra, lỗi kết nối, hoặc sự kiện quan trọng (riêng kênh cho dev và user).
- **Logging lệnh**: Lưu chi tiết mọi lệnh giao dịch (symbol, loại lệnh, volume, giá vào/ra, thời gian, profit/loss) để dễ dàng export và phân tích.
- **Giao diện người dùng**: Dashboard Streamlit để start/stop bot, chỉnh sửa config thời gian thực, xem trạng thái live và lịch sử lệnh.
- **Hỗ trợ multi-bot**: Mỗi bot chạy như một process Python riêng biệt, dễ chạy nhiều instance với config khác nhau.

### Công Nghệ Sử Dụng
- Python 3.10+
- MetaTrader5 (API chính thức)
- python-telegram-bot (gửi thông báo)
- Streamlit (giao diện web)
- PyYAML (đọc config)
- Pandas & SQLite (xử lý và lưu log, phân tích)

## Hướng Dẫn Cài Đặt

1. **Clone repository**
   ```bash
   git clone <your-repo-url>
   cd mt5_forex_bot
   ```

2. **Tạo virtual environment (khuyến nghị)**
   ```bash
   python -m venv venv
   source venv/bin/activate    # Linux/Mac
   venv\Scripts\activate       # Windows
   ```

3. **Cài đặt dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Cấu hình project**
   - Copy file mẫu config (nếu có) hoặc tạo mới file `config/config.yaml` với nội dung cơ bản:
     ```yaml
     mt5:
       login: 12345678              # Login MT5
       password: "your_password"    # Password MT5
       server: "Exness-MT5Real"     # Server broker (ví dụ Exness)
     
     telegram:
       bot_token: "123456:ABC-DEF"  # Token từ BotFather
       dev_chat_id: 123456789       # Chat ID dev (nhận debug)
       user_chat_id: 987654321      # Chat ID user (nhận alert trade)
     
     strategy:
       symbol: "EURUSD"
       timeframe: "H1"
       risk_percent: 1.0
       # Các tham số strategy khác...
     
     logging:
       level: "INFO"
       path: "logs/trades.log"
       db_path: "data/trades.db"
     ```

5. **Yêu cầu bổ sung**
   - Cài đặt và mở MetaTrader 5 terminal trên Windows (bot cần terminal đang chạy để kết nối).
   - Tạo Telegram Bot qua @BotFather để lấy `bot_token`.
   - Lấy `chat_id` bằng cách chat với bot và truy cập `https://api.telegram.org/bot<token>/getUpdates`.

## Hướng Dẫn Sử Dụng

### 1. Chạy Bot Trading
```bash
python main.py
```
- Có thể truyền config khác: `python main.py --config config/my_custom.yaml`

### 2. Chạy Giao Diện Streamlit
```bash
streamlit run app.py
```
- Mở trình duyệt tại `http://localhost:8501` để:
  - Start/Stop bot
  - Chỉnh sửa tham số strategy thời gian thực
  - Xem trạng thái tài khoản, vị thế mở, log gần nhất
  - Export dữ liệu giao dịch

### 3. Phân Tích Lịch Sử Giao Dịch
Sau khi có log, bạn có thể chạy script phân tích (sẽ triển khai sau):
```bash
python -m src.analysis.analyzer
```
Hoặc dùng Streamlit để xem biểu đồ và metrics trực tiếp.

## Cấu Trúc Project
```
mt5_forex_bot/
├── config/               # File cấu hình
├── src/                  # Source code chính
│   ├── bot/              # MT5 connector, strategy, trader loop
│   ├── notifications/    # Telegram notifier
│   ├── logging/          # Custom logger & DB handler
│   ├── analysis/         # Phân tích & export dữ liệu
│   └── ui/               # Streamlit dashboard
├── logs/                 # File log giao dịch
├── data/                 # Database SQLite & file export
├── main.py               # Entry point chạy bot
├── app.py                # Entry point Streamlit
├── requirements.txt
└── README.md
```

## Lưu Ý Quan Trọng
- **Rủi ro tài chính**: Bot trading có thể gây mất tiền. Luôn test kỹ trên tài khoản demo trước khi chạy live.
- **Kết nối MT5**: Terminal MT5 phải đang mở và đã login tài khoản.
- **Weekend**: Chỉ crypto chạy 24/7 trên Exness; các cặp forex truyền thống đóng cửa cuối tuần.
- **Debug**: Đặt `logging.level: "DEBUG"` trong config để nhận thông tin chi tiết.

## License
MIT License

Chúc bạn code vui và project thành công! 🚀

Nếu có bất kỳ vấn đề nào, hãy mở issue trên repository hoặc liên hệ trực tiếp.
