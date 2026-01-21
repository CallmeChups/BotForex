# MT5 Forex Trading Bot - Tóm Tắt Codebase

**Cập Nhật Lần Cuối**: 2026-01-17
**Phiên Bản**: 0.1.0
**Trạng Thái**: Early-Stage PoC

## Tổng Quan Project

MT5 Forex Trading Bot là một ứng dụng Python thực hiện giao dịch forex tự động sử dụng MetaTrader5 API. Nó triển khai chiến lược đa timeframe kết hợp MACD (H4), Stochastic (M30), và Moving Average Crossover (M5) với hỗ trợ Telegram notifications.

**Kích Thước**: 136 dòng code lõi (src/) + 219 dòng test/reference (test/)
**Trạng Thái**: Proof-of-Concept hoạt động (test/ref.py là triển khai tham chiếu)

## Cấu Trúc Thư Mục

```
E:\Project\BotForex\
├── src/                          # Core source code (136 dòng)
│   ├── calculation.py            # Technical indicators (70 dòng)
│   │   ├── calculate_macd()      # MACD calculation
│   │   ├── calculate_stoch()     # Stochastic oscillator
│   │   ├── calculate_ma()        # Simple Moving Average
│   │   ├── calculate_ema()       # Exponential Moving Average
│   │   └── check_cross_2_list_updated()  # Signal detection
│   ├── telegram.py               # Telegram notifications (58 dòng)
│   │   └── send_message()        # Send alert with retry
│   └── utils.py                  # Utility functions (8 dòng)
│       └── non_zero_range()      # Handle zero-value ranges
│
├── test/                         # Test & reference scripts
│   ├── test.py                   # MT5 connection test (55 dòng)
│   │   └── Basic MT5 login & data retrieval
│   └── ref.py                    # Working reference strategy (164 dòng)
│       ├── Multi-timeframe logic
│       ├── Signal detection
│       └── Order execution
│
├── config/
│   └── config.yaml               # Configuration (EMPTY - needs setup)
│
├── main.py                       # Entry point (EMPTY STUB)
├── app.py                        # Streamlit dashboard (EMPTY STUB)
├── requirements.txt              # Dependencies
├── README.md                      # Main documentation (Vietnamese)
├── strategy.txt                  # Strategy notes (Vietnamese)
├── note.txt                      # Trading notes (Vietnamese)
├── CLAUDE.md                     # Claude Code instructions
│
├── logs/                         # Log directory (empty)
├── data/                         # Data directory (empty)
└── docs/                         # Project documentation
    ├── project-overview-pdr.md   # This PDR
    ├── code-standards.md         # Code standards
    ├── codebase-summary.md       # This file
    ├── system-architecture.md    # Architecture design
    └── project-roadmap.md        # Development roadmap
```

## Thành Phần Lõi

### 1. Module Tính Toán Chỉ Báo (`src/calculation.py` - 70 dòng)

**Mục đích**: Tính toán các chỉ báo kỹ thuật và phát hiện tín hiệu

**Hàm Chính**:

```python
def calculate_macd(df, period_fast=12, period_slow=26, signal=9, column='close', adjust=False)
# Returns: (MACD_line, MACD_signal_line)
# Tính MACD = EMA_fast - EMA_slow, signal = EMA(MACD)
```

```python
def calculate_stoch(df, k_length=14, k_smooth=1, d_smooth=3)
# Returns: {'k': smooth_k_percentage, 'd': smooth_d_percentage}
# Tính Stochastic oscillator: %K = (Close - Low) / (High - Low) * 100
```

```python
def calculate_ma(df, period)
# Returns: Moving Average list
# Tính SMA đơn giản
```

```python
def calculate_ema(df, period=100)
# Returns: EMA values list
# Tính Exponential Moving Average với multiplier = 2/(period+1)
```

```python
def check_cross_2_list_updated(list_1, list_2, period=3, confirm=2)
# Returns: {'up': bool, 'down': bool}
# Phát hiện crossover giữa hai line (MACD cross signal, Price cross MA, etc)
# Logic: Kiểm tra nếu đã có 1 crossover trong period cuối cùng và confirm từ cuối
```

**Phụ Thuộc**:
- numpy: Tính toán số học
- src.utils.non_zero_range: Xử lý trường hợp high == low (crypto)

