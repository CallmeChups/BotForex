"""Flappy Bird BUY/SELL pattern detection and trade level calculation."""

import math

import numpy as np

from src.utils import get_pip_value


MIN_CHILDREN = 2
MAX_CHILDREN = 7
EMA_WARMUP_WINDOW = 120
MAX_FATHER_BODY_POINTS = 6.0


def calculate_flappy_ema_series(
    close_values,
    span: int,
    window: int = EMA_WARMUP_WINDOW,
) -> list[float]:
    """Calculate EMA using the same bounded warmup window as the live bot."""
    if span <= 0:
        raise ValueError("EMA span must be positive")
    if window <= 0:
        raise ValueError("EMA warmup window must be positive")

    if isinstance(close_values, np.ndarray):
        values = np.asarray(close_values, dtype=float)
    else:
        values = np.asarray(list(close_values), dtype=float)
    if values.size == 0:
        return []
    alpha = 2.0 / (span + 1.0)
    decay = 1.0 - alpha
    warmup_end = min(values.size, window)
    result = np.empty(values.size, dtype=float)
    result[0] = values[0]
    for index in range(1, warmup_end):
        result[index] = alpha * values[index] + decay * result[index - 1]

    if values.size > window:
        # For a full bounded window the recursive EMA is a fixed convolution:
        # the window seed has decay**(window-1), later values have alpha-weighted
        # decay coefficients. NumPy performs this O(n*window) work in C.
        kernel = np.empty(window, dtype=float)
        kernel[:-1] = alpha * decay ** np.arange(window - 1)
        kernel[-1] = decay ** (window - 1)
        result[window - 1:] = np.convolve(values, kernel, mode="valid")
    return result.tolist()


def calculate_flappy_ema_snapshot(
    close_values,
    periods: dict[str, int],
    window: int = EMA_WARMUP_WINDOW,
) -> dict[str, float]:
    """Return the latest bounded-warmup EMA values for a period group."""
    return {
        slot: calculate_flappy_ema_series(close_values, int(periods[slot]), window)[-1]
        for slot in ("short", "medium", "long")
    }


def calculate_flappy_ema_cross_lifecycle(
    close_values,
    fast_period: int = 8,
    slow_period: int = 13,
    window: int = EMA_WARMUP_WINDOW,
) -> tuple[list[str | None], list[int | None]]:
    """Track the active EMA fast/slow cross direction and its candle age."""
    fast_values = calculate_flappy_ema_series(close_values, fast_period, window)
    slow_values = calculate_flappy_ema_series(close_values, slow_period, window)
    directions: list[str | None] = []
    ages: list[int | None] = []
    active_direction = None
    active_age = None
    for index, (fast, slow) in enumerate(zip(fast_values, slow_values)):
        previous_fast = fast_values[index - 1] if index else None
        previous_slow = slow_values[index - 1] if index else None
        if previous_fast is not None and previous_slow is not None:
            if previous_fast <= previous_slow and fast > slow:
                active_direction = "BUY"
                active_age = 0
            elif previous_fast >= previous_slow and fast < slow:
                active_direction = "SELL"
                active_age = 0
            elif active_age is not None:
                active_age += 1
        directions.append(active_direction)
        ages.append(active_age)
    return directions, ages


