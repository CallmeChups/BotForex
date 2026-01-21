# MT5 Forex Trading Bot - Kiến Trúc Hệ Thống

**Cập Nhật Lần Cuối**: 2026-01-17
**Phiên Bản**: 0.1.0
**Project**: MT5 Forex Trading Bot - Giao dịch Forex Tự Động

## Tổng Quan Kiến Trúc

MT5 Forex Trading Bot sử dụng mô hình **Layered Pipeline Architecture** - một cấu trúc đơn, modular để xử lý dữ liệu từ MT5, tính toán chỉ báo, phát hiện tín hiệu giao dịch, gửi lệnh, và thông báo.

### Thiết Kế Pattern: Pipeline Xử Lý

```
┌─────────────────────────────────────┐
│   Data Input Layer                  │
│   (MT5 Connection & Data Fetch)     │
└──────────────┬──────────────────────┘
               │
┌──────────────▼──────────────────────┐
│   Calculation Layer                 │
│   (Technical Indicators)            │
├─ MACD (H4)                         │
├─ Stochastic (M30)                  │
├─ Moving Average (M5)               │
└──────────────┬──────────────────────┘
               │
┌──────────────▼──────────────────────┐
│   Signal Detection Layer            │
│   (Strategy Logic)                  │
├─ Cross Detection                   │
├─ Condition Checking                │
└──────────────┬──────────────────────┘
               │
┌──────────────▼──────────────────────┐
│   Order Execution Layer             │
│   (MT5 Order Management)            │
├─ Price Preparation                 │
├─ SL/TP Calculation                 │
├─ Order Sending                     │
└──────────────┬──────────────────────┘
               │
┌──────────────▼──────────────────────┐
│   Notification Layer                │
│   (User Alerts)                     │
├─ Telegram Messages                 │
├─ Retry Logic                       │
└──────────────┬──────────────────────┘
               │
┌──────────────▼──────────────────────┐
│   Logging Layer                     │
│   (Record Keeping)                  │
├─ Trade Details                     │
├─ Error Logs                        │
└─────────────────────────────────────┘
```

## Thành Phần Hệ Thống

### 1. Data Input Layer

**Mục đích**: Kết nối MT5, lấy dữ liệu real-time, xử lý frames

**Thành Phần**:
- **MT5 Connection** (test/ref.py:23-31)
  - `mt5.initialize()`: Khởi tạo
  - `mt5.login(account, password, server)`: Đăng nhập
  - Error handling cho connection failure

- **Data Fetching** (test/ref.py:48-57)
  - `mt5.copy_rates_range(symbol, timeframe, date_from, date_to)`
  - Lấy OHLC cho 3 timeframes: H4, M30, M5
  - Dữ liệu 1 tuần mỗi vòng lặp

**Output Format**:
```python
{
    'time': Unix timestamp,
    'open': Float (giá mở),
    'high': Float (giá cao),
    'low': Float (giá thấp),
    'close': Float (giá đóng),
    'tick_volume': Int (volume)
}
# Được convert thành pd.DataFrame
```

**Error Handling**:
- Retry nếu dữ liệu trống
- Log failure và continue
- Timeout management

### 2. Calculation Layer

**Mục đích**: Tính các chỉ báo kỹ thuật

**Module**: `src/calculation.py` (70 dòng)

**Hàm Tính Toán**:

#### MACD Calculation
```python
def calculate_macd(df, period_fast=12, period_slow=26, signal=9, column='close')
# Returns: (macd_line list, signal_line list)
# Logic:
#   EMA_fast = df['close'].ewm(span=12).mean()
#   EMA_slow = df['close'].ewm(span=26).mean()
#   MACD = EMA_fast - EMA_slow
#   Signal = MACD.ewm(span=9).mean()
```

**Complexity**: O(n) - một lần pass
**Performance**: < 0.5 sec cho 1 năm data

#### Stochastic Calculation
```python
def calculate_stoch(df, k_length=14, k_smooth=1, d_smooth=3)
# Returns: {'k': pd.Series, 'd': pd.Series}
# Logic:
#   max_high = high.rolling(k_length).max()
#   min_low = low.rolling(k_length).min()
#   %K = (close - min_low) / (max_high - min_low) * 100
#   %K_smooth = %K.rolling(k_smooth).mean()
#   %D = %K_smooth.rolling(d_smooth).mean()
```

