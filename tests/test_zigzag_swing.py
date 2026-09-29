import pandas as pd

from src.zigzag_swing import detect_confirmed_pivots


def test_detect_confirmed_pivots_waits_for_right_side_confirmation():
    data = pd.DataFrame(
        {
            "high": [10, 12, 15, 13, 11, 12, 16, 14, 13, 15, 18, 17],
            "low": [8, 9, 10, 7, 6, 7, 9, 8, 5, 6, 10, 11],
        }
    )

    pivots = detect_confirmed_pivots(
        data,
        point_size=0.1,
        depth=2,
        deviation_points=3,
        back_step=2,
    )

    assert pivots == [
        {"index": 2, "kind": "high", "price": 15.0, "confirmed_index": 4},
        {"index": 4, "kind": "low", "price": 6.0, "confirmed_index": 6},
        {"index": 6, "kind": "high", "price": 16.0, "confirmed_index": 8},
        {"index": 8, "kind": "low", "price": 5.0, "confirmed_index": 10},
    ]
    assert all(pivot["confirmed_index"] > pivot["index"] for pivot in pivots)
    assert all(pivot["index"] != 10 for pivot in pivots)


def test_detect_confirmed_pivots_does_not_replace_confirmed_history():
    data = pd.DataFrame(
        {
            "high": [10, 11, 14, 13, 15, 12, 9],
            "low": [8, 9, 10, 10.5, 10.7, 10, 9],
        }
    )

    pivots = detect_confirmed_pivots(
        data,
        point_size=0.1,
        depth=1,
        deviation_points=0,
        back_step=3,
    )

    assert pivots[0] == {
        "index": 2,
        "kind": "high",
        "price": 14.0,
        "confirmed_index": 3,
    }


def test_detect_confirmed_pivots_stays_stable_when_more_bars_arrive():
    full_data = pd.DataFrame(
        {
            "high": [10, 11, 15, 13, 12, 11, 10, 11, 12, 13, 17, 14, 12],
            "low": [8, 9, 10, 9.5, 9.2, 9.0, 8.8, 8.9, 9.1, 9.4, 10.5, 10.0, 9.7],
        }
    )

    early_pivots = detect_confirmed_pivots(
        full_data.iloc[:5],
        point_size=0.1,
        depth=1,
        deviation_points=10,
        back_step=1,
    )
    full_pivots = detect_confirmed_pivots(
        full_data,
        point_size=0.1,
        depth=1,
        deviation_points=10,
        back_step=1,
    )

    assert early_pivots == [
        {"index": 2, "kind": "high", "price": 15.0, "confirmed_index": 3}
    ]
    assert full_pivots[0] == early_pivots[0]


def test_detect_confirmed_pivots_uses_back_step_to_allow_later_same_side_pivots():
    data = pd.DataFrame(
        {
            "high": [10, 11, 14, 13, 15, 12, 11, 16, 13],
            "low": [8, 9, 10, 11, 12, 13, 14, 15, 16],
        }
    )

    tight_back_step = detect_confirmed_pivots(
        data,
        point_size=0.1,
        depth=1,
        deviation_points=0,
        back_step=1,
    )
    wide_back_step = detect_confirmed_pivots(
        data,
        point_size=0.1,
        depth=1,
        deviation_points=0,
        back_step=10,
    )

    assert [pivot["index"] for pivot in tight_back_step] == [2, 4, 7]
    assert [pivot["index"] for pivot in wide_back_step] == [2]