def diagnose_flappy_higher_timeframe(
    candle: dict,
    ema_values: dict[str, float],
    direction: str,
    mode: str,
    enabled: bool = True,
    mode_enabled: bool = True,
) -> dict:
    """Validate the HTF candle against the selected current-TF EMA mode."""
    direction = direction.upper()
    if direction not in {"BUY", "SELL"}:
        return {"valid": False, "reason": "invalid_direction", "metrics": {}, "checks": []}
    if mode not in {"consensus", "fallback"}:
        return {"valid": False, "reason": "invalid_ema_mode", "metrics": {}, "checks": []}
    if not enabled:
        return {
            "valid": True,
            "reason": "higher_timeframe_filter_disabled",
            "metrics": {},
            "checks": [],
        }
    if not mode_enabled:
        return {"valid": False, "reason": "higher_timeframe_mode_disabled", "metrics": {}, "checks": []}
    short, medium, long = (float(ema_values[key]) for key in ("short", "medium", "long"))
    is_buy = direction == "BUY"
    full_order_ok = short > medium > long if is_buy else short < medium < long
    short_medium_order_ok = short > medium if is_buy else short < medium
    close_side_ok = candle["close"] > long if is_buy else candle["close"] < long
    open_side_ok = (
        candle["open"] > long and candle["close"] > long
        if is_buy else candle["open"] < long and candle["close"] < long
    )
    order_ok = full_order_ok if mode == "consensus" else short_medium_order_ok
    checks = [
        {
            "key": "ema_order",
            "label": (
                "3 EMA HTF đúng thứ tự"
                if mode == "consensus" else
                "EMA ngắn và trung hạn HTF đúng thứ tự"
            ),
            "passed": order_ok,
         "actual": f"{short:.5f}, {medium:.5f}, {long:.5f}"},
        {
            "key": "close_side",
            "label": "CLOSE HTF đúng phía EMA dài hạn",
         "passed": close_side_ok, "actual": f"{candle['close']:.5f} / {long:.5f}"},
    ]
    if mode == "consensus":
        checks.append({
            "key": "open_side", "label": "OPEN HTF đúng phía EMA dài hạn",
            "passed": candle["open"] > long if is_buy else candle["open"] < long,
            "actual": f"OPEN={candle['open']:.5f}, CLOSE={candle['close']:.5f}, EMA={long:.5f}",
        })
    valid = order_ok and close_side_ok and (
        open_side_ok if mode == "consensus" else True
    )
    return {
        "valid": valid,
        "reason": None if valid else (
            "higher_timeframe_ema_order_failed"
            if not order_ok else
            "higher_timeframe_close_side_failed"
            if not close_side_ok else
            "higher_timeframe_open_side_failed"
        ),
        "metrics": {"open": candle["open"], "close": candle["close"], "ema": dict(ema_values), "mode": mode},
        "checks": checks,
    }


def _body(candle: dict) -> float:
    return abs(candle["close"] - candle["open"])


def _ema_order_valid(
    father: dict,
    ema13: float,
    ema21: float,
    ema55: float,
    is_buy: bool,
    fallback_ema13: float | None = None,
    fallback_ema21: float | None = None,
    fallback_ema55: float | None = None,
) -> bool:
    fallback_ema13 = ema13 if fallback_ema13 is None else fallback_ema13
    fallback_ema21 = ema21 if fallback_ema21 is None else fallback_ema21
    fallback_ema55 = ema55 if fallback_ema55 is None else fallback_ema55
    standard_order = (
        ema13 > ema21 > ema55
        if is_buy else ema13 < ema21 < ema55
    )
    if standard_order:
        return True

    return (
        fallback_ema13 > fallback_ema21 and fallback_ema13 < fallback_ema55
        and father["open"] < fallback_ema55 < father["close"]
        if is_buy else
        fallback_ema13 < fallback_ema21 and fallback_ema13 > fallback_ema55
        and father["open"] > fallback_ema55 > father["close"]
    )


def _ema_mode(
    father: dict,
    ema13: float,
    ema21: float,
    ema55: float,
    fallback_ema13: float,
    fallback_ema21: float,
    fallback_ema55: float,
    is_buy: bool,
) -> str | None:
    standard = ema13 > ema21 > ema55 if is_buy else ema13 < ema21 < ema55
    if standard:
        return "consensus"
    fallback = (
        fallback_ema13 > fallback_ema21 and fallback_ema13 < fallback_ema55
        and father["open"] < fallback_ema55 < father["close"]
        if is_buy else
        fallback_ema13 < fallback_ema21 and fallback_ema13 > fallback_ema55
        and father["open"] > fallback_ema55 > father["close"]
    )
    return "fallback" if fallback else None


