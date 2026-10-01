---
title: "Selectable Pivot Detector for Swing EMA ZigZag"
description: "Add a selectable Confirmed ZigZag or SwingTrendLineTD/Fractal pivot detector with detector-specific settings."
status: completed
priority: P2
effort: 2-3d
branch: main
tags: [feature, backend, frontend, trading]
created: 2026-10-02
---

# Selectable Pivot Detector for Swing EMA ZigZag

## Overview

Add a `Pivot Detector` selector to the Swing EMA strategy. The user can choose
between the existing confirmed ZigZag detector and a new
SwingTrendLineTD/Fractal detector based on
[`indicators/SwingTrendLineTD.mq5`](../../indicators/SwingTrendLineTD.mq5).
Each detector exposes only its own logic-related parameters.

The new detector includes:

- Fractal High/Low detection.
- SwingTrend High/Low line state.
- Breakout event detection.
- An independent switch controlling whether Breakout is required for entry.

When selected, the optional SwingTrendLineTD detector follows the indicator:

- Fractal Strength: `2`.
- Breakout filter: enabled.
- Breakout confirmation: wick/High-Low, not Close.

The existing ZigZag detector remains available and keeps its current defaults:
Depth `2`, Deviation `3`, Back Step `3`.

## Decisions

| Area | Decision |
|---|---|
| Detector choices | Confirmed ZigZag; SwingTrendLineTD / Fractal |
| Strategy default detector | Confirmed ZigZag |
| Optional detector | SwingTrendLineTD / Fractal |
| Fractal confirmation | Strength bars on each side; no repaint before right-side confirmation |
| Breakout default | Enabled for SwingTrendLineTD |
| Breakout confirmation default | Wick/High-Low |
| Display-only indicator options | Excluded from strategy config |
| Common structure filter | Existing pivot distance and structure-age filters remain active |
| Existing ZigZag | Preserve behavior and settings |

## Detector-specific configuration

Strategy YAML keys:

```yaml
pivot_detector: zigzag

zigzag:
  depth: 2
  deviation_points: 3
  back_step: 3

fractal:
  strength: 2
  breakout_enabled: true
  breakout_by_close: false
```

Only the active detector's settings are shown in the UI.

The following indicator inputs are intentionally excluded because they only
control MT5 rendering rather than pivot or entry logic:

- Marker shape, color, size, and pixel shift.
- High/Low line style, color, and width.
- Nearest-line visibility and style.
- Breakout line color, width, style, and visual extension.
- Time marker schedule and rendering options.
- Display-window sizes whose only purpose is chart rendering.

## Architecture

### New detector module

Create [`src/pivot_detectors.py`](../../src/pivot_detectors.py) as the shared
detector boundary. It must not depend on Streamlit, MT5, or backtest state.

Expose typed result data or dict-compatible records for:

```python
detect_pivots(...)
detect_swing_lines(...)
detect_breakouts(...)
```

The result must preserve:

- Pivot index and price.
- Pivot kind (`high` or `low`).
- Confirmation index.
- Swing line segments.
- Breakout direction, broken pivot, and breakout candle index.

Keep the existing implementation in
[`src/zigzag_swing.py`](../../src/zigzag_swing.py) as the ZigZag detector
implementation or wrap it behind the new boundary without changing its output
semantics.

### SwingTrendLineTD behavior

Replicate the logic from `SwingTrendLineTD.mq5` in chronological Python index
order:

1. A fractal high at index `i` requires:
   - `high[i] > high[i-k]` for each `k` in `1..strength`.
   - `high[i] >= high[i+k]` for each `k` in `1..strength`.
2. A fractal low applies the mirrored comparisons.
3. The candidate becomes usable only at `i + strength`.
4. The high swing chain continues through lower highs and resets on a
   higher/equal high.
5. The low swing chain continues through higher lows and resets on a
   lower/equal low.
6. Breakout state tracks the nearest active confirmed high/low.
7. With `breakout_by_close = false`, use High/Low crossing.
8. With `breakout_by_close = true`, use Close crossing.
9. A breakout cannot use the same candle that first confirms its fractal.

If both high and low conditions are true for one candle, preserve both events
in detector output rather than silently dropping one. The strategy adapter may
reject an ambiguous entry when direction cannot be determined safely.

## Strategy integration

Update [`src/swing_ema_strategy.py`](../../src/swing_ema_strategy.py):

1. Accept the selected detector and detector-specific settings.
2. Request normalized pivots from the detector boundary.
3. Keep common structure logic unchanged:
   - BUY: Low 1 → High 1 → Low 2, optional High 2.
   - SELL: High 1 → Low 1 → High 2, optional Low 2.
   - Pivot distance filter.
   - Structure-age filter.
   - EMA consensus and fallback filters.
   - Stop Order, SL, TP, expiry, and EMA exit behavior.
4. When SwingTrendLineTD Breakout filtering is enabled:
   - Require a confirmed Breakout matching the signal direction.
   - Use the Breakout candle as the signal/BO candle metadata.
5. When the Breakout filter is disabled:
   - Use confirmed Fractal structure without requiring a Breakout event.
6. Keep `setup_pivots`, `signal_candle_index`, `setup_id`, and chart metadata
   normalized so both detectors can use the existing chart code.

No detector-specific logic should be embedded directly in
[`src/backtest.py`](../../src/backtest.py) or
[`src/bot_runner.py`](../../src/bot_runner.py).

## Configuration propagation

Update the complete config path:

```text
YAML
  -> strategy_manager
  -> Backtest/Bots UI
  -> bot_manager or run_backtest
  -> live runner/backtest engine
  -> swing_ema_strategy
```

Files expected to change:

