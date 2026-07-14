from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.factors.evaluator import FactorEvaluator
from src.factors.forward_returns import calculate_forward_returns
from src.factors.quantile_analysis import (
    assign_quantiles,
    calculate_quantile_returns,
    calculate_quantile_turnover,
    calculate_top_bottom_spread,
)


def test_forward_returns_close_to_future_close_and_tail_missing():
    price = pd.DataFrame({
        "trade_date": pd.date_range("2020-01-01", periods=3),
        "ts_code": ["000001.SZ"] * 3,
        "close": [10.0, 11.0, 12.1],
    })

    result = calculate_forward_returns(price, periods=[1, 2])

    assert result.loc[0, "forward_return_1d"] == pytest.approx(0.1)
    assert result.loc[0, "forward_return_2d"] == pytest.approx(0.21)
    assert pd.isna(result.loc[2, "forward_return_1d"])


def _processed_and_returns() -> tuple[pd.DataFrame, pd.DataFrame]:
    dates = pd.to_datetime(["2020-01-01", "2020-01-02"])
    rows = []
    returns = []

    for date in dates:
        for i in range(10):
            code = f"{i:06d}.SZ"
            score = float(i)
            rows.append({
                "trade_date": date,
                "ts_code": code,
                "factor_id": "unit_factor",
                "raw_value": score,
                "factor_score": score,
            })
            returns.append({
                "trade_date": date,
                "ts_code": code,
                "forward_return_1d": score / 100,
                "forward_return_5d": score / 50,
                "forward_return_20d": -score / 100,
            })

    return pd.DataFrame(rows), pd.DataFrame(returns)


def test_factor_evaluator_ic_rank_ic_icir_and_annual_stats():
    processed, returns = _processed_and_returns()
    evaluator = FactorEvaluator(periods=[1, 5, 20], quantiles=5)

    result = evaluator.evaluate(processed, returns)

    assert result.summary["ic"]["1"]["ic_mean"] == pytest.approx(1.0)
    assert result.summary["ic"]["1"]["rank_ic_mean"] == pytest.approx(1.0)
    assert result.summary["ic"]["1"]["ic_positive_ratio"] == pytest.approx(1.0)
    assert "2020" in result.summary["annual"]["1"]
    assert result.summary["decay"]["20"] == pytest.approx(-1.0)


def test_quantile_grouping_top_bottom_and_turnover():
    processed, returns = _processed_and_returns()
    quantiled = assign_quantiles(processed, quantiles=5)
    merged = quantiled.merge(returns, on=["trade_date", "ts_code"], how="left")
    quantile_returns = calculate_quantile_returns(merged, periods=[1])
    spread = calculate_top_bottom_spread(quantile_returns)
    turnover = calculate_quantile_turnover(quantiled, quantile=5)

    assert set(quantiled["factor_quantile"].dropna()) == {1, 2, 3, 4, 5}
    assert spread["top_bottom_spread"].mean() > 0
    assert np.isnan(turnover["turnover"].iloc[0])
    assert turnover["turnover"].iloc[1] == pytest.approx(0.0)