def diagnose_flappy_bird(
    mother: dict | None,
    children: list[dict],
    father: dict,
    ema13: float,
    ema21: float,
    ema55: float,
    min_father_body_points: float = 2.0,
    include_checks: bool = False,
    direction: str = "BUY",
    min_child_candles: int = MIN_CHILDREN,
    max_child_candles: int = 5,
    mother_coverage_enabled: bool = True,
    fallback_ema13: float | None = None,
    fallback_ema21: float | None = None,
    fallback_ema55: float | None = None,
    consensus_enabled: bool = True,
    fallback_enabled: bool = True,
    requested_ema_mode: str | None = None,
    higher_timeframe_filter: dict | None = None,
    current_timeframe_filter_enabled: bool = True,
    max_child_body_points: float = 2.0,
    use_mother_candle: bool = True,
    no_mother_child_candles: int = 2,
    no_mother_child_body_ratio: float = 1.5,
    no_mother_child_body_max_points: float = 1.5,
    no_mother_father_wick_max_pct: float = 40.0,
) -> dict:
    """Return validation status and metrics, optionally including the audit table."""
    if no_mother_child_candles < 1:
        raise ValueError("no_mother_child_candles must be positive")
    if no_mother_child_body_ratio <= 0:
        raise ValueError("no_mother_child_body_ratio must be positive")
    if no_mother_child_body_max_points < 0:
        raise ValueError("no_mother_child_body_max_points must be non-negative")
    if not 0 <= no_mother_father_wick_max_pct <= 100:
        raise ValueError("no_mother_father_wick_max_pct must be between 0 and 100")
    if use_mother_candle and mother is None:
        raise ValueError("mother is required when use_mother_candle is enabled")
    if not use_mother_candle and mother is not None:
        mother = None

    child_bodies = [_body(child) for child in children]
    direction = direction.upper()
    if direction not in {"BUY", "SELL"}:
        raise ValueError(f"Unsupported Flappy Bird direction: {direction}")
    is_buy = direction == "BUY"
    highest_child_high = max((child["high"] for child in children), default=None)
    lowest_child_low = min((child["low"] for child in children), default=None)
    highest_child_body = max(child_bodies, default=0.0)
    last_child_body = child_bodies[-1] if child_bodies else 0.0
    adjacent_children = children[-2:]
    adjacent_child_bodies = [_body(child) for child in adjacent_children]
    adjacent_child_high = max((child["high"] for child in adjacent_children), default=None)
    adjacent_child_low = min((child["low"] for child in adjacent_children), default=None)
    metrics = {
        "child_count": len(children),
        "mother_body": _body(mother) if mother is not None else None,
        "father_body": _body(father),
        "largest_child_body": highest_child_body,
        "last_child_body": last_child_body,
        "adjacent_child_bodies": adjacent_child_bodies,
        "max_child_body_points": max_child_body_points,
        "highest_child_high": highest_child_high,
        "lowest_child_low": lowest_child_low,
        "mother_high": mother["high"] if mother is not None else None,
        "mother_low": mother["low"] if mother is not None else None,
        "father_upper_wick": max(0.0, father["high"] - father["close"]),
        "father_lower_wick": max(0.0, father["close"] - father["low"]),
        "father_wick_pct": (
            (max(0.0, father["high"] - father["close"]) if is_buy
             else max(0.0, father["close"] - father["low"])) / _body(father) * 100
            if _body(father) else None
        ),
        "ema13": ema13,
        "ema21": ema21,
        "ema55": ema55,
        "fallback_ema13": ema13 if fallback_ema13 is None else fallback_ema13,
        "fallback_ema21": ema21 if fallback_ema21 is None else fallback_ema21,
        "fallback_ema55": ema55 if fallback_ema55 is None else fallback_ema55,
        "min_father_body_points": min_father_body_points,
        "max_father_body_points": MAX_FATHER_BODY_POINTS,
        "pattern_mode": "with_mother" if use_mother_candle else "without_mother",
        "no_mother_child_body_ratio": no_mother_child_body_ratio,
        "no_mother_child_body_max_points": no_mother_child_body_max_points,
        "no_mother_father_wick_max_pct": no_mother_father_wick_max_pct,
    }
    metrics["ema_mode"] = _ema_mode(
        father, ema13, ema21, ema55,
        metrics["fallback_ema13"], metrics["fallback_ema21"],
        metrics["fallback_ema55"], is_buy,
    )
    if not consensus_enabled and metrics["ema_mode"] == "consensus":
        metrics["ema_mode"] = None
    if not fallback_enabled and metrics["ema_mode"] == "fallback":
        metrics["ema_mode"] = None
    if requested_ema_mode is not None:
        if requested_ema_mode not in {"consensus", "fallback"}:
            raise ValueError("requested_ema_mode must be consensus or fallback")
        if (
            requested_ema_mode == "consensus" and not consensus_enabled
        ) or (
            requested_ema_mode == "fallback" and not fallback_enabled
        ):
            metrics["ema_mode"] = None
            requested_valid = False
        else:
            selected_values = (
                (ema13, ema21, ema55)
                if requested_ema_mode == "consensus"
                else (metrics["fallback_ema13"], metrics["fallback_ema21"], metrics["fallback_ema55"])
            )
            requested_valid = (
                selected_values[0] > selected_values[1] > selected_values[2]
                if is_buy and requested_ema_mode == "consensus"
                else selected_values[0] < selected_values[1] < selected_values[2]
                if not is_buy and requested_ema_mode == "consensus"
                else (
                    selected_values[0] > selected_values[1] and selected_values[0] < selected_values[2]
                    and father["open"] < selected_values[2] < father["close"]
                    if is_buy else
                    selected_values[0] < selected_values[1] and selected_values[0] > selected_values[2]
                    and father["open"] > selected_values[2] > father["close"]
                )
            )
            metrics["ema_mode"] = requested_ema_mode if requested_valid else None
    if not current_timeframe_filter_enabled:
        if requested_ema_mode in {"consensus", "fallback"}:
            metrics["ema_mode"] = requested_ema_mode
        elif consensus_enabled:
            metrics["ema_mode"] = "consensus"
        elif fallback_enabled:
            metrics["ema_mode"] = "fallback"
    higher_timeframe_debug = None
    if metrics["ema_mode"] is not None and higher_timeframe_filter is not None:
        if higher_timeframe_filter.get("candle") is None:
            higher_timeframe_debug = {
                "valid": False,
                "reason": "higher_timeframe_data_unavailable",
                "metrics": {},
                "checks": [],
            }
        else:
            higher_timeframe_debug = diagnose_flappy_higher_timeframe(
                higher_timeframe_filter["candle"],
                higher_timeframe_filter["ema_values"],
                direction,
                higher_timeframe_filter.get("mode", metrics["ema_mode"]),
                bool(higher_timeframe_filter.get("enabled", True)),
                bool(higher_timeframe_filter.get("mode_enabled", True)),
            )
        if not higher_timeframe_debug["valid"]:
            metrics["ema_mode"] = None
    filter_ema13 = (
        metrics["fallback_ema13"] if metrics["ema_mode"] == "fallback" else ema13
    )
    filter_ema21 = (
        metrics["fallback_ema21"] if metrics["ema_mode"] == "fallback" else ema21
    )
    mother_body = metrics["mother_body"] or 0.0
    father_body = metrics["father_body"]
    mother_is_directional = (
        mother is not None and (
            mother["close"] > mother["open"]
            if is_buy else mother["close"] < mother["open"]
        )
    )
    no_mother_children_inside_father = bool(children) and (
        father["low"] <= min(child["low"] for child in children)
        and father["high"] >= max(child["high"] for child in children)
    )
    no_mother_child_bodies_valid = bool(children) and all(
        body < father_body / no_mother_child_body_ratio
        and body < no_mother_child_body_max_points
        for body in child_bodies
    )
    no_mother_wick_valid = father_body > 0 and (
        father["high"] - father["close"]
        if is_buy else father["close"] - father["low"]
    ) < (no_mother_father_wick_max_pct / 100.0) * father_body
    no_mother_ema_valid = (
        father["open"] >= ema21 if is_buy else father["open"] <= ema21
    )
    if not include_checks:
        if not use_mother_candle and len(children) != no_mother_child_candles:
            reason = "no_mother_child_count_invalid"
        elif use_mother_candle and not min_child_candles <= len(children) <= max_child_candles:
            reason = "invalid_child_count"
        elif (use_mother_candle and mother_body <= 0) or father_body <= 0:
            reason = "zero_candle_body"
        elif metrics["ema_mode"] is None:
            reason = "ema_order_failed"
        elif use_mother_candle and not mother_is_directional:
            reason = "mother_direction_failed"
        elif use_mother_candle and any(mother_body <= body for body in child_bodies):
            reason = "mother_body_not_larger"
        elif use_mother_candle and mother_coverage_enabled and (not children or (
            mother["high"] < max(max(child["open"], child["close"]) for child in children)
            if is_buy else
            mother["low"] > min(min(child["open"], child["close"]) for child in children)
        )):
            reason = "mother_body_not_covered"
        elif not use_mother_candle and not no_mother_children_inside_father:
            reason = "no_mother_children_outside_father"
        elif not use_mother_candle and not no_mother_child_bodies_valid:
            reason = "no_mother_child_body_above_maximum"
        elif use_mother_candle and any(body > max_child_body_points for body in adjacent_child_bodies):
            reason = "child_body_above_maximum"
        elif use_mother_candle and father_body <= 1.5 * last_child_body:
            reason = "father_body_ratio_failed"
        elif use_mother_candle and (
            (father["high"] - father["close"] >= 0.30 * father_body)
            if is_buy else
            (father["close"] - father["low"] >= 0.30 * father_body)
        ):
            reason = "father_upper_wick_too_large" if is_buy else "father_lower_wick_too_large"
        elif not use_mother_candle and not no_mother_wick_valid:
            reason = "no_mother_father_wick_too_large"
        elif current_timeframe_filter_enabled and (
            (
            father["open"] < filter_ema13 or father["low"] <= filter_ema21
            if is_buy else
            father["open"] > filter_ema13 or father["high"] >= filter_ema21
            )
            if use_mother_candle else not no_mother_ema_valid
        ):
            reason = "father_ema_filter_failed"
        elif use_mother_candle and (not children or (
            father["close"] <= adjacent_child_high
            if is_buy else father["close"] >= adjacent_child_low
        )):
            reason = "father_close_not_above_children" if is_buy else "father_close_not_below_children"
        elif father_body <= min_father_body_points:
            reason = "father_body_below_minimum"
        elif father_body > MAX_FATHER_BODY_POINTS:
            reason = "father_body_above_maximum"
        else:
            reason = None
        return {
            "valid": reason is None and (
                higher_timeframe_debug is None or higher_timeframe_debug["valid"]
            ),
            "reason": (
                higher_timeframe_debug.get("reason")
                if higher_timeframe_debug and not higher_timeframe_debug["valid"]
                else reason
            ),
            "metrics": metrics,
            "higher_timeframe_debug": higher_timeframe_debug,
        }

    checks = [
        {
            "key": "child_count",
            "label": "Số nến Con trong khoảng cấu hình",
            "passed": (
                len(children) == no_mother_child_candles
                if not use_mother_candle
                else min_child_candles <= len(children) <= max_child_candles
            ),
            "actual": len(children),
            "expected": f"{min_child_candles}..{max_child_candles}",
        },
        {
            "key": "ema_order",
            "label": "EMA chuẩn hoặc EMA55 breakout fallback",
            "passed": metrics["ema_mode"] is not None,
            "actual": f"{ema13:.5f}, {ema21:.5f}, {ema55:.5f}",
            "expected": (
                "EMA13 > EMA21 > EMA55 hoặc Cha cắt EMA55 từ dưới lên"
                if is_buy else
                "EMA13 < EMA21 < EMA55 hoặc Cha cắt EMA55 từ trên xuống"
            ),
        },
        {
            "key": "mother_body",
            "label": "Thân Mẹ lớn hơn mọi thân Con",
            "passed": (
                mother_body > 0 and all(mother_body > body for body in child_bodies)
                if use_mother_candle else True
            ),
            "actual": f"{mother_body:.5f} > {highest_child_body:.5f}",
            "expected": "Body Mẹ > Body Con lớn nhất",
        },
        {
            "key": "mother_direction",
            "label": "Nến Mẹ cùng chiều với chiến lược",
            "passed": mother_is_directional if use_mother_candle else True,
            "actual": (
                "Bullish" if mother["close"] > mother["open"]
                else "Bearish" if mother["close"] < mother["open"]
                else "Doji"
            ),
            "expected": "Bullish (BUY)" if is_buy else "Bearish (SELL)",
        },
        {
            "key": "mother_coverage",
            "label": "HIGH Mẹ bao trùm thân các Con" if is_buy else "LOW Mẹ bao trùm thân các Con",
            "passed": (
                True if not use_mother_candle else
                bool(children)
                and (
                    not mother_coverage_enabled
                    or (
                        mother["high"] >= max(
                            max(child["open"], child["close"]) for child in children
                        )
                        if is_buy
                        else mother["low"] <= min(
                            min(child["open"], child["close"]) for child in children
                        )
                    )
                )
            ),
            "actual": (
                "Không áp dụng" if not use_mother_candle else
                f'{mother["high"]:.5f} >= {max((max(child["open"], child["close"]) for child in children), default=0):.5f}'
                if is_buy else
                f'{mother["low"]:.5f} <= {min((min(child["open"], child["close"]) for child in children), default=0):.5f}'
            ),
            "expected": (
                "Không áp dụng" if not use_mother_candle else
                "Bật: HIGH Mẹ >= thân trên cao nhất của Con"
                if is_buy and mother_coverage_enabled else
                "Bật: LOW Mẹ <= thân dưới thấp nhất của Con"
                if mother_coverage_enabled else "Tắt: không kiểm tra bao thân"
            ),
        },
        {
            "key": "child_body_maximum",
            "label": "Thân hai nến Con cuối không vượt mức tối đa",
            "passed": (
                no_mother_child_bodies_valid
                if not use_mother_candle else
                bool(adjacent_children) and all(
                    body <= max_child_body_points for body in adjacent_child_bodies
                )
            ),
            "actual": ", ".join(f"{body:.5f}" for body in adjacent_child_bodies),
            "expected": (
                f"mỗi Con < body Cha / {no_mother_child_body_ratio:g} "
                f"và < {no_mother_child_body_max_points:g}"
                if not use_mother_candle else f"<= {max_child_body_points:.5f}"
            ),
        },
        {
            "key": "father_body_ratio",
            "label": "Thân Cha > 1.5 lần thân Con cuối",
            "passed": (
                True if not use_mother_candle else
                father_body > 0 and father_body > 1.5 * last_child_body
            ),
            "actual": (
                "Không áp dụng" if not use_mother_candle
                else f"{father_body:.5f} > {1.5 * last_child_body:.5f}"
            ),
            "expected": (
                "Không áp dụng" if not use_mother_candle
                else "Body Cha > 1.5 x Body Con cuối"
            ),
        },
        {
            "key": "father_upper_wick",
            "label": "Râu trên Cha < 30% thân Cha" if is_buy else "Râu dưới Cha < 30% thân Cha",
            "passed": (
                no_mother_wick_valid if not use_mother_candle else
                father_body > 0 and (
                father["high"] - father["close"] < 0.30 * father_body
                if is_buy else father["close"] - father["low"] < 0.30 * father_body
                )
            ),
            "actual": f'{metrics["father_wick_pct"] or 0:.2f}%',
            "expected": f'< {no_mother_father_wick_max_pct:g}%'
            if not use_mother_candle else "< 30%",
        },
        {
            "key": "father_ema_filter",
            "label": "OPEN Cha >= EMA13 và LOW Cha > EMA21" if is_buy else "OPEN Cha <= EMA13 và HIGH Cha < EMA21",
            "passed": not current_timeframe_filter_enabled or (
                no_mother_ema_valid if not use_mother_candle else
                father["open"] >= filter_ema13 and father["low"] > filter_ema21
                if is_buy else father["open"] <= filter_ema13 and father["high"] < filter_ema21
            ),
            "actual": (
                f'OPEN {father["open"]:.5f} >= EMA {filter_ema13:.5f}; LOW {father["low"]:.5f} > EMA {filter_ema21:.5f}'
                if is_buy else
                f'OPEN {father["open"]:.5f} <= EMA {filter_ema13:.5f}; HIGH {father["high"]:.5f} < EMA {filter_ema21:.5f}'
            ),
            "expected": "Cả hai điều kiện đều đúng",
        },
        {
            "key": "father_close_breakout",
            "label": "CLOSE Cha > HIGH hai Con cuối" if is_buy else "CLOSE Cha < LOW hai Con cuối",
            "passed": (
                True if not use_mother_candle else
                bool(children) and (
                father["close"] > adjacent_child_high
                if is_buy else father["close"] < adjacent_child_low
                )
            ),
            "actual": (
                "Không áp dụng" if not use_mother_candle else
                f'{father["close"]:.5f} > {(adjacent_child_high or 0):.5f}'
                if is_buy else f'{father["close"]:.5f} < {(adjacent_child_low or 0):.5f}'
            ),
            "expected": "CLOSE Cha > HIGH hai Con cuối" if is_buy else "CLOSE Cha < LOW hai Con cuối",
        },
        {
            "key": "father_minimum_body",
            "label": "Thân Cha trong khoảng cho phép",
            "passed": min_father_body_points < father_body <= MAX_FATHER_BODY_POINTS,
            "actual": f"{father_body:.5f}",
            "expected": f"> {min_father_body_points:.5f} và <= {MAX_FATHER_BODY_POINTS:.1f}",
        },
    ]
    reason_by_key = {
        "child_count": "invalid_child_count",
        "ema_order": "ema_order_failed",
        "mother_body": "mother_body_not_larger",
        "mother_coverage": "mother_body_not_covered",
        "father_body_ratio": "father_body_ratio_failed",
        "father_upper_wick": "father_upper_wick_too_large" if is_buy else "father_lower_wick_too_large",
        "father_ema_filter": "father_ema_filter_failed",
        "father_close_breakout": "father_close_not_above_children" if is_buy else "father_close_not_below_children",
        "father_minimum_body": "father_body_below_minimum",
        "child_body_maximum": "child_body_above_maximum",
        "no_mother_child_count": "no_mother_child_count_invalid",
        "no_mother_children_inside_father": "no_mother_children_outside_father",
        "no_mother_child_body": "no_mother_child_body_above_maximum",
        "no_mother_father_wick": "no_mother_father_wick_too_large",
    }
    if higher_timeframe_debug is not None:
        checks.extend(higher_timeframe_debug.get("checks", []))
    failed_check = next((check for check in checks if not check["passed"]), None)
    has_zero_body = (use_mother_candle and mother_body <= 0) or father_body <= 0
    return {
        "valid": failed_check is None and not has_zero_body,
        "reason": (
            higher_timeframe_debug.get("reason")
            if higher_timeframe_debug and not higher_timeframe_debug["valid"]
            else "zero_candle_body" if has_zero_body else (
            (
                "father_body_below_minimum"
                if failed_check and failed_check["key"] == "father_minimum_body"
                and father_body <= min_father_body_points
                else "father_body_above_maximum"
                if failed_check and failed_check["key"] == "father_minimum_body"
                else reason_by_key.get(failed_check["key"])
            ) if failed_check else None
        )),
        "metrics": metrics,
        "checks": checks,
        "higher_timeframe_debug": higher_timeframe_debug,
    }


