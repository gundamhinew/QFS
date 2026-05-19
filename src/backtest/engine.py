from __future__ import annotations

import pandas as pd

from src.backtest.account import Account
from src.backtest.broker import Broker
from src.backtest.trading_rules import can_buy, can_sell
from src.datahub.data_manager import DataManager


class BacktestEngine:
    """
    回测引擎。

    作用：
    1. 按交易日推进回测；
    2. 将信号日期映射到下一交易日执行，避免 T 日收盘信号 T 日成交；
    3. 调用 Broker 执行交易；
    4. 更新 Account；
    5. 记录净值曲线和交易限制日志。

    当前版本：
    - T 日 target_positions 只代表信号日期；
    - T+1 日 open 成交；
    - T+1 日 close 估值；
    - 在引擎层处理涨跌停买卖限制，Broker 不依赖行情数据源。
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

        # 记录因为涨跌停、缺行情等原因没有成交的指令。
        self.restriction_logs: list[dict] = []

    @staticmethod
    def _find_next_trade_date(
        signal_date: pd.Timestamp,
        trade_dates: list[pd.Timestamp]
    ) -> pd.Timestamp | None:
        """
        为信号日期寻找下一个可交易日。

        注意这里必须严格大于 signal_date，不能把信号日期和执行日期混用。
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

        第一版单独维护 restriction_log，不污染 Broker 的真实成交记录。
        """

        self.restriction_logs.append({
            "signal_date": signal_date,
            "trade_date": execute_date,
            "ts_code": ts_code,
            "side": side,
            "reason": reason
        })

    def _prepare_price_data(
        self,
        start: str,
        end: str
    ) -> pd.DataFrame:
        """
        读取并补充回测所需行情数据。

        行情数据提供交易日序列、open 成交价、close 估值价以及涨跌停判断字段。
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

        # 尽量补充 name、market 字段，供涨跌停规则识别 ST、创业板、科创板。
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
            策略生成的目标持仓。trade_date 表示信号日期，不是成交日期。

        start, end:
            回测区间。

        返回
        ----
        equity_curve:
            净值曲线，trade_date 记录实际执行日期。
        """

        if target_positions.empty:
            return pd.DataFrame()

        price_df = self._prepare_price_data(
            start=start,
            end=end
        )

        if price_df.empty:
            return pd.DataFrame()

        targets = target_positions.copy()
        targets["signal_date"] = pd.to_datetime(
            targets["trade_date"]
        )

        # 交易日序列必须从行情数据获得，而不是只依赖信号日期。
        trade_dates = sorted(
            price_df["trade_date"].dropna().unique()
        )

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

            # 信号日目标组合。
            today_target = targets[
                targets["signal_date"] == signal_date
            ].copy()

            # 执行日行情。open 用于成交，close 用于收盘估值。
            execute_price = price_df[
                price_df["trade_date"] == execute_date
            ].copy()

            if execute_price.empty:
                continue

            open_map = self._build_price_map(
                execute_price,
                price_col="open"
            )
            close_map = self._build_price_map(
                execute_price,
                price_col="close"
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

            # ======================
            # 第一步：卖出不在目标组合里的股票
            # ======================

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

                self.broker.execute_order(
                    account=self.account,
                    trade_date=execute_date,
                    ts_code=ts_code,
                    side="sell",
                    shares=shares,
                    price=open_map[ts_code]
                )

            # ======================
            # 第二步：调整目标组合
            # ======================

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

                # 目标买卖股数。第一版暂不强制按 100 股手数取整。
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

                    self.broker.execute_order(
                        account=self.account,
                        trade_date=execute_date,
                        ts_code=ts_code,
                        side="buy",
                        shares=target_shares,
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

                    self.broker.execute_order(
                        account=self.account,
                        trade_date=execute_date,
                        ts_code=ts_code,
                        side="sell",
                        shares=abs(target_shares),
                        price=open_price
                    )

            # ======================
            # 第三步：执行日收盘后记录账户状态
            # ======================

            self.account.record_daily_snapshot(
                trade_date=execute_date,
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
