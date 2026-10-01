from types import SimpleNamespace

import pandas as pd
import pytest

from src import bot_runner, orders, state_file


def test_live_entry_decision_delegates_all_swing_settings(monkeypatch):
    candles = object()
    captured = {}
    expected = {"direction": "BUY", "entry_price": 101.0}

    def build_signal(**kwargs):
        captured.update(kwargs)
        return expected

    monkeypatch.setattr(
        "src.swing_ema_strategy.build_swing_ema_entry_signal",
        build_signal,
    )
    monkeypatch.setattr(bot_runner, "get_pip_value", lambda symbol: 0.01)

    result = bot_runner.swing_ema_zigzag_entry_decision(
        df=candles,
        symbol="TEST",
        ema_periods={"fast": 8, "medium": 13, "slow": 34},
        zigzag_depth=4,
        zigzag_deviation_points=2.5,
        zigzag_back_step=2,
        min_structure_candles=8,
        max_structure_candles=18,
        ema_cross_window_candles=12,
        rr_ratio=2.5,
        pending_expiry_candles=5,
        sl_buffer_price=0.04,
        entry_buffer_price=0.02,
        use_pivot2_for_buy=False,
        use_pivot2_for_sell=True,
        ema_consensus_enabled=False,
        ema_fallback_enabled=True,
        fallback_ema_periods={"fast": 8, "medium": 13, "slow": 34},
    )

    assert result is expected
    assert captured == {
        "data": candles,
        "symbol_point_size": 0.01,
        "ema_periods": {"fast": 8, "medium": 13, "slow": 34},
        "zigzag_depth": 4,
        "zigzag_deviation_points": 2.5,
        "zigzag_back_step": 2,
        "min_structure_candles": 8,
        "max_structure_candles": 18,
        "min_pivot_distance_candles": 5,
        "max_pivot_distance_candles": 15,
        "ema_cross_window_candles": 12,
        "rr_ratio": 2.5,
        "pending_expiry_candles": 5,
        "sl_buffer_price": 0.04,
        "entry_buffer_price": 0.02,
        "use_pivot2_for_buy": False,
        "use_pivot2_for_sell": True,
        "ema_consensus_enabled": False,
        "ema_fallback_enabled": True,
        "fallback_ema_periods": {"fast": 8, "medium": 13, "slow": 34},
    }