def detect_flappy_bird_signal(
    mother: dict | None,
    children: list[dict],
    father: dict,
    ema13: float,
    ema21: float,
    ema55: float,
    min_father_body_points: float = 2.0,
    direction: str = "BUY",
    min_child_candles: int = MIN_CHILDREN,
    max_child_candles: int = 5,
    mother_coverage_enabled: bool = True,
    fallback_ema13: float | None = None,
    fallback_ema21: float | None = None,
    fallback_ema55: float | None = None,
    consensus_enabled: bool = True,
    fallback_enabled: bool = True,
    requested_ema_mode: str | None = None,
    higher_timeframe_filter: dict | None = None,
    current_timeframe_filter_enabled: bool = True,
    max_child_body_points: float = 2.0,
    use_mother_candle: bool = True,
    no_mother_child_candles: int = 2,
    no_mother_child_body_ratio: float = 1.5,
    no_mother_child_body_max_points: float = 1.5,
    no_mother_father_wick_max_pct: float = 40.0,
) -> bool:
    """Return whether the candle window satisfies the BUY pattern."""
    return diagnose_flappy_bird(
        mother, children, father, ema13, ema21, ema55, min_father_body_points,
        direction=direction,
        min_child_candles=min_child_candles,
        max_child_candles=max_child_candles,
        mother_coverage_enabled=mother_coverage_enabled,
        fallback_ema13=fallback_ema13,
        fallback_ema21=fallback_ema21,
        fallback_ema55=fallback_ema55,
        consensus_enabled=consensus_enabled,
        fallback_enabled=fallback_enabled,
        requested_ema_mode=requested_ema_mode,
        higher_timeframe_filter=higher_timeframe_filter,
        current_timeframe_filter_enabled=current_timeframe_filter_enabled,
        max_child_body_points=max_child_body_points,
        use_mother_candle=use_mother_candle,
        no_mother_child_candles=no_mother_child_candles,
        no_mother_child_body_ratio=no_mother_child_body_ratio,
        no_mother_child_body_max_points=no_mother_child_body_max_points,
        no_mother_father_wick_max_pct=no_mother_father_wick_max_pct,
    )["valid"]


