---
title: "Mở rộng Chim bay đồng thuận theo mẫu minh họa"
description: "Cho phép Chim bay chạy cả biến thể có Nến Mẹ hiện tại và biến thể 2 Nến Con + Nến Cha theo hình minh họa."
status: pending
priority: P1
effort: 8h
branch: main
tags: [feature, backend, frontend, testing]
created: 2026-09-22
---

# Mở rộng Chim bay đồng thuận theo mẫu minh họa

## Overview

Thêm switch `Sử dụng Nến Mẹ` cho Chim bay/EMA đồng thuận. Mặc định bật để
giữ hành vi hiện tại. Khi tắt, engine nhận diện mẫu chỉ gồm 2 Nến Con và
Nến Cha theo hình minh họa, dùng cùng luồng signal/limit order của Flappy
Bird. Live bot, backtest, audit debug và UI phải dùng cùng một bộ điều kiện.

Phạm vi strategy: tích hợp biến thể mới vào **Multi Flappy Bird**, không đổi
logic mặc định của **Flappy Bird** hiện tại. User chọn Multi Flappy Bird khi
cần bộ lọc M1/M5 và switch có/không Nến Mẹ; chọn Flappy Bird để giữ strategy
cũ và tránh thay đổi các bot đang chạy.

## Phases

| # | Phase | Status | Effort | Link |
|---|---|---|---:|---|
| 1 | Chuẩn hóa model và điều kiện pattern | Pending | 3h | [phase-01](./phase-01-core-pattern.md) |
| 2 | Tích hợp config, live, backtest và UI | Pending | 3h | [phase-02-integration.md](./phase-02-integration.md) |
| 3 | Test, audit và tài liệu | Pending | 2h | [phase-03-validation.md](./phase-03-validation.md) |

## Dependencies

- Cửa sổ cross được chốt là tuổi giao cắt EMA8/EMA13 trên M1, tối đa 15 nến
  từ cross đến Nến Cha.
- Mỗi Nến Con phải nhỏ hơn `body Cha / 1,5` và đồng thời nhỏ hơn `1,5`
  đơn vị giá.
- Khi không có Mẹ, SL dùng toàn bộ hai Con + Cha.
- Các giá trị `1,5`, `40%`, `15 nến` và `buffer` đều phải là config; không
  hard-code trong detector, live runner hoặc backtest.
- Không thay đổi hành vi mặc định khi `use_mother_candle=true`.
- Không dùng `None` giả làm Nến Mẹ trong signal; model phải biểu diễn rõ pattern
  có hoặc không có Mẹ để debug và tính SL chính xác.
- `flappy_bird` không render switch no-mother; `multi_flappy_bird` mới có
  switch và các threshold riêng.

## Acceptance Summary

- Chim bay có switch bật/tắt Nến Mẹ trong Create Bot và Backtest.
- Bật: tất cả test/hành vi Flappy Bird hiện tại vẫn giữ nguyên.
- Tắt: mẫu 2 Con + Cha có thể tạo signal BUY/SELL theo điều kiện đã chốt.
- Live và backtest cho cùng kết quả trên cùng OHLC/EMA/HTF data.
- Debug UI hiển thị đúng pattern mode và PASS/FAIL từng điều kiện.