@pytest.mark.parametrize("test_mode", [True, False])
def test_live_swing_order_uses_previous_closed_candle_for_fill_protection(
    monkeypatch, test_mode
):
    class FakeMT5:
        ORDER_TYPE_BUY = 0

        def symbol_info(self, symbol):
            return SimpleNamespace(volume_min=0.01)

        def orders_get(self, **kwargs):
            return []

        def positions_get(self, **kwargs):
            if not test_mode:
                return [SimpleNamespace(
                    ticket=9002,
                    identifier=9001,
                    order=9001,
                    symbol="XAUUSD",
                    magic=212500,
                    type=self.ORDER_TYPE_BUY,
                    price_open=100.4,
                    time=1,
                    volume=0.01,
                )]
            return []

        def shutdown(self):
            pass

    mt5 = FakeMT5()
    logs = []
    submitted = []
    modified = []
    frames = []
    frame_updates = (
        ((0, 100.05), (1, 100.5))
        if test_mode
        else ((0, 100.05), (0, 100.5))
    )
    for offset, high in frame_updates:
        times = pd.date_range(
            "2025-01-01",
            periods=60,
            freq="min",
            tz="UTC",
        ).astype("int64") // 10**9
        frame = pd.DataFrame({
            "time": times,
            "open": [100.0] * 60,
            "high": [100.05] * 60,
            "low": [99.95] * 60,
            "close": [100.0] * 60,
        })
        frame.loc[59, "time"] += offset * 60
        frame.loc[59, "high"] = high
        if offset:
            frame.loc[59, "open"] = 100.4
            frame.loc[59, "close"] = 100.45
        frames.append(frame)

    signal = {
        "direction": "BUY",
        "entry_price": 100.2,
        "stop_loss": 99.5,
        "take_profit": 101.6,
        "expiry_bars": 7,
        "setup_id": "BUY:pullback-structure",
    }
    loaded_setup_keys = []
    reserved_setup_ids = []
    monkeypatch.setattr(
        state_file,
        "load_swing_setup_ids",
        lambda path, key: (loaded_setup_keys.append(key) or set()),
    )
    monkeypatch.setattr(
        state_file,
        "reserve_swing_setup_id",
        lambda path, key, setup_id: (
            reserved_setup_ids.append((key, setup_id)) or True
        ),
    )
    monkeypatch.setattr(
        state_file,
        "release_swing_setup_id",
        lambda *args: None,
    )
    decisions = iter((signal, None))
    requested_candle_counts = []
    monkeypatch.setattr(bot_runner, "get_mt5_connection", lambda credentials: (mt5, None))
    monkeypatch.setattr(
        bot_runner, "_ensure_mt5_connected", lambda mt5_ref, credentials: (mt5, None)
    )
    monkeypatch.setattr(
        bot_runner,
        "get_recent_candles",
        lambda *args: (requested_candle_counts.append(args[-1]) or frames.pop(0)),
    )
    monkeypatch.setattr(
        bot_runner, "swing_ema_zigzag_entry_decision", lambda **kwargs: next(decisions)
    )
    monkeypatch.setattr(bot_runner, "send_telegram", lambda *args, **kwargs: None)
    monkeypatch.setattr(bot_runner, "log", logs.append)
    monkeypatch.setattr(bot_runner, "_write_bot_state", lambda *args: None)
    monkeypatch.setattr(bot_runner, "_register_in_running_bots", lambda **kwargs: None)
    monkeypatch.setattr(bot_runner, "_unregister_from_running_bots", lambda *args: None)
    monkeypatch.setattr(bot_runner, "_check_pending_restart", lambda pid: False)
    monkeypatch.setattr(bot_runner, "_clear_pending_restart", lambda pid: None)
    monkeypatch.setattr(
        bot_runner,
        "_has_duplicate_swing_pending",
        lambda *args, **kwargs: False,
    )

    def place_stop_order(*args, **kwargs):
        submitted.append((args, kwargs))
        return True, "simulated", None if test_mode else 9001, "submitted"

    monkeypatch.setattr(orders, "place_stop_order", place_stop_order)
    monkeypatch.setattr(
        orders,
        "modify_position_sl_tp",
        lambda *args, **kwargs: (
            modified.append((args, kwargs)) or (True, "protection updated")
        ),
    )
    monkeypatch.setattr("src.bot_history_manager.create_session", lambda **kwargs: "session")
    monkeypatch.setattr("src.bot_history_manager.close_session", lambda session_id: None)
    monkeypatch.setattr("src.bot_history_manager.record_trade", lambda *args, **kwargs: None)

    sleep_calls = 0

    def stop_loop(_interval):
        nonlocal sleep_calls
        sleep_calls += 1
        if sleep_calls == 2:
            raise KeyboardInterrupt

    monkeypatch.setattr(bot_runner.time, "sleep", stop_loop)
    args = SimpleNamespace(
        strategy="swing_ema_zigzag",
        timeframe="M1",
        ema_short_period=13,
        ema_medium_period=21,
        ema_long_period=55,
        fallback_ema_short_period=None,
        fallback_ema_medium_period=None,
        fallback_ema_long_period=None,
        use_pivot2_for_buy=None,
        use_pivot2_for_sell=None,
        ema_consensus_enabled=None,
        ema_fallback_enabled=None,
        zigzag_depth=3,
        zigzag_deviation_points=3.0,
        zigzag_back_step=3,
        min_structure_candles=10,
        max_structure_candles=20,
        ema_cross_window_candles=15,
        ema_exit_enabled=0,
        ema_exit_period=21,
        pending_expiry_candles=7,
        max_pending_orders_per_symbol=0,
        sl_buffer_pips=5.0,
        entry_buffer_pips=2.0,
        tp_type="price_based",
        sl_type="price_based",
        rr_ratio=2.0,
        lot_size=0.01,
        lot_mode="fixed",
        risk_mode="percent",
        risk_percent=0.5,
        risk_amount=5.0,
        symbol="XAUUSD",
        user="tester",
        test=test_mode,
        interval=0.01,
        managed_by_ui=True,
        log_file="",
    )
    params = {
        "timeframe": "M1",
        "swing_ema_periods": {"fast": 13, "medium": 21, "slow": 55},
        "swing_fallback_ema_periods": {
            "fast": 89,
            "medium": 144,
            "slow": 233,
        },
        "ema_fallback_enabled": True,
        "magic": 212500,
        "lot_size": 0.01,
    }

    bot_runner.run_swing_ema_zigzag_bot(args, "swing_ema_zigzag", params, {})

    assert requested_candle_counts == [932, 932]
    assert len(submitted) == 1
    assert submitted[0][1]["test"] is test_mode
    assert submitted[0][1]["sl"] is None
    assert submitted[0][1]["tp"] is None
    assert signal["created_bar_index"] == 0
    assert signal["expires_at_bar"] == 7
    if test_mode:
        assert not loaded_setup_keys
        assert not reserved_setup_ids
    else:
        assert loaded_setup_keys == [
            "swing_ema_zigzag:XAUUSD:tester:212500:live"
        ]
        assert reserved_setup_ids == [
            ("swing_ema_zigzag:XAUUSD:tester:212500:live", "BUY:pullback-structure")
        ]
    assert any("Fill-based protection: SL=99.45000 TP=102.30000" in message for message in logs)
    if test_mode:
        assert any("[TEST] Swing stop filled @ 100.40" in message for message in logs)
        assert not modified
    else:
        assert modified[0][0][0] == 9002
        assert modified[0][0][1] == pytest.approx(99.45)
        assert modified[0][0][2] == pytest.approx(102.3)