def analyze_flappy_bird(
    symbol: str,
    mother: dict | None,
    children: list[dict],
    father: dict,
    ema13: float,
    ema21: float,
    ema55: float,
    lot_size: float = 0.01,
    sl_buffer_pips: float = 5.0,
    entry_body_percent: float = 5.0,
    rr_ratio: float = 2.0,
    min_father_body_points: float = 2.0,
    direction: str = "BUY",
    min_child_candles: int = MIN_CHILDREN,
    max_child_candles: int = 5,
    mother_coverage_enabled: bool = True,
    fallback_ema13: float | None = None,
    fallback_ema21: float | None = None,
    fallback_ema55: float | None = None,
    consensus_enabled: bool = True,
    fallback_enabled: bool = True,
    requested_ema_mode: str | None = None,
    higher_timeframe_filter: dict | None = None,
    current_timeframe_filter_enabled: bool = True,
    max_child_body_points: float = 2.0,
    use_mother_candle: bool = True,
    no_mother_child_candles: int = 2,
    no_mother_child_body_ratio: float = 1.5,
    no_mother_child_body_max_points: float = 1.5,
    no_mother_father_wick_max_pct: float = 40.0,
    no_mother_sl_buffer_pips: float | None = None,
) -> dict | None:
    """Return a standard pending limit signal or None."""
    diagnostics = diagnose_flappy_bird(
        mother, children, father, ema13, ema21, ema55, min_father_body_points,
        direction=direction,
        min_child_candles=min_child_candles,
        max_child_candles=max_child_candles,
        mother_coverage_enabled=mother_coverage_enabled,
        fallback_ema13=fallback_ema13,
        fallback_ema21=fallback_ema21,
        fallback_ema55=fallback_ema55,
        consensus_enabled=consensus_enabled,
        fallback_enabled=fallback_enabled,
        requested_ema_mode=requested_ema_mode,
        higher_timeframe_filter=higher_timeframe_filter,
        current_timeframe_filter_enabled=current_timeframe_filter_enabled,
        max_child_body_points=max_child_body_points,
        use_mother_candle=use_mother_candle,
        no_mother_child_candles=no_mother_child_candles,
        no_mother_child_body_ratio=no_mother_child_body_ratio,
        no_mother_child_body_max_points=no_mother_child_body_max_points,
        no_mother_father_wick_max_pct=no_mother_father_wick_max_pct,
    )
    if not diagnostics["valid"]:
        return None

    pip_value = get_pip_value(symbol)
    father_body = _body(father)
    last_child = children[-1]
    is_buy = direction.upper() == "BUY"
    entry_price = father["close"] + (1 if not is_buy else -1) * father_body * (entry_body_percent / 100.0)
    if is_buy:
        stop_reference = min(
            father["low"],
            *(child["low"] for child in children),
        ) if not use_mother_candle else min(father["low"], last_child["low"])
        buffer_pips = (
            no_mother_sl_buffer_pips
            if not use_mother_candle and no_mother_sl_buffer_pips is not None
            else sl_buffer_pips
        )
        stop_loss = stop_reference - buffer_pips * pip_value
        sl_pips = (entry_price - stop_loss) / pip_value
        take_profit = entry_price + sl_pips * pip_value * rr_ratio
    else:
        stop_reference = max(
            father["high"],
            *(child["high"] for child in children),
        ) if not use_mother_candle else max(father["high"], last_child["high"])
        buffer_pips = (
            no_mother_sl_buffer_pips
            if not use_mother_candle and no_mother_sl_buffer_pips is not None
            else sl_buffer_pips
        )
        stop_loss = stop_reference + buffer_pips * pip_value
        sl_pips = (stop_loss - entry_price) / pip_value
        take_profit = entry_price - sl_pips * pip_value * rr_ratio
    if (
        not all(math.isfinite(value) for value in (entry_price, stop_loss, take_profit))
        or sl_pips <= 0
        or (is_buy and not stop_loss < entry_price < take_profit)
        or (not is_buy and not take_profit < entry_price < stop_loss)
    ):
        return None
    return {
        "symbol": symbol,
        "direction": "BUY" if is_buy else "SELL",
        "order_type": "BUY_LIMIT" if is_buy else "SELL_LIMIT",
        "entry_price": entry_price,
        "stop_loss": stop_loss,
        "take_profit": take_profit,
        "sl_pips": sl_pips,
        "lot_size": lot_size,
        "mother": mother,
        "children": children,
        "father": father,
        "ema13": ema13,
        "ema21": ema21,
        "ema55": ema55,
        "fallback_ema13": diagnostics["metrics"]["fallback_ema13"],
        "fallback_ema21": diagnostics["metrics"]["fallback_ema21"],
        "fallback_ema55": diagnostics["metrics"]["fallback_ema55"],
        "ema_mode": diagnostics["metrics"].get("ema_mode"),
        "debug": diagnostics,
        "higher_timeframe_debug": diagnostics.get("higher_timeframe_debug"),
        "higher_timeframe": (
            higher_timeframe_filter.get("candle")
            if higher_timeframe_filter else None
        ),
    }
