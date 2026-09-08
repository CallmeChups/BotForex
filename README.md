# BotForex - MT5 Forex Bot

**Phiên Bản**: 0.3.1 | **Trạng Thái**: Production-ready

Bot trading forex tự động sử dụng Python và MetaTrader 5. Dashboard Streamlit với layout 2 cột compacted để quản lý bot, chạy backtest và theo dõi lệnh. Deploy tự động qua GitHub Actions + Tailscale SSH.

## Tính Năng

- **Hai chiến lược**: Master Candle (vào lệnh 21:05 HCM) + FEG EMA21 (pattern 2 nến cùng hướng + EMA21 filter)
- **Layout 2 cột compacted**: Streamlit form zones (General/Entry/Order Settings & Risk/Exit) với colored headers, FEG Margins + Wick Filter split
- **Backtest engine**: EMA indicator overlay, trace ID (BT-...) copyable, per-trade debug fields
- **Live bot**: order trace ID (ORD-...), auto-restart sau crash, mọi lỗi gửi Telegram
- **CI/CD**: GitHub Actions → Tailscale SSH → Windows server, auto restart Streamlit
- **Telegram**: kênh main (trade alerts) + kênh error (mọi lỗi server)
- **Test suite**: 25 pytest tests
- **Vietnamese labels**: Full translated UI with approved translation table

## Cài Đặt

```bash
git clone https://github.com/CallmeChups/BotForex.git
cd BotForex
python -m venv .venv
.venv\Scripts\activate    # Windows
pip install -r requirements.txt
```

Yêu cầu: MetaTrader 5 terminal đang chạy trên Windows, MT5 credentials, Telegram bot token.

## Cấu Hình

### `config/auth.yaml`
```yaml
credentials:
  usernames:
    admin:
      name: Admin
      password: "<hashed>"
      role: admin
      mt5:
        login: 12345678
        password: "your_mt5_password"
        server: "Exness-MT5Real"
```

### Environment Variables (`.env`)
```
TELEGRAM_BOT_TOKEN=123456:ABC-DEF
TELEGRAM_CHAT_ID=987654321
TELEGRAM_ERROR_CHAT_ID=123456789
```

`TELEGRAM_BOT_TOKEN` phải là token hiện tại do `@BotFather` cấp, có dạng
`<bot_id>:<secret>`. Nếu log ghi `HTTP 401 Unauthorized`, token đã sai hoặc
đã bị revoke; tạo token mới bằng `/token` tại `@BotFather`, cập nhật `.env`,
rồi restart dashboard và bot. Dashboard/subprocess sẽ ưu tiên giá trị mới nhất
trong file `.env`.

## Chạy

```bash
# Dashboard Streamlit
streamlit run app.py

# Hoặc dùng script (trên server)
scripts\start_streamlit.bat
```

## Bot Trading

Bot chạy như subprocess từ UI (trang 1_Bots.py), hoặc trực tiếp:

```bash
# Test mode (không đặt lệnh thật)
python src/bot_runner.py --strategy feg_ema21 --symbol XAUUSD --user admin --test 1

# Live mode
python src/bot_runner.py --strategy feg_ema21 --symbol XAUUSD --user admin --test 0
```

Bot tự restart sau crash (30s delay). Mọi lỗi gửi Telegram.
Khi dừng bot từ dashboard, hệ thống cũng gửi thông báo stop vào Telegram.

Chu kỳ quét live được cấu hình trên trang **Create Bot** theo mili giây.
Giá trị mặc định là `1000 ms` (1 giây), tối thiểu `100 ms`; runner chuyển
giá trị này thành giây khi gọi `time.sleep()`. Có thể đặt tối thiểu `100 ms` (theo bước `100 ms`). Chu kỳ ngắn giúp bot phản
ứng nhanh hơn trong M1, nhưng không làm dữ liệu nến MT5 cập nhật nhanh hơn và
tăng tải gọi API/CPU; nên bắt đầu ở `500–1000 ms` rồi giảm xuống `100 ms` nếu
broker/terminal đáp ứng đủ nhanh.

## Backtest Verification

Chạy với MT5 connected để verify logic per-trade:

```bash
python scripts/verify_backtest.py --symbol XAUUSD --days 90 --strategy feg
```

