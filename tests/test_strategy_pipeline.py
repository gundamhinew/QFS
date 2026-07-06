from __future__ import annotations

import pandas as pd
import pytest

from src.portfolio.top_n_equal_weight import TopNEqualWeightPortfolio
from src.risk.basic import BasicWeightConstraint
from src.strategies.pipeline import StrategyPipeline
from src.strategies.rebalance_policy import RebalancePolicy
from src.timing.noop import NoOpTiming


def _model_scores() -> pd.DataFrame:
    rows = []
    for date in pd.to_datetime(["2020-01-01", "2020-01-02", "2020-01-31", "2020-02-03"]):
        for idx, score in enumerate([3.0, 2.0, 1.0]):
            rows.append({
                "trade_date": date,
                "ts_code": f"00000{idx + 1}.SZ",
                "model_id": "unit_model",
                "model_score": score,
                "factor_count": 1,
                "missing_factor_count": 0,
            })
    return pd.DataFrame(rows)


def _strategy_config(frequency: str = "daily") -> dict:
    return {
        "strategy_id": "unit_strategy",
        "rebalance": {"frequency": frequency},
        "portfolio": {
            "type": "top_n_equal_weight",
            "params": {
                "top_n": 2,
                "max_single_weight": 0.6,
                "normalize_weights": True,
            },
        },
        "timing": {"type": "noop"},
        "risk": {
            "type": "basic_weight_constraint",
            "max_single_weight": 0.6,
            "normalize_weights": True,
        },
    }


def test_top_n_selection_equal_weight_and_max_single_weight():
    result = TopNEqualWeightPortfolio().build(
        _model_scores(),
        {
            "params": {
                "top_n": 2,
                "max_single_weight": 0.6,
                "normalize_weights": True,
            }
        },
    )

    first_day = result[result["trade_date"] == pd.Timestamp("2020-01-01")]
    assert first_day["ts_code"].tolist() == ["000001.SZ", "000002.SZ"]
    assert first_day["raw_target_weight"].tolist() == pytest.approx([0.5, 0.5])
    assert first_day["raw_target_weight"].max() <= 0.6


def test_rebalance_policy_daily_weekly_monthly():
    scores = _model_scores()

    assert len(RebalancePolicy("daily").filter_model_scores(scores)["trade_date"].unique()) == 4
    weekly_dates = RebalancePolicy("weekly").filter_model_scores(scores)["trade_date"].drop_duplicates().tolist()
    monthly_dates = RebalancePolicy("monthly").filter_model_scores(scores)["trade_date"].drop_duplicates().tolist()

    assert weekly_dates == [pd.Timestamp("2020-01-02"), pd.Timestamp("2020-01-31"), pd.Timestamp("2020-02-03")]
    assert monthly_dates == [pd.Timestamp("2020-01-31"), pd.Timestamp("2020-02-03")]


def test_noop_timing_sets_full_exposure():
    weights = pd.DataFrame({
        "trade_date": [pd.Timestamp("2020-01-01")],
        "ts_code": ["000001.SZ"],
        "raw_target_weight": [1.0],
        "strategy_id": ["unit_strategy"],
    })

    result = NoOpTiming().apply(weights)

    assert result["exposure"].iloc[0] == 1.0


def test_basic_weight_constraint_nonnegative_cap_and_exposure():
    weights = pd.DataFrame({
        "trade_date": [pd.Timestamp("2020-01-01"), pd.Timestamp("2020-01-01")],
        "ts_code": ["000001.SZ", "000002.SZ"],
        "raw_target_weight": [0.8, 0.4],
        "strategy_id": ["unit_strategy", "unit_strategy"],
        "exposure": [1.0, 1.0],
    })

    result = BasicWeightConstraint().apply(
        weights,
        {"max_single_weight": 0.6, "normalize_weights": True},
    )

    assert result["target_weight"].max() <= 0.6
    assert result["target_weight"].sum() <= 1.0 + 1e-9

    bad = weights.copy()
    bad.loc[0, "raw_target_weight"] = -0.1
    with pytest.raises(ValueError, match="non-negative"):
        BasicWeightConstraint().apply(bad, {})


def test_strategy_pipeline_target_positions_validation_daily_and_monthly():
    daily = StrategyPipeline().build_target_positions(
        _model_scores(),
        _strategy_config("daily"),
    )
    monthly = StrategyPipeline().build_target_positions(
        _model_scores(),
        _strategy_config("monthly"),
    )

    assert {"trade_date", "ts_code", "target_weight", "strategy_id"}.issubset(daily.columns)
    assert daily["strategy_id"].unique().tolist() == ["unit_strategy"]
    assert len(daily["trade_date"].drop_duplicates()) == 4
    assert monthly["trade_date"].drop_duplicates().tolist() == [
        pd.Timestamp("2020-01-31"),
        pd.Timestamp("2020-02-03"),
    ]


def test_single_and_multi_factor_models_share_strategy_pipeline():
    single_targets = StrategyPipeline().build_target_positions(
        _model_scores(),
        _strategy_config("daily"),
    )
    multi_scores = _model_scores().copy()
    multi_scores["model_id"] = "multi_model"
    multi_targets = StrategyPipeline().build_target_positions(
        multi_scores,
        _strategy_config("daily"),
    )

    assert not single_targets.empty
    assert not multi_targets.empty
    assert list(single_targets.columns) == list(multi_targets.columns)
