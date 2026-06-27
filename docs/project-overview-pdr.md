# BotForex - Tổng Quan & PDR

**Tên Project**: BotForex - Giao dịch MT5 Tự Động Đa Chiến Lược
**Phiên Bản**: 0.3.0
**Cập Nhật Lần Cuối**: 2026-06-27
**Trạng Thái**: Production-ready (CI/CD + Trace IDs + Full Error Coverage)
**Repository**: E:\Project\BotForex

## Tóm Tắt

BotForex là ứng dụng Streamlit đa trang để quản lý, backtest và vận hành bot giao dịch MT5 tự động. Hỗ trợ hai chiến lược: **Master Candle** (vào lệnh theo giờ cố định) và **FEG EMA21** (quét pattern 2 nến liên tục với bộ lọc EMA21, cả 2 nến phải cùng hướng). Deploy tự động qua GitHub Actions + Tailscale SSH. Trace ID system cho mỗi backtest run và live order để debug dễ dàng.

## Mục Đích Project

### Tầm Nhìn
Nền tảng giao dịch tự động linh hoạt, hỗ trợ nhiều chiến lược trên MT5, với dashboard quản lý và backtest tích hợp, CI/CD tự động, và observability đầy đủ.

### Tính Năng Chính
- **Dashboard Streamlit** đa trang: Bots, Orders, Signals, Strategies, Backtest, Settings
- **Backtest engine**: fetch OHLC từ MT5, simulate trades, lưu lịch sử, xuất Excel, EMA overlay chart
- **Live bot runner**: subprocess tách biệt, gate test/live, Telegram notifications, auto-restart
- **Multi-strategy**: YAML-driven, discriminator `entry.type` (time / pattern)
- **Xác thực**: role-based (admin/user) qua streamlit-authenticator
- **CI/CD**: GitHub Actions + Tailscale SSH → Windows server, tự động pull code + restart Streamlit
- **Trace ID system**: mỗi backtest run (BT-...) và live order (ORD-...) có ID riêng để grep log
- **Full Telegram error coverage**: mọi lỗi server gửi về error channel, không silent

## Chiến Lược Hiện Có

### Master Candle (`strategies/master_candle.yaml`)
- **Entry**: Nến M5 lúc 21:05 HCM
- **Hướng**: Close > Open → BUY; Close < Open → SELL; Close == Open → SKIP
- **SL/TP**: Neo vào nến entry (candle body ± buffer_k pips), TP = risk × rr_ratio
- **Magic**: 210500

### FEG EMA21 (`strategies/feg_ema21.yaml`)
- **Entry**: Pattern 2 nến (candle1 + candle2, **cùng hướng**) + EMA21 filter, quét liên tục M1
- **Same-type rule (v0.3.0)**: C1 và C2 phải cùng bullish hoặc cùng bearish — mixed pair bị reject
- **SELL**: (both bearish) H2>H1, C2<L1, L2>EMA21(+dist_pips tùy chọn)
- **BUY**: (both bullish) L2<L1, C2>H1, H2<EMA21(-dist_pips tùy chọn)
- **SL/TP**: Neo vào candle2, buffer_k=50 pips, TP = risk × rr_ratio
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
- EMA overlay toggle trên interactive chart
- Run ID (BT-...) hiển thị dạng copyable code block
- Debug fields per trade: `_c1`, `_c2`, `_ema`, `_exit_pos` cho verification
- Lưu kết quả vào lịch sử, xuất Excel

**FR3: Live Bot**
- Khởi chạy bot như subprocess riêng biệt
- Test mode (simulate, no MT5 order) và Live mode (đặt lệnh thật)
- Order ID (ORD-...) prefix mọi log line, gửi kèm Telegram
- Auto-restart sau crash (30s delay, vô hạn lần)
- Tất cả lỗi gửi Telegram về error channel
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

**FR7: CI/CD Deploy**
- Manual trigger từ GitHub Actions
- Tailscale SSH vào Windows server (no port forwarding needed)
- git pull + pip install + restart Streamlit qua schtasks
- Verify Streamlit lên port 8501 sau restart — fail workflow nếu không

