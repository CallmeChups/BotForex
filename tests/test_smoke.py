def test_can_import_src_utils():
    from src.utils import get_pip_value
    assert get_pip_value("XAUUSD") == 0.1
    assert get_pip_value("BTCUSD") == 1.0
    assert get_pip_value("EURUSD") == 0.0001
