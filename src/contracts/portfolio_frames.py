"""Contract for final target positions consumed by backtest execution."""

from __future__ import annotations

import numpy as np
import pandas as pd

from src.contracts.factor_frames import (
    _normalize_trade_date,
    _validate_no_duplicate_keys,
    _validate_not_empty,
    _validate_numeric_column,
    _validate_required_columns,
)


TARGET_POSITIONS_COLUMNS = [
    "trade_date",
    "ts_code",
    "target_weight",
    "strategy_id",
]


def validate_target_positions(
    df: pd.DataFrame,
    max_daily_weight: float = 1.000001,
) -> pd.DataFrame:
    """
    Validate and normalize a TargetPositions frame.

    Required columns:
        trade_date, ts_code, target_weight, strategy_id
    """

    frame_name = "TargetPositions"
    _validate_not_empty(df, frame_name)
    _validate_required_columns(df, TARGET_POSITIONS_COLUMNS, frame_name)

    result = _normalize_trade_date(df, frame_name)

    required_nan_cols = [
        "trade_date",
        "ts_code",
        "target_weight",
        "strategy_id",
    ]
    if result[required_nan_cols].isna().any().any():
        raise ValueError(
            f"{frame_name} contains NaN values in required columns"
        )

    _validate_numeric_column(
        result,
        column="target_weight",
        frame_name=frame_name,
        allow_nan=False,
    )

    result = result.copy()
    result["target_weight"] = pd.to_numeric(
        result["target_weight"],
        errors="raise",
    )

    if (result["target_weight"] < 0).any():
        raise ValueError(f"{frame_name}.target_weight contains negative values")

    values = result["target_weight"].to_numpy(dtype=float)
    if np.isinf(values).any():
        raise ValueError(f"{frame_name}.target_weight contains inf values")

    _validate_no_duplicate_keys(
        result,
        key_columns=["trade_date", "strategy_id", "ts_code"],
        frame_name=frame_name,
    )

    daily_weight = (
        result.groupby(["trade_date", "strategy_id"])["target_weight"]
        .sum()
    )
    overweight = daily_weight[daily_weight > max_daily_weight]

    if not overweight.empty:
        sample = [
            {
                "trade_date": idx[0],
                "strategy_id": idx[1],
                "target_weight_sum": float(value),
            }
            for idx, value in overweight.head(5).items()
        ]
        raise ValueError(
            f"{frame_name} daily target_weight sum exceeds "
            f"{max_daily_weight}. Examples: {sample}"
        )

    return result
