from __future__ import annotations

import numpy as np
import pandas as pd

from src.factors.base import BaseFactor
from src.factors.registry import register_factor


OUTPUT_COLUMNS = ["trade_date", "ts_code", "factor_value"]


@register_factor("size")
class SizeFactor(BaseFactor):
    """Company size measured by the natural logarithm of total market value."""

    factor_name = "size"

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

        required = ["trade_date", "ts_code", "total_mv"]
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

        total_mv = pd.to_numeric(result["total_mv"], errors="raise")
        result["factor_value"] = np.log(total_mv.where(total_mv > 0))

        return (
            result[OUTPUT_COLUMNS]
            .sort_values(["trade_date", "ts_code"], kind="stable")
            .reset_index(drop=True)
        )


__all__ = ["SizeFactor"]