**Complexity**: O(n) với rolling windows
**Performance**: < 0.3 sec

#### Moving Average
```python
def calculate_ma(df, period)
# Returns: List of MA values
# Simple rolling mean
```

#### EMA Calculation
```python
def calculate_ema(df, period=100)
# Returns: List of EMA values
# Manual calculation với multiplier = 2/(period+1)
```

**Dependency**: `src.utils.non_zero_range()`
- Xử lý trường hợp high == low (crypto data)
- Tránh division by zero

### 3. Signal Detection Layer

**Mục đích**: Phát hiện tín hiệu giao dịch từ các chỉ báo

**Hàm Chính**: `check_cross_2_list_updated(list_1, list_2, period=3, confirm=2)`

**Logic**:
```
Input: Hai line (ví dụ MACD line vs Signal line)
Output: {'up': bool, 'down': bool}

Algorithm:
1. Lấy 'period' bars cuối cùng (default 3)
2. Kiểm tra nếu có 1 crossover trong period này
3. Nếu có, kiểm tra 'confirm' bars (default 2) từ cuối
4. Return True nếu crossover đã confirm
```

**Ứng Dụng**:
```python
# MACD Signal
cross_macd = check_cross_2_list_updated(
    macd_line, signal_line, period=10, confirm=1
)

# MA Crossover
cross_ma = check_cross_2_list_updated(
    close_prices, ma_20, period=10, confirm=1
)

# Stochastic Threshold (không phải crossover)
# Kiểm tra trực tiếp giá trị
if first_stoch['k'][-1] < 20:
    stoch_signal = True
```

**Sensitivity Tuning**:
- `period`: Số bars để kiểm tra (larger = less responsive)
- `confirm`: Số bars confirm (larger = more confirmation)

### 4. Strategy Logic Layer

**Mục đích**: Kết hợp các tín hiệu thành quyết định giao dịch

**Location**: `test/ref.py` (lines 84-165)

**Entry Rules**:

**BUY Entry** (lines 84-91):
```
Condition: ALL của sau
├─ MACD line > Signal line (cross up) → H4 uptrend
├─ AND Stochastic(7,5,3)['k'][-1] < 20 → M30 oversold
├─ AND Stochastic(13,13,5)['k'][-1] < 50 → M30 confirmation
├─ AND Close > MA10 → M5 price above short MA
└─ AND Close > MA20 → M5 price above long MA
```

**SELL Entry** (lines 126-132):
```
Condition: ALL của sau
├─ MACD line < Signal line (cross down) → H4 downtrend
├─ AND Stochastic(7,5,3)['k'][-1] > 80 → M30 overbought
├─ AND Stochastic(13,13,5)['k'][-1] > 50 → M30 confirmation
├─ AND Close < MA10 → M5 price below short MA
└─ AND Close < MA20 → M5 price below long MA
```

**Multi-Timeframe Hierarchy**:
```
H4 (Trend Direction)
  ↓
M30 (Momentum/Confirmation)
  ↓
M5 (Entry Point Precision)
```

### 5. Order Execution Layer

**Mục đích**: Gửi lệnh đến MT5 với quản lý rủi ro

**Flow** (lines 93-123, 136-163):

```
1. Check Price
   ├─ sell_price = mt5.symbol_info_tick(symbol).bid
   └─ buy_price = mt5.symbol_info_tick(symbol).ask

2. Calculate SL/TP
   ├─ SL = entry_price * (1 ± STOP_LOSS)
   └─ TP = entry_price * (1 ± TAKE_PROFIT)
   └─ STOP_LOSS = TAKE_PROFIT = 1.5 (tương tự ATR)

3. Build Request
   └─ request = {
        'action': mt5.TRADE_ACTION_DEAL,
        'symbol': 'BTCUSDm',
        'price': entry_price,
        'sl': stop_loss,
        'tp': take_profit,
        'deviation': 20,
        'type': mt5.ORDER_TYPE_BUY/SELL,
        'volume': 0.1,
        'type_time': mt5.ORDER_TIME_GTC,
        'type_filling': mt5.ORDER_FILLING_IOC,
        'comment': 'Py Buy/Sell Position'
      }

4. Send Order
   ├─ result = mt5.order_send(request)
   └─ Check result._asdict()['order'] != 0

5. Handle Result
   ├─ Success: Log trade, break loop
   └─ Failure: Log error, continue
```

