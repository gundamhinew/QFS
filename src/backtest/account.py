from __future__ import annotations

import pandas as pd


class Account:
    """
    回测账户。

    作用：
    1. 保存当前现金；
    2. 保存当前持仓；
    3. 计算当前总资产；
    4. 保存历史净值曲线；
    5. 为后续回测和实盘统一账户结构。

    当前第一版：
    暂不考虑融资融券、期货、杠杆等复杂情况。
    """

    def __init__(
        self,
        initial_cash: float = 1_000_000
    ):
        """
        初始化账户。

        参数
        ----
        initial_cash:
            初始资金。
        """

        self.initial_cash = initial_cash

        # 当前现金
        self.cash = initial_cash

        # 当前持仓
        # 结构：
        # {
        #     "000001.SZ": {
        #         "shares": 1000,
        #         "cost": 12.5
        #     }
        # }
        self.positions: dict = {}

        # 每日账户快照
        self.history: list[dict] = []

    def get_position_shares(
        self,
        ts_code: str
    ) -> float:
        """
        获取某只股票当前持仓股数。
        """

        if ts_code not in self.positions:
            return 0.0

        return self.positions[ts_code]["shares"]

    def get_position_market_value(
        self,
        ts_code: str,
        price: float
    ) -> float:
        """
        获取某只股票当前市值。
        """

        shares = self.get_position_shares(ts_code)

        return shares * price

    def get_total_market_value(
        self,
        price_map: dict[str, float]
    ) -> float:
        """
        计算当前总持仓市值。

        参数
        ----
        price_map:
            当前价格字典：
            {
                "000001.SZ": 13.5,
                ...
            }
        """

        total = 0.0

        for ts_code in self.positions:

            if ts_code not in price_map:
                continue

            shares = self.positions[ts_code]["shares"]
            price = price_map[ts_code]

            total += shares * price

        return total

    def get_total_equity(
        self,
        price_map: dict[str, float]
    ) -> float:
        """
        计算当前总资产。

        总资产 =
            现金 + 持仓市值
        """

        market_value = self.get_total_market_value(
            price_map=price_map
        )

        return self.cash + market_value

    def update_position(
        self,
        ts_code: str,
        shares: float,
        cost: float
    ):
        """
        更新某只股票持仓。

        参数
        ----
        ts_code:
            股票代码。

        shares:
            最新持仓股数。

        cost:
            持仓成本价。
        """

        if shares <= 0:

            # 持仓为0时直接删除
            if ts_code in self.positions:
                del self.positions[ts_code]

            return

        self.positions[ts_code] = {
            "shares": shares,
            "cost": cost
        }

    def record_daily_snapshot(
        self,
        trade_date: pd.Timestamp,
        price_map: dict[str, float]
    ):
        """
        记录每日账户状态。

        参数
        ----
        trade_date:
            当前交易日。

        price_map:
            当前价格字典。
        """

        market_value = self.get_total_market_value(
            price_map=price_map
        )

        total_equity = (
            self.cash + market_value
        )

        snapshot = {
            "trade_date": trade_date,
            "cash": self.cash,
            "market_value": market_value,
            "total_equity": total_equity
        }

        self.history.append(snapshot)

    def get_equity_curve(
        self
    ) -> pd.DataFrame:
        """
        获取历史净值曲线。
        """

        if not self.history:
            return pd.DataFrame()

        df = pd.DataFrame(self.history)

        df = df.sort_values(
            "trade_date"
        ).reset_index(drop=True)

        df["daily_return"] = (
            df["total_equity"]
            .pct_change()
        )

        df["nav"] = (
            df["total_equity"]
            / self.initial_cash
        )

        return df