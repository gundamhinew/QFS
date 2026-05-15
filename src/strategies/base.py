from __future__ import annotations

from abc import ABC, abstractmethod
import pandas as pd


class BaseStrategy(ABC):
    """
    策略基类。

    作用：
    1. 规定所有策略的统一接口；
    2. 输入处理后的因子数据；
    3. 输出目标持仓；
    4. 为后续回测和 QMT 执行提供统一格式。

    标准输出格式：
        trade_date
        ts_code
        target_weight
        strategy_name
    """

    strategy_name: str = "base_strategy"

    def __init__(self, params: dict | None = None):
        self.params = params or {}

    @abstractmethod
    def generate_target_positions(
        self,
        factor_df: pd.DataFrame
    ) -> pd.DataFrame:
        """
        根据因子数据生成目标持仓。

        参数
        ----
        factor_df:
            已经过 FactorProcessor 处理后的因子数据。

        返回
        ----
        target_positions:
            目标持仓表，至少包含：
                trade_date
                ts_code
                target_weight
                strategy_name
        """
        pass