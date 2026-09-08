# BotForex — Hướng dẫn tái sử dụng codebase

> Tài liệu này mô tả trạng thái thực tế của source trong workspace hiện tại. Không đưa thông tin bí mật từ `config/auth.yaml` hoặc `.env` vào tài liệu.

Live bot nhận `interval` theo giây dưới dạng số thực để hỗ trợ polling dưới một
giây. UI Create Bot hiển thị và lưu lựa chọn theo mili giây (mặc định `1000`,
tối thiểu `100`, bước `100`), sau đó chuyển `interval_ms / 1000` trước khi gọi
`bot_manager.start_bot`. Vì vậy bot M1 không còn bị khóa ở chu kỳ tối thiểu
5 giây; tuy nhiên chu kỳ quá ngắn chỉ tăng tần suất đọc MT5, không tạo thêm
nến hoặc tick mới.

## 1. Mục tiêu và phạm vi

BotForex là dashboard Streamlit nhiều trang để:

- xác thực người dùng và phân quyền `admin`/`user`;
- đọc định nghĩa chiến lược YAML;
- backtest dữ liệu OHLC từ MetaTrader 5 (MT5);
- khởi động, dừng và theo dõi bot trading chạy bằng subprocess;
- đặt lệnh thị trường hoặc lệnh chờ trên MT5;
- lưu lịch sử và log dạng file;
- gửi thông báo giao dịch/lỗi qua Telegram;
- triển khai lên Windows server qua GitHub Actions, Tailscale và SSH.

MT5 Python API là phụ thuộc Windows/terminal MT5. Có thể import một số module và chạy unit test không cần MT5, nhưng backtest dữ liệu thật và live bot cần terminal MT5 đã khởi động, đăng nhập và có symbol hợp lệ.

## 2. Kiến trúc và luồng chính

```text
Trình duyệt
   │
   ▼
Streamlit app.py ── xác thực ── pages/*.py
   │                         ├─ strategy_manager ── strategies/*.yaml
   │                         ├─ backtest ────────── MT5 lịch sử
   │                         └─ bot_manager ─────── subprocess bot_runner.py
   │
   ├─ data/*.json, data/orders.csv
   ├─ logs/*.log
   └─ Telegram (chat chính / chat lỗi)

bot_runner.py ── strategy module ── orders.py ── MT5 order_send

GitHub Actions ── Tailscale ── SSH ── Windows server
                         ├─ git pull + pip install
                         ├─ API :8502
                         ├─ Streamlit :8501
                         └─ bot restart an toàn theo trạng thái
```

### Luồng dashboard

1. `app.py` gọi `st.set_page_config`, đọc `.env`, rồi hiển thị login bằng `src.auth`.
2. Cookie/session của `streamlit-authenticator` khôi phục trạng thái đăng nhập.
3. Streamlit tự phát hiện các file đánh số trong `pages/`; mỗi page gọi `require_auth()`.
4. Page gọi module `src`, đọc/ghi YAML hoặc file runtime, rồi rerun khi người dùng thay đổi dữ liệu.
5. Các lỗi page nên đi qua `src.utils.report_page_error`, nơi gửi traceback rút gọn đến error chat nếu đã cấu hình Telegram.

### Luồng backtest

1. `pages/5_Backtest.py` chọn user, strategy, symbol, timeframe, khoảng ngày và thông số risk.
2. `src.backtest.fetch_historical_data()` kết nối MT5, lấy tối đa 99.999 nến, chuyển timestamp UTC sang `Asia/Ho_Chi_Minh`, rồi lọc khoảng ngày.
3. `run_backtest()` định tuyến theo `entry_type`:
   - `time`: Master Candle;
   - `pattern`: FEG Classic, FEG Reverse hoặc FEG Stop Order theo `strategy`.
4. Engine tính entry/SL/TP, mô phỏng TP/SL/time/BE, tính P&L pips/USD, equity curve và thống kê. Riêng Flappy Bird, EMA dùng cùng cửa sổ warmup tối đa 120 nến như Live Bot.
5. Backtest pattern thêm cột `ema<period>` vào OHLC và giữ trường trace `_c1`, `_c2`, `_ema`, `_exit_pos`. Master Candle giữ `_candle`.
6. UI hiển thị `run_id` dạng `BT-...`, bảng giao dịch, biểu đồ và EMA overlay; có thể lưu `data/backtest_history.json` và xuất Excel.

