from src import orders


def test_place_order_test_mode_does_not_touch_mt5(monkeypatch):
    called = {"connect": False}

    def fake_conn(creds=None):
        called["connect"] = True
        return None, "should not be called"

    monkeypatch.setattr(orders, "get_mt5_connection", fake_conn)

    success, msg, ticket = orders.place_order(
        "XAUUSD", "SELL", 0.01, sl=102.5, tp=89.0, test=True,
    )
    assert success is True
    assert ticket is None
    assert "TEST" in msg
    assert called["connect"] is False  # không gọi MT5 ở test mode


def test_place_order_live_sends_and_returns_ticket(monkeypatch):
    class FakeTick:
        bid = 98.0
        ask = 98.1

    class FakeSymbolInfo:
        visible = True

    class FakeResult:
        retcode = 99
        order = 777777
        comment = "done"

    class FakeMT5:
        TRADE_RETCODE_DONE = 99
        ORDER_TYPE_BUY = 0
        ORDER_TYPE_SELL = 1
        TRADE_ACTION_DEAL = 1
        ORDER_TIME_GTC = 0
        ORDER_FILLING_IOC = 0

        def symbol_info(self, s):
            return FakeSymbolInfo()

        def symbol_select(self, s, v):
            return True

        def symbol_info_tick(self, s):
            return FakeTick()

        def order_send(self, req):
            return FakeResult()

        def shutdown(self):
            pass

    fake = FakeMT5()
    monkeypatch.setattr(orders, "get_mt5_connection", lambda creds=None: (fake, None))
    # place_order dùng `import MetaTrader5 as mt5_module` cho hằng số -> patch sys.modules
    import sys
    monkeypatch.setitem(sys.modules, "MetaTrader5", fake)

    success, msg, ticket = orders.place_order(
        "XAUUSD", "SELL", 0.01, sl=102.5, tp=89.0, test=False, magic=212100, comment="FEG",
    )
    assert success is True
    assert ticket == 777777


def test_place_limit_order_accepts_placed_retcode(monkeypatch):
    class FakeSymbolInfo:
        visible = True
        trade_tick_size = 0.01
        point = 0.01
        digits = 2
        trade_stops_level = 0

    class FakeTick:
        bid = 101.0
        ask = 101.1

    class FakeResult:
        retcode = 10008
        order = 888888
        comment = "placed"

    class FakeMT5:
        TRADE_RETCODE_DONE = 10009
        TRADE_RETCODE_PLACED = 10008
        ORDER_TYPE_BUY_LIMIT = 2
        ORDER_TYPE_SELL_LIMIT = 3
        TRADE_ACTION_PENDING = 5
        ORDER_TIME_GTC = 0
        ORDER_FILLING_RETURN = 2

        def symbol_info(self, symbol):
            return FakeSymbolInfo()

        def symbol_select(self, symbol, enabled):
            return True

        def symbol_info_tick(self, symbol):
            return FakeTick()

        def order_send(self, request):
            return FakeResult()

        def shutdown(self):
            pass

    fake = FakeMT5()
    monkeypatch.setattr(orders, "get_mt5_connection", lambda creds=None: (fake, None))
    import sys
    monkeypatch.setitem(sys.modules, "MetaTrader5", fake)

    success, message, ticket = orders.place_limit_order(
        "XAUUSD", "SELL", 0.01, price=102.0, sl=104.0, tp=98.0,
        test=False, magic=212400, comment="FLAPPY-TEST",
    )
    assert success is True
    assert ticket == 888888
    assert "placed" in message


def test_place_stop_order_accepts_placed_retcode_and_reports_submission(monkeypatch):
    class FakeSymbolInfo:
        visible = True

    class FakeResult:
        retcode = 10008
        order = 888889
        comment = "placed"

    class FakeMT5:
        TRADE_RETCODE_DONE = 10009
        TRADE_RETCODE_PLACED = 10008
        ORDER_TYPE_BUY_STOP = 4
        TRADE_ACTION_PENDING = 5
        ORDER_TIME_GTC = 0
        ORDER_FILLING_RETURN = 2

        def symbol_info(self, symbol):
            return FakeSymbolInfo()

        def order_send(self, request):
            return FakeResult()

        def shutdown(self):
            pass

    fake = FakeMT5()
    monkeypatch.setattr(orders, "get_mt5_connection", lambda creds=None: (fake, None))
    import sys
    monkeypatch.setitem(sys.modules, "MetaTrader5", fake)

    result = orders.place_stop_order(
        "XAUUSD",
        "BUY",
        0.01,
        100.5,
        comment="SWG-setup-token",
        return_status=True,
    )

    assert result[0] is True
    assert result[2] == 888889
    assert result[3] == "submitted"


def test_place_stop_order_marks_missing_response_as_unknown(monkeypatch):
    class FakeSymbolInfo:
        visible = True

    class FakeMT5:
        TRADE_RETCODE_DONE = 10009
        TRADE_RETCODE_PLACED = 10008
        ORDER_TYPE_BUY_STOP = 4
        TRADE_ACTION_PENDING = 5
        ORDER_TIME_GTC = 0
        ORDER_FILLING_RETURN = 2

        def symbol_info(self, symbol):
            return FakeSymbolInfo()

        def order_send(self, request):
            return None

        def shutdown(self):
            pass

    fake = FakeMT5()
    monkeypatch.setattr(orders, "get_mt5_connection", lambda creds=None: (fake, None))
    import sys
    monkeypatch.setitem(sys.modules, "MetaTrader5", fake)

    result = orders.place_stop_order(
        "XAUUSD",
        "BUY",
        0.01,
        100.5,
        return_status=True,
    )

    assert result[0] is False
    assert result[3] == "unknown"


def test_modify_position_sl_tp_updates_live_position(monkeypatch):
    class FakeResult:
        retcode = 10009
        comment = "done"

    class FakeMT5:
        TRADE_ACTION_SLTP = 6
        TRADE_RETCODE_DONE = 10009

        def order_send(self, request):
            assert request == {
                "action": self.TRADE_ACTION_SLTP,
                "position": 777,
                "sl": 99.0,
                "tp": 112.0,
            }
            return FakeResult()

        def shutdown(self):
            pass

    fake = FakeMT5()
    monkeypatch.setattr(orders, "get_mt5_connection", lambda creds=None: (fake, None))
    import sys
    monkeypatch.setitem(sys.modules, "MetaTrader5", fake)

    success, message = orders.modify_position_sl_tp(777, 99.0, 112.0)

    assert success is True
    assert "updated" in message.lower()
