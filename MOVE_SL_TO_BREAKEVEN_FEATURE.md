# Move SL to Breakeven - Feature Documentation

## Tổng Quan

Tính năng "Move SL to Breakeven" tự động dời Stop Loss lên điểm hòa vốn (entry price) khi giá đạt được một phần mục tiêu (TP), giúp bảo vệ lợi nhuận và biến trade thành "risk-free" (chỉ có thể hòa vốn hoặc thắng).

## Cách Hoạt Động

### Ví Dụ: Lệnh BUY

**Setup ban đầu:**
- Entry: 5000
- SL: 4990 (risk 10 pips)
- TP: 5020 (reward 20 pips, RR = 2:1)

**Khi bật Move SL to Breakeven với trigger 50%:**
- Trigger Price = Entry + (TP - Entry) × 50% = 5000 + (5020 - 5000) × 50% = 5010
- Khi giá đạt 5010 → SL tự động dời lên 5000 (= Entry)
- **Kết quả:** Trade chỉ có thể hòa vốn (5000) hoặc thắng (5020), không thể thua!

### Ví Dụ: Lệnh SELL

**Setup ban đầu:**
- Entry: 5000
- SL: 5010 (risk 10 pips)
- TP: 4980 (reward 20 pips, RR = 2:1)

**Khi bật Move SL to Breakeven với trigger 50%:**
- Trigger Price = Entry - (Entry - TP) × 50% = 5000 - (5000 - 4980) × 50% = 4990
- Khi giá đạt 4990 → SL tự động dời xuống 5000 (= Entry)
- **Kết quả:** Trade chỉ có thể hòa vốn (5000) hoặc thắng (4980), không thể thua!

## Cấu Hình

### Parameters

1. **move_sl_to_breakeven** (bool)
   - `True`: Bật tính năng
   - `False`: Tắt tính năng (mặc định)

2. **breakeven_trigger_percent** (float)
   - Giá trị: 10% - 90%
   - Mặc định: 50%
   - Ý nghĩa: Khi giá đạt được X% của khoảng cách đến TP, SL sẽ được dời về entry

### Trong Bot Create UI

1. Vào trang **Bots**
2. Phần **Exit Types** → tìm checkbox **"Move SL to Breakeven"**
3. Tích vào checkbox để bật tính năng
4. Điều chỉnh **"Breakeven Trigger (%)"** nếu cần (mặc định 50%)

### Via Command Line

```bash
python src/bot_runner.py \
  --strategy master_candle \
  --symbol XAUUSD \
  --user admin \
  --test 0 \
  --move_sl_to_breakeven 1 \
  --breakeven_trigger_percent 50
```

## Telegram Notification

Khi SL được dời về breakeven, bot sẽ gửi thông báo:

```
[OK] SL Moved to Breakeven

Symbol: XAUUSD
Direction: BUY
Entry: 5000.00
New SL: 5000.00
Trigger: 5010.00 (50% TP)

Trade is now risk-free!
```

## Logic Chi Tiết

### BUY Order
```python
# Tính trigger price
tp_distance = TP - Entry
trigger_price = Entry + (tp_distance × trigger_percent / 100)

# Kiểm tra nếu giá đạt trigger (dùng HIGH của candle)
if candle_high >= trigger_price:
    new_sl = Entry  # Dời SL về entry
    # Modify position trong MT5 (LIVE mode)
    # hoặc update active_trade (TEST mode)
```

### SELL Order
```python
# Tính trigger price
tp_distance = Entry - TP
trigger_price = Entry - (tp_distance × trigger_percent / 100)

# Kiểm tra nếu giá đạt trigger (dùng LOW của candle)
if candle_low <= trigger_price:
    new_sl = Entry  # Dời SL về entry
    # Modify position trong MT5 (LIVE mode)
    # hoặc update active_trade (TEST mode)
```

## Implementation Details

### Files Modified

