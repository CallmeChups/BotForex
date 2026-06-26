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
