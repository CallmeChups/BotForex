# Time Window Filter & Backtest History Column Redesign

**Ngày:** 2026-06-27
**Trạng thái:** Approved
**Mục tiêu:** Cho phép expert test trong khung giờ nhất định (start_time/end_time) trên cả backtest lẫn live bot; đồng thời reorder Backtest History columns theo thứ tự ưu tiên thực tế.

---

## 1. Tổng Quan

Hai tính năng độc lập nhưng cùng spec:

| Feature | Scope |
|---------|-------|
| Time window filter | `src/backtest.py`, `pages/5_Backtest.py`, `src/bot_runner.py`, `src/bot_manager.py`, `src/backtest_history.py` |
| History column order | `src/backtest_history.py`, `pages/5_Backtest.py` |

---

## 2. Time Window Filter

### 2.1 Behavior

- User set `Entry Start Time` và `Entry End Time` (HH:MM) — áp dụng **mỗi ngày** trong date range.
- Default: `00:00–23:59` → không filter (behavior y hệt hiện tại).
- Timezone: `Asia/Ho_Chi_Minh` (giống master candle).
- Khi đang hold lệnh (active_trade) và time window kết thúc → **tiếp tục hold**, chỉ gate *vào lệnh mới*.
- Áp dụng cho **cả hai strategy**: Master Candle và FEG EMA21.

### 2.2 Helper Function (thêm vào `src/backtest.py` và `src/bot_runner.py`)

```python
from datetime import time
from zoneinfo import ZoneInfo

_TZ_HCM = ZoneInfo("Asia/Ho_Chi_Minh")

def _in_time_window(ts: pd.Timestamp, start: time, end: time) -> bool:
    """True nếu ts (HCM local time) nằm trong [start, end] inclusive."""
    local = ts.astimezone(_TZ_HCM).time().replace(second=0, microsecond=0)
    if start <= end:
        return start <= local <= end
    # overnight window (e.g. 22:00–02:00) — không cần cho v1 nhưng handle đúng
    return local >= start or local <= end
```

Đặt trong `src/utils.py` để tái dùng ở cả `backtest.py` và `bot_runner.py`.

### 2.3 Backtest Engine (`src/backtest.py`)

**`run_backtest()` signature** — thêm 2 params:

```python
def run_backtest(
    ...,
    entry_start_time: time = time(0, 0),   # default = no filter
    entry_end_time: time = time(23, 59),   # default = no filter
) -> dict:
```

**Master Candle path** — hiện tại filter nến theo `entry_hour:entry_minute` cố định. Với time window, thay thế bằng range:

```python
# Trước (filter 1 nến cố định per ngày):
entry_candles = day_df[(day_df['hour'] == entry_hour) & (day_df['minute'] == entry_minute)]

# Sau (filter theo window):
entry_candles = day_df[day_df['time'].apply(
    lambda ts: _in_time_window(ts, entry_start_time, entry_end_time)
)]
```

> **Lưu ý**: Với Master Candle, `entry_hour:entry_minute` vẫn được giữ nguyên. Time window là filter *bổ sung* — nến phải vừa match `entry_hour:entry_minute` vừa nằm trong window. Vì Master Candle chỉ vào 1 nến cố định/ngày, window chủ yếu dùng để lọc theo ngày (nếu giờ entry nằm ngoài window thì ngày đó skip).

**FEG path** (`_run_feg_backtest()`) — thêm 2 params, gate trong while loop:

```python
def _run_feg_backtest(
    ...,
    entry_start_time: time = time(0, 0),
    entry_end_time: time = time(23, 59),
):
    ...
    while i < n:
        candle_time = df.at[i, 'time']
        if not _in_time_window(candle_time, entry_start_time, entry_end_time):
            i += 1
            continue
        c1 = ...
        direction = detect_feg_signal(...)
        ...
```

### 2.4 Backtest UI (`pages/5_Backtest.py`)

Thêm 2 `st.time_input` vào section params, hiển thị cho **cả hai strategy**:

```python
col_ts, col_te = st.columns(2)
with col_ts:
    entry_start_time = st.time_input("Entry Start Time", value=time(0, 0))
with col_te:
    entry_end_time = st.time_input("Entry End Time", value=time(23, 59))
```

Pass vào `run_backtest(... entry_start_time=entry_start_time, entry_end_time=entry_end_time)`.

Lưu vào `backtest_config`:
```python
backtest_config = {
    ...
    'entry_start_time': entry_start_time.strftime('%H:%M'),
    'entry_end_time': entry_end_time.strftime('%H:%M'),
}
```

### 2.5 Live Bot (`src/bot_runner.py`)

**Argparse** — thêm 2 args:

```python
parser.add_argument('--entry_start_time', type=str, default='00:00', help='Entry window start HH:MM (HCM)')
parser.add_argument('--entry_end_time',   type=str, default='23:59', help='Entry window end HH:MM (HCM)')
```

Parse sang `time` object khi startup:

```python
from datetime import datetime as _dt
entry_start = _dt.strptime(args.entry_start_time, '%H:%M').time()
entry_end   = _dt.strptime(args.entry_end_time,   '%H:%M').time()
```

**`run_feg_bot()`** — gate trước `feg_entry_decision`:

```python
now_hcm = datetime.now(_TZ_HCM)
if active_trade is None:
    if _in_time_window(now_hcm, entry_start, entry_end):
        signal = feg_entry_decision(...)
    # else: skip entry, continue monitoring active_trade if any
```

**`run_master_candle_bot()`** — gate quanh `check_entry_time()`:

```python
if check_entry_time(entry_time) and _in_time_window(now_hcm, entry_start, entry_end):
    # proceed to entry logic
```

### 2.6 Bot Manager (`src/bot_manager.py`)

**`build_bot_command()`** — thêm 2 params:

```python
def build_bot_command(
    ...,
    entry_start_time: str = '00:00',
    entry_end_time: str = '23:59',
):
    ...
    cmd += ['--entry_start_time', entry_start_time, '--entry_end_time', entry_end_time]
```

**Bot start UI** (`pages/1_Bots.py`) — thêm 2 `st.time_input` trong form tạo bot, pass string `HH:MM` vào `build_bot_command`.

---

## 3. Backtest History Column Redesign

### 3.1 `HISTORY_COLUMNS` mới (`src/backtest_history.py`)

```python
HISTORY_COLUMNS = {
    'core': [
        'Date Range',    # "YYYY-MM-DD – YYYY-MM-DD"
        'Start Time',    # entry_start_time
        'End Time',      # entry_end_time
        'Trades',
        'Win Rate %',
        'Total Pips',
        'Total USD',
        'Lot Mode',
        'RR Ratio',
    ],
    'config': [
        'Strategy', 'Symbol', 'Timeframe',
        'Entry Time', 'Entry Type', 'EMA Period', 'EMA Dist',
        'Entry Mode', 'Entry %', 'Max Candles', 'Buffer K',
        'TP Type', 'SL Type', 'Fixed Lot', 'Start Equity',
        'Risk Mode', 'Risk %', 'Risk $',
    ],
    'summary': [
        'Wins', 'Losses', 'Avg Pips', 'Best', 'Worst',
        'Max Wins', 'Max Losses', 'TP Exits', 'SL Exits', 'Time Exits',
        'Final Equity',
    ],
    'default_optional': ['Strategy', 'Symbol', 'Timeframe', 'Entry Type'],
}
```

`core` columns: **luôn hiển thị**, theo đúng thứ tự user yêu cầu.
`config` + `summary`: user ẩn/hiện qua multiselect (giữ pattern hiện tại).

### 3.2 `history_to_dataframe()` — thêm 2 cột mới

```python
'Start Time': config.get('entry_start_time', '00:00'),
'End Time':   config.get('entry_end_time',   '23:59'),
```

Cột `'Date Range'` đã tồn tại → giữ nguyên.

### 3.3 UI Backtest History (`pages/5_Backtest.py`)

Đảm bảo multiselect default hiện `config['default_optional']`, các cột `core` không có trong multiselect (luôn hiển thị). Pattern này đã có — chỉ cần đảm bảo column order trong DataFrame match `HISTORY_COLUMNS['core']` trước `config`/`summary`.

---

## 4. Files Thay Đổi

| File | Thay đổi |
|------|---------|
| `src/utils.py` | Thêm `_in_time_window(ts, start, end) -> bool` |
| `src/backtest.py` | `run_backtest()` + `_run_feg_backtest()` nhận `entry_start_time`, `entry_end_time`; apply filter |
| `src/backtest_history.py` | `HISTORY_COLUMNS` redesign; `history_to_dataframe()` thêm Start Time / End Time |
| `src/bot_runner.py` | Argparse + `run_feg_bot()` + `run_master_candle_bot()` gate theo time window |
| `src/bot_manager.py` | `build_bot_command()` thêm `entry_start_time`, `entry_end_time` |
| `pages/5_Backtest.py` | Thêm 2 `st.time_input`; pass to `run_backtest`; lưu vào config; column display update |
| `pages/1_Bots.py` | Thêm 2 `st.time_input` trong form tạo bot |

**Không thêm file mới.** Không thay đổi strategy YAML.

---

## 5. Tests

Thêm vào `tests/test_backtest_feg.py`:
- `test_feg_backtest_time_window_blocks_signal()` — signal ngoài window → 0 trades
- `test_feg_backtest_time_window_allows_signal()` — signal trong window → 1 trade

Thêm vào `tests/test_backtest_time_characterization.py`:
- `test_master_candle_time_window_blocks()` — entry giờ 21:05 ngoài window 09:00–10:00 → 0 trades

Thêm vào `tests/test_feg_strategy.py` hoặc file mới `tests/test_time_window.py`:
- `test_in_time_window_inside()`, `test_in_time_window_outside()`, `test_in_time_window_boundary()`

---

## 6. Constraints

- `_in_time_window` dùng `Asia/Ho_Chi_Minh` timezone — candle time trong df phải có tzinfo (đã đúng với data từ MT5).
- Default `00:00–23:59` = no-op → backward-compat với tất cả tests hiện tại.
- Backtest history records cũ (không có `entry_start_time`/`entry_end_time`) → `config.get()` trả `'00:00'`/`'23:59'` — không crash.
- `run_backtest` signature backward-compat: new params có default → callers hiện tại không cần thay đổi.