1. **src/bot_runner.py**
   - Added parameters: `move_sl_to_breakeven`, `breakeven_trigger_percent`
   - Added monitoring logic to check trigger and move SL
   - Added tracking field: `sl_moved_to_breakeven` in `active_trade`
   - Works in both TEST and LIVE modes

2. **src/bot_manager.py**
   - Added parameters to `start_bot()` function
   - Added parameters to command building
   - Added parameters to bot_info storage
   - Added parameters to `restart_bot()`

3. **pages/1_Bots.py**
   - Added UI checkbox and number input
   - Added parameters to bot creation call

### MT5 Position Modification (LIVE Mode)

```python
request = {
    "action": mt5.TRADE_ACTION_SLTP,
    "symbol": symbol,
    "position": ticket,
    "sl": new_sl,
    "tp": tp
}
result = mt5.order_send(request)
```

## Best Practices

### Trigger Percent Recommendations

| Trigger % | Risk Level | Use Case |
|-----------|-----------|----------|
| 25-35% | Aggressive | Nhanh chóng bảo vệ lợi nhuận, phù hợp với thị trường biến động cao |
| 40-60% | Balanced | Cân bằng giữa bảo vệ và cho phép trade phát triển |
| 65-80% | Conservative | Cho phép trade có nhiều không gian, chỉ bảo vệ khi gần TP |

### Khi Nào Nên Dùng

✅ **Nên dùng khi:**
- Thị trường biến động cao (XAUUSD, crypto)
- RR ratio ≥ 2:1
- Muốn bảo vệ lợi nhuận sớm
- Trading trong news events
- Không thể monitor trades liên tục

❌ **Không nên dùng khi:**
- RR ratio < 1.5:1 (ít không gian để dời SL)
- Thị trường range-bound (giá dễ hit breakeven rồi reverse)
- Muốn tối đa hóa lợi nhuận (chấp nhận rủi ro cao hơn)

## Testing

### Test Mode
```bash
# Test với demo account
python src/bot_runner.py \
  --strategy master_candle \
  --symbol XAUUSD \
  --user user \
  --test 1 \
  --move_sl_to_breakeven 1 \
  --breakeven_trigger_percent 50 \
  --entry_time "$(date +%H:%M)"
```

Bot sẽ:
1. Đặt lệnh test (không có order thật)
2. Monitor candles
3. Khi giá đạt 50% TP → gửi notification
4. Update SL trong tracking (không modify order thật)

### Live Mode
- Kiểm tra trong LIVE mode với demo account
- Bot sẽ modify position SL trong MT5 thật sự
- Verify bằng cách xem position trong MT5 terminal

## Troubleshooting

### Issue: SL không được dời

**Nguyên nhân:**
- Giá chưa đạt trigger price
- Bot đang offline/crashed
- MT5 không cho phép modify (market closed, insufficient margin)

**Giải pháp:**
- Check logs: `[OK] SL moved to breakeven: ...`
- Verify trigger price calculation
- Check MT5 connection

### Issue: Lệnh bị đóng tại breakeven

**Đây KHÔNG phải bug!** Đó là cách feature hoạt động đúng:
- Giá đạt trigger → SL dời về entry
- Giá reverse → hit SL tại entry → đóng lệnh hòa vốn
- **Đây là mục đích của feature: Bảo vệ vốn!**

## Benefits

1. **Risk Management:** Giảm risk về 0 khi đạt trigger
2. **Peace of Mind:** Không lo lỗ sau khi SL moved
3. **Flexibility:** Điều chỉnh trigger % theo trading style
4. **Automation:** Không cần manually modify SL
5. **Consistency:** Logic rõ ràng, không phụ thuộc cảm xúc

## Status

✅ **COMPLETED AND READY TO USE**

- Implementation: ✅ Done
- Testing: ✅ Verified
- Documentation: ✅ Complete
- UI Integration: ✅ Complete
