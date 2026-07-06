from __future__ import annotations

import pandas as pd
import pytest

from src.contracts.factor_frames import (
    validate_processed_factor_frame,
    validate_raw_factor_frame,
)
from src.contracts.model_frames import validate_model_score_frame
from src.contracts.portfolio_frames import validate_target_positions


def test_validate_raw_factor_frame_success():
    df = pd.DataFrame({
        "trade_date": ["2020-01-01", "2020-01-02"],
        "ts_code": ["000001.SZ", "000002.SZ"],
        "factor_id": ["momentum", "momentum"],
        "factor_value": [0.1, None],
    })

    result = validate_raw_factor_frame(df)

    assert pd.api.types.is_datetime64_any_dtype(result["trade_date"])
    assert result["factor_value"].isna().sum() == 1


def test_validate_raw_factor_frame_missing_column_raises():
    df = pd.DataFrame({
        "trade_date": ["2020-01-01"],
        "ts_code": ["000001.SZ"],
        "factor_value": [0.1],
    })

    with pytest.raises(ValueError, match="missing required columns"):
        validate_raw_factor_frame(df)


def test_validate_raw_factor_frame_duplicate_key_raises():
    df = pd.DataFrame({
        "trade_date": ["2020-01-01", "2020-01-01"],
        "ts_code": ["000001.SZ", "000001.SZ"],
        "factor_id": ["momentum", "momentum"],
        "factor_value": [0.1, 0.2],
    })

    with pytest.raises(ValueError, match="duplicate keys"):
        validate_raw_factor_frame(df)


def test_validate_raw_factor_frame_inf_raises():
    df = pd.DataFrame({
        "trade_date": ["2020-01-01"],
        "ts_code": ["000001.SZ"],
        "factor_id": ["momentum"],
        "factor_value": [float("inf")],
    })

    with pytest.raises(ValueError, match="inf"):
        validate_raw_factor_frame(df)


def test_validate_raw_factor_frame_bad_trade_date_raises():
    df = pd.DataFrame({
        "trade_date": ["not-a-date"],
        "ts_code": ["000001.SZ"],
        "factor_id": ["momentum"],
        "factor_value": [0.1],
    })

    with pytest.raises(ValueError, match="cannot be converted"):
        validate_raw_factor_frame(df)


def test_validate_processed_factor_frame_success():
    df = pd.DataFrame({
        "trade_date": ["2020-01-01"],
        "ts_code": ["000001.SZ"],
        "factor_id": ["momentum"],
        "raw_value": [0.1],
        "factor_score": [1.2],
    })

    result = validate_processed_factor_frame(df)

    assert pd.api.types.is_datetime64_any_dtype(result["trade_date"])


def test_validate_model_score_frame_success():
    df = pd.DataFrame({
        "trade_date": ["2020-01-01"],
        "ts_code": ["000001.SZ"],
        "model_id": ["model_a"],
        "model_score": [0.5],
    })

    result = validate_model_score_frame(df)

    assert pd.api.types.is_datetime64_any_dtype(result["trade_date"])


def test_validate_target_positions_success():
    df = pd.DataFrame({
        "trade_date": ["2020-01-01", "2020-01-01"],
        "ts_code": ["000001.SZ", "000002.SZ"],
        "target_weight": [0.4, 0.6],
        "strategy_id": ["strategy_a", "strategy_a"],
    })

    result = validate_target_positions(df)

    assert pd.api.types.is_datetime64_any_dtype(result["trade_date"])


def test_validate_target_positions_negative_weight_raises():
    df = pd.DataFrame({
        "trade_date": ["2020-01-01"],
        "ts_code": ["000001.SZ"],
        "target_weight": [-0.1],
        "strategy_id": ["strategy_a"],
    })

    with pytest.raises(ValueError, match="negative"):
        validate_target_positions(df)


def test_validate_target_positions_overweight_raises():
    df = pd.DataFrame({
        "trade_date": ["2020-01-01", "2020-01-01"],
        "ts_code": ["000001.SZ", "000002.SZ"],
        "target_weight": [0.7, 0.7],
        "strategy_id": ["strategy_a", "strategy_a"],
    })

    with pytest.raises(ValueError, match="exceeds"):
        validate_target_positions(df)


def test_validate_target_positions_duplicate_stock_raises():
    df = pd.DataFrame({
        "trade_date": ["2020-01-01", "2020-01-01"],
        "ts_code": ["000001.SZ", "000001.SZ"],
        "target_weight": [0.4, 0.4],
        "strategy_id": ["strategy_a", "strategy_a"],
    })

    with pytest.raises(ValueError, match="duplicate keys"):
        validate_target_positions(df)
