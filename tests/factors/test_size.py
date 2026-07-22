from __future__ import annotations

import numpy as np
import pandas as pd

from src.factors.base import BaseFactor
from src.factors.registry import DEFAULT_FACTOR_REGISTRY
from src.factors.size import SizeFactor


class DailyBasicDataManager:
    def __init__(self, data):
        self.data = data
        self.calls = []

    def get_daily_basic(self, start, end, ts_codes=None):
        self.calls.append({"start": start, "end": end, "ts_codes": ts_codes})
        return self.data.copy()


def test_size_registration_and_base_factor_interface():
    assert DEFAULT_FACTOR_REGISTRY.get("size") is SizeFactor
    assert issubclass(SizeFactor, BaseFactor)


def test_size_formula_and_invalid_market_values():
    data = pd.DataFrame([
        {"trade_date": "2024-01-02", "ts_code": "000004.SZ", "total_mv": -1.0},
        {"trade_date": "2024-01-02", "ts_code": "000002.SZ", "total_mv": np.nan},
        {"trade_date": "2024-01-02", "ts_code": "000001.SZ", "total_mv": 100.0},
        {"trade_date": "2024-01-02", "ts_code": "000003.SZ", "total_mv": 0.0},
    ])

    result = SizeFactor(DailyBasicDataManager(data)).build(
        "2024-01-01",
        "2024-01-31",
    ).set_index("ts_code")

    assert result.loc["000001.SZ", "factor_value"] == np.log(100.0)
    assert pd.isna(result.loc["000002.SZ", "factor_value"])
    assert pd.isna(result.loc["000003.SZ", "factor_value"])
    assert pd.isna(result.loc["000004.SZ", "factor_value"])


def test_size_forwards_universe_and_sorts_unique_output():
    data = pd.DataFrame([
        {"trade_date": "2024-01-03", "ts_code": "000002.SZ", "total_mv": 400.0},
        {"trade_date": "2024-01-02", "ts_code": "000002.SZ", "total_mv": 200.0},
        {"trade_date": "2024-01-02", "ts_code": "000001.SZ", "total_mv": 100.0},
    ])
    dm = DailyBasicDataManager(data)
    universe = ["000001.SZ", "000002.SZ"]

    result = SizeFactor(dm).build(
        "2024-01-01",
        "2024-01-31",
        universe=universe,
    )

    assert dm.calls == [{
        "start": "2024-01-01",
        "end": "2024-01-31",
        "ts_codes": universe,
    }]
    assert result.equals(
        result.sort_values(["trade_date", "ts_code"], kind="stable")
        .reset_index(drop=True)
    )
    assert not result.duplicated(["trade_date", "ts_code"]).any()


def test_size_empty_input_returns_standard_empty_frame():
    result = SizeFactor(DailyBasicDataManager(pd.DataFrame())).build(
        "2024-01-01",
        "2024-01-31",
    )

    assert result.empty
    assert list(result.columns) == ["trade_date", "ts_code", "factor_value"]