### Parameter hiển thị theo strategy

`src.strategy_manager.get_strategy_parameters()` chuẩn hóa giá trị từ YAML,
còn `pages/5_Backtest.py` quyết định control nào được hiển thị hoặc khóa trên UI.
Hai lớp này cần được giữ đồng bộ khi thêm parameter mới.

Riêng Flappy Bird, các điều kiện pattern đã được định nghĩa cố định trong
`src/flappy_bird_strategy.py` và `strategies/flappy_bird.yaml`, nên UI không
hiển thị các setting generic không áp dụng:

- Wick Filter BUY/SELL;
- Entry mode và Entry % chỉnh tay;
- các EMA/margin filter của FEG;
- giới hạn số nến Master Candle.

Các giá trị cần cho engine vẫn được gán nội bộ từ YAML hoặc giá trị mặc định,
không bị xóa khỏi config truyền vào backtest. Các strategy khác vẫn hiển thị
Wick Filter và các parameter tương ứng như trước. Khi thay đổi parameter list,
ưu tiên cập nhật YAML, mapping trong `strategy_manager` và nhánh UI liên quan,
đồng thời kiểm tra payload truyền vào `run_backtest()`.

Trên trang Create Bot, timeframe, RR và số nến chờ pending là các override được
phép chỉnh cho Flappy Bird. Timeframe đi qua `bot_manager` vào `bot_runner`;
RR đi vào signal Flappy để tính TP; `limit_order_candles` quyết định thời gian
giữ lệnh LIMIT chưa khớp. Nếu người dùng không override, giá trị YAML được sử
dụng.

### Luồng live bot

1. `pages/1_Bots.py` gọi `bot_manager.start_bot()`.
2. `bot_manager` chống trùng strategy/symbol/user, tạo lệnh chạy `src/bot_runner.py`, ghi PID và tham số vào `data/running_bots.json`, đồng thời tạo log riêng.
3. `bot_runner` đọc credential theo user, strategy YAML và các override CLI.
4. `entry.type=time` chạy Master Candle theo giờ HCM; `entry.type=pattern` dispatch:
   - `feg_ema21` → FEG Classic;
   - `feg_reverse` → đảo BUY/SELL của pattern FEG;
   - `feg_stop_order` → pending BUY_STOP/SELL_STOP.
5. Bot bỏ nến đang chạy, dùng nến đã đóng; kiểm tra tín hiệu, đặt lệnh (hoặc mô phỏng nếu `--test 1`), theo dõi exit và ghi trạng thái.
6. Mỗi live order có ID `ORD-YYMMDD-HHMMSS-SYMBOL-XXXX`. Crash được log, gửi Telegram error và khởi động lại theo vòng lặp của runner; deploy còn hỗ trợ cờ `logs/pending_restart/<pid>.flag` để chờ bot idle rồi restart.

## 3. Cấu trúc thư mục

```text
BotForex/
├── app.py                         # entry Streamlit, login và dashboard tổng quan
├── api_server.py                  # HTTP API nội bộ đọc log/session, mặc định :8502
├── pages/
│   ├── 1_Bots.py                  # tạo/dừng/restart/chuyển mode bot, lịch sử session
│   ├── 2_Orders.py                # vị thế, account, đặt/đóng/cancel lệnh MT5
│   ├── 3_Signals.py               # lưu và xem tín hiệu dạng CSV
│   ├── 4_Strategies.py            # xem/tạo/sửa/xóa/bật tắt YAML strategy
│   ├── 5_Backtest.py              # chạy, xem, lưu và export backtest
│   ├── 6_Simulation.py            # mô phỏng exit độc lập
│   ├── 7_Users.py                 # quản lý user, chỉ admin
│   └── 8_Settings.py              # credential/setting, chỉ admin ở phần nhạy cảm
├── src/
│   ├── auth.py                    # auth YAML, bcrypt, role và credential MT5
│   ├── strategy_manager.py        # CRUD YAML và chuẩn hóa params
│   ├── strategy.py                # flow Master Candle cũ/tiện ích giao dịch chung
│   ├── feg_strategy.py            # FEG Classic signal + levels
│   ├── feg_reverse_strategy.py    # FEG pattern rồi đảo hướng lệnh
│   ├── feg_stop_order_strategy.py # FEG với pending stop
│   ├── backtest.py                # lấy dữ liệu, engine và thống kê
│   ├── backtest_history.py        # JSON history và Excel export
│   ├── bot_manager.py             # subprocess/PID/runtime state
│   ├── bot_runner.py              # vòng live, reconnect, entry/exit, restart
│   ├── orders.py                  # market/limit/stop/close/cancel MT5
│   ├── bot_history_manager.py     # session và trade history của bot
│   ├── calculation.py             # MACD, MA, EMA, stochastic và cross
│   ├── utils.py                   # pip, levels, exit, time window, page errors
│   └── telegram.py                # module Telegram cũ; không nên dùng lại nguyên trạng
├── strategies/                    # YAML strategy definitions
├── config/                        # auth.yaml và config.yaml
├── data/                          # JSON/CSV runtime, thường server-local
├── logs/                          # log bot, Streamlit, API, pending restart
├── scripts/                       # verification, startup và chẩn đoán
├── tests/                         # pytest unit/regression tests
├── .github/workflows/deploy.yml  # deploy thủ công lên Windows server
├── requirements.txt               # package versions
└── .streamlit/config.toml        # headless, port 8501, runOnSave
```

