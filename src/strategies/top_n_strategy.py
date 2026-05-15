from __future__ import annotations

import pandas as pd

from src.strategies.base import BaseStrategy


class TopNEqualWeightStrategy(BaseStrategy):
    """
    Top N 等权策略。

    策略逻辑：
    1. 每个交易日根据因子百分位排序；
    2. 选择因子表现最好的前 N 只股票；
    3. 对入选股票进行等权配置。

    当前用途：
    作为第一版单因子策略示例。
    """

    strategy_name = "top_n_equal_weight"

    def generate_target_positions(
        self,
        factor_df: pd.DataFrame
    ) -> pd.DataFrame:
        """
        生成目标持仓。

        参数
        ----
        factor_df:
            已处理因子表，至少包含：
                trade_date
                ts_code
                factor_percentile

        返回
        ----
        target_positions:
            每个交易日的目标持仓：
                trade_date
                ts_code
                target_weight
                strategy_name
        """

        if factor_df.empty:
            return pd.DataFrame()

        top_n = self.params.get("top_n", 50)
        percentile_col = self.params.get(
            "percentile_col",
            "factor_percentile"
        )

        df = factor_df.copy()
        df["trade_date"] = pd.to_datetime(df["trade_date"])

        # 每个交易日内，按因子百分位从高到低排序。
        df = df.sort_values(
            ["trade_date", percentile_col],
            ascending=[True, False]
        )

        # 每个交易日选前 N 只股票。
        selected = (
            df.groupby("trade_date")
            .head(top_n)
            .copy()
        )

        # 如果某天可选股票不足 top_n，则按实际选中数量等权。
        selected_count = (
            selected.groupby("trade_date")["ts_code"]
            .transform("count")
        )

        selected["target_weight"] = 1.0 / selected_count

        selected["strategy_name"] = self.strategy_name

        target_positions = selected[
            [
                "trade_date",
                "ts_code",
                "target_weight",
                "strategy_name"
            ]
        ].copy()

        target_positions = target_positions.sort_values(
            ["trade_date", "ts_code"]
        ).reset_index(drop=True)

        return target_positions