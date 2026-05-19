from __future__ import annotations

import numpy as np
import pandas as pd


class PerformanceAnalyzer:
    """
    绩效分析器。

    输入回测产生的日频净值曲线和交易记录，输出常用绩效指标。
    第一版只依赖 equity_curve 和 trade_log，不反向依赖回测引擎。
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

    @staticmethod
    def _calc_turnover(
        equity_curve: pd.DataFrame,
        trade_log: pd.DataFrame
    ) -> float:
        """
        计算简化换手率。

        第一版用成交额合计 / 平均总资产。后续可升级为按日双边换手、
        单边换手或组合权重变化口径。
        """

        if equity_curve.empty or trade_log.empty:
            return 0.0

        if "trade_value" not in trade_log.columns:
            return 0.0

        avg_equity = equity_curve["total_equity"].mean()

        if avg_equity <= 0 or pd.isna(avg_equity):
            return 0.0

        return float(trade_log["trade_value"].abs().sum() / avg_equity)

    def analyze(
        self,
        equity_curve: pd.DataFrame,
        trade_log: pd.DataFrame | None = None
    ) -> dict:
        """
        输出绩效指标字典。

        指标均基于日频净值计算，夏普率暂按无风险利率为 0 的简化口径。
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
                "turnover": 0.0,
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
            float(excess_return.mean() / returns.std(ddof=0) * np.sqrt(self.annualization))
            if not returns.empty and returns.std(ddof=0) > 0
            else np.nan
        )

        return {
            "final_nav": final_nav,
            "total_return": float(total_return),
            "annual_return": float(annual_return),
            "annual_volatility": annual_volatility,
            "sharpe": sharpe,
            "max_drawdown": self._max_drawdown(df["nav"]),
            "turnover": self._calc_turnover(df, trade_log),
            "number_of_trades": int(len(trade_log)),
        }
