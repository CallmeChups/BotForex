# Hướng Dẫn Sử Dụng Logs

## Vị Trí Logs

Tất cả logs được lưu trong folder `logs/`:
- Format: `bot_<strategy>_<symbol>_<user>_<pid>_<timestamp>.log`
- Ví dụ: `logs/bot_master_candle_XAUUSD_admin_12345_20260201_141530.log`

## Cách Xem Logs

### Cách 1: Sử dụng Script (Đơn giản nhất)

```bash
python view_logs.py
```

Script này cho phép:
- Liệt kê tất cả log files
- Xem log file cụ thể
- Theo dõi log real-time (giống `tail -f`)

### Cách 2: Mở File Trực Tiếp

Mở file log bằng bất kỳ text editor nào:
- Notepad
- Notepad++
- VS Code
- Sublime Text

### Cách 3: Terminal

```bash
# Xem toàn bộ file
type logs\bot_12345.log

# Xem 50 dòng cuối
powershell -Command "Get-Content logs\bot_12345.log -Tail 50"

# Theo dõi real-time
powershell -Command "Get-Content logs\bot_12345.log -Wait -Tail 50"
```

## Cấu Trúc Logs

Bot ghi log theo 5 bước chính:

### STEP 1/5: Loading Strategy
```
[STEP 1/5] Loading strategy: master_candle
✓ Strategy loaded: Master Candle
  Strategy parameters: {...}
```

**Kiểm tra:**
- ❌ Nếu thấy "Strategy not found" → Strategy ID sai
- ✓ Nếu thấy "Strategy loaded" → OK

### STEP 2/5: Configuration
```
[STEP 2/5] Configuration:
  RR Ratio: 2.0
  Max Candles: 7
  Buffer K: 5.0 pips
  Entry Time: 14:15
  Timeframe: M5
  Entry Mode: range_percent
  Entry Percent: 30.0%
  Lot Mode: fixed
  Lot Size: 0.01
  TP Type: price_based
  SL Type: close_based
  Move SL to Breakeven: DISABLED
```

**Kiểm tra:** Tất cả thông số có đúng không?

### STEP 3/5: MT5 Credentials
```
[STEP 3/5] Getting MT5 credentials for user: admin
✓ MT5 credentials loaded:
  Login: 12345678
  Server: MetaQuotes-Demo
  Password: ********
```

**Kiểm tra:**
- ❌ Nếu thấy "No credentials found" → Chưa config MT5 account
- ❌ Nếu thấy "MT5 login not configured" → Thiếu login/password/server
- ✓ Nếu thấy credentials loaded → OK

### STEP 4/5: Telegram Notification
```
[STEP 4/5] Sending startup notification to Telegram
✓ Telegram notification sent
```
hoặc
```
⚠ Telegram notification failed (not critical)
```

### STEP 5/5: Main Loop Started
```
============================================================
[STEP 5/5] BOT MAIN LOOP STARTED
============================================================
✓ Waiting for entry time: 14:15
✓ Timeframe: M5
✓ Symbol: XAUUSD
✓ Check interval: 1s
✓ Current time: 14:10:30 01/02/2026

Bot is now running and monitoring...
Press Ctrl+C to stop or use 'Stop' button in UI
============================================================
```

**Kiểm tra:**
- ✓ Nếu thấy phần này → Bot đang chạy và chờ entry time
- ❌ Nếu KHÔNG thấy → Bot bị dừng ở bước trước, kiểm tra lại log

## Khi Đến Entry Time

Bot sẽ log chi tiết từng bước:

### 1/6: MT5 Connection
```
[1/6] Connecting to MT5...
  Server: MetaQuotes-Demo
  Login: 12345678
✓ MT5 connected successfully
```

### 2/6: Fetching Candle
```
[2/6] Fetching candle data...
  Symbol: XAUUSD
  Timeframe: M5
  Will check continuously for up to 2 seconds to get correct candle
✓ Correct candle found! (attempts: 3, time: 0.245s)
Candle: 14:10 (expected 14:10)
```

### 3/6: Analyzing Candle
```
[3/6] Analyzing candle...
  Candle Time: 2026-01-31 14:10:00
  O=2686.50000, H=2689.80000, L=2686.10000, C=2689.20000
  Body: 2.70000
  Pip value: 0.01
  Buffer K: 5.0 pips
  Buffer offset: 0.05000
```

### 4/6: Determining Direction
```
[4/6] Determining direction...
  Comparing: C (2689.20000) vs O (2686.50000)
✓ Direction: BUY (C > O: 2689.20000 > 2686.50000)
Entry Mode: range_percent (30.0%)
Entry = C - (30.0% × 2.70000) = 2689.20000 - 0.81000 = 2688.39000

=== BUY CALCULATION ===
Entry: 2688.39000
SL: L - buffer = 2686.10000 - 0.05000 = 2686.05000
Risk: 2.34000 (234.0 pips)
TP: Entry + (Risk × 2.0) = 2688.39000 + 4.68000 = 2693.07000
TP Distance: 468.0 pips
```

### 5/6: Calculating Lot Size
```
[5/6] Calculating lot size...
  Lot mode: fixed
  Final lot: 0.01
```

### 6/6: Placing Order
```
[6/6] Placing order...
  Test Mode: NO (LIVE ORDER)
  🔴 LIVE MODE: Placing real order on MT5 account
  Symbol: XAUUSD
  Direction: BUY
  Lot: 0.01
  Entry: 2688.39000
  SL: 2686.05000
  TP: 2693.07000

  Order Type: PENDING ORDER (LIMIT)
  Reason: Entry mode is 'range_percent' (30.0%)
  Price will wait at: 2688.39000

  Calling place_pending_order()...

  ✅ SUCCESS! Order placed
  Ticket: 123456789
  Message: Pending order placed at 2688.39000
```

