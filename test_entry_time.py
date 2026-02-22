from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

TIMEZONE = ZoneInfo("Asia/Ho_Chi_Minh")

def check_entry_time(entry_time: str, timeframe_str: str, current_time: datetime) -> bool:
    """Check if current time is right after entry candle closes"""
    target_hour, target_minute = map(int, entry_time.split(':'))
    
    timeframe_minutes = {
        'M1': 1, 'M5': 5, 'M15': 15, 'M30': 30,
        'H1': 60, 'H4': 240, 'D1': 1440
    }
    offset_minutes = timeframe_minutes.get(timeframe_str, 5)
    
    # Create entry candle close time
    entry_dt = datetime(current_time.year, current_time.month, current_time.day, 
                       target_hour, target_minute, tzinfo=TIMEZONE)
    candle_close_dt = entry_dt + timedelta(minutes=offset_minutes)
    
    return current_time.hour == candle_close_dt.hour and current_time.minute == candle_close_dt.minute

# Test với data user
entry_time = "14:10"
timeframe = "M5"

# Candle 14:10 close lúc 14:15
test_time_1415 = datetime(2026, 1, 31, 14, 15, 0, tzinfo=TIMEZONE)
result = check_entry_time(entry_time, timeframe, test_time_1415)
print(f"Entry time: {entry_time}, Timeframe: {timeframe}")
print(f"Check at 14:15: {result} (Expected: True)")
print(f"Candle close time: 14:10 + 5 min = 14:15")
print()

# Test thời gian khác
test_time_1420 = datetime(2026, 1, 31, 14, 20, 0, tzinfo=TIMEZONE)
result2 = check_entry_time(entry_time, timeframe, test_time_1420)
print(f"Check at 14:20: {result2} (Expected: False)")
