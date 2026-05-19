from __future__ import annotations

import pandas as pd

from src.datahub.data_manager import DataManager
from src.universe.filters import (
    exclude_bj_stocks,
    exclude_low_amount,
    exclude_low_price,
    exclude_new_stocks,
    exclude_st_stocks,
    exclude_suspended,
)


class UniverseBuilder:
    """
    股票池构建器。

    Universe 层只负责在指定日期范围内过滤可选股票，不删除也不改写原始数据。
    后续因子计算和策略选股可以用输出的 trade_date + ts_code 限定股票池。
    """

    def __init__(
        self,
        dm: DataManager,
        min_list_days: int = 120,
        min_close: float = 2.0,
        min_amount: float = 30_000_000
    ):
        self.dm = dm
        self.min_list_days = min_list_days
        self.min_close = min_close
        self.min_amount = min_amount

    @staticmethod
    def _add_amount_yuan(df: pd.DataFrame) -> pd.DataFrame:
        """
        增加成交额人民币口径字段。

        tushare daily.amount 通常为千元，这里保留原 amount，同时增加 amount_yuan
        供股票池过滤使用。
        """

        if df.empty or "amount" not in df.columns:
            return df

        result = df.copy()
        result["amount_yuan"] = result["amount"] * 1000

        return result

    def build(
        self,
        start: str,
        end: str
    ) -> pd.DataFrame:
        """
        构建指定区间的每日股票池。

        返回字段至少包含 trade_date、ts_code，并尽量保留 name、market、
        list_date、close、amount 等辅助字段，方便调试和后续过滤扩展。
        """

        price = self.dm.get_daily_price(
            start=start,
            end=end,
            ts_codes=None
        )

        if price.empty:
            return pd.DataFrame(columns=["trade_date", "ts_code"])

        stock_basic = self.dm.get_stock_basic(active_only=True)

        if stock_basic.empty:
            df = price.copy()
        else:
            keep_cols = [
                col for col in [
                    "ts_code",
                    "name",
                    "market",
                    "exchange",
                    "list_date",
                    "list_status",
                ]
                if col in stock_basic.columns
            ]
            df = price.merge(
                stock_basic[keep_cols],
                on="ts_code",
                how="left"
            )

        df["trade_date"] = pd.to_datetime(df["trade_date"])
        df = self._add_amount_yuan(df)

        # 过滤顺序从交易可行性到股票属性再到流动性，便于后续定位被剔除原因。
        df = exclude_suspended(df)
        df = exclude_bj_stocks(df)
        df = exclude_st_stocks(df)
        df = exclude_new_stocks(
            df,
            min_list_days=self.min_list_days
        )
        df = exclude_low_price(
            df,
            min_close=self.min_close
        )
        df = exclude_low_amount(
            df,
            min_amount=self.min_amount
        )

        output_cols = [
            col for col in [
                "trade_date",
                "ts_code",
                "name",
                "market",
                "exchange",
                "list_date",
                "close",
                "amount",
                "amount_yuan",
                "vol",
            ]
            if col in df.columns
        ]

        return (
            df[output_cols]
            .sort_values(["trade_date", "ts_code"])
            .reset_index(drop=True)
        )
