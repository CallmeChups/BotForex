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

### FEG EMA21 — Điều Kiện Vào Lệnh

**SELL** (cả 2 nến phải bearish):
- H2 > H1 (high mới cao hơn)
- C2 < L1 (close dưới low nến trước)
- L2 > EMA21 (low trên EMA)

**BUY** (cả 2 nến phải bullish):
- L2 < L1 (low mới thấp hơn)
- C2 > H1 (close trên high nến trước)
- H2 < EMA21 (high dưới EMA)

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