**Lưu Ý Bảo Mật**:
- Không có xác thực, không có I/O
- Hoàn toàn stateless

### 2. Module Telegram Notification (`src/telegram.py` - 58 dòng)

**Mục đích**: Gửi thông báo cảnh báo giao dịch qua Telegram

**Hàm Chính**:

```python
def send_message(msg, chat_id, max_retries=5, token=TOKEN, disable_notification=True, debug=False)
# Gửi tin nhắn đến một hoặc nhiều chat_id
# - Retry tối đa 5 lần nếu fail (sleep 5s giữa các lần)
# - Support multiple chat_ids (string hoặc list)
# - Tùy chọn disable notification sound (disable_notification=True)
# - Debug mode: in console thay vì gửi thực tế
```

**Hardcoded Constants**:
```python
TOKEN = "7363572293:AAHd595bWg7liBafg8qEmasPh8Zx1I2crWo"  # ⚠️ SECURITY ISSUE
```

**Phụ Thuộc**:
- telebot: Kết nối Telegram
- requests: POST HTTP
- time: Sleep giữa retries

**⚠️ Bảo Mật**:
- Token hardcoded (cần ngoài hóa)
- Không có xác thực API key
- Test code ở dòng 40-41 gửi tin nhắn thực tế

### 3. Module Tiện Ích (`src/utils.py` - 8 dòng)

**Mục đích**: Hàm tiện ích dùng chung

```python
def non_zero_range(high: Series, low: Series) -> Series
# Trả về high - low, nhưng thêm epsilon nếu kết quả = 0
# Dùng để tránh division by zero trong Stochastic calculation
```

**Phụ Thuộc**:
- pandas.Series: Xử lý data frame
- sys.float_info: Lấy epsilon

### 4. Test MT5 Connection (`test/test.py` - 55 dòng)

**Mục đích**: Kiểm tra kết nối MT5 và lấy dữ liệu

**Nội Dung**:
- Kết nối đến tài khoản MT5: `account = 415016785`
- Lấy dữ liệu 1 tuần với khung M1
- Chuyển đổi timestamp sang múi giờ Việt Nam
- In dữ liệu lên console

**Hardcoded Credentials**:
```python
account = 415016785
password = "Taptrade211225@"
server = "Exness-MT5Trial14"
```

**⚠️ Bảo Mật**: Thông tin xác thực bị expose

### 5. Reference Strategy (`test/ref.py` - 164 dòng)

**Mục đích**: Triển khai tham chiếu hoạt động của chiến lược giao dịch

**Hardcoded Credentials**:
```python
account = 243254313
password = "Test2312025@"
server = "Exness-MT5Trial14"
```

**Chiến Lược**:
- **Timeframe Long (H4)**: MACD cross up/down
- **Timeframe Mid (M30)**: Stochastic(7,5,3) < 20 (buy) hoặc > 80 (sell)
                          Stochastic(13,13,5) < 50 (buy) hoặc > 50 (sell)
- **Timeframe Short (M5)**: Price > MA10 & MA20 (buy) hoặc < (sell)

**Entry Logic**:
```
BUY: MACD cross up (H4)
     AND Stoch(7,5,3) < 20 (M30)
     AND Stoch(13,13,5) < 50 (M30)
     AND Close > MA10 (M5)
     AND Close > MA20 (M5)

SELL: MACD cross down (H4)
      AND Stoch(7,5,3) > 80 (M30)
      AND Stoch(13,13,5) > 50 (M30)
      AND Close < MA10 (M5)
      AND Close < MA20 (M5)
```

**Order Execution**:
- Loại lệnh: TRADE_ACTION_DEAL (lệnh thị trường)
- Volume: 0.1 lot
- SL/TP: 1.5x lot (tương đương ATR)
- Deviation: 20 pips
- Type: BUY hoặc SELL

**Vòng Lặp**:
- Loop vô tận
- Lấy dữ liệu 1 tuần
- Tính toán tất cả chỉ báo
- Kiểm tra tín hiệu
- Gửi lệnh nếu match
- Break sau khi gửi thành công

**Lưu Ý**:
- Phụ thuộc vào test.py để setup (commented out import)
- Ghi log + print cho debug
- Break sau đó không có exit logic (chỉ test 1 giao dịch)

