from __future__ import annotations

import pandas as pd


DEFAULT_FORWARD_PERIODS = [1, 5, 20]


def calculate_forward_returns(
    price_df: pd.DataFrame,
    periods: list[int] | None = None,
    price_col: str = "close",
) -> pd.DataFrame:
    """
    Calculate research-only forward returns from T close to T+h close.

    These returns are for factor evaluation only. They are not executable
    trading returns and must not be used to build or standardize factors.
    """

    periods = periods or DEFAULT_FORWARD_PERIODS

    if price_df.empty:
        columns = ["trade_date", "ts_code"] + [
            f"forward_return_{period}d"
            for period in periods
        ]
        return pd.DataFrame(columns=columns)

    required = {"trade_date", "ts_code", price_col}
    missing = required - set(price_df.columns)

    if missing:
        raise ValueError(
            f"price_df is missing required columns: {sorted(missing)}"
        )

    result = price_df[["trade_date", "ts_code", price_col]].copy()
    result["trade_date"] = pd.to_datetime(result["trade_date"])
    result = result.sort_values(["ts_code", "trade_date"]).reset_index(drop=True)

    price = pd.to_numeric(result[price_col], errors="coerce")

    for period in periods:
        if period <= 0:
            raise ValueError("forward return periods must be positive integers")

        future_price = price.groupby(result["ts_code"]).shift(-period)
        result[f"forward_return_{period}d"] = future_price / price - 1

    return result.drop(columns=[price_col])