**Order Parameters**:
| Parameter | Value | Ý Nghĩa |
|-----------|-------|--------|
| action | TRADE_ACTION_DEAL | Lệnh thị trường (market order) |
| type | ORDER_TYPE_BUY/SELL | Hướng giao dịch |
| volume | 0.1 | Kích thước (0.1 lot) |
| sl | entry*(1-1.5) | Stop loss (1.5x từ entry) |
| tp | entry*(1+1.5) | Take profit (1.5x từ entry) |
| deviation | 20 | Slippage tolerance (pips) |
| type_time | ORDER_TIME_GTC | Good-till-cancelled |
| type_filling | ORDER_FILLING_IOC | Immediate-or-cancel |

**Error Handling**:
- Check `result._asdict()['order'] == 0` → failure
- Get error message: `result._asdict()['comment']`
- Retry login nếu session mati
- Log timestamp khi trade executed

### 6. Notification Layer

**Mục đích**: Thông báo user qua Telegram

**Module**: `src/telegram.py` (58 dòng)

**Hàm Chính**:
```python
def send_message(msg, chat_id, max_retries=5, token=TOKEN,
                 disable_notification=True, debug=False)
```

**Features**:
- **Retry Logic**: Tối đa 5 lần, sleep 5 giây giữa lần
- **Multiple Recipients**: Support list chat_ids
- **Disable Sound**: `disable_notification=True`
- **Debug Mode**: In console thay vì gửi thực

**Flow**:
```
1. Validate chat_id
   ├─ Nếu string → convert thành list
   └─ Nếu list → dedup với set()

2. For each chat_id:
   ├─ POST /sendMessage
   ├─ Retry nếu fail (max 5 lần)
   ├─ Sleep 5s giữa retry
   └─ Log result

3. Error Handling
   └─ Catch generic Exception, retry
```

**Message Template** (sẽ implement):
```
Entry Signal:
📈 BUY SIGNAL on BTCUSDm
Entry: $28,500
SL: $27,975
TP: $29,025
Risk/Reward: 1:1.5

Trade Executed:
✅ BUY order #12345
Volume: 0.1
Entry: $28,500
Time: 2026-01-17 10:30 UTC
```

**Hardcoded Token**:
```python
TOKEN = "7363572293:AAHd595bWg7liBafg8qEmasPh8Zx1I2crWo"  # ⚠️ SECURITY
```
*Fix: Move to environment variables*

### 7. Logging Layer

**Mục đích**: Ghi lại chi tiết giao dịch và lỗi

**Hiện Tại**: Chỉ có `print()` statements
**Kế Hoạch**: Implement `logging` module

**Expected Log Levels**:
```python
logger.debug("Processing signal...")     # Chi tiết
logger.info("Trade executed: BUY 0.1")   # Thông tin quan trọng
logger.warning("High slippage: 50 pips") # Cảnh báo
logger.error("MT5 connection lost")      # Lỗi
logger.critical("Balance depleted")      # Nghiêm trọng
```

**Trade Log Format**:
```
Timestamp: 2026-01-17 10:30:45.123
Action: BUY
Symbol: BTCUSDm
Volume: 0.1
Entry: 28500.25
SL: 27975.25
TP: 29025.25
Status: SUCCESS
Comment: Py Buy Position
```

## Dòng Dữ Liệu (Data Flow)

### Main Loop

