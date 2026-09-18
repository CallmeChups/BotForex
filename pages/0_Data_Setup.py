"""Shared market-data cache setup."""

from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import streamlit as st

from src.auth import (
    require_auth,
    get_user_mt5_credentials,
    get_user_mt5_backtest_credentials,
)
from src.ohlc_cache import CACHE_FILE, TIMEFRAME_MINUTES, ensure_range, get_metadata


st.set_page_config(page_icon="💾", page_title="Data Setup", layout="wide")
username, _ = require_auth()
TIMEZONE = ZoneInfo("Asia/Ho_Chi_Minh")


def _get_data_credentials(username: str) -> tuple[dict, str]:
    """Use the configured Backtest account, falling back to the live account."""
    backtest_credentials = get_user_mt5_backtest_credentials(username)
    if all(backtest_credentials.values()):
        return backtest_credentials, "Backtest MT5 Override"
    return get_user_mt5_credentials(username), "MT5 Account trong Settings"


def main():
    st.title("💾 Market Data Setup")
    st.caption("Cache dùng chung trên máy cho Backtest. Mặc định preload 90 ngày gần nhất.")

    col1, col2 = st.columns(2)
    with col1:
        # MT5 symbol names can be case-sensitive (for example, XAUUSDm).
        symbol = st.text_input("Symbol", value="XAUUSDm").strip()
        days = st.number_input(
            "Số ngày preload", min_value=90, max_value=3650,
            value=90, step=90,
            help="Mặc định là 90 ngày; có thể tải thêm lịch sử khi cần.",
        )
    with col2:
        timeframes = st.multiselect(
            "Timeframe cần preload",
            options=list(TIMEFRAME_MINUTES),
            default=["M1", "M5"],
            help="Multi Flappy Bird mặc định cần M1 và M5.",
        )
        st.info(f"Database: `{Path(CACHE_FILE).name}`")

    credentials, credential_source = _get_data_credentials(username)
    login_label = credentials.get("login") or "chưa cấu hình"
    server_label = credentials.get("server") or "chưa cấu hình"
    st.caption(
        f"Account dùng để tải dữ liệu: `{login_label}` @ `{server_label}` "
        f"({credential_source})"
    )

    if st.button("⬇️ Preload / cập nhật dữ liệu", type="primary", width="stretch"):
        if not symbol:
            st.error("Vui lòng nhập symbol.")
        elif not timeframes:
            st.error("Vui lòng chọn ít nhất một timeframe.")
        else:
            end = datetime.now(TIMEZONE)
            start = end - timedelta(days=int(days))
            failed = False
            for timeframe in timeframes:
                with st.status(f"Đang cập nhật {symbol} / {timeframe}...", expanded=False) as status:
                    _, error, source = ensure_range(
                        symbol, timeframe, start, end, credentials
                    )
                    if error:
                        failed = True
                        status.update(label=f"{timeframe}: lỗi", state="error")
                        st.error(f"{symbol} / {timeframe}: {error}")
                    else:
                        status.update(
                            label=f"{timeframe}: {'đã lấy thêm' if source == 'fetched' else 'đã có sẵn'}",
                            state="complete",
                        )
            if failed:
                st.warning("Một hoặc nhiều timeframe chưa cập nhật thành công.")
            else:
                st.success("Đã hoàn tất cập nhật cache.")

    st.subheader("Trạng thái cache")
    rows = []
    for timeframe in TIMEFRAME_MINUTES:
        metadata = get_metadata(symbol, timeframe)
        if metadata is None:
            rows.append({
                "Symbol": symbol, "Timeframe": timeframe,
                "Từ": "-", "Đến": "-", "Số nến": 0, "Cập nhật": "-", "Trạng thái": "Chưa có",
            })
            continue
        oldest = datetime.fromtimestamp(metadata["oldest_open_time_utc"], TIMEZONE)
        newest = datetime.fromtimestamp(metadata["newest_open_time_utc"], TIMEZONE)
        rows.append({
            "Symbol": symbol,
            "Timeframe": timeframe,
            "Từ": oldest.strftime("%Y-%m-%d %H:%M"),
            "Đến": newest.strftime("%Y-%m-%d %H:%M"),
            "Số nến": metadata["candle_count"],
            "Cập nhật": metadata["last_sync_utc"][:19].replace("T", " "),
            "Trạng thái": "Sẵn sàng",
        })
    st.dataframe(rows, width="stretch", hide_index=True)


if __name__ == "__main__":
    main()
