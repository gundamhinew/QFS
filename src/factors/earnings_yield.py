from __future__ import annotations

import numpy as np
import pandas as pd

from src.factors.base import BaseFactor
from src.factors.registry import register_factor


OUTPUT_COLUMNS = ["trade_date", "ts_code", "factor_value"]


@register_factor("earnings_yield")
class EarningsYieldFactor(BaseFactor):
    """Trailing earnings yield calculated as the reciprocal of PE TTM."""

    factor_name = "earnings_yield"

    def build(
        self,
        start: str,
        end: str,
        universe: list[str] | None = None,
    ) -> pd.DataFrame:
        daily_basic = self.dm.get_daily_basic(
            start=start,
            end=end,
            ts_codes=universe,
        )
        if daily_basic.empty:
            return pd.DataFrame(columns=OUTPUT_COLUMNS)

        required = ["trade_date", "ts_code", "pe_ttm"]
        missing = [column for column in required if column not in daily_basic.columns]
        if missing:
            raise ValueError(f"Daily basic data is missing required columns: {missing}")

        result = daily_basic[required].copy()
        result["trade_date"] = pd.to_datetime(
            result["trade_date"],
            errors="raise",
            format="mixed",
        )
        if result.duplicated(["trade_date", "ts_code"]).any():
            raise ValueError("Daily basic data contains duplicate trade_date and ts_code keys")

        pe_ttm = pd.to_numeric(result["pe_ttm"], errors="raise")
        result["factor_value"] = 1.0 / pe_ttm.mask(pe_ttm == 0)
        result["factor_value"] = result["factor_value"].replace(
            [np.inf, -np.inf],
            np.nan,
        )

        return (
            result[OUTPUT_COLUMNS]
            .sort_values(["trade_date", "ts_code"], kind="stable")
            .reset_index(drop=True)
        )


__all__ = ["EarningsYieldFactor"]
