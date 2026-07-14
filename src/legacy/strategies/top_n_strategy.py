from __future__ import annotations

import pandas as pd

from src.portfolio.top_n_equal_weight import TopNEqualWeightPortfolio
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

        percentile_col = self.params.get(
            "percentile_col",
            "factor_percentile"
        )

        df = factor_df.copy()
        df["trade_date"] = pd.to_datetime(df["trade_date"])
        model_scores = df[
            [
                "trade_date",
                "ts_code",
                percentile_col,
            ]
        ].rename(columns={percentile_col: "model_score"})
        model_scores["model_id"] = "legacy_single_factor"

        base_weights = TopNEqualWeightPortfolio().build(
            model_scores=model_scores,
            config={
                "params": {
                    "top_n": self.params.get("top_n", 50),
                    "normalize_weights": True,
                }
            },
        )

        selected = base_weights.rename(
            columns={"raw_target_weight": "target_weight"}
        ).copy()
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