Thư mục `.claude/`, `.superpowers/` và các tài sản trong `docs/assets/` là tooling/tài liệu phụ trợ, không phải runtime trading core.

## 4. Cấu hình và credential

### `config/auth.yaml`

`src.auth` đọc cấu trúc:

```yaml
cookie:
  name: <cookie-name>
  key: <random-secret>
  expiry_days: 30
credentials:
  usernames:
    <username>:
      name: <display-name>
      email: <email>
      password: <bcrypt-hash>
      role: admin | user
      mt5:
        login: <account>
        password: <password>
        server: <broker-server>
      mt5_backtest:       # tùy chọn, account riêng cho backtest
        login: <account>
        password: <password>
        server: <broker-server>
```

`register_user()` và trang Users ghi file này trực tiếp. Không commit credential thật; nếu file đã từng chứa mật khẩu/token trong Git, cần rotate và làm sạch history trước khi public repository.

### `.env`

Các biến được source sử dụng gồm:

| Biến | Dùng cho |
|---|---|
| `TELEGRAM_BOT_TOKEN` | token gọi Bot API |
| `TELEGRAM_CHAT_ID` | chat thông báo giao dịch/thông thường |
| `TELEGRAM_ERROR_CHAT_ID` | chat lỗi server/page/bot |
| `TELEGRAM_TEST_CHAT_ID` | chat khi bấm test từ dashboard |

HTTP `401 Unauthorized` từ Telegram là lỗi Bot Token, không phải lỗi chu kỳ
scan hoặc timeframe. Token phải được cấp bởi `@BotFather`; sau khi cập nhật
`.env` cần restart subprocess bot. Nút **Test Telegram** ở Settings dùng trực
tiếp giá trị đang nhập trên form để kiểm tra token/chat ID mới.
| `MT5_LOGIN`, `MT5_PASSWORD`, `MT5_SERVER` | fallback cho `orders.py` khi không truyền credential |
| `SYMBOL` | symbol hiển thị mặc định ở dashboard |

Credential per-user trong `auth.yaml` được ưu tiên hơn fallback môi trường trong các flow truyền `credentials`.

### Streamlit

`.streamlit/config.toml` đặt `headless=true`, `port=8501`, `runOnSave=true`, tắt usage stats. API server mặc định lắng nghe `0.0.0.0:8502`; chỉ expose qua mạng tin cậy/Tailscale hoặc thêm auth nếu đưa ra ngoài.

## 5. Chiến lược và quy ước YAML

`strategy_manager.get_strategy_parameters()` biến YAML thành dict thống nhất. `entry.type` là discriminator; thiếu field này mặc định là `time`.

### Ranh giới giữa YAML và code

