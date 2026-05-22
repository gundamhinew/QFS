from __future__ import annotations

import numpy as np
import pandas as pd


class PerformanceAnalyzer:
    """
    绩效分析器。

    输入回测产生的日频净值曲线和交易记录，输出常用绩效指标。
    """

    def __init__(
        self,
        annualization: int = 252,
        risk_free_rate: float = 0.0
    ):
        self.annualization = annualization
        self.risk_free_rate = risk_free_rate

    @staticmethod
    def _max_drawdown(nav: pd.Series) -> float:
        """
        基于净值序列计算最大回撤。
        """

        running_max = nav.cummax()
        drawdown = nav / running_max - 1

        return float(drawdown.min())

    def _calc_turnover(
        self,
        equity_curve: pd.DataFrame,
        trade_log: pd.DataFrame
    ) -> dict[str, float]:
        """
        计算区间总换手、日均换手和年化换手。
        """

        zero_turnover = {
            "total_turnover": 0.0,
            "average_daily_turnover": 0.0,
            "annualized_turnover": 0.0,
        }

        if equity_curve.empty or trade_log.empty:
            return zero_turnover

        required_trade_cols = {"trade_date", "trade_value"}
        required_equity_cols = {"trade_date", "total_equity"}

        if not required_trade_cols.issubset(trade_log.columns):
            return zero_turnover

        if not required_equity_cols.issubset(equity_curve.columns):
            return zero_turnover

        equity = equity_curve.copy()
        trades = trade_log.copy()

        equity["trade_date"] = pd.to_datetime(equity["trade_date"])
        trades["trade_date"] = pd.to_datetime(trades["trade_date"])
        trades["abs_trade_value"] = trades["trade_value"].abs()

        valid_equity = equity[
            equity["total_equity"].notna()
            & (equity["total_equity"] > 0)
        ].copy()

        if valid_equity.empty:
            return zero_turnover

        avg_equity = valid_equity["total_equity"].mean()

        if avg_equity <= 0 or pd.isna(avg_equity):
            return zero_turnover

        total_turnover = (
            trades["abs_trade_value"].sum()
            / avg_equity
        )

        daily_trade_value = (
            trades
            .groupby("trade_date", as_index=False)["abs_trade_value"]
            .sum()
        )

        daily_turnover = daily_trade_value.merge(
            valid_equity[["trade_date", "total_equity"]],
            on="trade_date",
            how="inner"
        )

        if daily_turnover.empty:
            average_daily_turnover = 0.0
        else:
            daily_turnover["daily_turnover"] = (
                daily_turnover["abs_trade_value"]
                / daily_turnover["total_equity"]
            )
            average_daily_turnover = daily_turnover[
                "daily_turnover"
            ].mean()

        annualized_turnover = (
            average_daily_turnover * self.annualization
        )

        return {
            "total_turnover": float(total_turnover),
            "average_daily_turnover": float(average_daily_turnover),
            "annualized_turnover": float(annualized_turnover),
        }

    def analyze(
        self,
        equity_curve: pd.DataFrame,
        trade_log: pd.DataFrame | None = None
    ) -> dict:
        """
        输出绩效指标字典。
        """

        trade_log = trade_log if trade_log is not None else pd.DataFrame()

        if equity_curve.empty:
            return {
                "final_nav": np.nan,
                "total_return": np.nan,
                "annual_return": np.nan,
                "annual_volatility": np.nan,
                "sharpe": np.nan,
                "max_drawdown": np.nan,
                "total_turnover": 0.0,
                "average_daily_turnover": 0.0,
                "annualized_turnover": 0.0,
                "number_of_trades": 0,
            }

        df = equity_curve.copy()
        df = df.sort_values("trade_date").reset_index(drop=True)

        if "nav" not in df.columns:
            df["nav"] = df["total_equity"] / df["total_equity"].iloc[0]

        returns = df["nav"].pct_change().dropna()
        final_nav = float(df["nav"].iloc[-1])
        total_return = final_nav - 1

        days = max(len(df), 1)
        annual_return = (final_nav ** (self.annualization / days)) - 1

        annual_volatility = float(
            returns.std(ddof=0) * np.sqrt(self.annualization)
        ) if not returns.empty else 0.0

        excess_return = returns - self.risk_free_rate / self.annualization
        sharpe = (
            float(
                excess_return.mean()
                / returns.std(ddof=0)
                * np.sqrt(self.annualization)
            )
            if not returns.empty and returns.std(ddof=0) > 0
            else np.nan
        )

        turnover_metrics = self._calc_turnover(df, trade_log)

        return {
            "final_nav": final_nav,
            "total_return": float(total_return),
            "annual_return": float(annual_return),
            "annual_volatility": annual_volatility,
            "sharpe": sharpe,
            "max_drawdown": self._max_drawdown(df["nav"]),
            "total_turnover": turnover_metrics["total_turnover"],
            "average_daily_turnover": turnover_metrics[
                "average_daily_turnover"
            ],
            "annualized_turnover": turnover_metrics[
                "annualized_turnover"
            ],
            "number_of_trades": int(len(trade_log)),
        }
