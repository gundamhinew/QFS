from __future__ import annotations

import pandas as pd

from src.datahub.point_in_time import align_fina_indicator_to_universe
from src.factors.base import BaseFactor
from src.factors.registry import register_factor


ALLOWED_INDICATOR_FIELDS = frozenset({"roe_yearly", "netprofit_yoy"})
OUTPUT_COLUMNS = ["trade_date", "ts_code", "factor_value"]


@register_factor("financial_indicator")
class FinancialIndicatorFactor(BaseFactor):
    """Latest publicly available value of a configured financial indicator."""

    factor_name = "financial_indicator"

    def build(
        self,
        start: str,
        end: str,
        universe: list[str] | None = None,
    ) -> pd.DataFrame:
        indicator_field = self.params.get("indicator_field")
        if not indicator_field:
            raise ValueError("indicator_field is required")
        if indicator_field not in ALLOWED_INDICATOR_FIELDS:
            allowed = sorted(ALLOWED_INDICATOR_FIELDS)
            raise ValueError(
                f"Unsupported indicator_field '{indicator_field}'. Allowed fields: {allowed}"
            )

        daily_price = self.dm.get_daily_price(
            start=start,
            end=end,
            ts_codes=universe,
        )
        if daily_price.empty:
            return pd.DataFrame(columns=OUTPUT_COLUMNS)

        required = ["trade_date", "ts_code"]
        missing = [column for column in required if column not in daily_price.columns]
        if missing:
            raise ValueError(f"Daily price data is missing required columns: {missing}")

        universe_df = daily_price[required].copy()
        universe_df["trade_date"] = pd.to_datetime(
            universe_df["trade_date"],
            errors="raise",
            format="mixed",
        )
        start_date = pd.to_datetime(start, errors="raise", format="mixed")
        end_date = pd.to_datetime(end, errors="raise", format="mixed")
        universe_df = universe_df[
            universe_df["trade_date"].between(
                start_date,
                end_date,
                inclusive="both",
            )
        ].copy()
        if universe_df.empty:
            return pd.DataFrame(columns=OUTPUT_COLUMNS)

        financial_df = self.dm.get_fina_indicator(
            start=None,
            end=end,
            ts_codes=universe,
            fields=[indicator_field],
        )
        if financial_df.empty:
            financial_df = pd.DataFrame(columns=[
                "ts_code",
                "ann_date",
                "end_date",
                indicator_field,
            ])
        aligned = align_fina_indicator_to_universe(
            financial_df=financial_df,
            universe_df=universe_df,
            fields=[indicator_field],
        )
        result = aligned.rename(columns={indicator_field: "factor_value"})

        return (
            result[OUTPUT_COLUMNS]
            .sort_values(["trade_date", "ts_code"], kind="stable")
            .reset_index(drop=True)
        )


__all__ = ["FinancialIndicatorFactor"]
