"""Shared SQLite cache for MT5 OHLC candles."""

from __future__ import annotations

import sqlite3
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd


DATA_DIR = Path(__file__).resolve().parent.parent / "data"
CACHE_FILE = DATA_DIR / "ohlc_cache.sqlite3"
TIMEFRAME_MINUTES = {
    "M1": 1, "M5": 5, "M15": 15, "M30": 30,
    "H1": 60, "H4": 240, "D1": 1440,
}
OHLC_COLUMNS = (
    "time", "open", "high", "low", "close", "tick_volume", "spread", "real_volume"
)
LOCAL_TIMEZONE = ZoneInfo("Asia/Ho_Chi_Minh")
MARKET_HOLIDAYS = {(1, 1), (12, 25), (12, 26)}


def _connect(path: Path = CACHE_FILE) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path)
    connection.execute("PRAGMA journal_mode=WAL")
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS ohlc_candles (
            symbol TEXT NOT NULL,
            timeframe TEXT NOT NULL,
            open_time_utc INTEGER NOT NULL,
            open REAL NOT NULL,
            high REAL NOT NULL,
            low REAL NOT NULL,
            close REAL NOT NULL,
            tick_volume INTEGER,
            spread INTEGER,
            real_volume INTEGER,
            PRIMARY KEY (symbol, timeframe, open_time_utc)
        )
        """
    )
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS ohlc_metadata (
            symbol TEXT NOT NULL,
            timeframe TEXT NOT NULL,
            oldest_open_time_utc INTEGER,
            newest_open_time_utc INTEGER,
            candle_count INTEGER NOT NULL DEFAULT 0,
            last_sync_utc TEXT NOT NULL,
            PRIMARY KEY (symbol, timeframe)
        )
        """
    )
    return connection


def _timestamps_to_epoch(values) -> list[int]:
    timestamps = pd.to_datetime(values, utc=True)
    return [int(value.timestamp()) for value in timestamps]


