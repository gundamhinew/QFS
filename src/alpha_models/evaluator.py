from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd

from src.factors.evaluator import FactorEvaluator
from src.factors.quantile_analysis import (
    assign_quantiles,
    calculate_quantile_returns,
    calculate_top_bottom_spread,
)


@dataclass
class ModelEvaluationResult:
    summary: dict[str, Any]
    factor_correlation: pd.DataFrame
    factor_contribution: pd.DataFrame
    model_ic_series: pd.DataFrame
    model_quantile_returns: pd.DataFrame


class ModelEvaluator:
    def __init__(
        self,
        periods: list[int],
        quantiles: int = 5,
    ):
        self.periods = periods
        self.quantiles = quantiles

    def evaluate(
        self,
        model_scores: pd.DataFrame,
        aligned_factors: pd.DataFrame,
        forward_returns: pd.DataFrame,
        config: dict,
    ) -> ModelEvaluationResult:
        processed_like = model_scores[[
            "trade_date",
            "ts_code",
            "model_score",
        ]].rename(columns={"model_score": "factor_score"}).copy()
        processed_like["factor_id"] = config["model_id"]
        processed_like["raw_value"] = processed_like["factor_score"]

        factor_eval = FactorEvaluator(
            periods=self.periods,
            quantiles=self.quantiles,
        ).evaluate(processed_like, forward_returns)

        factor_cols = [
            col
            for col in aligned_factors.columns
            if col not in {
                "trade_date",
                "ts_code",
                "factor_count",
                "missing_factor_count",
            }
        ]
        factor_correlation = self._correlation_matrix(aligned_factors, factor_cols)
        contribution = self._factor_contribution(model_scores)
        summary = self._summary(
            model_scores=model_scores,
            factor_eval_summary=factor_eval.summary,
            factor_correlation=factor_correlation,
            contribution=contribution,
            config=config,
        )

        return ModelEvaluationResult(
            summary=summary,
            factor_correlation=factor_correlation,
            factor_contribution=contribution,
            model_ic_series=factor_eval.ic_series,
            model_quantile_returns=factor_eval.quantile_returns,
        )

    def _correlation_matrix(
        self,
        aligned_factors: pd.DataFrame,
        factor_cols: list[str],
    ) -> pd.DataFrame:
        rows = []

        for method in ["pearson", "spearman"]:
            data = aligned_factors[factor_cols]
            if method == "spearman":
                corr = data.rank().corr(method="pearson")
            else:
                corr = data.corr(method="pearson")

            for row_factor in factor_cols:
                for col_factor in factor_cols:
                    rows.append({
                        "method": method,
                        "factor_i": row_factor,
                        "factor_j": col_factor,
                        "correlation": corr.loc[row_factor, col_factor],
                    })

        return pd.DataFrame(rows)

    def _factor_contribution(
        self,
        model_scores: pd.DataFrame,
    ) -> pd.DataFrame:
        contribution_cols = [
            col
            for col in model_scores.columns
            if col.startswith("contribution_")
        ]
        rows = []

        for col in contribution_cols:
            rows.append({
                "factor": col.replace("contribution_", "", 1),
                "average_contribution": float(model_scores[col].mean()),
                "average_abs_contribution": float(model_scores[col].abs().mean()),
            })

        return pd.DataFrame(rows)

    def _summary(
        self,
        model_scores: pd.DataFrame,
        factor_eval_summary: dict[str, Any],
        factor_correlation: pd.DataFrame,
        contribution: pd.DataFrame,
        config: dict,
    ) -> dict[str, Any]:
        score = model_scores["model_score"]
        missing_ratio = float(
            model_scores["missing_factor_count"].sum()
            / max(
                (
                    model_scores["factor_count"]
                    + model_scores["missing_factor_count"]
                ).sum(),
                1,
            )
        )

        summary = {
            "model_id": config["model_id"],
            "model_type": config["model_type"],
            "row_count": int(len(model_scores)),
            "model_score_mean": float(score.mean()),
            "model_score_std": float(score.std(ddof=0)),
            "model_score_min": float(score.min()),
            "model_score_max": float(score.max()),
            "missing_policy": config.get("alignment", {}).get("missing_policy"),
            "missing_policy_impact": {
                "average_factor_count": float(model_scores["factor_count"].mean()),
                "average_missing_factor_count": float(model_scores["missing_factor_count"].mean()),
                "missing_ratio": missing_ratio,
            },
            "factor_config_weights": {
                item.get("alias") or item.get("factor_id"): item.get("weight", 1.0)
                for item in config.get("factors", [])
            },
            "factor_actual_average_contribution": {
                row["factor"]: row["average_contribution"]
                for _, row in contribution.iterrows()
            } if not contribution.empty else {},
            "factor_correlation_max_abs": float(
                factor_correlation.loc[
                    factor_correlation["factor_i"] != factor_correlation["factor_j"],
                    "correlation",
                ].abs().max()
            ) if not factor_correlation.empty and len(config.get("factors", [])) > 1 else np.nan,
            "model_research": factor_eval_summary,
        }

        return summary
