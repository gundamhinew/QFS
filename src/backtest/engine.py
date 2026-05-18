from __future__ import annotations

import pandas as pd

from src.backtest.account import Account
from src.backtest.broker import Broker
from src.datahub.data_manager import DataManager


class BacktestEngine:
    """
    回测引擎。

    作用：
    1. 按交易日推进回测；
    2. 根据目标持仓进行调仓；
    3. 调用 Broker 执行交易；
    4. 更新 Account；
    5. 记录净值曲线。

    当前第一版：
    - 日频调仓；
    - 使用收盘价成交；
    - 不考虑停牌和涨跌停；
    - 不考虑未来函数以外的复杂约束。
    """

    def __init__(
        self,
        dm: DataManager,
        initial_cash: float = 1_000_000
    ):

        self.dm = dm

        self.account = Account(
            initial_cash=initial_cash
        )

        self.broker = Broker()

    def run_backtest(
        self,
        target_positions: pd.DataFrame,
        start: str,
        end: str
    ) -> pd.DataFrame:
        """
        运行回测。

        参数
        ----
        target_positions:
            策略生成的目标持仓。

        start, end:
            回测区间。

        返回
        ----
        equity_curve:
            净值曲线。
        """

        if target_positions.empty:
            return pd.DataFrame()

        # 获取回测期间行情
        price_df = self.dm.get_daily_price(
            start=start,
            end=end,
            ts_codes=None
        )

        if price_df.empty:
            return pd.DataFrame()

        price_df["trade_date"] = pd.to_datetime(
            price_df["trade_date"]
        )

        target_positions["trade_date"] = pd.to_datetime(
            target_positions["trade_date"]
        )

        # 所有交易日
        trade_dates = sorted(
            target_positions["trade_date"].unique()
        )

        for trade_date in trade_dates:

            # 当天目标组合
            today_target = target_positions[
                target_positions["trade_date"] == trade_date
            ].copy()

            # 当天行情
            today_price = price_df[
                price_df["trade_date"] == trade_date
            ].copy()

            if today_price.empty:
                continue

            # 构建价格字典
            price_map = dict(
                zip(
                    today_price["ts_code"],
                    today_price["close"]
                )
            )

            # 当前总资产
            total_equity = self.account.get_total_equity(
                price_map=price_map
            )

            # 当前持仓股票
            current_codes = set(
                self.account.positions.keys()
            )

            # 目标持仓股票
            target_codes = set(
                today_target["ts_code"]
            )

            # ======================
            # 第一步：卖出不在目标组合里的股票
            # ======================

            sell_codes = current_codes - target_codes

            for ts_code in sell_codes:

                if ts_code not in price_map:
                    continue

                shares = self.account.get_position_shares(
                    ts_code
                )

                self.broker.execute_order(
                    account=self.account,
                    trade_date=trade_date,
                    ts_code=ts_code,
                    side="sell",
                    shares=shares,
                    price=price_map[ts_code]
                )

            # ======================
            # 第二步：调整目标组合
            # ======================

            for _, row in today_target.iterrows():

                ts_code = row["ts_code"]

                if ts_code not in price_map:
                    continue

                target_weight = row["target_weight"]
                close_price = price_map[ts_code]

                target_value = (
                    total_equity * target_weight
                )

                current_shares = (
                    self.account.get_position_shares(
                        ts_code
                    )
                )

                current_value = (
                    current_shares * close_price
                )

                diff_value = (
                    target_value - current_value
                )

                # 目标买入股数
                target_shares = (
                    diff_value // close_price
                )

                if target_shares > 0:

                    self.broker.execute_order(
                        account=self.account,
                        trade_date=trade_date,
                        ts_code=ts_code,
                        side="buy",
                        shares=target_shares,
                        price=close_price
                    )

                elif target_shares < 0:

                    self.broker.execute_order(
                        account=self.account,
                        trade_date=trade_date,
                        ts_code=ts_code,
                        side="sell",
                        shares=abs(target_shares),
                        price=close_price
                    )

            # ======================
            # 第三步：记录每日账户状态
            # ======================

            self.account.record_daily_snapshot(
                trade_date=trade_date,
                price_map=price_map
            )

        return self.account.get_equity_curve()