def append_candles(
    symbol: str,
    timeframe: str,
    candles: pd.DataFrame,
    path: Path = CACHE_FILE,
) -> int:
    """Insert or replace candles and refresh dataset metadata."""
    if timeframe not in TIMEFRAME_MINUTES:
        raise ValueError(f"Unsupported timeframe: {timeframe}")
    if candles is None or candles.empty:
        return 0
    missing = [column for column in ("time", "open", "high", "low", "close") if column not in candles]
    if missing:
        raise ValueError(f"OHLC data missing columns: {', '.join(missing)}")

    frame = candles.copy()
    epochs = _timestamps_to_epoch(frame["time"])
    rows = []
    for index, row in frame.reset_index(drop=True).iterrows():
        rows.append((
            symbol, timeframe, epochs[index],
            float(row["open"]), float(row["high"]),
            float(row["low"]), float(row["close"]),
            int(row.get("tick_volume", 0) or 0),
            int(row.get("spread", 0) or 0),
            int(row.get("real_volume", 0) or 0),
        ))
    with _connect(path) as connection:
        connection.executemany(
            """
            INSERT OR REPLACE INTO ohlc_candles
            (symbol, timeframe, open_time_utc, open, high, low, close,
             tick_volume, spread, real_volume)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            rows,
        )
        connection.execute(
            """
            INSERT INTO ohlc_metadata
            (symbol, timeframe, oldest_open_time_utc, newest_open_time_utc,
             candle_count, last_sync_utc)
            SELECT symbol, timeframe, MIN(open_time_utc), MAX(open_time_utc),
                   COUNT(*), ?
            FROM ohlc_candles
            WHERE symbol = ? AND timeframe = ?
            ON CONFLICT(symbol, timeframe) DO UPDATE SET
              oldest_open_time_utc=excluded.oldest_open_time_utc,
              newest_open_time_utc=excluded.newest_open_time_utc,
              candle_count=excluded.candle_count,
              last_sync_utc=excluded.last_sync_utc
            """,
            (datetime.now(timezone.utc).isoformat(), symbol, timeframe),
        )
    return len(rows)


def get_metadata(symbol: str, timeframe: str, path: Path = CACHE_FILE) -> dict | None:
    with _connect(path) as connection:
        row = connection.execute(
            """
            SELECT oldest_open_time_utc, newest_open_time_utc, candle_count,
                   last_sync_utc
            FROM ohlc_metadata WHERE symbol=? AND timeframe=?
            """,
            (symbol, timeframe),
        ).fetchone()
    if row is None:
        return None
    return {
        "symbol": symbol, "timeframe": timeframe,
        "oldest_open_time_utc": row[0],
        "newest_open_time_utc": row[1],
        "candle_count": row[2],
        "last_sync_utc": row[3],
    }


def load_range(
    symbol: str,
    timeframe: str,
    start: datetime,
    end: datetime,
    path: Path = CACHE_FILE,
) -> pd.DataFrame:
    start_epoch, end_epoch = _timestamps_to_epoch([start, end])
    with _connect(path) as connection:
        rows = connection.execute(
            """
            SELECT open_time_utc, open, high, low, close,
                   tick_volume, spread, real_volume
            FROM ohlc_candles
            WHERE symbol=? AND timeframe=?
              AND open_time_utc >= ? AND open_time_utc <= ?
            ORDER BY open_time_utc
            """,
            (symbol, timeframe, start_epoch, end_epoch),
        ).fetchall()
    columns = ["time", "open", "high", "low", "close",
               "tick_volume", "spread", "real_volume"]
    frame = pd.DataFrame(rows, columns=columns)
    if not frame.empty:
        frame["time"] = pd.to_datetime(frame["time"], unit="s", utc=True)
        frame["time"] = frame["time"].dt.tz_convert("Asia/Ho_Chi_Minh")
    return frame


def _interior_gaps(
    symbol: str,
    timeframe: str,
    start: datetime,
    end: datetime,
    path: Path,
) -> list[tuple[datetime, datetime]]:
    """Find short interior gaps; long gaps are normal market closures."""
    frame = load_range(symbol, timeframe, start, end, path)
    if len(frame) < 2:
        return []
    step = timedelta(minutes=TIMEFRAME_MINUTES[timeframe])
    timestamps = list(pd.to_datetime(frame["time"], utc=True))
    gaps = []
    for previous, current in zip(timestamps, timestamps[1:]):
        gap_duration = current - previous
        if step < gap_duration <= timedelta(days=3):
            # Forex/CFD markets are normally closed over the weekend. A gap
            # crossing any Saturday/Sunday is expected and must not be fetched.
            calendar_days = (current.date() - previous.date()).days
            crosses_weekend = any(
                (previous + timedelta(days=offset)).weekday() >= 5
                for offset in range(calendar_days + 1)
            )
            if crosses_weekend:
                continue
            # Many CFD symbols also have a daily rollover/session break. Treat
            # a same-day gap of up to six hours as a normal market closure.
            if previous.date() == current.date() and gap_duration <= timedelta(hours=6):
                continue
            if _is_expected_market_closure(
                previous.to_pydatetime(), current.to_pydatetime()
            ):
                continue
            gaps.append((
                previous.to_pydatetime() + step,
                current.to_pydatetime() - step,
            ))
    return gaps


def _is_expected_market_closure(start: datetime, end: datetime) -> bool:
    """Return whether a boundary gap is a normal weekend/session closure."""
    start_local = start.astimezone(LOCAL_TIMEZONE)
    end_local = end.astimezone(LOCAL_TIMEZONE)
    duration = end_local - start_local
    if duration <= timedelta(0):
        return False
    if duration > timedelta(days=3):
        return False
    if start_local.date() == end_local.date() and duration <= timedelta(hours=6):
        return True
    calendar_days = (end_local.date() - start_local.date()).days
    crosses_weekend = any(
        (start_local + timedelta(days=offset)).weekday() >= 5
        for offset in range(calendar_days + 1)
    )
    # Keep holiday handling explicit: broker CFD feeds commonly close longer
    # than the daily break on these fixed-date market holidays.
    return crosses_weekend or any(
        (start_local + timedelta(days=offset)).strftime("%m-%d") in {
            f"{month:02d}-{day:02d}" for month, day in MARKET_HOLIDAYS
        }
        for offset in range(calendar_days + 1)
    )


def _fetch_mt5_range(
    symbol: str,
    timeframe: str,
    start: datetime,
    end: datetime,
    credentials: dict,
) -> tuple[pd.DataFrame | None, str | None]:
    try:
        import MetaTrader5 as mt5
    except ImportError:
        return None, "MT5 not available (Windows only)"
    from src.backtest import get_mt5_timeframe

    if not mt5.initialize():
        return None, "MT5 initialization failed"
    try:
        login = int(credentials.get("login") or 0)
        password = credentials.get("password", "")
        server = credentials.get("server", "")
        if not login or not password or not server:
            return None, "MT5 credentials not configured"
        if not mt5.login(login=login, password=password, server=server):
            return None, f"MT5 login failed: {mt5.last_error()}"
        symbol_info = mt5.symbol_info(symbol)
        if symbol_info is None:
            return None, (
                f"MT5 không tìm thấy symbol '{symbol}'. "
                f"Kiểm tra account/server và tên symbol trong Market Watch."
            )
        if not mt5.symbol_select(symbol, True):
            return None, f"MT5 không thể bật symbol '{symbol}': {mt5.last_error()}"
        # Request a small recent slice first. Some MT5 terminals load symbol
        # history asynchronously after the first rates request.
        mt5_timeframe = get_mt5_timeframe(timeframe)
        warmup_rates = None
        for _ in range(10):
            warmup_rates = mt5.copy_rates_from_pos(symbol, mt5_timeframe, 0, 2)
            if warmup_rates is not None and len(warmup_rates):
                break
            time.sleep(1)
        if warmup_rates is None or not len(warmup_rates):
            requested_root = symbol.upper().removesuffix("M")
            matching_symbols = [
                item.name for item in (mt5.symbols_get() or ())
                if item.name.upper().startswith(requested_root)
            ][:10]
            return None, (
                f"MT5 chưa tải history cho {symbol} {timeframe} sau 10 giây "
                f"(symbol đang dùng: {symbol}; symbol tương tự trong Market Watch: "
                f"{', '.join(matching_symbols) or 'không có'}). "
                f"Hãy mở chart {symbol}/{timeframe} trong đúng terminal MT5 "
                f"đang chạy rồi thử lại."
            )

        chunk = timedelta(days=30)
        frames = []
        cursor = start.astimezone(timezone.utc)
        end_utc = end.astimezone(timezone.utc)
        while cursor <= end_utc:
            chunk_end = min(cursor + chunk - timedelta(seconds=1), end_utc)
            rates = mt5.copy_rates_range(
                symbol, mt5_timeframe, cursor, chunk_end
            )
            if rates is not None and len(rates):
                frames.append(pd.DataFrame(rates))
            cursor = chunk_end + timedelta(seconds=1)
        if not frames:
            # Some terminals/brokers return no rows from copy_rates_range until
            # history has been loaded in the terminal. Probe the available
            # recent bars so the error can distinguish missing history from an
            # invalid symbol.
            recent_rates = mt5.copy_rates_from_pos(
                symbol, get_mt5_timeframe(timeframe), 0, 100_000
            )
            if recent_rates is not None and len(recent_rates):
                recent_frame = pd.DataFrame(recent_rates)
                recent_frame["time"] = pd.to_datetime(
                    recent_frame["time"], unit="s", utc=True
                )
                available_start = recent_frame["time"].min().strftime("%Y-%m-%d")
                available_end = recent_frame["time"].max().strftime("%Y-%m-%d")
                return None, (
                    f"MT5 chỉ có dữ liệu {symbol} {timeframe} từ "
                    f"{available_start} đến {available_end}; không có dữ liệu "
                    f"trong khoảng yêu cầu. Hãy tăng 'Max bars in chart' trong "
                    f"MT5 hoặc mở chart {symbol} để tải lịch sử."
                )
            return None, (
                f"MT5 không trả về dữ liệu lịch sử cho {symbol} {timeframe}. "
                f"Đăng nhập thành công nhưng terminal chưa tải history; hãy "
                f"mở chart {symbol}, chọn timeframe {timeframe}, rồi thử lại."
            )
        frame = pd.concat(frames, ignore_index=True).drop_duplicates(subset=["time"])
        frame["time"] = pd.to_datetime(frame["time"], unit="s", utc=True).dt.tz_convert(
            "Asia/Ho_Chi_Minh"
        )
        frame = frame.sort_values("time").reset_index(drop=True)
        # MT5 can return a recent subset silently when the terminal's
        # "Max bars in chart" limit is lower than the requested history.
        # Do not mark that subset as a successful preload; otherwise the cache
        # looks healthy while the requested leading months remain unavailable.
        requested_start = start.astimezone(timezone.utc)
        requested_end = end.astimezone(timezone.utc)
        actual_start = pd.Timestamp(frame["time"].iloc[0]).tz_convert("UTC").to_pydatetime()
        actual_end = pd.Timestamp(frame["time"].iloc[-1]).tz_convert("UTC").to_pydatetime()
        tolerance = timedelta(days=7)
        if actual_start > requested_start + tolerance:
            return None, (
                f"MT5 chỉ trả dữ liệu {symbol} {timeframe} từ "
                f"{actual_start.strftime('%Y-%m-%d %H:%M')} trong khi cần từ "
                f"{requested_start.strftime('%Y-%m-%d %H:%M')}. "
                "Hãy tăng MT5 > Tools > Options > Charts > Max bars in chart "
                "(khuyến nghị 1,000,000), restart MT5 và mở lại chart/timeframe."
            )
        if actual_end < requested_end - tolerance:
            return None, (
                f"MT5 chỉ trả dữ liệu {symbol} {timeframe} đến "
                f"{actual_end.strftime('%Y-%m-%d %H:%M')} trong khi cần đến "
                f"{requested_end.strftime('%Y-%m-%d %H:%M')}. "
                "Hãy mở chart đúng symbol/timeframe để MT5 tải thêm history rồi thử lại."
            )
        return frame, None
    except Exception as error:
        return None, str(error)
    finally:
        mt5.shutdown()


def ensure_range(
    symbol: str,
    timeframe: str,
    start: datetime,
    end: datetime,
    credentials: dict,
    path: Path = CACHE_FILE,
) -> tuple[pd.DataFrame | None, str | None, str]:
    """Return a cached range, fetching only missing leading/trailing ranges."""
    if timeframe not in TIMEFRAME_MINUTES:
        return None, f"Unsupported timeframe: {timeframe}", "error"
    step_seconds = TIMEFRAME_MINUTES[timeframe] * 60
    # MT5 does not return the currently forming candle. Align the requested
    # end to the last completed candle so a complete cache is not treated as
    # missing merely because the clock is inside the active candle.
    end_epoch = int(end.astimezone(timezone.utc).timestamp())
    normalized_end = datetime.fromtimestamp(
        end_epoch - (end_epoch % step_seconds), timezone.utc
    ) - timedelta(seconds=step_seconds)
    if start >= normalized_end:
        return None, "Start date must be before end date", "error"
    end = normalized_end
    metadata = get_metadata(symbol, timeframe, path)
    fetch_ranges = []
    fetched_any = False
    if metadata is None:
        fetch_ranges.append((start, end))
    else:
        oldest = datetime.fromtimestamp(metadata["oldest_open_time_utc"], timezone.utc)
        newest = datetime.fromtimestamp(metadata["newest_open_time_utc"], timezone.utc)
        start_utc, end_utc = start.astimezone(timezone.utc), end.astimezone(timezone.utc)
        step = timedelta(minutes=TIMEFRAME_MINUTES[timeframe])
        if start_utc < oldest:
            fetch_ranges.append((start_utc, min(end_utc, oldest - step)))
        if end_utc > newest:
            trailing_start = max(start_utc, newest + step)
            # Brokers can publish the newest bar with a short delay. Do not
            # fail an otherwise complete preload because only one or two
            # just-closed candles are not available yet.
            trailing_candles = int((end_utc - trailing_start) / step) + 1
            if trailing_candles > 2:
                fetch_ranges.append((trailing_start, end_utc))

    for fetch_start, fetch_end in fetch_ranges:
        if fetch_start > fetch_end:
            continue
        frame, error = _fetch_mt5_range(symbol, timeframe, fetch_start, fetch_end, credentials)
        if error:
            if _is_expected_market_closure(fetch_start, fetch_end):
                continue
            direction = "đầu" if fetch_start <= start.astimezone(timezone.utc) else "cuối"
            return None, (
                f"Cache thiếu dữ liệu ở {direction} khoảng yêu cầu "
                f"({fetch_start.strftime('%Y-%m-%d %H:%M')} → "
                f"{fetch_end.strftime('%Y-%m-%d %H:%M')}). {error}"
            ), "error"
        append_candles(symbol, timeframe, frame, path)
        fetched_any = True

    for fetch_start, fetch_end in _interior_gaps(symbol, timeframe, start, end, path):
        frame, error = _fetch_mt5_range(symbol, timeframe, fetch_start, fetch_end, credentials)
        if error:
            return None, (
                f"Cache có gap nội bộ cần bổ sung "
                f"({fetch_start.strftime('%Y-%m-%d %H:%M')} → "
                f"{fetch_end.strftime('%Y-%m-%d %H:%M')}). {error}"
            ), "error"
        append_candles(symbol, timeframe, frame, path)
        fetched_any = True

    result = load_range(symbol, timeframe, start, end, path)
    if result.empty:
        return None, "Cache không có dữ liệu trong khoảng đã chọn.", "missing"
    requested_start = start.astimezone(timezone.utc)
    requested_end = end.astimezone(timezone.utc)
    actual_start = pd.Timestamp(result["time"].iloc[0]).tz_convert("UTC").to_pydatetime()
    actual_end = pd.Timestamp(result["time"].iloc[-1]).tz_convert("UTC").to_pydatetime()
    if actual_start > requested_start and not _is_expected_market_closure(
        requested_start, actual_start
    ):
        return None, (
            f"Cache chưa đủ dữ liệu đầu khoảng yêu cầu: có từ "
            f"{actual_start.strftime('%Y-%m-%d %H:%M')} UTC, cần từ "
            f"{requested_start.strftime('%Y-%m-%d %H:%M')} UTC. "
            "Hãy preload lại sau khi MT5 tải đủ history."
        ), "missing"
    if actual_end < requested_end and not _is_expected_market_closure(
        actual_end, requested_end
    ):
        return None, (
            f"Cache chưa đủ dữ liệu cuối khoảng yêu cầu: có đến "
            f"{actual_end.strftime('%Y-%m-%d %H:%M')} UTC, cần đến "
            f"{requested_end.strftime('%Y-%m-%d %H:%M')} UTC. "
            "Hãy preload lại sau khi MT5 tải đủ history."
        ), "missing"
    return result, None, "fetched" if fetched_any else "cache"
