# BotForex - Lộ Trình Phát Triển

**Cập Nhật Lần Cuối**: 2026-06-27
**Phiên Bản**: 0.3.0
**Trạng Thái**: Production-ready (CI/CD + Trace IDs + Full Error Coverage)

## Tóm Tắt Thực Hiện

BotForex đã vượt qua giai đoạn PoC và đạt trạng thái production-ready với:
- Dashboard Streamlit đa trang đầy đủ (auth, bots, backtest, orders, strategies)
- Hai chiến lược hoạt động: Master Candle và FEG EMA21 (same-type candle rule)
- Backtest engine + lịch sử + Excel export + EMA chart overlay + run_id trace
- Live bot runner (test mode + live mode + order IDs + auto-restart + full error coverage)
- CI/CD pipeline (GitHub Actions + Tailscale SSH → Windows server)
- Verification script (per-trade trace từ MT5 data)
- 25 unit tests (pytest)

---

## Phase 1: Foundation ✅ Hoàn Thành (Jan 2026)

- [x] Streamlit dashboard đa trang
- [x] Xác thực role-based (admin/user)
- [x] MT5 credentials từ config/auth.yaml (không hardcode)
- [x] Telegram token từ env var
- [x] Logging và error handling
- [x] Strategy YAML system
- [x] Bot manager (subprocess start/stop/restart)
- [x] Bot runner (argparse entry point)
- [x] Place order với test/live gate
- [x] Backtest engine (Master Candle)
- [x] Backtest history (JSON + Excel export)

## Phase 2: Multi-Strategy ✅ Hoàn Thành (Jun 2026)

- [x] **FEG EMA21 strategy** — pattern 2 nến + EMA21 filter
  - [x] `src/feg_strategy.py`: `detect_feg_signal`, `analyze_feg`
  - [x] `strategies/feg_ema21.yaml`
  - [x] Backtest path: sequential while-loop, 1 lệnh/lúc, EMA warmup
  - [x] Live runner: `run_feg_bot`, `feg_entry_decision`, `get_recent_candles`
- [x] **Shared helpers** (tái dụng giữa strategies)
  - [x] `compute_trade_levels` (utils.py)
  - [x] `_compute_lot_size`, `_simulate_exit`, `_make_trade` (backtest.py)
- [x] **Strategy discriminator** `entry.type` (time / pattern) — backward-compat
- [x] **UI pattern-aware**
  - [x] 5_Backtest.py: ẩn Entry Time khi pattern, hiện EMA controls
  - [x] 1_Bots.py: EMA inputs trong form tạo bot
  - [x] 4_Strategies.py: read-only FEG view
- [x] **Backtest history**: thêm cột EMA (Entry Type, EMA Period, EMA Dist)
- [x] **25 unit tests** (pytest)
- [x] **place_order** gated bởi `test` flag, magic/comment parameterized

## Phase 3: Observability & Ops ✅ Hoàn Thành (Jun 2026)

- [x] **FEG same-type candle rule** — C1 và C2 phải cùng hướng (both bullish / both bearish)
  - Reject mixed-type pair trước khi check pattern
  - Update test fixtures cho tất cả SELL/BUY tests
- [x] **EMA indicator toggle** trên backtest interactive chart
  - Detect cột `ema*` trong `ohlc_data`
  - Expander "Indicators" với checkbox per EMA period
  - EMA21 = màu #FF6B00
  - `df[f"ema{ema_period}"] = ema` saved vào ohlc_data trong backtest engine
- [x] **Trace ID system**
  - Backtest run: `BT-YYMMDD-HHMMSS-SYMBOL-XXXX` → `stats["run_id"]`, hiển thị copyable
  - Live order: `ORD-YYMMDD-HHMMSS-SYMBOL-XXXX` → prefix mọi log line, gửi kèm Telegram
- [x] **Full Telegram error coverage** — mọi lỗi bot gửi `is_error=True` về error channel
  - Startup failures (strategy not found, credentials missing)
  - Candle data failures
  - MT5 monitor loop errors
  - FEG data insufficient
  - Order failed
  - Close position failed
  - Crash với traceback (last 800 chars)
- [x] **Auto-restart bot** — `while True` trong `__main__`, RESTART_DELAY=30s
- [x] **Per-trade debug fields** trong backtest trade dicts (underscore prefix)
  - Master Candle: `_candle`
  - FEG: `_c1`, `_c2`, `_ema`, `_exit_pos`
