# BotForex - Lộ Trình Phát Triển

**Cập Nhật Lần Cuối**: 2026-06-21
**Phiên Bản**: 0.2.0
**Trạng Thái**: Production-ready (multi-strategy)

## Tóm Tắt Thực Hiện

BotForex đã vượt qua giai đoạn PoC và đạt trạng thái production-ready với:
- Dashboard Streamlit đa trang đầy đủ (auth, bots, backtest, orders, strategies)
- Hai chiến lược hoạt động: Master Candle và FEG EMA21
- Backtest engine + lịch sử + Excel export
- Live bot runner (test mode + live mode)
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

## Phase 3: Infrastructure (Q3 2026) — Kế Hoạch

**Mục đích**: Mở rộng khả năng vận hành và giám sát

### Task 3.1: Database Persistence
- [ ] Chuyển `data/running_bots.json` sang SQLite hoặc PostgreSQL
- [ ] Lưu trade history vào DB thay vì chỉ JSON
- [ ] Query và filter lịch sử trade nâng cao

### Task 3.2: REST API
- [ ] FastAPI endpoint để control bot từ external
- [ ] Webhook nhận tín hiệu từ TradingView
- [ ] Auth token cho API

### Task 3.3: Multi-Symbol Parallel Bots
- [ ] Chạy nhiều bot cùng lúc (mỗi symbol độc lập)
- [ ] Aggregate P&L cross-symbol
- [ ] Global risk limit (max open trades)

### Task 3.4: Monitoring & Alerting
- [ ] Heartbeat check — Telegram alert nếu bot chết
- [ ] Daily P&L report tự động
- [ ] Drawdown alert khi vượt ngưỡng

## Phase 4: Optimization (Q4 2026+) — Tương Lai

### Task 4.1: Strategy Parameter Optimization
- [ ] Grid search hoặc Bayesian optimization trên backtest
- [ ] Walk-forward analysis
- [ ] Sharpe ratio / Max drawdown optimization

### Task 4.2: Thêm Strategy Mới
- [ ] Bollinger Band strategy
- [ ] Support/Resistance breakout
- [ ] Framework để thêm strategy custom (plugin-based)

### Task 4.3: Web Deploy
- [ ] Docker container
- [ ] Cloud deploy (VPS hoặc cloud provider)
- [ ] Process manager (supervisor hoặc systemd)

---

## Lịch Sử Phiên Bản

| Phiên bản | Ngày | Nội dung |
|-----------|------|---------|
| 0.1.0 | 2026-01 | PoC: Master Candle + Dashboard + Backtest |
| 0.2.0 | 2026-06 | FEG EMA21 strategy + multi-strategy UI + 25 tests |

## Tài Liệu Liên Quan

- [Project Overview & PDR](./project-overview-pdr.md)
- [Codebase Summary](./codebase-summary.md)
- [System Architecture](./system-architecture.md)
- [Code Standards](./code-standards.md)