**FR8: Verification Script**
- `scripts/verify_backtest.py`: per-trade trace từ MT5 data thật
- Hiển thị signal conditions (checkmarks), SL/TP math, exit info
- Dùng để manual verify logic trước khi test live

## Yêu Cầu Không Chức Năng

| NFR | Yêu Cầu |
|-----|---------|
| Bảo Mật | Credentials từ env vars / auth.yaml (không hardcode) |
| Test | 25 unit tests, pytest, backward-compat cho master_candle |
| Observability | Trace IDs, full Telegram error coverage, per-trade debug fields |
| Hiệu Suất | Backtest: < 5s cho 3 tháng M5 (~26k nến) |
| MT5 | Windows-only, lazy import |
| Extensibility | Thêm strategy = thêm YAML + (optional) signal file |
| Deploy | CI/CD tự động, verify sau restart |

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
│   ├── feg_strategy.py      # FEG pattern detection (same-type rule)
│   ├── backtest.py          # Engine backtest (master + FEG + debug fields + EMA col)
│   ├── bot_runner.py        # Live loop (order IDs, auto-restart, full error coverage)
│   ├── bot_manager.py       # Subprocess manager
│   ├── strategy_manager.py  # YAML → params
│   ├── orders.py            # MT5 order execution
│   └── utils.py             # Shared helpers
├── strategies/              # Strategy YAML definitions
│   ├── master_candle.yaml
│   └── feg_ema21.yaml       # buffer_k=50
├── scripts/                 # Utility scripts
│   ├── verify_backtest.py   # Phase 1 verification per-trade trace
│   └── start_streamlit.bat  # Windows schtasks restart helper
├── .github/workflows/
│   └── deploy.yml           # CI/CD pipeline
└── tests/                   # 25 pytest tests
```

Chi tiết: xem [Codebase Summary](./codebase-summary.md) và [System Architecture](./system-architecture.md).

## Trạng Thái Hiện Tại

### Hoàn Thành ✅
- Streamlit dashboard đa trang với auth
- Master Candle strategy (backtest + live)
- FEG EMA21 strategy (backtest + live, same-type candle rule)
- Backtest engine với shared helpers + debug fields + EMA column
- Backtest history (JSON, Excel export)
- EMA indicator toggle trên backtest chart
- Test mode gate (`place_order(test=True)`)
- **Trace ID system** — BT-... cho backtest, ORD-... cho live orders
- **Full Telegram error coverage** — mọi lỗi gửi error channel
- **Auto-restart bot** — loop trong `__main__`, 30s delay
- **CI/CD pipeline** — GitHub Actions + Tailscale SSH + schtasks restart
- **Verification script** — `scripts/verify_backtest.py` per-trade trace
- 25 unit tests (pytest)
- Bot manager (subprocess, start/stop/restart)
- Strategy YAML system (extensible)

### Chưa Thực Hiện
- REST API endpoint
- Database persistence (hiện dùng JSON)
- Multi-symbol parallel bots (hiện 1 bot/symbol)
- Heartbeat / daily P&L Telegram report

## Mối Nguy Hiểm & Cảnh Báo

| Mức | Vấn đề |
|-----|--------|
| ⚠️ Tài chính | Test kỹ trên demo account trước khi `--test 0` (live) |
| ℹ️ Platform | MT5 Windows-only — bot runner không chạy được trên Linux/Mac |
| ℹ️ Git | `config/auth.yaml` chứa MT5 password — cân nhắc nếu repo public |
| ℹ️ Deploy | SSH private key trong GitHub Secrets — rotate định kỳ |

## Tài Liệu Liên Quan

- [Codebase Summary](./codebase-summary.md)
- [System Architecture](./system-architecture.md)
- [Project Roadmap](./project-roadmap.md)
- [Code Standards](./code-standards.md)
- [MetaTrader5 Python Docs](https://www.mql5.com/en/docs/integration/python_metatrader5)
- [Streamlit Docs](https://docs.streamlit.io/)
