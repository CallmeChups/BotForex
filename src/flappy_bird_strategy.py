"""Flappy Bird BUY/SELL pattern detection and trade level calculation."""

import math

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
    values = list(close_values)
    if span <= 0:
        raise ValueError("EMA span must be positive")
    if window <= 0:
        raise ValueError("EMA warmup window must be positive")

    alpha = 2.0 / (span + 1.0)
    result = []
    for index in range(len(values)):
        start = max(0, index - window + 1)
        ema = float(values[start])
        for value in values[start + 1:index + 1]:
            ema = alpha * float(value) + (1.0 - alpha) * ema
        result.append(ema)
    return result


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
    mother: dict,
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
) -> dict:
    """Return validation status and metrics, optionally including the audit table."""
    child_bodies = [_body(child) for child in children]
    direction = direction.upper()
    if direction not in {"BUY", "SELL"}:
        raise ValueError(f"Unsupported Flappy Bird direction: {direction}")
    is_buy = direction == "BUY"
    highest_child_high = max((child["high"] for child in children), default=None)
    lowest_child_low = min((child["low"] for child in children), default=None)
    highest_child_body = max(child_bodies, default=0.0)
    last_child_body = child_bodies[-1] if child_bodies else 0.0
    metrics = {
        "child_count": len(children),
        "mother_body": _body(mother),
        "father_body": _body(father),
        "largest_child_body": highest_child_body,
        "last_child_body": last_child_body,
        "highest_child_high": highest_child_high,
        "lowest_child_low": lowest_child_low,
        "mother_high": mother["high"],
        "mother_low": mother["low"],
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
    filter_ema13 = (
        metrics["fallback_ema13"] if metrics["ema_mode"] == "fallback" else ema13
    )
    filter_ema21 = (
        metrics["fallback_ema21"] if metrics["ema_mode"] == "fallback" else ema21
    )
    mother_body = metrics["mother_body"]
    father_body = metrics["father_body"]
    mother_is_directional = (
        mother["close"] > mother["open"]
        if is_buy else mother["close"] < mother["open"]
    )
    if not include_checks:
        if not min_child_candles <= len(children) <= max_child_candles:
            reason = "invalid_child_count"
        elif mother_body <= 0 or father_body <= 0:
            reason = "zero_candle_body"
        elif metrics["ema_mode"] is None:
            reason = "ema_order_failed"
        elif not mother_is_directional:
            reason = "mother_direction_failed"
        elif any(mother_body <= body for body in child_bodies):
            reason = "mother_body_not_larger"
        elif mother_coverage_enabled and (not children or (
            mother["high"] < max(max(child["open"], child["close"]) for child in children)
            if is_buy else
            mother["low"] > min(min(child["open"], child["close"]) for child in children)
        )):
            reason = "mother_body_not_covered"
        elif father_body <= 1.5 * last_child_body:
            reason = "father_body_ratio_failed"
        elif (
            (father["high"] - father["close"] >= 0.30 * father_body)
            if is_buy else
            (father["close"] - father["low"] >= 0.30 * father_body)
        ):
            reason = "father_upper_wick_too_large" if is_buy else "father_lower_wick_too_large"
        elif (
            father["open"] < filter_ema13 or father["low"] <= filter_ema21
            if is_buy else
            father["open"] > filter_ema13 or father["high"] >= filter_ema21
        ):
            reason = "father_ema_filter_failed"
        elif not children or (
            father["close"] <= highest_child_high
            if is_buy else father["close"] >= lowest_child_low
        ):
            reason = "father_close_not_above_children" if is_buy else "father_close_not_below_children"
        elif father_body <= min_father_body_points:
            reason = "father_body_below_minimum"
        elif father_body > MAX_FATHER_BODY_POINTS:
            reason = "father_body_above_maximum"
        else:
            reason = None
        return {"valid": reason is None, "reason": reason, "metrics": metrics}

    checks = [
        {
            "key": "child_count",
            "label": "Số nến Con trong khoảng cấu hình",
            "passed": min_child_candles <= len(children) <= max_child_candles,
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
            "passed": mother_body > 0 and all(mother_body > body for body in child_bodies),
            "actual": f"{mother_body:.5f} > {highest_child_body:.5f}",
            "expected": "Body Mẹ > Body Con lớn nhất",
        },
        {
            "key": "mother_direction",
            "label": "Nến Mẹ cùng chiều với chiến lược",
            "passed": mother_is_directional,
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
                f'{mother["high"]:.5f} >= {max((max(child["open"], child["close"]) for child in children), default=0):.5f}'
                if is_buy else
                f'{mother["low"]:.5f} <= {min((min(child["open"], child["close"]) for child in children), default=0):.5f}'
            ),
            "expected": (
                "Bật: HIGH Mẹ >= thân trên cao nhất của Con"
                if is_buy and mother_coverage_enabled else
                "Bật: LOW Mẹ <= thân dưới thấp nhất của Con"
                if mother_coverage_enabled else "Tắt: không kiểm tra bao thân"
            ),
        },
        {
            "key": "father_body_ratio",
            "label": "Thân Cha > 1.5 lần thân Con cuối",
            "passed": father_body > 0 and father_body > 1.5 * last_child_body,
            "actual": f"{father_body:.5f} > {1.5 * last_child_body:.5f}",
            "expected": "Body Cha > 1.5 x Body Con cuối",
        },
        {
            "key": "father_upper_wick",
            "label": "Râu trên Cha < 30% thân Cha" if is_buy else "Râu dưới Cha < 30% thân Cha",
            "passed": father_body > 0 and (
                father["high"] - father["close"] < 0.30 * father_body
                if is_buy else father["close"] - father["low"] < 0.30 * father_body
            ),
            "actual": f'{metrics["father_wick_pct"] or 0:.2f}%',
            "expected": "< 30%",
        },
        {
            "key": "father_ema_filter",
            "label": "OPEN Cha >= EMA13 và LOW Cha > EMA21" if is_buy else "OPEN Cha <= EMA13 và HIGH Cha < EMA21",
            "passed": (
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
            "label": "CLOSE Cha > HIGH Con cao nhất" if is_buy else "CLOSE Cha < LOW Con thấp nhất",
            "passed": bool(children) and (
                father["close"] > highest_child_high
                if is_buy else father["close"] < lowest_child_low
            ),
            "actual": (
                f'{father["close"]:.5f} > {(highest_child_high or 0):.5f}'
                if is_buy else f'{father["close"]:.5f} < {(lowest_child_low or 0):.5f}'
            ),
            "expected": "CLOSE Cha > HIGH Con cao nhất" if is_buy else "CLOSE Cha < LOW Con thấp nhất",
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
    }
    failed_check = next((check for check in checks if not check["passed"]), None)
    has_zero_body = mother_body <= 0 or father_body <= 0
    return {
        "valid": failed_check is None and not has_zero_body,
        "reason": "zero_candle_body" if has_zero_body else (
            (
                "father_body_below_minimum"
                if failed_check and failed_check["key"] == "father_minimum_body"
                and father_body <= min_father_body_points
                else "father_body_above_maximum"
                if failed_check and failed_check["key"] == "father_minimum_body"
                else reason_by_key.get(failed_check["key"])
            ) if failed_check else None
        ),
        "metrics": metrics,
        "checks": checks,
    }


def detect_flappy_bird_signal(
    mother: dict,
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
    )["valid"]


def analyze_flappy_bird(
    symbol: str,
    mother: dict,
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
    )
    if not diagnostics["valid"]:
        return None

    pip_value = get_pip_value(symbol)
    father_body = _body(father)
    last_child = children[-1]
    is_buy = direction.upper() == "BUY"
    entry_price = father["close"] + (1 if not is_buy else -1) * father_body * (entry_body_percent / 100.0)
    if is_buy:
        stop_loss = min(father["low"], last_child["low"]) - sl_buffer_pips * pip_value
        sl_pips = (entry_price - stop_loss) / pip_value
        take_profit = entry_price + sl_pips * pip_value * rr_ratio
    else:
        stop_loss = max(father["high"], last_child["high"]) + sl_buffer_pips * pip_value
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
    }