- [x] **CI/CD pipeline** (GitHub Actions + Tailscale SSH)
  - Manual trigger với `restart_streamlit` input
  - Tailscale ephemeral auth (WireGuard VPN, no port forwarding)
  - SSH → Windows server, PowerShell: `git pull` + `pip install`
  - schtasks + `start_streamlit.bat` để restart Streamlit detached
  - Verify port 8501 sau 12s, fail workflow nếu không lên
- [x] **scripts/verify_backtest.py** — Phase 1 verification per-trade trace
  - Args: `--symbol`, `--days`, `--strategy`, `--user`
  - In signal conditions (✓/✗), SL/TP math, exit info, running equity
  - Summary block per strategy
- [x] **`.gitignore` clarification**
  - Tracked: `config/auth.yaml`, `.streamlit/config.toml` (deployed qua CI/CD)
  - Ignored: `data/orders.csv`, `data/running_bots.json`, `logs/` (server-local)

## Phase 4: Testing & Verification (Q3 2026) — Đang Thực Hiện

### Task 4.1: Phase 1 — Backtest Verification ✅ Sẵn Sàng
- [x] `scripts/verify_backtest.py` viết xong, test suite 25/25 pass
- [ ] **Chạy thực tế** với MT5 connected + `--symbol XAUUSD --days 90`
- [ ] Expert review per-trade trace, xác nhận logic đúng

### Task 4.2: Phase 2 — Live Demo Testing ⏳ Chờ Credentials
- [ ] User cung cấp demo account credentials mới
- [ ] Update `config/auth.yaml` với mt5 login/password/server
- [ ] Test mode: `python src/bot_runner.py --strategy feg_ema21 --symbol XAUUSDm --test 1`
  - [ ] MT5 connect OK
  - [ ] FEG pattern detected → Telegram `[TEST] BUY/SELL ...`
  - [ ] active_trade gated, subsequent signals skipped
  - [ ] TP/SL/TIME exit → Telegram exit message
- [ ] Live mode: `python src/bot_runner.py --strategy feg_ema21 --symbol XAUUSDm --test 0`
  - [ ] place_order → ticket visible on MT5 terminal
  - [ ] SL/TP khớp với verify_backtest.py trace
  - [ ] close_position on exit condition

## Phase 5: Infrastructure (Q3-Q4 2026) — Kế Hoạch

### Task 5.1: Database Persistence
- [ ] Chuyển `data/running_bots.json` sang SQLite
- [ ] Lưu trade history vào DB thay vì chỉ JSON
- [ ] Query và filter lịch sử trade nâng cao

### Task 5.2: Monitoring & Alerting
- [ ] Heartbeat check — Telegram alert nếu bot chết (không tự restart được)
- [ ] Daily P&L report tự động
- [ ] Drawdown alert khi vượt ngưỡng

### Task 5.3: REST API
- [ ] FastAPI endpoint để control bot từ external
- [ ] Webhook nhận tín hiệu từ TradingView
- [ ] Auth token cho API

### Task 5.4: Multi-Symbol Parallel Bots
- [ ] Chạy nhiều bot cùng lúc (mỗi symbol độc lập)
- [ ] Aggregate P&L cross-symbol
- [ ] Global risk limit (max open trades)

## Phase 6: Optimization (Q4 2026+) — Tương Lai

### Task 6.1: Strategy Parameter Optimization
- [ ] Grid search trên backtest
- [ ] Walk-forward analysis
- [ ] Sharpe ratio / Max drawdown optimization

### Task 6.2: Thêm Strategy Mới
- [ ] Bollinger Band strategy
- [ ] Support/Resistance breakout
- [ ] Framework plugin-based

### Task 6.3: Web Deploy
- [ ] Docker container
- [ ] Cloud deploy (VPS)
- [ ] Process manager (supervisor)

---

## Lịch Sử Phiên Bản

| Phiên bản | Ngày | Nội dung |
|-----------|------|---------|
| 0.1.0 | 2026-01 | PoC: Master Candle + Dashboard + Backtest |
| 0.2.0 | 2026-06-21 | FEG EMA21 strategy + multi-strategy UI + 25 tests |
| 0.3.0 | 2026-06-27 | Same-type candle rule + EMA chart toggle + Trace IDs + Full error coverage + CI/CD + Verify script |

## Tài Liệu Liên Quan

- [Project Overview & PDR](./project-overview-pdr.md)
- [Codebase Summary](./codebase-summary.md)
- [System Architecture](./system-architecture.md)
- [Code Standards](./code-standards.md)
