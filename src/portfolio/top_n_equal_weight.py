from __future__ import annotations

import pandas as pd

from src.portfolio.base import BasePortfolioBuilder
from src.portfolio.registry import register_portfolio_builder


@register_portfolio_builder("top_n_equal_weight")
class TopNEqualWeightPortfolio(BasePortfolioBuilder):
    portfolio_type = "top_n_equal_weight"

    def build(
        self,
        model_scores: pd.DataFrame,
        config: dict,
    ) -> pd.DataFrame:
        if model_scores.empty:
            return pd.DataFrame(
                columns=[
                    "trade_date",
                    "ts_code",
                    "raw_target_weight",
                    "model_score",
                ]
            )

        params = config.get("params", config)
        top_n = int(params.get("top_n", 50))
        max_single_weight = params.get("max_single_weight")
        minimum_score = params.get("minimum_score")
        normalize_weights = bool(params.get("normalize_weights", True))

        if top_n <= 0:
            raise ValueError("top_n must be positive")

        df = model_scores.copy()
        df["trade_date"] = pd.to_datetime(df["trade_date"])
        df["model_score"] = pd.to_numeric(df["model_score"], errors="raise")

        if minimum_score is not None:
            df = df[df["model_score"] >= float(minimum_score)].copy()

        df = df.sort_values(
            ["trade_date", "model_score"],
            ascending=[True, False],
        )
        selected = df.groupby("trade_date").head(top_n).copy()

        if selected.empty:
            return pd.DataFrame(
                columns=[
                    "trade_date",
                    "ts_code",
                    "raw_target_weight",
                    "model_score",
                ]
            )

        selected_count = selected.groupby("trade_date")["ts_code"].transform("count")
        selected["raw_target_weight"] = 1.0 / selected_count

        if max_single_weight is not None:
            max_weight = float(max_single_weight)
            if max_weight <= 0:
                raise ValueError("max_single_weight must be positive")
            selected["raw_target_weight"] = selected["raw_target_weight"].clip(
                upper=max_weight
            )

        if normalize_weights:
            daily_sum = selected.groupby("trade_date")["raw_target_weight"].transform("sum")
            selected["raw_target_weight"] = selected["raw_target_weight"] / daily_sum

            if max_single_weight is not None:
                selected["raw_target_weight"] = selected["raw_target_weight"].clip(
                    upper=float(max_single_weight)
                )

        return (
            selected[
                [
                    "trade_date",
                    "ts_code",
                    "raw_target_weight",
                    "model_score",
                ]
            ]
            .sort_values(["trade_date", "ts_code"])
            .reset_index(drop=True)
        )