def test_filled_swing_order_matches_new_position_ticket():
    class FakeMT5:
        ORDER_TYPE_BUY = 0

        def positions_get(self, symbol):
            return [SimpleNamespace(
                ticket=9002,
                identifier=9001,
                order=9001,
                symbol=symbol,
                magic=212500,
                type=self.ORDER_TYPE_BUY,
                time=10,
            )]

    pending_order = SimpleNamespace(ticket=9001)
    position = bot_runner._find_filled_position(
        FakeMT5(), pending_order, "XAUUSD", 212500, direction="BUY"
    )

    assert position.ticket == 9002


def test_swing_signal_is_duplicate_when_setup_matches_even_if_sl_changes():
    class FakeMT5:
        def orders_get(self, symbol):
            return []

    existing = {
        "direction": "SELL",
        "entry_price": 100.0,
        "stop_loss": 101.0,
        "take_profit": 98.0,
        "setup_id": "SELL:pivot-high:pivot-low",
    }
    refreshed_signal = {
        **existing,
        "setup_id": "SELL:different-high:same-entry",
        "stop_loss": 101.2,
        "take_profit": 97.6,
    }

    assert bot_runner._has_duplicate_swing_pending(
        FakeMT5(),
        [],
        refreshed_signal,
        "XAUUSD",
        212500,
        active_trades=[{"signal": existing}],
    )


def test_swing_signal_matches_broker_pending_by_entry_without_sl_tp():
    class FakeMT5:
        ORDER_TYPE_SELL_STOP = 5

        def orders_get(self, symbol):
            return [SimpleNamespace(
                symbol=symbol,
                magic=212500,
                type=self.ORDER_TYPE_SELL_STOP,
                price_open=100.0,
                sl=0.0,
                tp=0.0,
            )]

    signal = {
        "direction": "SELL",
        "entry_price": 100.0,
        "stop_loss": 101.0,
        "take_profit": 98.0,
        "setup_id": "SELL:new-pivot-pair",
    }

    assert bot_runner._has_duplicate_swing_pending(
        FakeMT5(),
        [],
        signal,
        "XAUUSD",
        212500,
    )


def test_legacy_swing_pending_blocks_new_setup_after_restart():
    class FakeMT5:
        def orders_get(self, symbol):
            return [SimpleNamespace(
                symbol=symbol,
                magic=212500,
                type=5,
                price_open=100.0,
                comment="SWING-OLD1",
            )]

        def positions_get(self, symbol):
            return []

    signal = {
        "direction": "SELL",
        "entry_price": 98.0,
        "stop_loss": 99.0,
        "take_profit": 96.0,
        "setup_id": "SELL:new-pullback",
    }

    assert bot_runner._has_duplicate_swing_pending(
        FakeMT5(),
        [],
        signal,
        "XAUUSD",
        212500,
    )


def test_persisted_setup_comment_matches_broker_order_at_different_entry():
    signal = {
        "direction": "BUY",
        "entry_price": 101.0,
        "stop_loss": 99.0,
        "take_profit": 105.0,
        "setup_id": "BUY:pullback-structure",
    }

    class FakeMT5:
        def orders_get(self, symbol):
            return [SimpleNamespace(
                symbol=symbol,
                magic=212500,
                type=4,
                price_open=100.5,
                comment=bot_runner._swing_setup_order_comment(signal["setup_id"]),
            )]

        def positions_get(self, symbol):
            return []

    assert bot_runner._has_duplicate_swing_pending(
        FakeMT5(),
        [],
        signal,
        "XAUUSD",
        212500,
    )


def test_swing_duplicate_check_fails_closed_when_broker_orders_unavailable():
    class FakeMT5:
        def orders_get(self, symbol):
            return None

    signal = {
        "direction": "BUY",
        "entry_price": 101.0,
        "stop_loss": 99.0,
        "take_profit": 105.0,
        "setup_id": "BUY:pullback-structure",
    }

    with pytest.raises(RuntimeError, match="Could not read pending orders"):
        bot_runner._has_duplicate_swing_pending(
            FakeMT5(),
            [],
            signal,
            "XAUUSD",
            212500,
        )
