from __future__ import annotations

import pandas as pd

from src.backtest.account import Account


class Broker:
    """
    模拟券商交易执行器。

    作用：
    1. 根据买卖指令执行交易；
    2. 扣减或增加现金；
    3. 更新账户持仓；
    4. 计算手续费、印花税和滑点；
    5. 记录交易明细。

    当前第一版：
    - 只支持股票现货；
    - 不考虑融资融券；
    - 不考虑涨跌停和停牌；
    - 后续会逐步补充真实交易约束。
    """

    def __init__(
        self,
        commission_rate: float = 0.0003,
        stamp_tax_rate: float = 0.001,
        slippage_rate: float = 0.001,
        min_commission: float = 5.0
    ):
        """
        初始化 Broker。

        参数
        ----
        commission_rate:
            佣金率，默认万三。

        stamp_tax_rate:
            印花税率，默认千一，只在卖出时收取。

        slippage_rate:
            滑点率，默认千一。

        min_commission:
            最低佣金，默认 5 元。
        """

        self.commission_rate = commission_rate
        self.stamp_tax_rate = stamp_tax_rate
        self.slippage_rate = slippage_rate
        self.min_commission = min_commission

        # 交易记录
        self.trades: list[dict] = []

    def _calc_commission(
        self,
        trade_value: float
    ) -> float:
        """
        计算佣金。

        A股通常存在最低佣金约束。
        """

        if trade_value <= 0:
            return 0.0

        return max(
            trade_value * self.commission_rate,
            self.min_commission
        )

    def _calc_stamp_tax(
        self,
        trade_value: float,
        side: str
    ) -> float:
        """
        计算印花税。

        A股印花税通常只在卖出时收取。
        """

        if side != "sell":
            return 0.0

        return trade_value * self.stamp_tax_rate

    def execute_order(
        self,
        account: Account,
        trade_date: pd.Timestamp,
        ts_code: str,
        side: str,
        shares: float,
        price: float
    ):
        """
        执行单笔订单。

        参数
        ----
        account:
            回测账户。

        trade_date:
            交易日期。

        ts_code:
            股票代码。

        side:
            buy 或 sell。

        shares:
            交易股数。

        price:
            基准成交价格。

        说明
        ----
        买入时：
            使用 price * (1 + slippage_rate)

        卖出时：
            使用 price * (1 - slippage_rate)
        """

        if shares <= 0:
            return

        if side not in ["buy", "sell"]:
            raise ValueError("side must be 'buy' or 'sell'")

        # 按滑点修正成交价
        if side == "buy":
            exec_price = price * (1 + self.slippage_rate)
        else:
            exec_price = price * (1 - self.slippage_rate)

        trade_value = shares * exec_price
        commission = self._calc_commission(trade_value)
        stamp_tax = self._calc_stamp_tax(trade_value, side)
        total_cost = commission + stamp_tax

        old_shares = account.get_position_shares(ts_code)

        if side == "buy":
            cash_needed = trade_value + total_cost

            # 现金不足则按可用现金缩小买入股数
            if cash_needed > account.cash:
                affordable_value = account.cash / (
                    1 + self.commission_rate + self.slippage_rate
                )

                shares = affordable_value // exec_price

                if shares <= 0:
                    return

                trade_value = shares * exec_price
                commission = self._calc_commission(trade_value)
                stamp_tax = 0.0
                total_cost = commission + stamp_tax
                cash_needed = trade_value + total_cost

            new_shares = old_shares + shares

            # 简化成本计算：使用成交价作为新成本。
            # 后续可以升级为加权平均成本。
            account.cash -= cash_needed
            account.update_position(
                ts_code=ts_code,
                shares=new_shares,
                cost=exec_price
            )

        else:
            # 卖出数量不能超过当前持仓
            sell_shares = min(shares, old_shares)

            if sell_shares <= 0:
                return

            trade_value = sell_shares * exec_price
            commission = self._calc_commission(trade_value)
            stamp_tax = self._calc_stamp_tax(trade_value, side)
            total_cost = commission + stamp_tax

            cash_received = trade_value - total_cost
            new_shares = old_shares - sell_shares

            account.cash += cash_received
            account.update_position(
                ts_code=ts_code,
                shares=new_shares,
                cost=exec_price
            )

            shares = sell_shares

        self.trades.append({
            "trade_date": trade_date,
            "ts_code": ts_code,
            "side": side,
            "shares": shares,
            "price": price,
            "exec_price": exec_price,
            "trade_value": trade_value,
            "commission": commission,
            "stamp_tax": stamp_tax,
            "total_cost": total_cost
        })

    def get_trade_log(self) -> pd.DataFrame:
        """
        获取交易记录。
        """

        if not self.trades:
            return pd.DataFrame()

        return pd.DataFrame(self.trades)