- [`strategies/swing_ema_zigzag.yaml`](../../strategies/swing_ema_zigzag.yaml)
- [`src/strategy_manager.py`](../../src/strategy_manager.py)
- [`src/backtest.py`](../../src/backtest.py)
- [`src/bot_manager.py`](../../src/bot_manager.py)
- [`src/bot_runner.py`](../../src/bot_runner.py)
- [`pages/5_Backtest.py`](../../pages/5_Backtest.py)
- [`pages/1_Bots.py`](../../pages/1_Bots.py)

Backward compatibility:

- Configs with explicit `pivot_detector` retain that detector.
- Configs without the new key use `zigzag` as the strategy default.
- Existing ZigZag keys remain readable.
- Detector-specific keys are ignored when another detector is selected.
- Invalid ranges fail explicitly with the repository's normal UI/runtime
  error path; no silent fallback is allowed.

## UI changes

In [`pages/5_Backtest.py`](../../pages/5_Backtest.py) and
[`pages/1_Bots.py`](../../pages/1_Bots.py):

1. Add a `Pivot Detector` selectbox.
2. Show ZigZag fields only for `Confirmed ZigZag`.
3. Show Fractal Strength, Breakout enabled, and Breakout by Close only for
   `SwingTrendLineTD / Fractal`.
4. Add Vietnamese `help` hints to every detector-specific parameter.
5. Keep common pivot-distance and structure filters visible for both detectors.
6. Save all active settings into backtest history and bot configuration.

Suggested labels:

- `Pivot Detector`
- `Fractal Strength (nến mỗi bên)`
- `Dùng Breakout làm điều kiện vào lệnh`
- `Xác nhận Breakout bằng giá đóng cửa`

## Chart integration

Extend the Swing chart overlay flow in
[`pages/5_Backtest.py`](../../pages/5_Backtest.py):

- Render Fractal High/Low markers.
- Render SwingTrend High/Low segments.
- Render Breakout event/level when available.
- Keep existing setup labels: Đáy 1, Đỉnh 1, Đáy 2, Đỉnh 2.
- Mark the Breakout candle as `Nến BO (tạo tín hiệu)` when the Breakout
  filter is enabled.
- Keep Entry marker reserved for the candle that actually fills the Stop
  Order.
- Keep the existing ZigZag overlay unchanged when ZigZag is selected.

## Testing plan

Add or update tests in:

- [`tests/test_zigzag_swing.py`](../../tests/test_zigzag_swing.py)
- [`tests/test_swing_ema_strategy.py`](../../tests/test_swing_ema_strategy.py)
- [`tests/test_backtest_swing_ema.py`](../../tests/test_backtest_swing_ema.py)
- [`tests/test_swing_ema_runtime.py`](../../tests/test_swing_ema_runtime.py)
- [`tests/test_strategy_manager_feg.py`](../../tests/test_strategy_manager_feg.py)
- [`tests/test_bot_command.py`](../../tests/test_bot_command.py)
- New detector tests, preferably
  [`tests/test_pivot_detectors.py`](../../tests/test_pivot_detectors.py)

Required coverage:

- Fractal High/Low detection with Strength `2`.
- Right-side confirmation timing.
- No repaint before confirmation.
- Lower-high and higher-low SwingTrend chains.
- High and Low Breakout with wick confirmation.
- High and Low Breakout with Close confirmation.
- Breakout is not accepted before pivot confirmation.
- Breakout enabled/disabled behavior.
- Detector-specific config parsing and defaults.
- Both detectors producing normalized setup metadata.
- Backtest/live propagation of detector settings.
- Existing ZigZag tests and behavior remain passing.

Validation commands:

```powershell
python -m pytest tests\test_pivot_detectors.py `
  tests\test_zigzag_swing.py `
  tests\test_swing_ema_strategy.py `
  tests\test_backtest_swing_ema.py `
  tests\test_swing_ema_runtime.py `
  tests\test_strategy_manager_feg.py `
  tests\test_bot_command.py -q

python -m py_compile src\pivot_detectors.py `
  src\swing_ema_strategy.py `
  src\backtest.py `
  src\bot_runner.py `
  pages\1_Bots.py `
  pages\5_Backtest.py

git diff --check
```

## Success criteria

- User can select either Pivot Detector in Backtest and Bots.
- Only relevant detector parameters are shown.
- SwingTrendLineTD default reproduces Strength-2 fractal timing and breakout
  semantics from the attached indicator.
- Breakout is required by default for the new detector and can be disabled.
- Backtest and live bot use the same detector output for the same candles and
  settings.
- Chart displays detector-specific pivots, lines, and Breakout metadata.
- Existing ZigZag behavior remains compatible.
- All targeted tests, syntax checks, and whitespace checks pass.

## Risks and mitigations

| Risk | Mitigation |
|---|---|
| MQL5 array orientation differs from Python order | Add fixed OHLC fixtures and assert exact indices |
| Breakout event appears before fractal confirmation | Gate all events by `confirmed_index` |
| Duplicate orders from repeated Breakout scans | Reuse normalized `setup_id` and existing duplicate guards |
| Old configs lack detector keys | Apply explicit migration/default logic |
| Display-only indicator settings affect strategy unexpectedly | Keep them out of detector logic/config |
| Both High and Low qualify on one candle | Preserve both in detector output and reject ambiguous entry safely |

## Implementation result

Completed the selectable detector path across strategy, backtest, live bot,
configuration UI, and Interactive Chart. The implementation adds
`src/pivot_detectors.py`, preserves confirmed ZigZag as the default, and makes
SwingTrendLineTD/Fractal selectable as an alternative. Targeted validation
passed: 94 tests.