## Công Nghệ Stack

| Thành Phần | Thư Viện | Phiên Bản | Mục Đích |
|-----------|---------|---------|---------|
| API Giao Dịch | MetaTrader5 | Latest | Kết nối MT5, lấy dữ liệu, gửi lệnh |
| Thông Báo | python-telegram-bot | Latest | Gửi cảnh báo Telegram |
| Xử Lý Dữ Liệu | pandas | Latest | DataFrame, time-series |
| Tính Toán | numpy | Latest | Mảng, tính toán số học |
| Cấu Hình | PyYAML | Latest | Đọc config.yaml |
| Debug | icecream | Latest | Logging debug |
| Dashboard (Sắp) | Streamlit | Latest | Web UI |

## Mô Hình Dữ Liệu

### Input từ MT5
```
Symbol: BTCUSDm (hoặc EURUSD, etc)
Timeframes: H4, M30, M5
Data per timeframe:
  - time: Unix timestamp
  - open: Giá mở
  - high: Giá cao nhất
  - low: Giá thấp nhất
  - close: Giá đóng
  - tick_volume: Volume tick
```

### DataFrame sau xử lý
```
Columns:
  - time: Unix timestamp
  - open, high, low, close: OHLC prices
  - tick_volume: Volume
  - real_time: Human-readable timestamp
```

### Indicator Outputs
```
MACD: (macd_line list, signal_line list)
Stochastic: {'k': Series, 'd': Series}
MA: List of moving averages
EMA: List of exponential moving averages
Signal: {'up': bool, 'down': bool}
```

### Order Structure
```python
{
  'action': mt5.TRADE_ACTION_DEAL,
  'symbol': 'BTCUSDm',
  'price': entry_price,
  'sl': stop_loss_price,
  'tp': take_profit_price,
  'deviation': 20,
  'type': mt5.ORDER_TYPE_BUY/SELL,
  'volume': 0.1,  # Lot size
  'type_time': mt5.ORDER_TIME_GTC,
  'type_filling': mt5.ORDER_FILLING_IOC,
  'comment': 'Py Buy/Sell Position'
}
```

## Luồng Xử Lý

```
1. Initialize MT5 Connection
   ├─ mt5.initialize()
   └─ mt5.login(account, password, server)

2. Data Retrieval (mỗi vòng lặp)
   ├─ mt5.copy_rates_range(symbol, timeframe, date_from, date_to)
   └─ Tạo DataFrame từ kết quả

3. Indicator Calculation
   ├─ calculate_macd(long_data)
   ├─ calculate_stoch(mid_data)
   ├─ calculate_ma(short_data)
   └─ check_cross_2_list_updated() cho tất cả

4. Signal Detection
   ├─ Kiểm tra tất cả conditions (BUY/SELL)
   └─ Nếu match → tiếp tới bước 5

5. Order Execution
   ├─ mt5.symbol_info_tick(symbol) → lấy bid/ask
   ├─ Tính SL/TP dựa trên 1.5x lot
   ├─ mt5.order_send(request)
   └─ Log result

6. Notification (sắp có)
   ├─ send_message() → Telegram
   └─ Log trade details
```

## Tệp Cấu Hình (Chưa Triển Khai)

**config/config.yaml** (expected format):
```yaml
mt5:
  login: 243254313
  password: "password_here"
  server: "Exness-MT5Trial14"

telegram:
  token: "bot_token_here"
  dev_chat_id: 123456789
  user_chat_id: 987654321

strategy:
  symbol: "BTCUSDm"
  lot: 0.1

timeframes:
  long: H4
  mid: M30
  short: M5

indicators:
  macd: [12, 26, 9]
  stoch_1: [7, 5, 3]
  stoch_2: [13, 13, 5]
  ma: [10, 20]

risk:
  sl_atr_multiplier: 1.5
  tp_atr_multiplier: 1.5
```

## Tỷ Lệ Code Coverage

