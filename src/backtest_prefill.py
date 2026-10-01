from collections.abc import Mapping
from typing import Any


def swing_backtest_widget_values(config: Mapping[str, Any]) -> dict[str, Any]:
    """Map saved Swing backtest settings to their Streamlit widget state keys."""
    values: dict[str, Any] = {}
    for config_key, widget_prefix in (
        ("swing_ema_periods", "backtest_swing_ema"),
        ("swing_fallback_ema_periods", "backtest_swing_fallback_ema"),
    ):
        group = config.get(config_key, {})
        if isinstance(group, Mapping):
            values.update({
                f"{widget_prefix}_{slot}": group[slot]
                for slot in ("fast", "medium", "slow")
                if slot in group
            })

    scalar_keys = {
        "swing_use_pivot2_for_buy": "backtest_swing_pivot2_buy",
        "swing_use_pivot2_for_sell": "backtest_swing_pivot2_sell",
        "swing_ema_consensus_enabled": "backtest_swing_ema_consensus_enabled",
        "swing_ema_fallback_enabled": "backtest_swing_ema_fallback_enabled",
        "swing_zigzag_depth": "backtest_swing_zigzag_depth",
        "swing_zigzag_deviation_points": "backtest_swing_zigzag_deviation",
        "swing_zigzag_back_step": "backtest_swing_zigzag_back_step",
        "swing_min_structure_candles": "backtest_swing_min_structure",
        "swing_max_structure_candles": "backtest_swing_max_structure",
        "swing_ema_cross_window_candles": "backtest_swing_cross_window",
        "swing_entry_buffer_pips": "backtest_swing_entry_buffer",
        "swing_sl_buffer_pips": "backtest_swing_sl_buffer",
        "swing_pending_expiry_candles": "backtest_swing_pending_expiry",
        "swing_max_pending_orders_per_symbol": "backtest_swing_max_pending",
        "swing_ema_exit_enabled": "backtest_swing_ema_exit_enabled",
        "swing_ema_exit_period": "backtest_swing_ema_exit_period",
    }
    values.update({
        widget_key: config[config_key]
        for config_key, widget_key in scalar_keys.items()
        if config_key in config
    })
    return values
