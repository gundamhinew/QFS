from __future__ import annotations

import pandas as pd

from src.contracts.factor_frames import (
    _normalize_trade_date,
    _validate_no_duplicate_keys,
    _validate_not_empty,
    _validate_numeric_column,
    _validate_required_columns,
)


MODEL_SCORE_COLUMNS = [
    "trade_date",
    "ts_code",
    "model_id",
    "model_score",
]


def validate_model_score_frame(df: pd.DataFrame) -> pd.DataFrame:
    """
    Validate and normalize a ModelScoreFrame.

    This only defines the data contract for future AlphaModel output. It does
    not implement any model construction logic.
    """

    frame_name = "ModelScoreFrame"
    _validate_not_empty(df, frame_name)
    _validate_required_columns(df, MODEL_SCORE_COLUMNS, frame_name)

    result = _normalize_trade_date(df, frame_name)
    _validate_numeric_column(
        result,
        column="model_score",
        frame_name=frame_name,
        allow_nan=False,
    )
    _validate_no_duplicate_keys(
        result,
        key_columns=["trade_date", "ts_code", "model_id"],
        frame_name=frame_name,
    )

    return result