- YAML chỉ mô tả tham số; không tự đăng ký algorithm mới. Trong `bot_runner.py`, mọi strategy `pattern` không phải `feg_stop_order` hoặc `feg_reverse` đều rơi vào `run_feg_bot()` và được xử lý như FEG Classic.
- Các strategy mới vì vậy phải có nhánh dispatch riêng trong live runner và backtest; chỉ thêm file YAML sẽ không làm strategy được thực thi đúng.
- Quy ước ưu tiên hiện tại là: giá trị CLI khác `None` được dùng trước YAML; nếu CLI có default cứng thì default đó cũng được xem là giá trị CLI và sẽ ghi đè YAML. Vì vậy strategy mới không được giả định YAML sẽ thắng các cờ như `ema_filter_enabled`, `buy_ema_side`, `sell_ema_side`, `lot_mode`, `risk_mode`, `risk_percent`, `limit_order_candles` và các wick filter. Muốn một tham số thực sự lấy từ YAML, parser phải dùng `default=None` và code mới áp default sau khi merge.
- Nhánh `time` hiện vẫn chứa công thức Master Candle riêng trong `run_bot()`; khi `--test 0`, đoạn đặt lệnh thật của nhánh này vẫn là TODO và chỉ ghi log. Không xem đây là live execution hoàn chỉnh khi tái sử dụng làm mẫu.

### Ba quyết định kỹ thuật khi thêm strategy

Đây là quy ước implementation đã chốt theo source hiện tại, không phải các lựa chọn cần người dùng quyết định lại:

| Chủ đề | Quy ước áp dụng | Vì sao cần biết |
|---|---|---|
| Signal contract | Module signal phải trả `direction` (`BUY`/`SELL`), `entry_price`, `stop_loss`, `take_profit`, `sl_pips`; nếu là pending order phải trả thêm loại lệnh và dữ liệu expiry/fill cần thiết. | `bot_runner.py` và backtest dùng các giá trị này để tính lot, đặt lệnh, mô phỏng fill và exit. YAML chỉ chứa tham số, không thay thế output runtime. |
| Live Master Candle | Không coi Master Candle là strategy live được hỗ trợ. Chỉ dùng cho characterization/backtest/test flow cho đến khi có implementation gọi `orders.place_order()` và test tương ứng. | Nhánh `time` hiện tính signal nhưng `--test 0` vẫn chỉ ghi `LIVE: Would place order here`; bật live không tạo lệnh thật. |
| CLI và YAML | CLI thắng YAML theo behavior hiện tại. Các cờ có default cứng luôn có thể ghi đè cấu hình YAML; strategy mới phải khai báo rõ các override này và dùng cùng giá trị cho live/backtest. | Tránh kết quả UI/backtest khác với runner do tưởng rằng YAML luôn là nguồn cuối cùng. |

#### Ý nghĩa của signal contract

- `direction` là hướng lệnh cuối cùng, không nhất thiết là hướng của pattern (FEG Reverse đảo hướng).
- `entry_price` là giá vào dự kiến; market dùng giá hiện tại/close theo flow, còn limit/stop phải được kiểm tra điều kiện khớp.
- `stop_loss`, `take_profit` và `sl_pips` phải nhất quán; `sl_pips` là khoảng cách dùng cho lot/risk, không tự suy ra lại từ một công thức khác.
- Strategy phải nêu rõ `market`, `limit` hoặc `stop`, thời hạn pending, quy tắc hủy khi không khớp, magic/comment và cho phép bao nhiêu vị thế đồng thời.

### Master Candle

File `strategies/master_candle.yaml`, timeframe M5, nến lúc `21:05` HCM:

- `close > open` → BUY;
- `close < open` → SELL;
- doji → bỏ qua;
- SL neo cực trị nến và buffer; TP = risk × `rr_ratio`;
- mặc định `price_based` cho TP, `close_based` cho SL, time exit 7 nến;
- magic được dùng theo convention Master Candle `210500`.

### FEG Classic (`feg_ema21`)

Hai nến phải cùng hướng và body C2 lớn hơn body C1.

- SELL: `H2 > H1 + h2_exceed`, `C2 < L1 - c2_gap`, và `L2` ở phía EMA SELL quy định (mặc định trên EMA).
- BUY: `L2 < L1 - h2_exceed`, `C2 > H1 + c2_gap`, và `H2` ở phía EMA BUY quy định (mặc định dưới EMA).
- `ema_margin_pips` tạo khoảng cách tối thiểu.
- wick filters `c2_*_wick_max_pct` là tùy chọn; `lt` loại râu quá dài, `gt` loại râu quá ngắn.
- entry mặc định tại close C2; `range_percent` kéo entry theo body C2.
- backtest mô phỏng một vị thế tại một thời điểm; live runner có thể giữ nhiều pending/active trade theo state, nhưng mặc định chỉ scan tín hiệu mới khi không còn active trade (trừ khi bật `re_entry_after_sl`).

