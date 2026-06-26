# Backtest & Live Demo Testing — Design Spec

**Ngày:** 2026-06-22
**Trạng thái:** Approved
**Mục tiêu:** Verify toàn bộ pipeline giao dịch — từ điều kiện vào lệnh đến đặt lệnh MT5 thật

---

## 1. Tổng Quan

Hai phase testing:

| Phase | Mục tiêu | Data source | Output |
|-------|----------|-------------|--------|
| 1 — Backtest simulation | Verify logic: entry condition, TP/SL math, exit, 1-trade-at-a-time | MT5 historical M5 | Trace script (console) |
| 2 — Live demo | Verify pipeline: MT5 connect, place_order, exit, Telegram | Demo account real-time | Log console + Telegram |

---

## 2. Phase 1 — Backtest Verification Script

### 2.1 File

```
scripts/verify_backtest.py
```

### 2.2 Cách Chạy

```bash
python scripts/verify_backtest.py --symbol XAUUSD --days 90
```

**Arguments:**
- `--symbol` — trading symbol (default: XAUUSD)
- `--days` — lookback period in days (default: 90)
- `--strategy` — `all` | `master_candle` | `feg` (default: `all`)

### 2.3 Cấu Trúc Script

```
1. Load credentials từ config/auth.yaml (admin user)
2. Connect MT5 + fetch M5 historical data (--days lookback)
3. ─── MASTER CANDLE ───────────────────────────────────────
   run_backtest(df, entry_type="time", ...)
   In trace từng trade (xem §2.4)
   In summary
4. ─── FEG EMA21 ──────────────────────────────────────────
   run_backtest(df, entry_type="pattern", ema_period=21, ...)
   In trace từng trade (xem §2.4)
   In summary
5. ─── OVERALL SUMMARY ─────────────────────────────────────
   Combined stats
```

### 2.4 Trace Output Format

**Master Candle — mỗi trade:**
```
[TRADE #N]
  Candle  : {time} | O={open} H={high} L={low} C={close}
  Signal  : C({close}) > O({open}) → BUY   [hoặc SELL / DOJI skip]
  Entry   : {entry_price}
  SL calc : L({low}) - {buffer_k}×{pip} = {sl}
  TP calc : E({entry}) + (E-SL)({sl_dist}) × {rr} = {tp}
  Exit    : {TP|SL|TIME} | {exit_time} | price={exit_price} | {n} candles
  PnL     : {pnl_pips:+.1f} pips | equity ${equity:.2f}
```

**FEG EMA21 — mỗi trade:**
```
[TRADE #N] @ candle i={i}
  C1      : {time} | H={h1} L={l1} C={c1}
  C2      : {time} | H={h2} L={l2} C={c2}
  EMA21   : {ema:.2f}
  Checks  : H2({h2})>H1({h1}){✓|✗}  C2({c2})<L1({l1}){✓|✗}  L2({l2})>EMA({ema}){✓|✗}
  Signal  : {SELL|BUY}
  Entry   : {entry_price}
  SL calc : H2({h2}) + {buffer_k}×{pip} = {sl}   [SELL]
  TP calc : E({entry}) - (SL-E)({sl_dist}) × {rr} = {tp}
  Exit    : {TP|SL|TIME} | {exit_time} | price={exit_price} | {n} candles
  PnL     : {pnl_pips:+.1f} pips | equity ${equity:.2f}
  Next scan from i={exit_pos+1}
```

**Summary block (mỗi strategy):**
```
════════════════════════════════════════
{STRATEGY} SUMMARY
  Trades   : {total}
  Win/Loss : {wins}/{losses} ({win_rate:.1f}%)
  P/F      : {profit_factor}
  Total    : {total_pips:+.1f} pips
  Equity   : ${final_equity:.2f}
════════════════════════════════════════
```

### 2.5 Verification Targets

Mỗi trade trong trace cho phép verify thủ công:

| Check | Cách verify |
|-------|------------|
| TP math | `entry ± sl_distance × rr_ratio` — tính lại tay từ numbers trong trace |
| SL math | `high/low ± buffer_k × pip_value` |
| FEG conditions | 3 dòng `Checks` hiện `✓`/`✗` từng điều kiện riêng biệt |
| 1-trade-at-a-time | `Next scan from i=N` — i phải > exit candle index |
| Exit correctness | Exit type + price khớp với TP/SL/TIME logic |
| PnL calculation | `(exit_price - entry) / pip_value × lot` |

