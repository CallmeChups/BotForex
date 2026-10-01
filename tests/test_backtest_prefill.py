from src.backtest_prefill import swing_backtest_widget_values


def test_swing_backtest_prefill_maps_saved_settings_to_widget_keys():
    values = swing_backtest_widget_values({
        "swing_ema_periods": {"fast": 8, "medium": 13, "slow": 21},
        "swing_fallback_ema_periods": {"fast": 5, "medium": 8, "slow": 13},
        "swing_use_pivot2_for_buy": False,
        "swing_use_pivot2_for_sell": True,
        "swing_ema_consensus_enabled": False,
        "swing_ema_fallback_enabled": True,
        "swing_zigzag_depth": 4,
        "swing_zigzag_deviation_points": 5.0,
        "swing_zigzag_back_step": 2,
        "swing_min_structure_candles": 12,
        "swing_max_structure_candles": 24,
        "swing_ema_cross_window_candles": 10,
        "swing_entry_buffer_pips": 3.0,
        "swing_sl_buffer_pips": 6.0,
        "swing_pending_expiry_candles": 9,
        "swing_max_pending_orders_per_symbol": 2,
        "swing_ema_exit_enabled": False,
        "swing_ema_exit_period": 34,
    })

    assert values == {
        "backtest_swing_ema_fast": 8,
        "backtest_swing_ema_medium": 13,
        "backtest_swing_ema_slow": 21,
        "backtest_swing_fallback_ema_fast": 5,
        "backtest_swing_fallback_ema_medium": 8,
        "backtest_swing_fallback_ema_slow": 13,
        "backtest_swing_pivot2_buy": False,
        "backtest_swing_pivot2_sell": True,
        "backtest_swing_ema_consensus_enabled": False,
        "backtest_swing_ema_fallback_enabled": True,
        "backtest_swing_zigzag_depth": 4,
        "backtest_swing_zigzag_deviation": 5.0,
        "backtest_swing_zigzag_back_step": 2,
        "backtest_swing_min_structure": 12,
        "backtest_swing_max_structure": 24,
        "backtest_swing_cross_window": 10,
        "backtest_swing_entry_buffer": 3.0,
        "backtest_swing_sl_buffer": 6.0,
        "backtest_swing_pending_expiry": 9,
        "backtest_swing_max_pending": 2,
        "backtest_swing_ema_exit_enabled": False,
        "backtest_swing_ema_exit_period": 34,
    }


def test_swing_backtest_prefill_ignores_missing_optional_settings():
    assert swing_backtest_widget_values({
        "swing_ema_periods": {"fast": 13, "medium": 21, "slow": 55},
    }) == {
        "backtest_swing_ema_fast": 13,
        "backtest_swing_ema_medium": 21,
        "backtest_swing_ema_slow": 55,
    }