### FEG Reverse (`feg_reverse`)

Tái sử dụng điều kiện/wick/EMA của FEG Classic, nhưng:

- pattern SELL → lệnh BUY;
- pattern BUY → lệnh SELL;
- SL/TP được tính lại theo hướng lệnh mới.

### FEG Stop Order (`feg_stop_order`)

Pattern FEG tạo pending breakout:

- BUY: entry `H2 + buffer_k × pip`, SL `L2`;
- SELL: entry `L2 - buffer_k × pip`, SL `H2`;
- bot dùng `place_stop_order()`, backtest chờ giá vượt entry trong `limit_order_candles`.

Các trường phổ biến: `rr_ratio`, `buffer_k`, `lot_size`, `entry_mode`, `entry_percent`, `max_candles`, `tp_type`, `sl_type`, `lot_mode`, `risk_mode`, `risk_percent`, `risk_amount`, `be_enabled`, `be_r`, `re_entry_after_sl`, EMA và wick filters.

### Flappy Bird (`flappy_bird`)

Strategy BUY/SELL LIMIT trên M5, được triển khai riêng trong `src/flappy_bird_strategy.py` và được định tuyến riêng trong backtest/live runner:

- BUY dùng `EMA13 > EMA21 > EMA55`; SELL dùng `EMA13 < EMA21 < EMA55`.
  Có fallback đối xứng khi EMA13/EMA21 cùng nằm dưới (BUY) hoặc trên (SELL)
  EMA55 và Nến Cha cắt EMA55 theo đúng hướng.
- Có số nến Con trong khoảng `min_child_candles`–`max_child_candles`, mặc định
  là 2–5; các giá trị này được truyền đồng nhất qua Backtest và Live Bot.
- Nến Mẹ phải cùng chiều với chiến lược: bullish cho BUY, bearish cho SELL.
- Thân Mẹ lớn hơn thân mọi nến con; `high` của Mẹ bao trùm toàn bộ thân các nến con.
- Thân Cha lớn hơn `1.5 ×` thân nến con liền kề trước đó. BUY giới hạn râu trên,
  SELL giới hạn râu dưới dưới `30%` thân Cha.
- BUY: `open Cha >= EMA13`, `low Cha > EMA21`, `close Cha > highest high`.
  SELL: `open Cha <= EMA13`, `high Cha < EMA21`, `close Cha < lowest low`.
- Thân Cha lớn hơn ngưỡng `min_father_body_points` (mặc định `2.0` price
  points) và không vượt quá `6.0` price points; chỉ ngưỡng tối thiểu được
  override ở Backtest và Create Bot.
- Entry là BUY LIMIT: `close Cha - 5% × thân Cha`.
- SL là `min(low Cha, low mọi nến con) - 5 pips`; TP là `2R`.
- SELL dùng SELL LIMIT: `close Cha + 5% × thân Cha`; SL là
  `max(high Cha, high mọi nến con) + 5 pips`; TP là `2R` hướng xuống.
- Pending chờ tối đa 7 nến. Khi cùng một nến chạm cả SL và TP, SL được ưu tiên trong backtest/test.
- `min_father_body_points`, `sl_buffer_pips`, `entry_body_percent`, `rr_ratio` và `limit_order_candles` nằm trong YAML; giới hạn trên Body Cha là hardcode `6.0`; `magic` mặc định là `212400`. Backtest và Create Bot đều cho phép override ngưỡng tối thiểu Body Cha và số nến pending từ UI.
- SL Flappy BUY = `min(Low Cha, Low Con liền kề) - sl_buffer_pips`; SL Flappy SELL = `max(High Cha, High Con liền kề) + sl_buffer_pips`. Chỉ Nến Con liền kề cuối cùng được dùng cho SL.
- EXIT TIME Flappy hiện tạm vô hiệu hóa (`max_candles=0`); vị thế chỉ thoát bởi SL/TP. Pending expiry vẫn độc lập và tiếp tục dùng `limit_order_candles`.
- Để debug signal, gọi `diagnose_flappy_bird(...)`. Hàm trả `valid`, `reason` và `metrics`; `reason` dùng mã ổn định như `ema_order_failed`, `mother_body_not_larger`, `father_upper_wick_too_large` hoặc `father_body_below_minimum`. Signal hợp lệ cũng mang theo cùng dữ liệu trong field `debug`.

