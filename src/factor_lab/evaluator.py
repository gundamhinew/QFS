from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd

from src.factor_lab.forward_returns import DEFAULT_FORWARD_PERIODS
from src.factor_lab.quantile_analysis import (
    assign_quantiles,
    calculate_monotonicity,
    calculate_quantile_nav,
    calculate_quantile_returns,
    calculate_quantile_turnover,
    calculate_top_bottom_spread,
)


@dataclass
class FactorEvaluationResult:
    summary: dict[str, Any]
    ic_series: pd.DataFrame
    quantile_returns: pd.DataFrame
    quantile_nav: pd.DataFrame
    coverage: pd.DataFrame
    merged: pd.DataFrame


class FactorEvaluator:
    """
    Single-factor research evaluator.

    The evaluator consumes processed factor scores and research-only forward
    close-to-close returns. It does not build portfolios or run trading
    backtests.
    """

    def __init__(
        self,
        periods: list[int] | None = None,
        quantiles: int = 5,
    ):
        self.periods = periods or DEFAULT_FORWARD_PERIODS
        self.quantiles = quantiles

    def evaluate(
        self,
        processed_factor: pd.DataFrame,
        forward_returns: pd.DataFrame,
    ) -> FactorEvaluationResult:
        processed = processed_factor.copy()
        processed["trade_date"] = pd.to_datetime(processed["trade_date"])

        returns = forward_returns.copy()
        returns["trade_date"] = pd.to_datetime(returns["trade_date"])

        quantiled = assign_quantiles(
            processed,
            score_col="factor_score",
            quantiles=self.quantiles,
        )
        merged = quantiled.merge(
            returns,
            on=["trade_date", "ts_code"],
            how="left",
        )

        ic_series = self._calculate_ic_series(merged)
        quantile_returns = calculate_quantile_returns(
            merged,
            periods=self.periods,
        )
        quantile_nav = calculate_quantile_nav(quantile_returns)
        coverage = self._calculate_coverage(processed, merged)
        spread = calculate_top_bottom_spread(
            quantile_returns,
            top_quantile=self.quantiles,
            bottom_quantile=1,
        )
        top_turnover = calculate_quantile_turnover(
            quantiled,
            quantile=self.quantiles,
        )
        bottom_turnover = calculate_quantile_turnover(
            quantiled,
            quantile=1,
        )

        summary = self._build_summary(
            processed=processed,
            merged=merged,
            ic_series=ic_series,
            quantile_returns=quantile_returns,
            spread=spread,
            top_turnover=top_turnover,
            bottom_turnover=bottom_turnover,
        )

        return FactorEvaluationResult(
            summary=summary,
            ic_series=ic_series,
            quantile_returns=quantile_returns,
            quantile_nav=quantile_nav,
            coverage=coverage,
            merged=merged,
        )

    def _calculate_ic_series(
        self,
        merged: pd.DataFrame,
    ) -> pd.DataFrame:
        rows = []

        for period in self.periods:
            return_col = f"forward_return_{period}d"
            if return_col not in merged.columns:
                continue

            for trade_date, day in merged.groupby("trade_date"):
                valid = day[["factor_score", return_col]].dropna()

                if len(valid) < 2:
                    pearson_ic = np.nan
                    rank_ic = np.nan
                else:
                    pearson_ic = valid["factor_score"].corr(
                        valid[return_col],
                        method="pearson",
                    )
                    rank_ic = valid["factor_score"].rank().corr(
                        valid[return_col].rank(),
                        method="pearson",
                    )

                rows.append({
                    "trade_date": trade_date,
                    "period": period,
                    "ic": pearson_ic,
                    "rank_ic": rank_ic,
                    "count": int(len(valid)),
                })

        return pd.DataFrame(rows)

    def _calculate_coverage(
        self,
        processed: pd.DataFrame,
        merged: pd.DataFrame,
    ) -> pd.DataFrame:
        total = (
            processed.groupby("trade_date")["ts_code"]
            .nunique()
            .rename("stock_count")
        )
        valid_factor = (
            processed.dropna(subset=["factor_score"])
            .groupby("trade_date")["ts_code"]
            .nunique()
            .rename("valid_factor_count")
        )

        coverage = pd.concat([total, valid_factor], axis=1).fillna(0)
        coverage["coverage_ratio"] = (
            coverage["valid_factor_count"] / coverage["stock_count"]
        )

        for period in self.periods:
            return_col = f"forward_return_{period}d"
            if return_col in merged.columns:
                valid_return = (
                    merged.dropna(subset=[return_col])
                    .groupby("trade_date")["ts_code"]
                    .nunique()
                    .rename(f"valid_forward_return_{period}d_count")
                )
                coverage = coverage.join(valid_return, how="left")

        return coverage.reset_index().fillna(0)

    def _build_summary(
        self,
        processed: pd.DataFrame,
        merged: pd.DataFrame,
        ic_series: pd.DataFrame,
        quantile_returns: pd.DataFrame,
        spread: pd.DataFrame,
        top_turnover: pd.DataFrame,
        bottom_turnover: pd.DataFrame,
    ) -> dict[str, Any]:
        summary: dict[str, Any] = {}

        summary["row_count"] = int(len(processed))
        summary["valid_date_count"] = int(processed["trade_date"].nunique())
        daily_count = processed.groupby("trade_date")["ts_code"].nunique()
        summary["daily_stock_count_mean"] = float(daily_count.mean())
        summary["daily_stock_count_median"] = float(daily_count.median())
        summary["daily_stock_count_min"] = int(daily_count.min())
        summary["nan_ratio"] = float(processed["factor_score"].isna().mean())
        summary["coverage_ratio"] = float(1.0 - summary["nan_ratio"])

        summary["ic"] = {}
        summary["annual"] = {}

        if not ic_series.empty:
            for period, period_ic in ic_series.groupby("period"):
                ic = period_ic["ic"].dropna()
                rank_ic = period_ic["rank_ic"].dropna()
                ic_std = float(ic.std(ddof=1)) if len(ic) > 1 else np.nan
                rank_std = float(rank_ic.std(ddof=1)) if len(rank_ic) > 1 else np.nan
                summary["ic"][str(period)] = {
                    "ic_mean": float(ic.mean()) if not ic.empty else np.nan,
                    "ic_std": ic_std,
                    "icir": float(ic.mean() / ic_std) if ic_std and not np.isnan(ic_std) else np.nan,
                    "ic_positive_ratio": float((ic > 0).mean()) if not ic.empty else np.nan,
                    "rank_ic_mean": float(rank_ic.mean()) if not rank_ic.empty else np.nan,
                    "rank_ic_std": rank_std,
                    "rank_icir": float(rank_ic.mean() / rank_std) if rank_std and not np.isnan(rank_std) else np.nan,
                    "rank_ic_positive_ratio": float((rank_ic > 0).mean()) if not rank_ic.empty else np.nan,
                }

                period_annual = period_ic.copy()
                period_annual["year"] = period_annual["trade_date"].dt.year
                annual_rows = {}
                for year, year_ic in period_annual.groupby("year"):
                    annual_rows[str(year)] = {
                        "ic_mean": float(year_ic["ic"].mean()),
                        "rank_ic_mean": float(year_ic["rank_ic"].mean()),
                    }
                summary["annual"][str(period)] = annual_rows

        summary["quantile_returns_mean"] = {}
        if not quantile_returns.empty:
            quantile_mean = (
                quantile_returns.groupby(["period", "factor_quantile"])["mean_return"]
                .mean()
            )
            for (period, quantile), value in quantile_mean.items():
                summary["quantile_returns_mean"].setdefault(str(period), {})[
                    str(int(quantile))
                ] = float(value)

        summary["top_bottom_spread_mean"] = {}
        summary["annual_top_bottom_spread"] = {}
        if not spread.empty:
            for period, period_spread in spread.groupby("period"):
                summary["top_bottom_spread_mean"][str(period)] = float(
                    period_spread["top_bottom_spread"].mean()
                )
                annual = period_spread.copy()
                annual["year"] = annual["trade_date"].dt.year
                summary["annual_top_bottom_spread"][str(period)] = {
                    str(year): float(year_df["top_bottom_spread"].mean())
                    for year, year_df in annual.groupby("year")
                }

        summary["monotonicity"] = {
            str(period): calculate_monotonicity(quantile_returns, period=period)
            for period in self.periods
        }

        summary["decay"] = {
            str(period): summary["ic"].get(str(period), {}).get("ic_mean", np.nan)
            for period in self.periods
        }

        summary["top_quantile_turnover_mean"] = float(
            top_turnover["turnover"].mean()
        ) if not top_turnover.empty else np.nan
        summary["bottom_quantile_turnover_mean"] = float(
            bottom_turnover["turnover"].mean()
        ) if not bottom_turnover.empty else np.nan

        return summary
