from __future__ import annotations

import pandas as pd

from src.factors.base import BaseFactor
from src.factors.registry import register_factor


@register_factor("momentum_12_1")
class Momentum121Factor(BaseFactor):
    """12-1 momentum using total-return adjusted closing prices."""

    factor_id = "momentum_12_1"
    factor_name = "momentum_12_1"
    output_columns = [
        "trade_date",
        "ts_code",
        "factor_name",
        "factor_value",
    ]

    def build(
        self,
        start: str,
        end: str,
        universe: list[str] | None = None,
    ) -> pd.DataFrame:
        lookback = self.params.get("lookback_trading_days", 252)
        skip_recent = self.params.get("skip_recent_trading_days", 21)
        history_buffer = self.params.get("history_buffer_calendar_days", 450)
        self._validate_parameters(lookback, skip_recent, history_buffer)

        start_date = self._parse_date(start, "start")
        end_date = self._parse_date(end, "end")
        if start_date > end_date:
            raise ValueError("start must be less than or equal to end")

        history_start = start_date - pd.Timedelta(days=history_buffer)
        price = self.dm.get_adjusted_price(
            start=history_start.strftime("%Y-%m-%d"),
            end=end_date.strftime("%Y-%m-%d"),
            ts_codes=universe,
            adjust="total_return",
        )

        if price.empty:
            return pd.DataFrame(columns=self.output_columns)

        required_columns = ["trade_date", "ts_code", "adj_close"]
        missing = [column for column in required_columns if column not in price.columns]
        if missing:
            raise ValueError(f"Adjusted price data is missing required columns: {missing}")

        work = price.copy()
        try:
            work["trade_date"] = pd.to_datetime(
                work["trade_date"],
                errors="raise",
                format="mixed",
            )
        except Exception as exc:
            raise ValueError(
                "Adjusted price trade_date contains values that cannot be converted to datetime"
            ) from exc

        if work["trade_date"].isna().any():
            raise ValueError(
                "Adjusted price trade_date contains values that cannot be converted to datetime"
            )
        if work.duplicated(["trade_date", "ts_code"]).any():
            raise ValueError(
                "Adjusted price data contains duplicate trade_date and ts_code keys"
            )

        work = work.sort_values(
            ["ts_code", "trade_date"],
            kind="stable",
        ).reset_index(drop=True)
        grouped_close = work.groupby("ts_code", sort=False)["adj_close"]
        work["factor_value"] = (
            grouped_close.shift(skip_recent)
            / grouped_close.shift(lookback)
            - 1
        )
        work = work[
            work["trade_date"].between(start_date, end_date, inclusive="both")
        ].copy()
        work["factor_name"] = self.factor_name

        return (
            work[self.output_columns]
            .sort_values(["trade_date", "ts_code"], kind="stable")
            .reset_index(drop=True)
        )

    @staticmethod
    def _validate_parameters(
        lookback: int,
        skip_recent: int,
        history_buffer: int,
    ) -> None:
        parameters = {
            "lookback_trading_days": lookback,
            "skip_recent_trading_days": skip_recent,
            "history_buffer_calendar_days": history_buffer,
        }
        for name, value in parameters.items():
            if isinstance(value, bool) or not isinstance(value, int):
                raise ValueError(f"{name} must be an integer")

        if skip_recent <= 0:
            raise ValueError("skip_recent_trading_days must be greater than 0")
        if lookback <= skip_recent:
            raise ValueError(
                "lookback_trading_days must be greater than skip_recent_trading_days"
            )
        if history_buffer <= 0:
            raise ValueError("history_buffer_calendar_days must be greater than 0")

    @staticmethod
    def _parse_date(value: str, name: str) -> pd.Timestamp:
        try:
            parsed = pd.to_datetime(value, errors="raise", format="mixed")
        except Exception as exc:
            raise ValueError(f"{name} cannot be converted to datetime") from exc
        if pd.isna(parsed):
            raise ValueError(f"{name} cannot be converted to datetime")
        return pd.Timestamp(parsed)


__all__ = ["Momentum121Factor"]