Ví dụ cấu hình hiện tại trong `strategies/flappy_bird.yaml`:

```yaml
entry:
  type: pattern
  timeframe: M5
  pattern: flappy_bird
  ema_periods: [13, 21, 55]

parameters:
  entry_body_percent: 5.0
  sl_buffer_pips: 5.0
  rr_ratio: 2.0
  min_father_body_points: 2.0
  limit_order_candles: 7
  magic: 212400
```

Khi chạy trực tiếp, dùng `--strategy flappy_bird`. Strategy hỗ trợ cả BUY và
SELL; symbol được phép theo YAML hiện tại là `XAUUSD` và `XAUUSDm`.
`2.0 price points` là chênh lệch tuyệt đối giữa OPEN và CLOSE của nến Cha,
không phải 2 lần giá thị trường.

### Pip, risk và exit

`src.utils.get_pip_value()` đang dùng quy ước: BTC `1.0`, ETH/XAU `0.1`, JPY `0.01`, forex còn lại `0.0001`. USD/pip/lot trong backtest dùng bảng riêng của `backtest.get_pip_value_per_lot()`; khi live flex lot ưu tiên tick value/tick size từ broker.

`check_exit()` kiểm tra TP trước SL trong cùng một candle. `price_based` dùng high/low; `close_based` dùng close. Nếu không chạm, time exit dùng close nến cuối. Đây là mô phỏng OHLC, không biết thứ tự intrabar khi TP và SL cùng nằm trong range.

## 6. Backtest, history và verification

Ví dụ:

```powershell
python scripts/verify_backtest.py --symbol XAUUSD --days 90 --strategy all
python scripts/verify_backtest.py --symbol XAUUSD --days 7 --strategy feg --timeframe M1
```

Script đọc credential user từ `config/auth.yaml`, fetch MT5, chạy Master Candle/FEG và in trace từng giao dịch: candle, EMA, điều kiện signal, công thức SL/TP, exit, P&L và vị trí scan tiếp theo. Đây là bước kiểm tra thủ công trước demo/live, không thay thế kiểm thử broker.

`data/backtest_history.json` lưu summary/config/trades đã bỏ các field debug bắt đầu bằng `_`. `backtest_history.py` cung cấp CRUD, DataFrame so sánh và Excel gồm sheet cấu hình/tóm tắt và trades. `data/bot_history.json` lưu session bot và trade đã đóng; trường `verified` phân biệt giá broker xác nhận với giá ước tính.

## 7. Live bot, lệnh và logging

Chạy trực tiếp:

```powershell
python src/bot_runner.py --strategy feg_ema21 --symbol XAUUSD --user admin --test 1
python src/bot_runner.py --strategy feg_ema21 --symbol XAUUSD --user admin --test 0
```

`--test 1` là gate an toàn: `orders.place_order`, `place_limit_order`, `place_stop_order` trả mô phỏng và không gọi MT5. Chỉ dùng `--test 0` sau khi đã kiểm tra demo và thông số.

Mô tả trên áp dụng cho các flow pattern dùng `src.orders`; nhánh Master Candle trong `run_bot()` hiện chưa gọi `orders.place_order` khi live mà chỉ ghi `LIVE: Would place order here`.

Bot runner:

- lấy nến đã đóng (`get_recent_candles` bỏ nến cuối đang chạy);
- reconnect MT5 khi terminal mất kết nối;
- hỗ trợ fixed/flex lot, entry window HCM, BE, time exit, re-entry tùy strategy;
- ghi log bằng `logging`, với `--log_file` do manager truyền;
- ghi `data/bot_state.json` để deploy biết bot đang active/pending; các process
  dùng lock liên process và retry khi replace trên Windows, còn lỗi telemetry
  chỉ ghi cảnh báo và không làm bot trading crash;
- đăng ký PID/session vào `data/running_bots.json` và `data/bot_history.json`;
- thông báo startup, entry, exit và lỗi qua Telegram.
- khi dừng từ dashboard, `bot_manager` gửi thông báo stop; runner suppress
  thông báo stop nội bộ để tránh gửi trùng.

