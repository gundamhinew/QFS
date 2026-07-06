from __future__ import annotations

import pandas as pd

from src.factors.base import BaseFactor
from src.factors.registry import register_factor


@register_factor("momentum")
class MomentumFactor(BaseFactor):

    factor_id = "momentum"
    factor_name = "momentum"

    def build(
        self,
        start: str,
        end: str,
        universe: list[str] | None = None
    ) -> pd.DataFrame:

        lookback = self.params.get("lookback", 60)

        price = self.dm.get_adjusted_price(
            start=start,
            end=end,
            ts_codes=universe,
            adjust="total_return"
        )

        if price.empty:
            return pd.DataFrame()

        price = price.sort_values(
            ["ts_code", "trade_date"]
        ).reset_index(drop=True)

        price["factor_value"] = (
            price.groupby("ts_code")["adj_close"]
            .transform(
                lambda x:
                x / x.shift(lookback) - 1
            )
        )

        factor = price[
            ["ts_code", "trade_date", "factor_value"]
        ].copy()

        factor["factor_name"] = (
            f"mom_{lookback}"
        )

        return factor