| File | LOC | Type | Status |
|------|-----|------|--------|
| src/calculation.py | 70 | Core | ✅ Working |
| src/telegram.py | 58 | Core | ✅ Working (hardcoded) |
| src/utils.py | 8 | Utility | ✅ Working |
| test/ref.py | 164 | Reference | ✅ Working |
| test/test.py | 55 | Test | ✅ Connection test |
| main.py | 0 | Entry point | ❌ Stub |
| app.py | 0 | Dashboard | ❌ Stub |
| **Total** | **355** | | |

## Các Vấn Đề & Cảnh Báo

### 🔴 Critical (Bảo Mật)
1. **Hardcoded Credentials**
   - MT5 account/password: test/test.py:24-26, test/ref.py:19-21
   - Telegram token: src/telegram.py:5
   - **Fix**: Dùng environment variables hoặc .env file

2. **No Encryption**
   - Credentials in plaintext trong source code
   - **Fix**: Sử dụng secrets management (vault, AWS Secrets, etc)

### 🟠 High Priority
1. **Empty Entry Points**
   - main.py: Stub, không có logic chính
   - app.py: Stub, không có dashboard
   - **Fix**: Implement entry points + config loading

2. **No Error Handling**
   - Không try-catch cho MT5 calls
   - Không fallback nếu Telegram fail
   - **Fix**: Thêm comprehensive error handling

3. **No Logging**
   - Chỉ có print statements
   - Không có file logs
   - **Fix**: Setup logging module

### 🟡 Medium Priority
1. **No Configuration Management**
   - config.yaml là empty
   - Hardcoded values trong code
   - **Fix**: Implement config loading

2. **No Test Suite**
   - Chỉ có test/test.py & test/ref.py
   - Không có unit tests
   - **Fix**: Viết test suite

3. **Single Trade Only**
   - test/ref.py break sau khi trade 1 lệnh
   - **Fix**: Implement continuous loop

### 🔵 Low Priority
1. **No Backtesting**
   - Không có backtesting module
   - Chỉ live/paper trading

2. **No Database**
   - Không lưu lịch sử trade
   - Không có analytics

3. **No Documentation Code**
   - Docstrings thiếu
   - Comments ít

## Quy Trình Phát Triển Tiếp Theo

1. **Phase 1 - Cleanup & Config**
   - [ ] Ngoài hóa credentials
   - [ ] Implement main.py
   - [ ] Setup config.yaml
   - [ ] Thêm logging

2. **Phase 2 - Dashboard & UI**
   - [ ] Implement app.py Streamlit
   - [ ] Start/Stop controls
   - [ ] Real-time monitoring

3. **Phase 3 - Enhancement**
   - [ ] Improve strategy (thêm filter)
   - [ ] Backtesting module
   - [ ] Database storage

## Hướng Dẫn Cài Đặt Môi Trường

```bash
# 1. Create virtual environment
python -m venv venv

# 2. Activate (Windows)
venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Setup environment variables
# Tạo .env file hoặc set system variables:
set MT5_LOGIN=243254313
set MT5_PASSWORD=...
set MT5_SERVER=...
set TELEGRAM_TOKEN=...

# 5. Run tests
python test/test.py

# 6. Run reference strategy (sau khi ngoài hóa credentials)
python test/ref.py
```

## Phụ Thuộc & Thư Viện

Xem `requirements.txt`:
- MetaTrader5: MT5 API
- python-telegram-bot: Telegram integration
- streamlit: Web dashboard (sắp)
- pyyaml: Config parsing
- pandas: Data manipulation
- icecream: Debug printing

## Tài Liệu Liên Quan

- [Project Overview & PDR](./project-overview-pdr.md)
- [Code Standards](./code-standards.md)
- [System Architecture](./system-architecture.md)
- [Project Roadmap](./project-roadmap.md)

## Ghi Chú Bảo Trì

- Kiểm tra credentials định kỳ (quarterly security audit)
- Monitor bot uptime
- Review trade logs hàng tuần
- Update strategy parameters theo market conditions
- Backup config & credentials an toàn

## Các Câu Hỏi Chưa Giải Quyết

1. **Credential Management**: Nên sử dụng giải pháp nào?
2. **Backtesting**: Có cần framework backtesting?
3. **Multiple Strategies**: Có support nhiều strategy cùng lúc?
4. **Paper Trading vs Live**: Cơ chế switch?
5. **Monitoring**: Cần monitoring tool ngoài Telegram?
