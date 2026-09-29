from types import SimpleNamespace

import pandas as pd

from src import bot_runner, orders


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
        "ema_cross_window_candles": 12,
        "rr_ratio": 2.5,
        "pending_expiry_candles": 5,
        "sl_buffer_price": 0.04,
        "entry_buffer_price": 0.02,
    }


def test_live_test_mode_simulates_swing_order_fill_without_mt5(monkeypatch):
    class FakeMT5:
        def symbol_info(self, symbol):
            return SimpleNamespace(volume_min=0.01)

        def orders_get(self, **kwargs):
            return []

        def positions_get(self, **kwargs):
            return []

        def shutdown(self):
            pass

    mt5 = FakeMT5()
    logs = []
    submitted = []
    frames = []
    for offset, high in ((0, 100.05), (1, 100.5)):
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
    }
    decisions = iter((signal, None))
    monkeypatch.setattr(bot_runner, "get_mt5_connection", lambda credentials: (mt5, None))
    monkeypatch.setattr(
        bot_runner, "_ensure_mt5_connected", lambda mt5_ref, credentials: (mt5, None)
    )
    monkeypatch.setattr(bot_runner, "get_recent_candles", lambda *args: frames.pop(0))
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
    monkeypatch.setattr(bot_runner, "_has_duplicate_swing_pending", lambda *args: False)

    def place_stop_order(*args, **kwargs):
        submitted.append((args, kwargs))
        return True, "simulated", None

    monkeypatch.setattr(orders, "place_stop_order", place_stop_order)
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
        test=True,
        interval=0.01,
        managed_by_ui=True,
        log_file="",
    )
    params = {
        "timeframe": "M1",
        "swing_ema_periods": {"fast": 13, "medium": 21, "slow": 55},
        "magic": 212500,
        "lot_size": 0.01,
    }

    bot_runner.run_swing_ema_zigzag_bot(args, "swing_ema_zigzag", params, {})

    assert len(submitted) == 1
    assert submitted[0][1]["test"] is True
    assert signal["created_bar_index"] == 0
    assert signal["expires_at_bar"] == 7
    assert any("[TEST] Swing stop filled @ 100.40" in message for message in logs)


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
