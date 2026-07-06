from __future__ import annotations

import pandas as pd
import pytest

from src.alpha_models.aligner import FactorAligner
from src.alpha_models.category_weighted import CategoryWeightedAlphaModel
from src.alpha_models.equal_weight import EqualWeightAlphaModel
from src.alpha_models.single_factor import SingleFactorAlphaModel
from src.alpha_models.weighted_score import WeightedScoreAlphaModel, normalize_weights
from src.contracts.model_frames import validate_model_score_frame


def _factor(alias: str, missing: bool = False) -> pd.DataFrame:
    rows = [
        {
            "trade_date": "2020-01-01",
            "ts_code": "000001.SZ",
            "factor_id": alias,
            "raw_value": 1.0,
            "factor_score": 1.0,
        },
        {
            "trade_date": "2020-01-01",
            "ts_code": "000002.SZ",
            "factor_id": alias,
            "raw_value": 2.0,
            "factor_score": 2.0,
        },
    ]
    if missing:
        rows = rows[:1]
    return pd.DataFrame(rows)


def _config(model_type: str = "weighted_score") -> dict:
    return {
        "model_id": "unit_model",
        "model_type": model_type,
        "factors": [
            {"factor_id": "factor_a", "alias": "factor_a", "weight": 2.0},
            {"factor_id": "factor_b", "alias": "factor_b", "weight": 1.0},
        ],
        "alignment": {"missing_policy": "intersection", "min_factor_count": 1},
    }


def test_aligner_intersection_fill_zero_renormalize_and_min_factor_count():
    factors = {
        "factor_a": _factor("factor_a"),
        "factor_b": _factor("factor_b", missing=True),
    }
    aligner = FactorAligner()

    intersection = aligner.align(factors, missing_policy="intersection")
    assert intersection.shape[0] == 1
    assert intersection["missing_factor_count"].iloc[0] == 0

    fill_zero = aligner.align(factors, missing_policy="fill_zero", min_factor_count=1)
    assert fill_zero.shape[0] == 2
    assert fill_zero.loc[fill_zero["ts_code"] == "000002.SZ", "factor_b"].iloc[0] == 0

    renormalize = aligner.align(factors, missing_policy="renormalize", min_factor_count=1)
    assert renormalize.shape[0] == 2
    assert renormalize["missing_factor_count"].max() == 1

    with pytest.raises(ValueError, match="removed all rows"):
        aligner.align(factors, missing_policy="fill_zero", min_factor_count=3)


def test_single_factor_alpha_model_and_model_score_validation():
    config = {
        "model_id": "single",
        "model_type": "single_factor",
        "factors": [{"factor_id": "factor_a", "alias": "factor_a"}],
    }

    result = SingleFactorAlphaModel().build(
        {"factor_a": _factor("factor_a")},
        config,
    )

    assert result["model_score"].tolist() == [1.0, 2.0]
    validate_model_score_frame(result)


def test_equal_weight_alpha_model():
    config = _config("equal_weight")
    factors = {
        "factor_a": _factor("factor_a"),
        "factor_b": _factor("factor_b"),
    }

    result = EqualWeightAlphaModel().build(factors, config)

    assert result["model_score"].tolist() == [1.0, 2.0]


def test_weighted_score_alpha_model_normalizes_weights_and_contributions():
    config = _config("weighted_score")
    factors = {
        "factor_a": _factor("factor_a"),
        "factor_b": _factor("factor_b"),
    }

    result = WeightedScoreAlphaModel().build(factors, config)

    assert normalize_weights({"a": 2, "b": 1}) == pytest.approx({"a": 2 / 3, "b": 1 / 3})
    assert result["model_score"].tolist() == pytest.approx([1.0, 2.0])
    assert "contribution_factor_a" in result.columns
    assert "contribution_factor_b" in result.columns

    bad = _config("weighted_score")
    bad["factors"][0]["weight"] = 1
    bad["factors"][1]["weight"] = -1
    with pytest.raises(ValueError, match="weight sum"):
        WeightedScoreAlphaModel().build(factors, bad)


def test_weighted_score_renormalize_uses_available_factor_weights():
    config = _config("weighted_score")
    config["alignment"] = {"missing_policy": "renormalize", "min_factor_count": 1}
    factors = {
        "factor_a": _factor("factor_a"),
        "factor_b": _factor("factor_b", missing=True),
    }

    result = WeightedScoreAlphaModel().build(factors, config)
    second = result[result["ts_code"] == "000002.SZ"].iloc[0]

    assert second["model_score"] == pytest.approx(2.0)
    assert second["missing_factor_count"] == 1


def test_category_weighted_alpha_model_avoids_factor_count_amplification():
    config = {
        "model_id": "category_model",
        "model_type": "category_weighted",
        "factors": [
            {"factor_id": "factor_a", "alias": "factor_a"},
            {"factor_id": "factor_b", "alias": "factor_b"},
            {"factor_id": "factor_c", "alias": "factor_c"},
        ],
        "categories": {
            "momentum": {"weight": 1.0, "factors": ["factor_a", "factor_b"]},
            "quality": {"weight": 1.0, "factors": ["factor_c"]},
        },
        "alignment": {"missing_policy": "intersection", "min_factor_count": 1},
    }
    factors = {
        "factor_a": _factor("factor_a"),
        "factor_b": _factor("factor_b"),
        "factor_c": _factor("factor_c"),
    }

    result = CategoryWeightedAlphaModel().build(factors, config)

    assert result["model_score"].tolist() == pytest.approx([1.0, 2.0])
    assert "contribution_factor_c" in result.columns