```
while True:
    ├─ 1. Get Data
    │  ├─ long_data = mt5.copy_rates_range(SYMBOL, H4, date_from, date_to)
    │  ├─ mid_data = mt5.copy_rates_range(SYMBOL, M30, date_from, date_to)
    │  └─ short_data = mt5.copy_rates_range(SYMBOL, M5, date_from, date_to)
    │
    ├─ 2. Calculate Indicators
    │  ├─ macd_line, signal_line = calculate_macd(long_data)
    │  ├─ first_stoch = calculate_stoch(mid_data, k_length=7, k_smooth=5, d_smooth=3)
    │  ├─ second_stoch = calculate_stoch(mid_data, k_length=13, k_smooth=13, d_smooth=5)
    │  ├─ ma_short = calculate_ma(short_data, 10)
    │  └─ ma_long = calculate_ma(short_data, 20)
    │
    ├─ 3. Detect Signals
    │  ├─ cross_macd = check_cross_2_list_updated(macd_line, signal_line)
    │  ├─ cross_price_ma_short = check_cross_2_list_updated(close_prices, ma_short)
    │  └─ cross_price_ma_long = check_cross_2_list_updated(close_prices, ma_long)
    │
    ├─ 4. Check Entry Conditions
    │  ├─ If ALL BUY conditions met:
    │  │  └─ Execute BUY order
    │  ├─ Else If ALL SELL conditions met:
    │  │  └─ Execute SELL order
    │  └─ Else:
    │     └─ Continue loop
    │
    ├─ 5. Execute Order (if triggered)
    │  ├─ Get current price (bid/ask)
    │  ├─ Calculate SL/TP
    │  ├─ Send order to MT5
    │  ├─ Check result
    │  └─ Log trade OR error
    │
    ├─ 6. Notify User
    │  ├─ Send Telegram alert
    │  └─ Include order details
    │
    └─ 7. Loop Next Cycle
```

## Kiến Trúc Quản Lý Trạng Thái

**Current State (Early PoC)**:
- Stateless execution (mỗi iteration độc lập)
- Không có persistent state
- Loop vô hạn, break sau 1 trade

**Future State (Phase 2)**:
```
State Variables:
├─ is_in_position: bool (có lệnh đang mở)
├─ position_type: 'BUY' | 'SELL' | None
├─ entry_price: float
├─ entry_time: datetime
├─ order_id: int
└─ pnl: float (realized P&L)

Entry Rules (với state):
├─ Allow BUY nếu NOT in_position
└─ Allow SELL nếu in_position AND position_type == 'BUY'

Exit Rules:
├─ SL hit → Automatic exit
├─ TP hit → Automatic exit
└─ Manual exit (Telegram command)
```

## Quy Trình Khởi Động

```
main.py (sắp implement)
  ├─ 1. Load config.yaml
  │  ├─ MT5 credentials
  │  ├─ Telegram tokens
  │  └─ Strategy parameters
  │
  ├─ 2. Initialize MT5
  │  ├─ mt5.initialize()
  │  └─ mt5.login(...)
  │
  ├─ 3. Initialize Telegram
  │  └─ Verify token valid
  │
  ├─ 4. Setup Logging
  │  ├─ Create logs/ directory
  │  └─ Setup file + console handlers
  │
  ├─ 5. Run Strategy Loop
  │  └─ Call ref.py main logic
  │
  └─ 6. Cleanup (on exit)
     ├─ mt5.shutdown()
     └─ Close log files
```

## Quản Lý Lỗi & Recovery

### Error Handling Strategy

```
┌─ MT5 Connection Error
│  ├─ Retry login (3 times)
│  ├─ Wait 5 seconds
│  └─ Exit if persist
│
├─ Order Send Failure
│  ├─ Log error
│  ├─ Parse error code
│  ├─ Retry if retriable (3 times)
│  └─ Continue to next cycle
│
├─ Data Fetch Empty
│  ├─ Retry 3 times
│  ├─ Wait 1 second between
│  └─ Continue if persistent
│
└─ Telegram Send Failure
   ├─ Retry 5 times
   ├─ Wait 5 seconds between
   └─ Log failure (non-blocking)
```

### Custom Exceptions (Planned)

```python
class MT5ConnectionError(Exception):
    """MT5 initialization or login failed"""
    pass

class OrderExecutionError(Exception):
    """Order send failed"""
    pass

class StrategyError(Exception):
    """Strategy logic error"""
    pass

class TelegramError(Exception):
    """Telegram notification failed"""
    pass
```

## Sơ Đồ Hoạt Động Tổng Quát

