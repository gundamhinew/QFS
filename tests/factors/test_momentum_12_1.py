from __future__ import annotations

import pandas as pd
import pytest

from src.factors.base import BaseFactor
from src.factors.momentum_12_1 import Momentum121Factor
from src.factors.registry import DEFAULT_FACTOR_REGISTRY


class RecordingDataManager:
    def __init__(self, price: pd.DataFrame):
        self.price = price
        self.calls = []

    def get_adjusted_price(
        self,
        start,
        end,
        ts_codes=None,
        price_cols=None,
        adjust="total_return",
    ):
        self.calls.append({
            "start": start,
            "end": end,
            "ts_codes": ts_codes,
            "adjust": adjust,
        })
        result = self.price.copy()
        if result.empty:
            return result
        dates = pd.to_datetime(result["trade_date"])
        result = result[
            dates.between(pd.Timestamp(start), pd.Timestamp(end), inclusive="both")
        ]
        if ts_codes is not None:
            result = result[result["ts_code"].isin(ts_codes)]
        return result.reset_index(drop=True)


def _price_frame(include_future: bool = False) -> pd.DataFrame:
    dates = pd.bdate_range("2023-01-02", periods=256)
    rows = []
    for index, trade_date in enumerate(dates):
        rows.extend([
            {
                "trade_date": trade_date,
                "ts_code": "000001.SZ",
                "adj_close": 10.0 + index,
            },
            {
                "trade_date": trade_date,
                "ts_code": "000002.SZ",
                "adj_close": 100.0 + 2 * index,
            },
        ])
    if include_future:
        rows.append({
            "trade_date": dates[-1] + pd.offsets.BDay(1),
            "ts_code": "000001.SZ",
            "adj_close": 1_000_000.0,
        })
    return pd.DataFrame(rows)


def _default_factor(dm, params=None):
    return Momentum121Factor(dm=dm, params=params)


def test_momentum_12_1_is_registered_and_implements_base_factor():
    assert DEFAULT_FACTOR_REGISTRY.get("momentum_12_1") is Momentum121Factor
    assert issubclass(Momentum121Factor, BaseFactor)
    assert Momentum121Factor.factor_name == "momentum_12_1"


def test_momentum_12_1_formula_uses_shift_21_and_shift_252_per_stock():
    price = _price_frame().sample(frac=1.0, random_state=7).reset_index(drop=True)
    dates = sorted(pd.to_datetime(price["trade_date"].unique()))
    start = dates[252]
    end = dates[254]
    dm = RecordingDataManager(price)

    result = _default_factor(dm).build(
        start=start.strftime("%Y-%m-%d"),
        end=end.strftime("%Y-%m-%d"),
        universe=["000001.SZ", "000002.SZ"],
    )
    first_day = result[result["trade_date"] == start].set_index("ts_code")

    assert first_day.loc["000001.SZ", "factor_value"] == pytest.approx(
        (10.0 + 231) / (10.0 + 0) - 1
    )
    assert first_day.loc["000002.SZ", "factor_value"] == pytest.approx(
        (100.0 + 2 * 231) / (100.0 + 2 * 0) - 1
    )
    assert set(result["factor_name"]) == {"momentum_12_1"}


def test_momentum_12_1_extends_history_and_forwards_universe():
    price = _price_frame()
    dates = sorted(pd.to_datetime(price["trade_date"].unique()))
    start = pd.Timestamp(dates[252])
    end = pd.Timestamp(dates[254])
    universe = ["000001.SZ"]
    dm = RecordingDataManager(price)

    _default_factor(dm).build(
        start=start.strftime("%Y-%m-%d"),
        end=end.strftime("%Y-%m-%d"),
        universe=universe,
    )

    assert dm.calls == [{
        "start": (start - pd.Timedelta(days=450)).strftime("%Y-%m-%d"),
        "end": end.strftime("%Y-%m-%d"),
        "ts_codes": universe,
        "adjust": "total_return",
    }]


def test_momentum_12_1_output_range_sorting_and_unique_keys():
    price = _price_frame().sample(frac=1.0, random_state=11).reset_index(drop=True)
    dates = sorted(pd.to_datetime(price["trade_date"].unique()))
    start = pd.Timestamp(dates[252])
    end = pd.Timestamp(dates[255])

    result = _default_factor(RecordingDataManager(price)).build(
        start=start.strftime("%Y-%m-%d"),
        end=end.strftime("%Y-%m-%d"),
    )

    assert list(result.columns) == [
        "trade_date", "ts_code", "factor_name", "factor_value"
    ]
    assert result["trade_date"].between(start, end, inclusive="both").all()
    assert not result.duplicated(["trade_date", "ts_code"]).any()
    assert result.equals(
        result.sort_values(["trade_date", "ts_code"], kind="stable")
        .reset_index(drop=True)
    )


def test_momentum_12_1_keeps_nan_when_history_is_insufficient():
    price = _price_frame().iloc[:40].copy()
    start = pd.to_datetime(price["trade_date"]).min()
    end = pd.to_datetime(price["trade_date"]).max()

    result = _default_factor(RecordingDataManager(price)).build(
        start=start.strftime("%Y-%m-%d"),
        end=end.strftime("%Y-%m-%d"),
    )

    assert result["factor_value"].isna().all()


def test_momentum_12_1_empty_input_has_stable_schema():
    result = _default_factor(RecordingDataManager(pd.DataFrame())).build(
        start="2024-01-01",
        end="2024-01-31",
        universe=["000001.SZ"],
    )

    assert result.empty
    assert list(result.columns) == [
        "trade_date", "ts_code", "factor_name", "factor_value"
    ]


@pytest.mark.parametrize(
    "params, message",
    [
        ({"lookback_trading_days": True}, "lookback_trading_days"),
        ({"lookback_trading_days": 252.0}, "lookback_trading_days"),
        ({"skip_recent_trading_days": 0}, "skip_recent_trading_days"),
        ({"skip_recent_trading_days": True}, "skip_recent_trading_days"),
        (
            {"lookback_trading_days": 21, "skip_recent_trading_days": 21},
            "lookback_trading_days",
        ),
        ({"history_buffer_calendar_days": 0}, "history_buffer_calendar_days"),
        ({"history_buffer_calendar_days": False}, "history_buffer_calendar_days"),
    ],
)
def test_momentum_12_1_rejects_invalid_parameters(params, message):
    with pytest.raises(ValueError, match=message):
        _default_factor(RecordingDataManager(pd.DataFrame()), params=params).build(
            start="2024-01-01",
            end="2024-12-31",
        )


def test_momentum_12_1_does_not_use_prices_after_end_date():
    base_price = _price_frame(include_future=False)
    future_price = _price_frame(include_future=True)
    dates = sorted(pd.to_datetime(base_price["trade_date"].unique()))
    start = pd.Timestamp(dates[252])
    end = pd.Timestamp(dates[255])

    base_result = _default_factor(RecordingDataManager(base_price)).build(
        start=start.strftime("%Y-%m-%d"),
        end=end.strftime("%Y-%m-%d"),
    )
    future_result = _default_factor(RecordingDataManager(future_price)).build(
        start=start.strftime("%Y-%m-%d"),
        end=end.strftime("%Y-%m-%d"),
    )

    pd.testing.assert_frame_equal(base_result, future_result)
