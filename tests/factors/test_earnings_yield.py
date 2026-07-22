from __future__ import annotations

import numpy as np
import pandas as pd

from src.factors.base import BaseFactor
from src.factors.earnings_yield import EarningsYieldFactor
from src.factors.registry import DEFAULT_FACTOR_REGISTRY


class DailyBasicDataManager:
    def __init__(self, data):
        self.data = data
        self.calls = []

    def get_daily_basic(self, start, end, ts_codes=None):
        self.calls.append({"start": start, "end": end, "ts_codes": ts_codes})
        return self.data.copy()


def test_earnings_yield_registration_and_base_factor_interface():
    assert DEFAULT_FACTOR_REGISTRY.get("earnings_yield") is EarningsYieldFactor
    assert issubclass(EarningsYieldFactor, BaseFactor)


def test_earnings_yield_formula_null_zero_negative_and_no_infinity():
    data = pd.DataFrame([
        {"trade_date": "2024-01-02", "ts_code": "000004.SZ", "pe_ttm": -5.0},
        {"trade_date": "2024-01-02", "ts_code": "000002.SZ", "pe_ttm": np.nan},
        {"trade_date": "2024-01-02", "ts_code": "000001.SZ", "pe_ttm": 10.0},
        {"trade_date": "2024-01-02", "ts_code": "000003.SZ", "pe_ttm": 0.0},
    ])

    result = EarningsYieldFactor(DailyBasicDataManager(data)).build(
        "2024-01-01",
        "2024-01-31",
    ).set_index("ts_code")

    assert result.loc["000001.SZ", "factor_value"] == 0.1
    assert pd.isna(result.loc["000002.SZ", "factor_value"])
    assert pd.isna(result.loc["000003.SZ", "factor_value"])
    assert result.loc["000004.SZ", "factor_value"] == -0.2
    values = result["factor_value"].dropna().to_numpy(dtype=float)
    assert not np.isinf(values).any()


def test_earnings_yield_forwards_universe_and_sorts_unique_output():
    data = pd.DataFrame([
        {"trade_date": "2024-01-03", "ts_code": "000002.SZ", "pe_ttm": 20.0},
        {"trade_date": "2024-01-02", "ts_code": "000002.SZ", "pe_ttm": 25.0},
        {"trade_date": "2024-01-02", "ts_code": "000001.SZ", "pe_ttm": 10.0},
    ])
    dm = DailyBasicDataManager(data)
    universe = ["000001.SZ", "000002.SZ"]

    result = EarningsYieldFactor(dm).build(
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
    assert result.loc[result["ts_code"] == "000002.SZ", "factor_value"].tolist() == [
        0.04,
        0.05,
    ]


def test_earnings_yield_empty_input_returns_standard_empty_frame():
    result = EarningsYieldFactor(DailyBasicDataManager(pd.DataFrame())).build(
        "2024-01-01",
        "2024-01-31",
    )

    assert result.empty
    assert list(result.columns) == ["trade_date", "ts_code", "factor_value"]