### 2.6 Exit Conditions Khi Script Fail

- MT5 connect fail → in error rõ ràng, exit code 1
- Fetch data trả về empty → in warning, skip strategy đó
- Exception trong trade loop → in trade index + exception, tiếp tục

---

## 3. Phase 2 — Live Demo Testing

### 3.1 Pre-condition

User cung cấp demo account credentials mới. Update `config/auth.yaml`:
```yaml
mt5:
  login: <new_demo_login>
  password: <new_demo_password>
  server: <broker_server>
```

Verify connection trước khi test bot:
```bash
python -c "
from src.orders import get_account_info
import yaml
creds = yaml.safe_load(open('config/auth.yaml'))['mt5']
info, err = get_account_info(creds)
print(info or err)
"
```

### 3.2 Step 2 — Test Mode (`--test 1`)

```bash
python src/bot_runner.py \
  --strategy feg_ema21 --symbol XAUUSDm \
  --user admin --test 1 --interval 60
```

**Verify:**
- [ ] MT5 connect + login OK (log in console)
- [ ] `get_recent_candles` trả về DataFrame, không có nến đang chạy
- [ ] EMA21 tính được
- [ ] Khi có FEG pattern → log signal + `[TEST] simulated`
- [ ] Telegram nhận được message `[TEST] BUY/SELL XAUUSDm ...`
- [ ] `active_trade` được set sau signal
- [ ] Signal tiếp theo bị bỏ qua khi `active_trade` không None
- [ ] Khi TP/SL/TIME → log exit + Telegram exit message

### 3.3 Step 3 — Live Mode (`--test 0`)

```bash
python src/bot_runner.py \
  --strategy feg_ema21 --symbol XAUUSDm \
  --user admin --test 0 --interval 60
```

**Verify:**
- [ ] `place_order` gọi MT5 thật → nhận ticket number
- [ ] Lệnh xuất hiện trên MT5 terminal với `magic=212100`, `comment="FEG"`
- [ ] SL/TP đặt đúng trên lệnh mở (so sánh với trace từ Phase 1)
- [ ] Telegram báo "Order placed at {price}"
- [ ] Khi exit condition hit → `close_position_by_ticket` đóng được
- [ ] Telegram báo exit type + PnL

**Safety:** Chỉ dùng demo account. Lot size default = 0.01 (minimum).

### 3.4 Step 4 — Master Candle Smoke Test

```bash
python src/bot_runner.py \
  --strategy master_candle --symbol XAUUSDm \
  --user admin --test 1 --interval 60
```

**Verify:**
- [ ] Dispatch vào `run_master_candle_bot` (không vào FEG path)
- [ ] Bot chờ đến 21:05 HCM và log "waiting for entry candle"
- [ ] Không cần live mode (master_candle đã chạy production)

### 3.5 Điểm Dừng

| Fail condition | Action |
|---|---|
| Step 2 fail (test mode) | Không proceed Step 3 |
| Step 3 fail (place_order) | Log lỗi cụ thể, không để lệnh treo trên MT5 |
| Lệnh mở nhưng bot crash | Close thủ công từ MT5 terminal hoặc `pages/2_Orders.py` |

---

## 4. Phụ Thuộc & Constraints

- MT5 terminal phải đang chạy và connected (Windows)
- `config/auth.yaml` phải có credentials hợp lệ
- `TELEGRAM_BOT_TOKEN` + `TELEGRAM_CHAT_ID` phải set trong `.env`
- `scripts/` directory phải có `__init__.py` hoặc script tự add `sys.path`
- Script chỉ cần `pytest` cho Phase 1 unit tests đã có; verify script dùng trực tiếp `src/` modules

---

## 5. Files Thêm Mới

| File | Mục đích |
|------|---------|
| `scripts/verify_backtest.py` | Phase 1 verification script |

**Không thêm gì khác.** Phase 2 dùng code đã có (`bot_runner.py`, `orders.py`).

---

## 6. Câu Hỏi Tồn Đọng

- Credentials demo account sẽ được cung cấp sau khi Phase 1 pass
- Symbol cho Phase 2: `XAUUSDm` (demo suffix) — confirm với user khi cung cấp credentials
