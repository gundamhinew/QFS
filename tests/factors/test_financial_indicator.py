from __future__ import annotations

import pandas as pd
import pytest

import src.factors.financial_indicator as financial_indicator_module
from src.datahub.point_in_time import align_fina_indicator_to_universe
from src.factors.base import BaseFactor
from src.factors.financial_indicator import FinancialIndicatorFactor
from src.factors.registry import DEFAULT_FACTOR_REGISTRY


class FinancialDataManager:
    def __init__(self, daily_price, financial):
        self.daily_price = daily_price
        self.financial = financial
        self.daily_calls = []
        self.financial_calls = []

    def get_daily_price(self, start, end, ts_codes=None):
        self.daily_calls.append({"start": start, "end": end, "ts_codes": ts_codes})
        return self.daily_price.copy()

    def get_fina_indicator(self, start=None, end=None, ts_codes=None, fields=None):
        self.financial_calls.append({
            "start": start,
            "end": end,
            "ts_codes": ts_codes,
            "fields": fields,
        })
        return self.financial.copy()


def _daily_price():
    dates = [
        "2024-04-01",
        "2024-04-02",
        "2024-04-03",
        "2024-04-08",
        "2024-04-09",
    ]
    return pd.DataFrame([
        {"trade_date": date, "ts_code": ts_code, "close": 10.0}
        for date in reversed(dates)
        for ts_code in ["000002.SZ", "000001.SZ"]
    ])


def _financial_data():
    return pd.DataFrame([
        {
            "ts_code": "000001.SZ",
            "ann_date": "2024-04-02",
            "end_date": "2023-12-31",
            "roe_yearly": 10.0,
            "netprofit_yoy": 100.0,
        },
        {
            "ts_code": "000001.SZ",
            "ann_date": "2024-04-06",
            "end_date": "2023-12-31",
            "roe_yearly": 11.0,
            "netprofit_yoy": 110.0,
        },
        {
            "ts_code": "000001.SZ",
            "ann_date": "2024-04-08",
            "end_date": "2024-03-31",
            "roe_yearly": 20.0,
            "netprofit_yoy": 200.0,
        },
        {
            "ts_code": "000002.SZ",
            "ann_date": "2024-04-01",
            "end_date": "2023-12-31",
            "roe_yearly": 30.0,
            "netprofit_yoy": 300.0,
        },
    ])


def _build(field, daily_price=None, financial=None, universe=None):
    dm = FinancialDataManager(
        _daily_price() if daily_price is None else daily_price,
        _financial_data() if financial is None else financial,
    )
    result = FinancialIndicatorFactor(
        dm=dm,
        params={"indicator_field": field},
    ).build(
        start="2024-04-01",
        end="2024-04-09",
        universe=universe,
    )
    return result, dm


def test_financial_indicator_registration_and_base_factor_interface():
    assert (
        DEFAULT_FACTOR_REGISTRY.get("financial_indicator")
        is FinancialIndicatorFactor
    )
    assert issubclass(FinancialIndicatorFactor, BaseFactor)


@pytest.mark.parametrize(
    ("field", "expected"),
    [
        ("roe_yearly", 10.0),
        ("netprofit_yoy", 100.0),
    ],
)
def test_financial_indicator_outputs_configured_field(field, expected):
    result, _ = _build(field)
    selected = result[
        (result["trade_date"] == pd.Timestamp("2024-04-03"))
        & (result["ts_code"] == "000001.SZ")
    ]

    assert selected["factor_value"].iloc[0] == expected


def test_financial_indicator_requires_supported_indicator_field():
    dm = FinancialDataManager(_daily_price(), _financial_data())

    with pytest.raises(ValueError, match="indicator_field is required"):
        FinancialIndicatorFactor(dm=dm).build("2024-04-01", "2024-04-09")
    with pytest.raises(ValueError, match="Unsupported indicator_field"):
        FinancialIndicatorFactor(
            dm=dm,
            params={"indicator_field": "gross_margin"},
        ).build("2024-04-01", "2024-04-09")


def test_financial_indicator_calls_existing_point_in_time_alignment(monkeypatch):
    calls = []

    def recording_alignment(financial_df, universe_df, fields):
        calls.append({
            "financial_rows": len(financial_df),
            "universe_rows": len(universe_df),
            "fields": fields,
        })
        return align_fina_indicator_to_universe(financial_df, universe_df, fields)

    monkeypatch.setattr(
        financial_indicator_module,
        "align_fina_indicator_to_universe",
        recording_alignment,
    )

    _build("roe_yearly")

    assert calls == [{
        "financial_rows": 4,
        "universe_rows": 10,
        "fields": ["roe_yearly"],
    }]


def test_financial_indicator_obeys_announcement_revision_and_carry_rules():
    result, _ = _build("roe_yearly")
    stock_a = result[result["ts_code"] == "000001.SZ"].set_index("trade_date")
    stock_b = result[result["ts_code"] == "000002.SZ"].set_index("trade_date")

    assert pd.isna(stock_a.loc["2024-04-01", "factor_value"])
    assert pd.isna(stock_a.loc["2024-04-02", "factor_value"])
    assert stock_a.loc["2024-04-03", "factor_value"] == 10.0
    assert stock_a.loc["2024-04-08", "factor_value"] == 11.0
    assert stock_a.loc["2024-04-09", "factor_value"] == 20.0

    assert pd.isna(stock_b.loc["2024-04-01", "factor_value"])
    assert stock_b.loc["2024-04-02", "factor_value"] == 30.0
    assert stock_b.loc["2024-04-09", "factor_value"] == 30.0


def test_financial_indicator_forwards_universe_to_both_data_reads():
    universe = ["000001.SZ", "000002.SZ"]
    _, dm = _build("roe_yearly", universe=universe)

    assert dm.daily_calls == [{
        "start": "2024-04-01",
        "end": "2024-04-09",
        "ts_codes": universe,
    }]
    assert dm.financial_calls == [{
        "start": None,
        "end": "2024-04-09",
        "ts_codes": universe,
        "fields": ["roe_yearly"],
    }]


def test_financial_indicator_filters_range_and_returns_unique_sorted_output():
    daily = pd.concat([
        _daily_price(),
        pd.DataFrame([
            {"trade_date": "2024-03-29", "ts_code": "000001.SZ", "close": 9.0},
            {"trade_date": "2024-04-10", "ts_code": "000001.SZ", "close": 11.0},
        ]),
    ], ignore_index=True)

    result, _ = _build("roe_yearly", daily_price=daily)

    assert result["trade_date"].between(
        pd.Timestamp("2024-04-01"),
        pd.Timestamp("2024-04-09"),
        inclusive="both",
    ).all()
    assert not result.duplicated(["trade_date", "ts_code"]).any()
    assert result.equals(
        result.sort_values(["trade_date", "ts_code"], kind="stable")
        .reset_index(drop=True)
    )


def test_financial_indicator_empty_daily_input_returns_standard_empty_frame():
    result, dm = _build(
        "roe_yearly",
        daily_price=pd.DataFrame(),
    )

    assert result.empty
    assert list(result.columns) == ["trade_date", "ts_code", "factor_value"]
    assert dm.financial_calls == []


def test_financial_indicator_empty_financial_input_preserves_universe_with_nan():
    result, _ = _build(
        "roe_yearly",
        financial=pd.DataFrame(),
    )

    assert len(result) == len(_daily_price())
    assert result["factor_value"].isna().all()