API nội bộ:

```text
GET /sessions
GET /log?order_id=ORD-...
GET /log?session_id=<id>&tail=200
GET /log?file=logs/<file>.log&tail=200
```

`api_server.py` chỉ cho đọc file trong `logs/` ở nhánh `file`; endpoint không có lớp authentication. Không bind ra Internet công khai.

## 8. Telegram

Flow mới trong `bot_runner.py` và `utils.report_page_error` đọc token/chat từ environment, dùng chat chính cho thông báo và error chat cho lỗi. Request có timeout; lỗi gửi Telegram không được phép che lỗi gốc.

`src/telegram.py` là module cũ có token hardcode và side effect gửi tin ngay khi import. Không import module này trong code mới; token hiện hữu phải được coi là đã lộ, rotate/revoke và chuyển hoàn toàn sang environment.

## 9. Deploy và vận hành Windows

Workflow `.github/workflows/deploy.yml` chỉ chạy qua `workflow_dispatch`, input `restart_streamlit`:

1. runner Ubuntu join tailnet bằng `TAILSCALE_AUTHKEY`;
2. tạo SSH key từ `DEPLOY_SSH_PRIVATE_KEY`;
3. SSH vào Windows server, `git pull` và `.venv\Scripts\pip.exe install -r requirements.txt`;
4. restart API :8502;
5. smart-restart bot: bot active/pending được gắn cờ deferred, bot idle dừng ngay;
6. tạo/chạy Task Scheduler cho `scripts/start_streamlit.bat`;
7. chờ và kiểm tra port 8501.

Các script liên quan:

- `scripts/start_streamlit.bat`: chạy Streamlit :8501 và redirect `logs/streamlit.log`;
- `scripts/start_api.bat`: chạy API :8502 và redirect `logs/api_server.log`;
- `start_server.bat`: chạy Streamlit + ngrok tương tác;
- `stop_server.bat`: dừng process theo tên, không phù hợp cho thao tác tinh vi với nhiều bot;
- `run_bots.ps1`: ví dụ chạy nhiều FEG bot song song ở live mode, đường dẫn đang hardcode;
- `scripts/test_live_order.py`, `check_live_signal.py`, `_scan_symbols.py`, `_check_gbp_1555.py`, `test_backtest_scenarios.py`: script chẩn đoán/thử nghiệm, cần đọc tham số trước khi chạy trên tài khoản thật.

Đường dẫn deploy trong workflow/script là `D:\BotForex` hoặc `E:\Project\BotForex` tùy file; khi tái sử dụng phải chuẩn hóa working directory, Python executable, quyền Task Scheduler và port.

## 10. Testing và phát triển an toàn

Chạy:

```powershell
pytest tests/ -v
```

Nhóm test hiện có bao phủ:

- FEG Classic signal, EMA margin, H2/C2 gap và wick;
- FEG Reverse;
- trade levels, pip/time window;
- Master Candle characterization và FEG backtest;
- test/live order gate;
- command builder của bot manager;
- history columns và import smoke.

Khi sửa strategy:

1. thêm/điều chỉnh YAML trước;
2. cập nhật module signal tương ứng;
3. thêm fixture nến cụ thể cho BUY/SELL, mixed candle, EMA block, wick block;
4. kiểm tra backtest và live decision dùng cùng công thức;
5. chạy `pytest`;
6. chạy verification với MT5/demo;
7. chỉ sau đó mới bật live.

Không thay đổi `src/utils.compute_trade_levels`, `check_exit` hoặc dispatcher mà không kiểm tra cả Master Candle, FEG Classic, Reverse và Stop Order; đây là các điểm dùng chung.

## 11. Cách mở rộng

### Thêm strategy YAML tương thích engine

