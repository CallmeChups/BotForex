# BotForex - Tổng Quan & PDR

**Tên Project**: BotForex - Giao dịch MT5 Tự Động Đa Chiến Lược
**Phiên Bản**: 0.2.0
**Cập Nhật Lần Cuối**: 2026-06-21
**Trạng Thái**: Production-ready (multi-strategy)
**Repository**: E:\Project\BotForex

## Tóm Tắt

BotForex là ứng dụng Streamlit đa trang để quản lý, backtest và vận hành bot giao dịch MT5 tự động. Hỗ trợ hai chiến lược: **Master Candle** (vào lệnh theo giờ cố định) và **FEG EMA21** (quét pattern 2 nến liên tục với bộ lọc EMA21). Kiến trúc YAML-driven: thêm chiến lược mới không cần sửa engine core.

## Mục Đích Project

### Tầm Nhìn
Nền tảng giao dịch tự động linh hoạt, hỗ trợ nhiều chiến lược trên MT5, với dashboard quản lý và backtest tích hợp.

### Tính Năng Chính
- **Dashboard Streamlit** đa trang: Bots, Orders, Signals, Strategies, Backtest, Settings
- **Backtest engine**: fetch OHLC từ MT5, simulate trades, lưu lịch sử, xuất Excel
- **Live bot runner**: subprocess tách biệt, gate test/live, Telegram notifications
- **Multi-strategy**: YAML-driven, discriminator `entry.type` (time / pattern)
- **Xác thực**: role-based (admin/user) qua streamlit-authenticator

## Chiến Lược Hiện Có

### Master Candle (`strategies/master_candle.yaml`)
- **Entry**: Nến M5 lúc 21:05 HCM
- **Hướng**: Close > Open → BUY; Close < Open → SELL
- **SL/TP**: Neo vào nến entry (candle body ± buffer_k pips), TP = risk × rr_ratio
- **Magic**: 210500

### FEG EMA21 (`strategies/feg_ema21.yaml`)
- **Entry**: Pattern 2 nến (candle1 + candle2) + EMA21 filter, quét liên tục M5
- **SELL**: H2>H1, C2<L1, L2>EMA21(+dist_pips tùy chọn)
- **BUY**: L2<L1, C2>H1, H2<EMA21(-dist_pips tùy chọn)
- **SL/TP**: Neo vào candle2, TP = risk × rr_ratio
- **1 lệnh tại 1 thời điểm** (backtest + live)
- **Magic**: 212100

## Yêu Cầu Chức Năng

**FR1: Strategy Management**
- Đọc strategy config từ YAML
- Hiển thị strategy info read-only (4_Strategies.py)
- Hỗ trợ thêm strategy mới qua YAML (không sửa engine)

**FR2: Backtest**
- Fetch dữ liệu lịch sử MT5 theo date range và timeframe
- Simulate trades theo logic strategy (time-based và pattern-based)
- Tính metrics: win rate, profit factor, equity curve, pnl pips/usd
- Lưu kết quả vào lịch sử, xuất Excel

**FR3: Live Bot**
- Khởi chạy bot như subprocess riêng biệt
- Test mode (simulate, no MT5 order) và Live mode (đặt lệnh thật)
- Tự động gửi Telegram khi vào/ra lệnh
- Quản lý trạng thái: start/stop/restart từ UI

**FR4: Lot & Risk Management**
- Lot cố định hoặc flex (tính từ equity + risk %)
- SL tính theo pip value của từng symbol

**FR5: Exit Management**
- TP/SL: price_based (wick) hoặc close_based (close)
- Time exit: sau max_candles nến (configurable)

**FR6: Dashboard & Auth**
- Login role-based (admin/user)
- Admin: quản lý users, settings toàn hệ thống
- User: chạy bot, backtest, xem orders/signals

## Yêu Cầu Không Chức Năng

| NFR | Yêu Cầu |
|-----|---------|
| Bảo Mật | Credentials từ env vars / auth.yaml (không hardcode) |
| Test | 25 unit tests, pytest, backward-compat cho master_candle |
| Hiệu Suất | Backtest: < 5s cho 3 tháng M5 (~26k nến) |
| MT5 | Windows-only, lazy import |
| Extensibility | Thêm strategy = thêm YAML + (optional) signal file |

## Kiến Trúc Kỹ Thuật

### Tech Stack

| Thành phần | Thư viện | Phiên bản |
|-----------|---------|---------|
| Dashboard | Streamlit | 1.52.2 |
| Auth | streamlit-authenticator | 0.4.2 |
| MT5 API | metatrader5 | 5.0.5430 (Windows) |
| Telegram | python-telegram-bot | 22.5 |
| Data | pandas | 2.3.3 |
| Charting | plotly | 6.5.2 |
| Config | PyYAML | 6.0.3 |
| Test | pytest | 8.3.4 |

### Cấu Trúc Thư Mục (Chính)

```
BotForex/
├── app.py                   # Streamlit entry (auth + home)
├── pages/                   # 8 UI pages
├── src/                     # 12 modules
│   ├── feg_strategy.py      # FEG pattern detection
│   ├── backtest.py          # Engine backtest (master + FEG)
│   ├── bot_runner.py        # Live loop (subprocess)
│   ├── bot_manager.py       # Subprocess manager
│   ├── strategy_manager.py  # YAML → params
│   ├── orders.py            # MT5 order execution
│   └── utils.py             # Shared helpers
├── strategies/              # Strategy YAML definitions
│   ├── master_candle.yaml
│   └── feg_ema21.yaml
├── tests/                   # 25 pytest tests
└── data/                    # Runtime data (JSON)
```

Chi tiết: xem [Codebase Summary](./codebase-summary.md) và [System Architecture](./system-architecture.md).

## Trạng Thái Hiện Tại

### Hoàn Thành ✅
- Streamlit dashboard đa trang với auth
- Master Candle strategy (backtest + live)
- FEG EMA21 strategy (backtest + live)
- Backtest engine với shared helpers
- Backtest history (JSON, Excel export)
- Test mode gate (`place_order(test=True)`)
- 25 unit tests (pytest)
- Bot manager (subprocess, start/stop/restart)
- Strategy YAML system (extensible)
- UI pattern-aware (Backtest, Bots, Strategies pages)
- Telegram notifications

### Chưa Thực Hiện
- REST API endpoint
- Database persistence (hiện dùng JSON)
- Multi-symbol parallel bots (hiện 1 bot/symbol)
- Web deploy (hiện chạy local)

## Mối Nguy Hiểm & Cảnh Báo

| Mức | Vấn đề |
|-----|--------|
| ⚠️ Medium | `config/auth.yaml` track trong git — cần `git rm --cached` + rotate password |
| ⚠️ Tài chính | Test kỹ trên demo account trước khi `--test 0` (live) |
| ℹ️ Platform | MT5 Windows-only — bot runner không chạy được trên Linux/Mac |

## Tài Liệu Liên Quan

- [Codebase Summary](./codebase-summary.md)
- [System Architecture](./system-architecture.md)
- [Project Roadmap](./project-roadmap.md)
- [Code Standards](./code-standards.md)
- [MetaTrader5 Python Docs](https://www.mql5.com/en/docs/integration/python_metatrader5)
- [Streamlit Docs](https://docs.streamlit.io/)