hoặc nếu lỗi:

```
  ❌ FAILURE! Order placement failed
  Error message: ...

  Possible causes:
  1. AutoTrading not enabled in MT5
  2. Insufficient margin
  3. Invalid lot size
  4. Market closed
  5. Invalid SL/TP levels

  Bot will skip this entry and wait for next day
```

## Monitoring Active Trade

```
============================================================
✓ Trade Created and Tracking Started
============================================================
  Direction: BUY
  Entry: 2688.39000
  SL: 2686.05000
  TP: 2693.07000
  Lot: 0.01
  Ticket: 123456789
  Is Pending: True
  Max Candles: 7
============================================================

Bot will now monitor this trade until exit...
```

## Các Log Khác

### Heartbeat (Mỗi 30s)
```
[Loop 30] ⏰ 14:15:30 | Entry: 14:15 | Active: False
[Loop 60] ⏰ 14:16:00 | Entry: 14:15 | Active: True
```

### Pending Order Filled
```
[OK] Pending order FILLED! Order filled at 2688.39000
Actual position - Entry=2688.39000, SL=2686.05000, TP=2693.07000
```

### TP/SL Hit
```
✓ Position closed by MT5 (SL/TP hit)
Fetching closed trades to determine exit reason...
Exit: TP HIT at 2693.07000
P&L: +468.0 pips
```

## Kiểm Tra Bot Có Chạy Không

1. **Check log file mới nhất:**
   ```bash
   dir logs\ /O-D
   ```
   File mới nhất phải có timestamp gần với thời điểm bạn start bot

2. **Xem nội dung log:**
   - Phải thấy đủ 5 STEPS
   - Phải thấy "BOT MAIN LOOP STARTED"
   - Phải thấy heartbeat logs mỗi 30s

3. **Nếu không thấy "BOT MAIN LOOP STARTED":**
   - Bot đã dừng ở một trong 4 steps đầu
   - Đọc log để xem lỗi gì (thường là MT5 credentials)

## Lưu Ý

- **Mỗi bot tạo 1 file log riêng** - dễ dàng tracking
- **Logs được flush realtime** - có thể xem ngay khi bot đang chạy
- **Logs không tự động xóa** - cần định kỳ dọn dẹp folder `logs/`
- **File log khá chi tiết** - dễ dàng debug mọi vấn đề

## Ví Dụ Thực Tế

### Bot Không Start (MT5 Credentials Lỗi)

```
[2026-02-01 14:10:00] [INFO] === Bot Logs ===
[2026-02-01 14:10:00] [INFO] Log file: logs/bot_master_candle_XAUUSD_admin_12345_20260201_141000.log
[2026-02-01 14:10:00] [INFO] Bot ID: master_candle_XAUUSD_admin_12345
[2026-02-01 14:10:00] [INFO] Started: 2026-02-01 14:10:00
[2026-02-01 14:10:00] [INFO] ============================================================
[2026-02-01 14:10:00] [INFO] Starting bot: master_candle | XAUUSD | user=admin
[2026-02-01 14:10:00] [INFO] Process ID: 12345
[2026-02-01 14:10:00] [INFO] Test mode: YES
[2026-02-01 14:10:01] [INFO] [STEP 1/5] Loading strategy: master_candle
[2026-02-01 14:10:01] [INFO] ✓ Strategy loaded: Master Candle
[2026-02-01 14:10:01] [INFO]   Strategy parameters: {...}
[2026-02-01 14:10:01] [INFO] [STEP 2/5] Configuration:
[2026-02-01 14:10:01] [INFO]   RR Ratio: 2.0
... (config logs)
[2026-02-01 14:10:02] [INFO] [STEP 3/5] Getting MT5 credentials for user: admin
[2026-02-01 14:10:02] [ERROR] ❌ CRITICAL ERROR: No credentials found for user: admin
[2026-02-01 14:10:02] [ERROR] Solution: Go to Settings page and configure MT5 account
[2026-02-01 14:10:02] [ERROR] Bot cannot start without MT5 credentials
```

→ **Giải pháp:** Vào Settings page config MT5 account

### Bot Chạy OK, Đang Chờ Entry Time

```
... (startup logs)
[2026-02-01 14:10:05] [INFO] ============================================================
[2026-02-01 14:10:05] [INFO] [STEP 5/5] BOT MAIN LOOP STARTED
[2026-02-01 14:10:05] [INFO] ============================================================
[2026-02-01 14:10:05] [INFO] ✓ Waiting for entry time: 14:15
[2026-02-01 14:10:05] [INFO] ✓ Timeframe: M5
[2026-02-01 14:10:05] [INFO] ✓ Symbol: XAUUSD
[2026-02-01 14:10:05] [INFO] ✓ Check interval: 1s
[2026-02-01 14:10:05] [INFO] ✓ Current time: 14:10:05 01/02/2026
[2026-02-01 14:10:05] [INFO]
[2026-02-01 14:10:05] [INFO] Bot is now running and monitoring...
[2026-02-01 14:10:05] [INFO] Press Ctrl+C to stop or use 'Stop' button in UI
[2026-02-01 14:10:05] [INFO] ============================================================
[2026-02-01 14:10:35] [INFO] [Loop 30] ⏰ 14:10:35 | Entry: 14:15 | Active: False
[2026-02-01 14:11:05] [INFO] [Loop 60] ⏰ 14:11:05 | Entry: 14:15 | Active: False
```

→ **OK!** Bot đang chạy bình thường, chờ đến 14:15 sẽ vào lệnh
