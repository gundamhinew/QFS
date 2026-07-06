from __future__ import annotations

import pandas as pd


VALID_REBALANCE_FREQUENCIES = {"daily", "weekly", "monthly"}


class RebalancePolicy:
    def __init__(self, frequency: str = "daily"):
        frequency = str(frequency).lower()
        if frequency not in VALID_REBALANCE_FREQUENCIES:
            raise ValueError(
                f"frequency must be one of {sorted(VALID_REBALANCE_FREQUENCIES)}"
            )
        self.frequency = frequency

    def select_signal_dates(
        self,
        signal_dates,
    ) -> list[pd.Timestamp]:
        dates = (
            pd.Series(pd.to_datetime(signal_dates))
            .dropna()
            .drop_duplicates()
            .sort_values()
            .reset_index(drop=True)
        )

        if dates.empty:
            return []

        if self.frequency == "daily":
            return dates.tolist()

        df = pd.DataFrame({"trade_date": dates})
        if self.frequency == "weekly":
            period = df["trade_date"].dt.to_period("W")
        else:
            period = df["trade_date"].dt.to_period("M")

        return (
            df.assign(period=period)
            .groupby("period", sort=True)["trade_date"]
            .max()
            .tolist()
        )

    def filter_model_scores(
        self,
        model_scores: pd.DataFrame,
    ) -> pd.DataFrame:
        if model_scores.empty:
            return model_scores.copy()

        signal_dates = self.select_signal_dates(model_scores["trade_date"])
        signal_date_set = set(signal_dates)
        result = model_scores.copy()
        result["trade_date"] = pd.to_datetime(result["trade_date"])
        return result[result["trade_date"].isin(signal_date_set)].copy()
