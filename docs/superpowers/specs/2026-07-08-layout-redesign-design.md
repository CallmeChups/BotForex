# Layout Redesign — Create Bot & Backtest

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task.

**Goal:** Thay thế toàn bộ layout variants (Classic compact, Classic verbose, New) bằng 1 layout duy nhất dùng colored section headers, tất cả zones mở sẵn, nhãn phần lớn tiếng Việt.

**Scope:** `pages/1_Bots.py` (tab Create Bot) và `pages/5_Backtest.py` (form params).

---

## 1. Quyết định kiến trúc

### 1.1 Layout pattern: Colored Section Headers

Bỏ hoàn toàn `st.expander` cho form params. Thay bằng section header dạng:

```python
st.markdown("""
<div style="background:#6366f118;border-left:3px solid #6366f1;
     padding:6px 14px;border-radius:4px;margin:16px 0 8px;
     font-size:11px;font-weight:700;letter-spacing:.06em;color:#818cf8;">
  ⚙ GENERAL
</div>""", unsafe_allow_html=True)
```

4 zones, 4 màu cố định:

| Zone | Icon | Màu | Hex |
|------|------|-----|-----|
| General | ⚙ | Indigo | `#6366f1` |
| Entry | 📈 | Emerald | `#10b981` |
| Order Settings & Risk | 📊 | Amber | `#f59e0b` |
| Exit | 🚪 | Red | `#ef4444` |

### 1.2 Loại bỏ layout variants

Xóa toàn bộ:
- `use_compact` toggle + compact/verbose branching
- `layout_version` radio (New / Classic)
- Code paths cho Classic layout (compact và verbose)

Giữ lại duy nhất code path của "New layout" hiện tại, refactor thành layout mới.

### 1.3 Helper function dùng chung

Tạo `_section_header(icon, title, color)` trong mỗi file để render colored header. Không tách file riêng (YAGNI — chỉ 2 file dùng).

---

## 2. Zone structure

### 2.1 Create Bot (`1_Bots.py` → `show_create_bot()`)

```
[Strategy selectbox]
[Load config từ Backtest — collapsed expander, giữ nguyên]

⚙ GENERAL
  row1 (3 cols): Tùy chọn symbol* | Test Mode | RR Ratio
  row2 (3 cols): Giới hạn số nến* | Chu kỳ quét (giây) | Lot Mode

📈 ENTRY  [chỉ hiện nếu is_pattern]
  sub "FEG Margins" (4 cols): EMA Period | H2 vượt H1 | C2 vượt L1/H1 | L2/H2 cách EMA
  ---
  sub "Wick Filter" (4 cols): BUY râu trên | BUY râu dưới | SELL râu trên | SELL râu dưới
  ---
  sub "Bộ lọc EMA" (3 cols): ☑ Bộ lọc EMA | BUY — Phía EMA | SELL — Phía EMA
  ---
  sub "Khung giờ & Kiểu vào lệnh" (4 cols):
    Giờ vào lệnh — Từ | Giờ vào lệnh — Đến | Entry Mode | Chờ khớp lệnh (nến)*
    [nếu feg_stop_order: thay Entry Mode + Chờ bằng Chờ khớp lệnh (nến) span 2]
    [nếu range_percent: thêm Entry Percent (%) làm col thứ 5]

📊 ORDER SETTINGS & RISK
  row1 (3 cols): Buffer K (pips) | ☐ Entry tiếp tục sau SL | Lot Size [nếu Fixed]
  [nếu Flex: row thêm (3 cols): Risk Mode | Risk mỗi lệnh (%) / ($) | — ]

🚪 EXIT
  row1 (4 cols): Take Profit (TP) Exit | Stop Loss (SL) Exit | ☐ Break-Even (BE) | BE Trigger (R)

[🚀 Khởi động Bot — full width primary]
[KHỞI ĐỘNG NHANH (TEST) — 3 quick buttons]
```

*checkbox kèm input

### 2.2 Backtest (`5_Backtest.py` — form params)

```
[Strategy selectbox]

⚙ GENERAL
  row1 (3 cols): Tùy chọn symbol* | Tùy chọn khung thời gian* | RR Ratio
  row2 (3 cols): Ngày bắt đầu | Ngày kết thúc | Giới hạn số nến*

📈 ENTRY  [chỉ hiện nếu is_pattern]
  [giống Create Bot — FEG Margins, Wick Filter, Bộ lọc EMA, Khung giờ & Kiểu vào lệnh]
  [nếu không phải pattern: Entry Time (time_input) duy nhất]

📊 ORDER SETTINGS & RISK
  row1 (4 cols): Buffer K (pips) | ☐ Entry tiếp tục sau SL | Lot Mode | Lot Size [nếu Fixed]
  [nếu Flex (3 cols): Vốn ban đầu ($) | Risk Mode | Risk mỗi lệnh (%) / ($)]

🚪 EXIT
  row1 (4 cols): Take Profit (TP) Exit | Stop Loss (SL) Exit | ☐ Break-Even (BE) | BE Trigger (R)

[▶ Run Backtest — full width primary]
```

---

## 3. Nhãn đã approved

| Nhãn gốc | Nhãn mới |
|-----------|----------|
| Custom symbol | Tùy chọn symbol |
| Enable Max Candles | Giới hạn số nến |
| Check Interval (seconds) | Chu kỳ quét (giây) |
| Custom TF | Tùy chọn khung thời gian |
| H2 > H1 + N pips | H2 vượt H1 (pips) |
| EMA Filter | Bộ lọc EMA |
| BUY EMA side | BUY — Phía EMA |
| SELL EMA side | SELL — Phía EMA |
| Window Start/End (HCM) | Giờ vào lệnh — Từ / Đến (HCM) |
| Re-Entry After SL | Entry tiếp tục sau SL |
| Risk per Trade (%) / ($) | Risk mỗi lệnh (%) / ($) |
| Starting Equity ($) | Vốn ban đầu ($) |
| Start Bot | Khởi động Bot |
| Quick Start (Test Mode) | Khởi động nhanh (Test) |
| Load from Backtest History | Load config từ Backtest |
| Reuse Config | Load config cũ |
| Manage History | Quản lý lịch sử |
| Filter by Strategy/Symbol | Lọc theo Strategy / Symbol |

**Giữ nguyên tiếng Anh:** Test Mode, RR Ratio, Lot Mode, Lot Size, EMA Period, Buffer K (pips), Entry Mode, Entry Percent (%), Chờ khớp lệnh (nến), Break-Even (BE), BE Trigger (R), Take Profit (TP) Exit, Stop Loss (SL) Exit, Risk Mode, Run Backtest.

---

## 4. Điều không thay đổi

- Tab structure (`Running Bots / Create Bot / Bot History`) trong `1_Bots.py` — giữ nguyên
- History section, results section, trade analysis trong `5_Backtest.py` — giữ nguyên
- Business logic, widget keys, session state keys — không đổi
- `_pf()`, `_parse_wick()`, `_migrate_config()` helpers — giữ nguyên
- Flash message (`_flash_success`) — giữ nguyên
- Backtest MT5 Override expander — giữ nguyên

---

## 5. Ràng buộc kỹ thuật

- `unsafe_allow_html=True` cho section headers
- Widget keys không đổi để tránh break session state
- Mỗi file tự chứa `_section_header()` helper (không chia sẻ module)
- Không dùng `st.expander` cho form params (trừ "Load config từ Backtest" và "Backtest MT5 Override")
- Tất cả widgets hiển thị luôn (không collapse) — dùng `st.columns` + `st.divider` thay cho expander
