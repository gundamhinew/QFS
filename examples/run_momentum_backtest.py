from __future__ import annotations

"""
This is only a demonstration script.

The recommended production-style entry point is:
python -m src.runner.backtest_runner --config configs/strategies/momentum_top50_monthly.yaml
"""

import sys
from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.backtest.engine import BacktestEngine
from src.backtest.performance import PerformanceAnalyzer
from src.datahub.data_manager import DataManager
from src.factors.momentum import MomentumFactor
from src.factors.processor import FactorProcessor
from src.strategies.top_n_strategy import TopNEqualWeightStrategy
from src.universe.universe_builder import UniverseBuilder


def main():
    """
    端到端运行 60 日动量 TopN 等权策略回测。

    流程：
    1. 初始化 DataManager；
    2. 构建 Universe；
    3. 计算动量因子；
    4. 用 FactorProcessor 标准化处理；
    5. 生成目标持仓；
    6. 用 BacktestEngine 执行 T+1 回测；
    7. 输出净值、交易记录和绩效摘要。
    """

    start = "2020-01-01"
    end = "2020-12-31"
    lookback = 60
    top_n = 50
    initial_cash = 1_000_000
    rebalance_frequency = "monthly"

    print("===== backtest parameters =====")
    print(f"start: {start}")
    print(f"end: {end}")
    print(f"lookback: {lookback}")
    print(f"top_n: {top_n}")
    print(f"initial_cash: {initial_cash}")
    print(f"rebalance_frequency: {rebalance_frequency}")

    dm = DataManager(raw_root=str(PROJECT_ROOT / "data" / "raw"))

    universe_builder = UniverseBuilder(dm=dm)
    universe = universe_builder.build(
        start=start,
        end=end
    )

    if universe.empty:
        print("Universe is empty.")
        return

    print("\n===== universe.shape =====")
    print(universe.shape)

    universe_codes = sorted(
        universe["ts_code"].dropna().unique().tolist()
    )

    factor = MomentumFactor(
        dm=dm,
        params={"lookback": lookback}
    )
    raw_factor = factor.build(
        start=start,
        end=end,
        universe=universe_codes
    )

    if raw_factor.empty:
        print("Raw factor is empty.")
        return

    print("\n===== raw_factor.shape =====")
    print(raw_factor.shape)

    raw_factor["trade_date"] = pd.to_datetime(raw_factor["trade_date"])

    # 用每日股票池限制因子横截面，避免策略选到 Universe 外股票。
    factor_in_universe = raw_factor.merge(
        universe[["trade_date", "ts_code"]],
        on=["trade_date", "ts_code"],
        how="inner"
    )

    print("\n===== factor_in_universe.shape =====")
    print(factor_in_universe.shape)

    processor = FactorProcessor()
    processed_factor = processor.process_single_factor(
        factor_in_universe,
        direction="positive",
        min_count=top_n
    )

    print("\n===== processed_factor.shape =====")
    print(processed_factor.shape)

    strategy = TopNEqualWeightStrategy(
        params={"top_n": top_n}
    )
    target_positions = strategy.generate_target_positions(
        processed_factor
    )

    print("\n===== target_positions.shape =====")
    print(target_positions.shape)

    engine = BacktestEngine(
        dm=dm,
        initial_cash=initial_cash,
        rebalance_frequency=rebalance_frequency
    )
    equity_curve = engine.run_backtest(
        target_positions=target_positions,
        start=start,
        end=end
    )

    trade_log = engine.get_trade_log()
    restriction_log = engine.get_restriction_log()

    analyzer = PerformanceAnalyzer()
    performance = analyzer.analyze(
        equity_curve=equity_curve,
        trade_log=trade_log
    )

    print("\n===== equity_curve.tail() =====")
    print(equity_curve.tail())

    print("\n===== trade_log.head() =====")
    print(trade_log.head())

    print("\n===== restriction_log.head() =====")
    print(restriction_log.head())

    print("\n===== performance summary =====")
    for key, value in performance.items():
        print(f"{key}: {value}")


if __name__ == "__main__":
    main()