In trace từng trade: signal conditions (✓/✗), SL/TP math, exit info, running equity.

## CI/CD Deploy

Manual trigger trên GitHub Actions tab. Secrets cần thiết:
- `TAILSCALE_AUTHKEY` — ephemeral Tailscale auth key
- `DEPLOY_SSH_PRIVATE_KEY` — SSH private key cho server

Workflow: Tailscale connect → SSH → git pull + pip install → [optional] restart Streamlit + verify port 8501.

## Chiến Lược

| Strategy | Entry | Magic |
|----------|-------|-------|
| Master Candle | Nến M5 lúc 21:05 HCM, Close>Open → BUY | 210500 |
| FEG EMA21 | Pattern 2 nến cùng hướng + EMA21 filter | 212100 |
| Flappy Bird BUY/SELL | BUY/SELL LIMIT theo EMA13/21/55 + mô hình Mẹ/Con/Cha trên M5 | 212400 |

### FEG EMA21 — Điều Kiện Vào Lệnh

**SELL** (cả 2 nến phải bearish):
- H2 > H1 (high mới cao hơn)
- C2 < L1 (close dưới low nến trước)
- L2 > EMA21 (low trên EMA)

**BUY** (cả 2 nến phải bullish):
- L2 < L1 (low mới thấp hơn)
- C2 > H1 (close trên high nến trước)
- H2 < EMA21 (high dưới EMA)

### Flappy Bird BUY/SELL

Flappy Bird tạo tín hiệu theo hai hướng. Với BUY:

- EMA xếp thứ tự: `EMA13 > EMA21 > EMA55`.
- Có số nến Con trong khoảng cấu hình `min_child_candles`–`max_child_candles`;
  mặc định là 2–5 nến.
- Nến Mẹ phải cùng chiều với chiến lược: bullish cho BUY, bearish cho SELL.
- Thân Mẹ lớn hơn thân của mọi nến con; `HIGH` Mẹ bao trùm toàn bộ thân các nến con.
- Thân Cha lớn hơn `1.5 ×` thân nến con liền kề trước đó.
- Râu trên Cha nhỏ hơn `30%` thân Cha.
- `OPEN Cha >= EMA13`, `LOW Cha > EMA21`.
- `CLOSE Cha` lớn hơn `HIGH` cao nhất của các nến con.
- Thân Cha lớn hơn ngưỡng `min_father_body_points` (mặc định `2.0` đơn vị giá)
  và không vượt quá `6.0` đơn vị giá; ngưỡng tối thiểu có thể chỉnh trong
  Backtest và Create Bot.

Với SELL, các điều kiện được đối xứng:

- EMA xếp thứ tự: `EMA13 < EMA21 < EMA55`.
- HIGH Mẹ bao trùm thân các nến Con theo hướng giảm; LOW Mẹ bao trùm đáy thân các Con.
- Thân Cha lớn hơn `1.5 ×` thân nến Con cuối.
- Râu dưới Cha nhỏ hơn `30%` thân Cha.
- `OPEN Cha <= EMA13`, `HIGH Cha < EMA21`.
- `CLOSE Cha` nhỏ hơn `LOW` thấp nhất của các nến Con.
- Thân Cha lớn hơn ngưỡng `min_father_body_points` (mặc định `2.0` đơn vị giá)
  và không vượt quá `6.0` đơn vị giá; ngưỡng tối thiểu có thể chỉnh trong
  Backtest và Create Bot.

Mức lệnh:

- Entry: `CLOSE Cha - 5% × thân Cha` (BUY LIMIT).
- SL: `min(LOW Cha, LOW các nến con) - 5 pips`.
- TP: `Entry + 2 × (Entry - SL)`.
- SELL: Entry = `CLOSE Cha + 5% × thân Cha` (SELL LIMIT), SL nằm trên HIGH
  lớn nhất của Cha/Con cộng 5 pips, TP = `Entry - 2 × (SL - Entry)`.
- Pending hết hạn sau 7 nến nếu chưa khớp.
- Backtest/test dùng cùng quy tắc EMA với Live Bot: mỗi EMA được tính trên tối
  đa 120 nến gần nhất (EMA warmup window). Nếu cùng nến chạm cả SL và TP thì
  backtest ưu tiên SL; trường hợp này không được dùng để suy diễn thứ tự khớp
  lệnh live của MT5.

