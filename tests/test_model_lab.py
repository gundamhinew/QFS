from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest
import yaml

from src.factor_lab.catalog import FactorCatalog
from src.model_lab.checker import ModelChecker
from src.model_lab.evaluator import ModelEvaluator


def _write_factor_config(root: Path, factor_id: str, status: str) -> Path:
    path = root / f"{factor_id}.yaml"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        yaml.safe_dump(
            {
                "schema_version": 2,
                "factor_id": factor_id,
                "implementation": "momentum",
                "version": 1,
                "status": status,
                "metadata": {},
                "data": {"raw_root": "data/raw"},
                "period": {"start": "2020-01-01", "end": "2020-01-03"},
                "universe": {},
                "params": {"lookback": 1},
                "preprocess": {},
                "evaluation": {},
                "storage": {},
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    return path


def _model_config(factor_path: Path, allow_unapproved: bool = False) -> dict:
    return {
        "schema_version": 2,
        "model_id": "unit_model",
        "model_type": "single_factor",
        "version": 1,
        "status": "research",
        "factors": [
            {
                "factor_id": "unit_factor",
                "alias": "unit_factor",
                "config": str(factor_path),
            }
        ],
        "alignment": {"missing_policy": "intersection", "min_factor_count": 1},
        "evaluation": {"allow_unapproved": allow_unapproved, "forward_periods": [1], "quantiles": 5},
        "output": {"output_root": "artifacts/model_runs"},
    }


def test_model_checker_approved_limit_and_allow_unapproved(tmp_path):
    config_root = tmp_path / "configs"
    factor_path = _write_factor_config(config_root, "unit_factor", "tested")
    catalog = FactorCatalog(config_root=config_root, artifacts_root=tmp_path / "artifacts")
    checker = ModelChecker(catalog=catalog)

    with pytest.raises(ValueError, match="Only approved"):
        checker.check(_model_config(factor_path, allow_unapproved=False))

    checker.check(_model_config(factor_path, allow_unapproved=True))


def test_model_checker_duplicate_and_missing_factor(tmp_path):
    config_root = tmp_path / "configs"
    factor_path = _write_factor_config(config_root, "unit_factor", "approved")
    catalog = FactorCatalog(config_root=config_root, artifacts_root=tmp_path / "artifacts")
    checker = ModelChecker(catalog=catalog)
    config = _model_config(factor_path, allow_unapproved=False)
    config["factors"].append(dict(config["factors"][0]))

    with pytest.raises(ValueError, match="Duplicate factor_id"):
        checker.check(config)

    config = _model_config(factor_path, allow_unapproved=False)
    config["factors"][0]["factor_id"] = "missing"
    with pytest.raises(KeyError):
        checker.check(config)


def test_model_evaluator_outputs_ic_quantiles_correlation_and_contribution():
    dates = pd.to_datetime(["2020-01-01"] * 10 + ["2020-01-02"] * 10)
    codes = [f"{i:06d}.SZ" for i in range(10)] * 2
    score = list(range(10)) * 2
    model_scores = pd.DataFrame({
        "trade_date": dates,
        "ts_code": codes,
        "model_id": "unit_model",
        "model_score": score,
        "factor_count": [1] * 20,
        "missing_factor_count": [0] * 20,
        "contribution_factor_a": score,
    })
    aligned = pd.DataFrame({
        "trade_date": dates,
        "ts_code": codes,
        "factor_a": score,
        "factor_count": [1] * 20,
        "missing_factor_count": [0] * 20,
    })
    returns = pd.DataFrame({
        "trade_date": dates,
        "ts_code": codes,
        "forward_return_1d": [x / 100 for x in score],
    })

    result = ModelEvaluator(periods=[1], quantiles=5).evaluate(
        model_scores=model_scores,
        aligned_factors=aligned,
        forward_returns=returns,
        config={
            "model_id": "unit_model",
            "model_type": "single_factor",
            "factors": [{"factor_id": "factor_a", "alias": "factor_a", "weight": 1}],
            "alignment": {"missing_policy": "intersection"},
        },
    )

    assert result.summary["model_research"]["ic"]["1"]["ic_mean"] == pytest.approx(1.0)
    assert not result.factor_correlation.empty
    assert not result.factor_contribution.empty
    assert not result.model_quantile_returns.empty
