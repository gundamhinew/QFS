from __future__ import annotations

import numpy as np
import pandas as pd


def assign_quantiles(
    df: pd.DataFrame,
    score_col: str = "factor_score",
    quantiles: int = 5,
    output_col: str = "factor_quantile",
) -> pd.DataFrame:
    result = df.copy()

    def _assign_one_day(values: pd.Series) -> pd.Series:
        valid = values.dropna()

        if valid.nunique(dropna=True) < 2:
            return pd.Series(np.nan, index=values.index)

        bucket_count = min(quantiles, int(valid.nunique(dropna=True)))
        ranked = values.rank(method="first", ascending=True)

        try:
            labels = pd.qcut(
                ranked,
                q=bucket_count,
                labels=False,
                duplicates="drop",
            )
        except ValueError:
            return pd.Series(np.nan, index=values.index)

        return labels.astype(float) + 1

    result[output_col] = (
        result.groupby("trade_date")[score_col]
        .transform(_assign_one_day)
    )
    return result


def calculate_quantile_returns(
    merged: pd.DataFrame,
    periods: list[int],
    quantile_col: str = "factor_quantile",
) -> pd.DataFrame:
    rows = []

    for period in periods:
        return_col = f"forward_return_{period}d"
        if return_col not in merged.columns:
            continue

        valid = merged.dropna(subset=[quantile_col, return_col]).copy()
        if valid.empty:
            continue

        grouped = (
            valid.groupby(["trade_date", quantile_col])[return_col]
            .mean()
            .reset_index()
        )
        grouped = grouped.rename(columns={return_col: "mean_return"})
        grouped["period"] = period
        rows.append(grouped)

    if not rows:
        return pd.DataFrame(
            columns=["trade_date", "factor_quantile", "mean_return", "period"]
        )

    return pd.concat(rows, ignore_index=True)


def calculate_quantile_nav(
    quantile_returns: pd.DataFrame,
) -> pd.DataFrame:
    if quantile_returns.empty:
        return pd.DataFrame(
            columns=["trade_date", "factor_quantile", "period", "nav"]
        )

    result = quantile_returns.sort_values(
        ["period", "factor_quantile", "trade_date"]
    ).copy()
    result["nav"] = (
        result.groupby(["period", "factor_quantile"])["mean_return"]
        .transform(lambda x: (1 + x.fillna(0)).cumprod())
    )

    return result[["trade_date", "factor_quantile", "period", "nav"]]


def calculate_top_bottom_spread(
    quantile_returns: pd.DataFrame,
    top_quantile: int = 5,
    bottom_quantile: int = 1,
) -> pd.DataFrame:
    if quantile_returns.empty:
        return pd.DataFrame(columns=["trade_date", "period", "top_bottom_spread"])

    pivot = quantile_returns.pivot_table(
        index=["trade_date", "period"],
        columns="factor_quantile",
        values="mean_return",
    )

    if top_quantile not in pivot.columns or bottom_quantile not in pivot.columns:
        return pd.DataFrame(columns=["trade_date", "period", "top_bottom_spread"])

    spread = (
        pivot[top_quantile] - pivot[bottom_quantile]
    ).rename("top_bottom_spread")

    return spread.reset_index()


def calculate_monotonicity(
    quantile_returns: pd.DataFrame,
    period: int = 1,
) -> float:
    data = quantile_returns[quantile_returns["period"] == period]

    if data.empty:
        return float("nan")

    avg = data.groupby("factor_quantile")["mean_return"].mean().sort_index()

    if len(avg) < 2:
        return float("nan")

    return float(
        avg.rank().corr(
            pd.Series(avg.index, index=avg.index).rank(),
            method="pearson",
        )
    )


def calculate_quantile_turnover(
    quantiled: pd.DataFrame,
    quantile: int,
    quantile_col: str = "factor_quantile",
) -> pd.DataFrame:
    rows = []
    previous_members: set[str] | None = None

    for trade_date, day in quantiled.sort_values("trade_date").groupby("trade_date"):
        members = set(
            day.loc[day[quantile_col] == quantile, "ts_code"]
            .dropna()
            .astype(str)
        )

        if previous_members is None or not previous_members:
            turnover = np.nan
        else:
            turnover = 1.0 - len(members & previous_members) / len(previous_members)

        rows.append({
            "trade_date": trade_date,
            "quantile": quantile,
            "turnover": turnover,
        })
        previous_members = members

    return pd.DataFrame(rows)
