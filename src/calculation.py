import numpy as np 
from src.utils import (
    non_zero_range,
)

def calculate_macd(
    df,
    period_fast: int = 12,
    period_slow: int = 26,
    signal: int = 9,
    column: str = "close",
    adjust: bool = False,
):
    EMA_fast = df[column].ewm(span=period_fast, adjust=adjust).mean()
    EMA_slow = df[column].ewm(span=period_slow, adjust=adjust).mean()
    MACD = EMA_fast - EMA_slow
    MACD_signal = MACD.ewm(span=signal, adjust=adjust).mean()

    return MACD.tolist(), MACD_signal.tolist()

def check_cross_2_list_updated(list_1, list_2, period=3, confirm=2):
    tmp_list_1 = list_1[-period:]
    tmp_list_2 = list_2[-period:]
    transition = 0
    prev_sign = 0
    change_index = 0
    for i in range(len(tmp_list_1)):
        if tmp_list_1[i] > tmp_list_2[i]:
            sign = 1
        elif tmp_list_1[i] < tmp_list_2[i]:
            sign = -1
        else:
            sign = 0
        if not prev_sign:
            prev_sign = sign
        elif sign != prev_sign:
            transition += 1
            change_index = i
        prev_sign = sign
        if transition >= 2:
            break
    if transition == 1:
        if prev_sign < 0 and period - change_index >= confirm:
            return {"up": False, "down": True}
        elif prev_sign > 0 and period - change_index >= confirm:
            return {"up": True, "down": False}
    return {"up": False, "down": False}

def calculate_ma(df, period):
    return df["close"].rolling(window=int(period)).mean().to_list()

def calculate_ema(df, period=100):
    close_prices = df["close"]
    sma = close_prices[:period].mean()
    multiplier = 2 / (period + 1)
    ema_values = [sma]
    for i in range(period, len(close_prices)):
        ema = (close_prices[i] - ema_values[-1]) * multiplier + ema_values[-1]
        ema_values.append(ema)

    return ema_values

def calculate_stoch(df, k_length=14, k_smooth=1, d_smooth=3):
    df['max_high'] = df['high'].rolling(k_length).max()
    df['min_low'] = df['low'].rolling(k_length).min()

    df['%K'] = (df['close'] - df['min_low']) * 100 / (non_zero_range(df['max_high'], df['min_low']))
    smooth_k_percentage = df['%K'].rolling(window=k_smooth).mean()
    smooth_d_percentage = smooth_k_percentage.rolling(window=d_smooth).mean()
 
    return {"k": smooth_k_percentage, "d": smooth_d_percentage}