1. Tạo `strategies/<id>.yaml` với `id`, `name`, `enabled`, `entry`, `exit`, `parameters`, `symbols`.
2. Nếu là time strategy, dùng `entry.type: time`; nếu là pattern, dùng `entry.type: pattern`.
3. Xác định trước hợp đồng của signal: nến đầu vào, hướng `BUY`/`SELL`, `entry_price`, `stop_loss`, `take_profit`, `sl_pips` và loại lệnh (market/limit/stop); không suy ra hợp đồng này chỉ từ schema YAML.
4. Với pattern dùng lại FEG Classic, chỉ cần `pattern`/tham số tương thích và kiểm thử; nếu không, strategy sẽ rơi vào fallback FEG Classic của `bot_runner.py`.
5. Với algorithm mới, thêm module signal, nhánh dispatch trong `backtest.py` và `bot_runner.py`, ánh xạ đầy đủ CLI/YAML override, thêm order type nếu cần, rồi thêm test.
6. So sánh hành vi live/test: `--test 1` phải mô phỏng cùng loại lệnh và quy tắc fill/expiry với live; ghi rõ magic, comment, timeout pending và quy tắc nhiều lệnh.
7. Tránh để UI tự chứa business logic; truyền tham số qua `strategy_manager` và `bot_manager`.

### Thêm page

Đặt file `pages/<số>_<Tên>.py`, gọi `require_auth()` trước dữ liệu nhạy cảm, bắt lỗi và dùng `report_page_error`, không khởi tạo MT5 ở import time nếu không cần.

### Thay persistence

Runtime hiện là JSON/CSV, không có transaction/lock/database. Nếu chuyển database, giữ schema tương đương cho history/session, thêm migration, xử lý nhiều bot ghi đồng thời và cập nhật API/UI cùng lúc.

## 12. Cảnh báo an toàn

- Tuyệt đối kiểm tra `--test 1`, tài khoản demo, symbol, lot, SL/TP và timezone trước live.
- `config/auth.yaml` trong workspace chứa credential nhạy cảm; không chia sẻ, không commit bản mới và rotate credential đã tồn tại trong lịch sử.
- `.env`, Telegram token, SSH private key và Tailscale auth key phải nằm ngoài log/commit; secrets CI cần giới hạn quyền và rotate định kỳ.
- Telegram/API :8502 không có thiết kế bảo mật đầy đủ cho Internet công khai.
- File JSON/CSV là telemetry, không phải nguồn sự thật của lệnh. `bot_state.json`
  được serialize bằng lock liên process để nhiều bot cập nhật an toàn; nếu ghi
  state thất bại, bot vẫn tiếp tục trading và log cảnh báo.
- OHLC backtest không mô phỏng spread, slippage, commission, latency và thứ tự intrabar đầy đủ; kết quả không phải cam kết lợi nhuận.
- Các script startup có đường dẫn tuyệt đối và hành vi khác nhau giữa máy phát triển/server.
- `strategy.py` và `src/telegram.py` là nhánh/tiện ích cũ; phải kiểm tra call site trước khi tái sử dụng.

## 13. Các giới hạn đã biết trước khi triển khai

1. `config/config.yaml` không phải nguồn cấu hình runtime có thể diễn giải; nguồn thực tế là `auth.yaml`, `.env`, YAML strategies và `.streamlit/config.toml`.
2. README và tài liệu cũ có thể lệch số test/phiên bản so với source hiện tại. Khi cần báo cáo số liệu, chạy `pytest tests/ -v` trên revision đang triển khai thay vì dùng con số trong README.
3. Workflow deploy hiện restart API, bot và Streamlit; đây là thứ tự vận hành được mô tả trong source workflow, còn việc chạy thật vẫn phụ thuộc Windows server, Task Scheduler và quyền hệ thống.
4. Đường dẫn deploy không đồng nhất giữa một số script (`D:\BotForex`, `E:\Project\BotForex`). Khi triển khai phải chọn working directory thực tế của server và kiểm tra lại script tương ứng; không suy ra đường dẫn từ tài liệu cũ.
5. `src/strategy.py` và nhánh Master Candle trong `bot_runner.py` là flow cũ/đặc thù; strategy mới phải dùng module signal riêng và nối vào dispatcher live/backtest, không dùng chúng làm template live hoàn chỉnh.
6. Pip/USD, filling và pending order vẫn phụ thuộc `symbol_info`, tick value/tick size và broker. Đây là tham số môi trường phải kiểm tra trên demo; không thể cố định một giá trị đúng cho mọi symbol.
7. Việc chạy end-to-end với MT5, Telegram, Tailscale và server deploy không được thay thế bằng unit test. Trước live phải chạy checklist trong mục 10 và xác nhận log/order trên tài khoản demo.
8. Signal contract, live Master Candle và thứ tự ưu tiên CLI/YAML đã được chốt tại mục 5; mọi strategy mới phải tuân thủ các quy ước đó.