Backtest chỉ lưu dữ liệu nến/EMA tối thiểu để không làm chậm toàn bộ lượt chạy.
Khi xem **Interactive Chart**, mục **Flappy Bird Signal Debug** sẽ tính audit
on-demand cho đúng trade đang chọn: cửa sổ Mẹ–Con–Cha, thời điểm Entry fill,
EMA, OHLC/body/wick và kết quả PASS/FAIL của từng điều kiện.

Trong lúc chạy Flappy Bird backtest, UI hiển thị progress theo thời gian thực:
phần trăm nến đã quét, ETA, số trade đã tạo, thời gian đã chạy và log các mốc
xử lý gần nhất. Engine dùng callback tùy chọn nên các script/test chạy trực tiếp
không bị phụ thuộc vào Streamlit.

Trong phần setting Backtest, Flappy Bird chỉ hiển thị các lựa chọn có ý nghĩa
với pattern này. Nhóm **Wick Filter**, các EMA/margin filter của FEG, Entry mode,
Entry % và giới hạn nến Master Candle được ẩn; các giá trị cố định như entry,
SL buffer, RR, minimum Father body và pending expiry vẫn được lấy từ YAML để
engine sử dụng. Các strategy khác không bị thay đổi và vẫn hiển thị setting
generic của chúng.

Với Flappy Bird, EXIT TIME hiện đang tạm ẩn/vô hiệu hóa. Vị thế chỉ thoát bởi
SL hoặc TP và không bị đóng tự động sau một số nến.

Với Flappy Bird, SL BUY lấy mức Low thấp hơn giữa Nến Cha và Nến Con liền kề
trước đó, rồi trừ `sl_buffer_pips`; SL SELL lấy mức High cao hơn giữa hai nến
này, rồi cộng `sl_buffer_pips`.

Trên trang **Backtest** và **Create Bot**, timeframe, RR và số nến chờ pending
của Flappy Bird có thể override trực tiếp từ UI. Nếu không thay đổi, chúng mặc
định theo YAML; timeframe được truyền đến live runner, RR được dùng khi tính TP
theo risk và pending expiry quyết định thời gian giữ lệnh LIMIT chưa khớp.

Vòng scan pattern dùng mảng NumPy theo vị trí thay vì `DataFrame.loc` lặp lại
cho từng cửa sổ Mẹ–Con–Cha; điều này tránh overhead pandas trong inner loop.

Định nghĩa đầy đủ và vị trí triển khai xem tại [docs/codebase-guide-vi.md](docs/codebase-guide-vi.md).

## Cấu Trúc Project

```
BotForex/
├── app.py                   # Streamlit entry point
├── pages/                   # 8 UI pages (Bots, Orders, Backtest...)
├── src/                     # Core modules
│   ├── feg_strategy.py      # FEG pattern detection
│   ├── backtest.py          # Backtest engine
│   ├── bot_runner.py        # Live bot loop
│   ├── bot_manager.py       # Subprocess manager
│   ├── orders.py            # MT5 order execution
│   └── utils.py             # Shared helpers
├── strategies/              # Strategy YAML configs
├── scripts/                 # verify_backtest.py, start_streamlit.bat
├── .github/workflows/       # deploy.yml CI/CD
├── tests/                   # 25 pytest tests
└── docs/                    # Documentation
```

## Tests

```bash
pytest tests/ -v
# 25 passed
```

## Lưu Ý

- MT5 terminal phải đang mở và connected (Windows only)
- Luôn test trên demo account trước khi chạy live (`--test 0`)
- Trace IDs: copy từ UI → grep log để debug
- `config/auth.yaml` và `.streamlit/config.toml` được track trong git (deployed qua CI/CD)
- `data/running_bots.json`, `logs/` là server-local (git-ignored)

## Docs

Xem thư mục `docs/` để biết chi tiết:
- [Codebase Summary](docs/codebase-summary.md)
- [System Architecture](docs/system-architecture.md)
- [Project Roadmap](docs/project-roadmap.md)
- [Project Overview & PDR](docs/project-overview-pdr.md)
