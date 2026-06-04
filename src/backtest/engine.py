from __future__ import annotations

import pandas as pd

from src.backtest.account import Account
from src.backtest.broker import Broker
from src.backtest.order_utils import round_buy_shares, round_sell_shares
from src.backtest.rebalance import filter_target_positions_by_rebalance
from src.backtest.trading_rules import can_buy, can_sell
from src.datahub.data_manager import DataManager


class BacktestEngine:
    """
    回测引擎。

    职责：
    1. 按交易日推进回测；
    2. 将 T 日信号映射到 T+1 交易日 open 执行；
    3. 只在调仓执行日交易；
    4. 每个交易日 close 后记录账户快照；
    5. 在引擎层处理交易限制，Broker 只负责执行订单和更新账户。
    """

    def __init__(
        self,
        dm: DataManager,
        initial_cash: float = 1_000_000,
        rebalance_frequency: str = "daily"
    ):

        self.dm = dm
        self.rebalance_frequency = rebalance_frequency

        self.account = Account(
            initial_cash=initial_cash
        )

        self.broker = Broker()

        # 记录因为涨跌停、缺行情、整手约束等原因没有成交的指令。
        self.restriction_logs: list[dict] = []

    @staticmethod
    def _find_next_trade_date(
        signal_date: pd.Timestamp,
        trade_dates: list[pd.Timestamp]
    ) -> pd.Timestamp | None:
        """
        为信号日期寻找下一个交易日。
        """

        for trade_date in trade_dates:
            if trade_date > signal_date:
                return trade_date

        return None

    @staticmethod
    def _build_price_map(
        price_df: pd.DataFrame,
        price_col: str
    ) -> dict[str, float]:
        """
        根据指定价格列构建 ts_code -> price 的字典。
        """

        valid = price_df.dropna(subset=[price_col])

        return dict(
            zip(
                valid["ts_code"],
                valid[price_col]
            )
        )

    def _record_restriction(
        self,
        signal_date: pd.Timestamp,
        execute_date: pd.Timestamp | None,
        ts_code: str,
        side: str,
        reason: str
    ):
        """
        记录未成交原因。
        """

        self.restriction_logs.append({
            "signal_date": signal_date,
            "trade_date": execute_date,
            "ts_code": ts_code,
            "side": side,
            "reason": reason
        })

    def _cap_buy_shares_by_cash(
        self,
        shares: int,
        price: float
    ) -> int:
        """
        根据当前可用现金限制买入股数，并保持 A 股整手约束。
        """

        if shares <= 0 or price <= 0:
            return 0

        exec_price = price * (1 + self.broker.slippage_rate)
        shares = int(shares)

        while shares > 0:
            trade_value = shares * exec_price
            commission = self.broker._calc_commission(trade_value)
            cash_needed = trade_value + commission

            if cash_needed <= self.account.cash:
                return shares

            shares -= 100

        return 0

    def _prepare_price_data(
        self,
        start: str,
        end: str
    ) -> pd.DataFrame:
        """
        读取并补充回测所需行情数据。
        """

        price_df = self.dm.get_daily_price(
            start=start,
            end=end,
            ts_codes=None
        )

        if price_df.empty:
            return price_df

        price_df = price_df.copy()
        price_df["trade_date"] = pd.to_datetime(
            price_df["trade_date"]
        )

        # 补充股票基础信息，供涨跌停规则识别 ST、创业板、科创板等。
        stock_basic = self.dm.get_stock_basic(active_only=False)

        if not stock_basic.empty:
            keep_cols = [
                col for col in [
                    "ts_code",
                    "name",
                    "market",
                    "exchange",
                ]
                if col in stock_basic.columns
            ]
            price_df = price_df.merge(
                stock_basic[keep_cols],
                on="ts_code",
                how="left"
            )

        return price_df.sort_values(
            ["trade_date", "ts_code"]
        ).reset_index(drop=True)

    def _build_execute_plan(
        self,
        targets: pd.DataFrame,
        trade_dates: list[pd.Timestamp]
    ) -> dict[pd.Timestamp, list[tuple[pd.Timestamp, pd.DataFrame]]]:
        """
        构建 execute_date -> [(signal_date, target_df)] 的调仓计划。
        """

        execute_plan: dict[pd.Timestamp, list[tuple[pd.Timestamp, pd.DataFrame]]] = {}

        signal_dates = sorted(
            targets["signal_date"].dropna().unique()
        )

        for signal_date in signal_dates:
            execute_date = self._find_next_trade_date(
                signal_date=signal_date,
                trade_dates=trade_dates
            )

            if execute_date is None:
                continue

            today_target = targets[
                targets["signal_date"] == signal_date
            ].copy()

            execute_plan.setdefault(
                execute_date,
                []
            ).append((signal_date, today_target))

        return execute_plan

    def _execute_rebalance(
        self,
        signal_date: pd.Timestamp,
        execute_date: pd.Timestamp,
        today_target: pd.DataFrame,
        execute_price: pd.DataFrame
    ):
        """
        在调仓执行日按 open 价格执行目标组合调整。
        """

        open_map = self._build_price_map(
            execute_price,
            price_col="open"
        )

        row_map = {
            row["ts_code"]: row
            for _, row in execute_price.iterrows()
        }

        # 使用执行日 open 估算调仓前总资产，保持成交价和 sizing 口径一致。
        total_equity = self.account.get_total_equity(
            price_map=open_map
        )

        current_codes = set(
            self.account.positions.keys()
        )

        target_codes = set(
            today_target["ts_code"]
        )

        # 第一步：卖出不在目标组合里的股票。
        sell_codes = current_codes - target_codes

        for ts_code in sell_codes:
            if ts_code not in open_map:
                self._record_restriction(
                    signal_date=signal_date,
                    execute_date=execute_date,
                    ts_code=ts_code,
                    side="sell",
                    reason="execute_date 缺少 open 行情，无法卖出"
                )
                continue

            price_row = row_map[ts_code]

            if not can_sell(price_row):
                self._record_restriction(
                    signal_date=signal_date,
                    execute_date=execute_date,
                    ts_code=ts_code,
                    side="sell",
                    reason="跌停限制，无法卖出"
                )
                continue

            shares = self.account.get_position_shares(
                ts_code
            )

            shares_to_sell = round_sell_shares(
                raw_shares_to_sell=shares,
                current_shares=shares,
                allow_full_exit=True
            )

            if shares_to_sell <= 0:
                self._record_restriction(
                    signal_date=signal_date,
                    execute_date=execute_date,
                    ts_code=ts_code,
                    side="sell",
                    reason="卖出股数不足一手且非清仓，未下单"
                )
                continue

            self.broker.execute_order(
                account=self.account,
                trade_date=execute_date,
                ts_code=ts_code,
                side="sell",
                shares=shares_to_sell,
                price=open_map[ts_code]
            )

        # 第二步：调整目标组合内股票。
        for _, row in today_target.iterrows():
            ts_code = row["ts_code"]

            if ts_code not in open_map:
                self._record_restriction(
                    signal_date=signal_date,
                    execute_date=execute_date,
                    ts_code=ts_code,
                    side="buy",
                    reason="execute_date 缺少 open 行情，无法调仓"
                )
                continue

            target_weight = row["target_weight"]
            open_price = open_map[ts_code]

            target_value = (
                total_equity * target_weight
            )

            current_shares = (
                self.account.get_position_shares(
                    ts_code
                )
            )

            current_value = (
                current_shares * open_price
            )

            diff_value = (
                target_value - current_value
            )

            # 目标买卖股数，实际下单前按 A 股 100 股整数交易规则取整。
            target_shares = (
                diff_value // open_price
            )

            price_row = row_map[ts_code]

            if target_shares > 0:
                if not can_buy(price_row):
                    self._record_restriction(
                        signal_date=signal_date,
                        execute_date=execute_date,
                        ts_code=ts_code,
                        side="buy",
                        reason="涨停限制，无法买入"
                    )
                    continue

                buy_shares = round_buy_shares(target_shares)
                buy_shares = self._cap_buy_shares_by_cash(
                    shares=buy_shares,
                    price=open_price
                )

                if buy_shares <= 0:
                    self._record_restriction(
                        signal_date=signal_date,
                        execute_date=execute_date,
                        ts_code=ts_code,
                        side="buy",
                        reason="买入股数不足一手，未下单"
                    )
                    continue

                self.broker.execute_order(
                    account=self.account,
                    trade_date=execute_date,
                    ts_code=ts_code,
                    side="buy",
                    shares=buy_shares,
                    price=open_price
                )

            elif target_shares < 0:
                if not can_sell(price_row):
                    self._record_restriction(
                        signal_date=signal_date,
                        execute_date=execute_date,
                        ts_code=ts_code,
                        side="sell",
                        reason="跌停限制，无法卖出"
                    )
                    continue

                sell_shares = round_sell_shares(
                    raw_shares_to_sell=abs(target_shares),
                    current_shares=current_shares,
                    allow_full_exit=True
                )

                if sell_shares <= 0:
                    self._record_restriction(
                        signal_date=signal_date,
                        execute_date=execute_date,
                        ts_code=ts_code,
                        side="sell",
                        reason="卖出股数不足一手且非清仓，未下单"
                    )
                    continue

                self.broker.execute_order(
                    account=self.account,
                    trade_date=execute_date,
                    ts_code=ts_code,
                    side="sell",
                    shares=sell_shares,
                    price=open_price
                )

    def run_backtest(
        self,
        target_positions: pd.DataFrame,
        start: str,
        end: str
    ) -> pd.DataFrame:
        """
        运行回测。

        `target_positions.trade_date` 表示信号日期，不是成交日期。
        调仓频率只控制哪些 signal_date 生效；估值仍然每天记录。
        """

        if target_positions.empty:
            return pd.DataFrame()

        price_df = self._prepare_price_data(
            start=start,
            end=end
        )

        if price_df.empty:
            return pd.DataFrame()

        targets = filter_target_positions_by_rebalance(
            target_positions=target_positions,
            frequency=self.rebalance_frequency
        )

        if targets.empty:
            return pd.DataFrame()

        targets = targets.copy()
        targets["signal_date"] = pd.to_datetime(
            targets["trade_date"]
        )

        # 交易日序列必须来自行情数据，而不是只依赖信号日期。
        trade_dates = sorted(
            price_df["trade_date"].dropna().unique()
        )

        execute_plan = self._build_execute_plan(
            targets=targets,
            trade_dates=trade_dates
        )

        # 主循环遍历所有交易日：只有调仓执行日交易，但每天都用 close 估值。
        for trade_date in trade_dates:
            daily_price = price_df[
                price_df["trade_date"] == trade_date
            ].copy()

            if daily_price.empty:
                continue

            if trade_date in execute_plan:
                for signal_date, today_target in execute_plan[trade_date]:
                    self._execute_rebalance(
                        signal_date=signal_date,
                        execute_date=trade_date,
                        today_target=today_target,
                        execute_price=daily_price
                    )

            close_map = self._build_price_map(
                daily_price,
                price_col="close"
            )

            self.account.record_daily_snapshot(
                trade_date=trade_date,
                price_map=close_map
            )

        return self.account.get_equity_curve()

    def get_trade_log(self) -> pd.DataFrame:
        """
        获取成交记录。
        """

        return self.broker.get_trade_log()

    def get_restriction_log(self) -> pd.DataFrame:
        """
        获取交易限制记录。
        """

        if not self.restriction_logs:
            return pd.DataFrame()

        return pd.DataFrame(self.restriction_logs)
