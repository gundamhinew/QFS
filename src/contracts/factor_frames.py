from __future__ import annotations

import numpy as np
import pandas as pd


RAW_FACTOR_COLUMNS = [
    "trade_date",
    "ts_code",
    "factor_id",
    "factor_value",
]

PROCESSED_FACTOR_COLUMNS = [
    "trade_date",
    "ts_code",
    "factor_id",
    "raw_value",
    "factor_score",
]


def _validate_not_empty(df: pd.DataFrame, frame_name: str) -> None:
    if df.empty:
        raise ValueError(f"{frame_name} must not be empty")


def _validate_required_columns(
    df: pd.DataFrame,
    required_columns: list[str],
    frame_name: str,
) -> None:
    missing = [
        col
        for col in required_columns
        if col not in df.columns
    ]

    if missing:
        raise ValueError(
            f"{frame_name} is missing required columns: {missing}"
        )


def _normalize_trade_date(
    df: pd.DataFrame,
    frame_name: str,
) -> pd.DataFrame:
    result = df.copy()

    try:
        result["trade_date"] = pd.to_datetime(
            result["trade_date"],
            errors="raise",
        )
    except Exception as exc:
        raise ValueError(
            f"{frame_name}.trade_date contains values that cannot be "
            f"converted to datetime: {exc}"
        ) from exc

    if result["trade_date"].isna().any():
        raise ValueError(f"{frame_name}.trade_date contains NaN values")

    return result


def _validate_numeric_column(
    df: pd.DataFrame,
    column: str,
    frame_name: str,
    allow_nan: bool,
) -> None:
    try:
        numeric = pd.to_numeric(df[column], errors="raise")
    except Exception as exc:
        raise ValueError(
            f"{frame_name}.{column} must be numeric: {exc}"
        ) from exc

    if not allow_nan and numeric.isna().any():
        raise ValueError(f"{frame_name}.{column} contains NaN values")

    values = numeric.to_numpy(dtype=float, na_value=np.nan)
    if np.isinf(values).any():
        raise ValueError(f"{frame_name}.{column} contains inf values")


def _validate_no_duplicate_keys(
    df: pd.DataFrame,
    key_columns: list[str],
    frame_name: str,
) -> None:
    duplicates = df.duplicated(subset=key_columns, keep=False)

    if duplicates.any():
        sample = (
            df.loc[duplicates, key_columns]
            .head(5)
            .to_dict("records")
        )
        raise ValueError(
            f"{frame_name} contains duplicate keys for {key_columns}. "
            f"Examples: {sample}"
        )


def validate_raw_factor_frame(df: pd.DataFrame) -> pd.DataFrame:
    """
    Validate and normalize a RawFactorFrame.

    Required columns:
        trade_date, ts_code, factor_id, factor_value
    """

    frame_name = "RawFactorFrame"
    _validate_not_empty(df, frame_name)
    _validate_required_columns(df, RAW_FACTOR_COLUMNS, frame_name)

    result = _normalize_trade_date(df, frame_name)
    _validate_numeric_column(
        result,
        column="factor_value",
        frame_name=frame_name,
        allow_nan=True,
    )
    _validate_no_duplicate_keys(
        result,
        key_columns=["trade_date", "ts_code", "factor_id"],
        frame_name=frame_name,
    )

    return result


def validate_processed_factor_frame(df: pd.DataFrame) -> pd.DataFrame:
    """
    Validate and normalize a ProcessedFactorFrame.

    Required columns:
        trade_date, ts_code, factor_id, raw_value, factor_score
    """

    frame_name = "ProcessedFactorFrame"
    _validate_not_empty(df, frame_name)
    _validate_required_columns(df, PROCESSED_FACTOR_COLUMNS, frame_name)

    result = _normalize_trade_date(df, frame_name)
    _validate_numeric_column(
        result,
        column="raw_value",
        frame_name=frame_name,
        allow_nan=True,
    )
    _validate_numeric_column(
        result,
        column="factor_score",
        frame_name=frame_name,
        allow_nan=False,
    )
    _validate_no_duplicate_keys(
        result,
        key_columns=["trade_date", "ts_code", "factor_id"],
        frame_name=frame_name,
    )

    return result