```
┌─────────────────────────────────────┐
│  MetaTrader5 Terminal (Running)     │
│  ├─ Symbol: BTCUSDm                 │
│  ├─ Account: Connected              │
│  └─ Real-time Prices                │
└────────────────┬────────────────────┘
                 │ OHLC Data (H4/M30/M5)
                 ▼
    ┌────────────────────────┐
    │  Bot Process (Python)  │
    │                        │
    │  ┌──────────────────┐  │
    │  │ Data Fetcher     │  │ (MT5 API)
    │  ├─ copy_rates_range│  │
    │  └──────────────────┘  │
    │         │              │
    │         ▼              │
    │  ┌──────────────────┐  │
    │  │ Calc Indicators  │  │ (calculation.py)
    │  ├─ MACD (H4)      │  │
    │  ├─ Stoch (M30)    │  │
    │  ├─ MA (M5)        │  │
    │  └──────────────────┘  │
    │         │              │
    │         ▼              │
    │  ┌──────────────────┐  │
    │  │ Detect Signals   │  │ (check_cross...)
    │  ├─ Crossovers     │  │
    │  ├─ Thresholds     │  │
    │  └──────────────────┘  │
    │         │              │
    │         ▼              │
    │  ┌──────────────────┐  │
    │  │ Strategy Logic   │  │ (Entry rules)
    │  ├─ BUY conditions │  │
    │  ├─ SELL conditions│  │
    │  └──────────────────┘  │
    │         │              │
    │    [If conditions met]  │
    │         │              │
    │         ▼              │
    │  ┌──────────────────┐  │
    │  │ Execute Order    │  │ (MT5 API)
    │  ├─ Calc SL/TP     │  │
    │  ├─ order_send()   │  │
    │  └──────────────────┘  │
    │         │              │
    │         ▼              │
    │  ┌──────────────────┐  │
    │  │ Notify User      │  │ (Telegram)
    │  ├─ Send alert     │  │
    │  ├─ Retry logic    │  │
    │  └──────────────────┘  │
    │         │              │
    │         ▼              │
    │  ┌──────────────────┐  │
    │  │ Log Trade        │  │
    │  ├─ File log        │  │
    │  ├─ Console output  │  │
    │  └──────────────────┘  │
    │         │              │
    └─────────┼──────────────┘
              │
              ▼ (Next iteration)
         [Loop back to 1]
```

## Module Dependency Graph

```
main.py (Entry point - chưa implement)
  └─ ref.py (Strategy runner)
     ├─ src.calculation
     │  ├─ calculate_macd()
     │  ├─ calculate_stoch()
     │  ├─ calculate_ma()
     │  ├─ calculate_ema()
     │  ├─ check_cross_2_list_updated()
     │  └─ src.utils
     │     └─ non_zero_range()
     │
     ├─ MetaTrader5 (External API)
     │  └─ mt5.initialize(), mt5.login(), mt5.copy_rates_range(), etc
     │
     ├─ pandas (Data handling)
     │  └─ pd.DataFrame()
     │
     ├─ numpy (Numerical)
     │  └─ np.array operations
     │
     └─ src.telegram (Notifications - sắp integrate)
        └─ send_message()
           ├─ requests (HTTP)
           └─ time (Retry delay)
```

## Tương Lai: Kiến Trúc Nâng Cao

### Phase 2: Modular Architecture

```
BotForex/
├── bot/
│   ├── strategy.py       # Strategy interface
│   ├── mt5_connector.py   # MT5 abstraction
│   └── position_manager.py # State management
├── indicators/
│   ├── base.py           # Indicator interface
│   ├── macd.py
│   ├── stochastic.py
│   └── ma.py
├── notifications/
│   ├── base.py
│   └─ telegram.py
├── logging/
│   └─ trade_logger.py
└── main.py
```

### Phase 3: Multi-Instance Support

```
BotForex/
├── instances/
│   ├── instance_1.yaml   # BTC long
│   ├── instance_2.yaml   # EUR short
│   └── instance_3.yaml   # GLD neutral
└── bot_manager.py        # Manage multiple instances
```

## Tài Liệu Liên Quan

- [Project Overview & PDR](./project-overview-pdr.md)
- [Code Standards](./code-standards.md)
- [Codebase Summary](./codebase-summary.md)
- [Project Roadmap](./project-roadmap.md)

## Unresolved Design Questions

1. **State Management**: Lưu trữ position state ở đâu (memory/database)?
2. **Multi-Symbol**: Một bot chỉ handle 1 symbol hay multiple?
3. **Backtesting**: Integration point nào?
4. **Risk Management**: Thêm max loss per day?
5. **Alert Frequency**: Gửi alert mỗi signal hay chỉ executed order?
