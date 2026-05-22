from __future__ import annotations

import pandas as pd


VALID_REBALANCE_FREQUENCIES = {"daily", "weekly", "monthly"}


def _validate_frequency(frequency: str) -> str:
    """
    校验调仓频率参数。
    """

    normalized = str(frequency).lower()

    if normalized not in VALID_REBALANCE_FREQUENCIES:
        raise ValueError(
            "frequency must be one of: daily, weekly, monthly"
        )

    return normalized


def get_rebalance_signal_dates(
    signal_dates: list | pd.Series,
    frequency: str = "daily"
) -> list[pd.Timestamp]:
    """
    根据调仓频率筛选真正用于调仓的信号日期。
    """

    frequency = _validate_frequency(frequency)

    if signal_dates is None or len(signal_dates) == 0:
        return []

    dates = (
        pd.Series(pd.to_datetime(signal_dates))
        .dropna()
        .drop_duplicates()
        .sort_values()
        .reset_index(drop=True)
    )

    if dates.empty:
        return []

    if frequency == "daily":
        return dates.tolist()

    df = pd.DataFrame({"signal_date": dates})

    if frequency == "weekly":
        period_key = df["signal_date"].dt.to_period("W")
    else:
        period_key = df["signal_date"].dt.to_period("M")

    rebalance_dates = (
        df.assign(period_key=period_key)
        .groupby("period_key", sort=True)["signal_date"]
        .max()
        .sort_values()
    )

    return rebalance_dates.tolist()


def filter_target_positions_by_rebalance(
    target_positions: pd.DataFrame,
    frequency: str = "daily"
) -> pd.DataFrame:
    """
    根据 trade_date 信号日期过滤目标持仓。
    """

    _validate_frequency(frequency)

    if target_positions.empty:
        return target_positions.copy()

    if "trade_date" not in target_positions.columns:
        raise ValueError(
            "target_positions must contain a 'trade_date' column"
        )

    targets = target_positions.copy()
    signal_dates = get_rebalance_signal_dates(
        targets["trade_date"],
        frequency=frequency
    )

    signal_date_set = set(signal_dates)
    target_signal_dates = pd.to_datetime(targets["trade_date"])

    return targets[
        target_signal_dates.isin(signal_date_set)
    ].copy()
