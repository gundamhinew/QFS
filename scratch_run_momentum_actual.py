from pathlib import Path
import pandas as pd

from src.datahub.data_manager import DataManager
from src.universe.universe_builder import UniverseBuilder
from src.factors.momentum import MomentumFactor
from src.factors.processor import FactorProcessor
from src.strategies.top_n_strategy import TopNEqualWeightStrategy
from src.backtest.engine import BacktestEngine
from src.backtest.performance import PerformanceAnalyzer


PROJECT_ROOT = Path(__file__).resolve().parent


def run_once(
    start="2020-01-01",
    end="2020-12-31",
    lookback=60,
    top_n=50,
    initial_cash=1_000_000,
    rebalance_frequency="monthly",
):
    print("===== params =====")
    print("start:", start)
    print("end:", end)
    print("lookback:", lookback)
    print("top_n:", top_n)
    print("initial_cash:", initial_cash)
    print("rebalance_frequency:", rebalance_frequency)

    dm = DataManager(raw_root=str(PROJECT_ROOT / "data" / "raw"))

    print("\n===== build universe =====")
    universe_builder = UniverseBuilder(dm=dm)
    universe = universe_builder.build(start=start, end=end)
    print("universe.shape:", universe.shape)
    print(universe.head())

    universe_codes = sorted(universe["ts_code"].dropna().unique().tolist())
    print("universe unique codes:", len(universe_codes))

    print("\n===== build raw factor =====")
    factor = MomentumFactor(dm=dm, params={"lookback": lookback})
    raw_factor = factor.build(
        start=start,
        end=end,
        universe=universe_codes,
    )
    print("raw_factor.shape:", raw_factor.shape)
    print(raw_factor.head())

    raw_factor["trade_date"] = pd.to_datetime(raw_factor["trade_date"])
    universe["trade_date"] = pd.to_datetime(universe["trade_date"])

    print("\n===== filter factor by daily universe =====")
    factor_in_universe = raw_factor.merge(
        universe[["trade_date", "ts_code"]],
        on=["trade_date", "ts_code"],
        how="inner",
    )
    print("factor_in_universe.shape:", factor_in_universe.shape)
    print(factor_in_universe.head())

    print("\n===== process factor =====")
    processor = FactorProcessor()
    processed_factor = processor.process_single_factor(
        factor_in_universe,
        direction="positive",
        min_count=top_n,
    )
    print("processed_factor.shape:", processed_factor.shape)
    print(processed_factor.head())

    print("\n===== generate target positions =====")
    strategy = TopNEqualWeightStrategy(params={"top_n": top_n})
    target_positions = strategy.generate_target_positions(processed_factor)
    print("target_positions.shape:", target_positions.shape)
    print(target_positions.head())
    print("target date count:", target_positions["trade_date"].nunique())

    print("\n===== run backtest =====")
    engine = BacktestEngine(
        dm=dm,
        initial_cash=initial_cash,
        rebalance_frequency=rebalance_frequency,
    )

    equity_curve = engine.run_backtest(
        target_positions=target_positions,
        start=start,
        end=end,
    )

    trade_log = engine.get_trade_log()
    restriction_log = engine.get_restriction_log()

    print("\n===== equity_curve.tail() =====")
    print(equity_curve.tail())

    print("\n===== trade_log.head() =====")
    print(trade_log.head())

    print("\n===== restriction_log.head() =====")
    print(restriction_log.head())

    print("\n===== basic checks =====")
    print("equity_curve.shape:", equity_curve.shape)
    print("trade_log.shape:", trade_log.shape)
    print("restriction_log.shape:", restriction_log.shape)

    if not trade_log.empty:
        print("actual trade date count:", trade_log["trade_date"].nunique())

        buy_log = trade_log[trade_log["side"] == "buy"].copy()
        invalid_buy = buy_log[buy_log["shares"] % 100 != 0]
        print("invalid buy count:", len(invalid_buy))
        if len(invalid_buy) > 0:
            print(invalid_buy.head())

    print("\n===== performance =====")
    analyzer = PerformanceAnalyzer()
    performance = analyzer.analyze(
        equity_curve=equity_curve,
        trade_log=trade_log,
    )

    for k, v in performance.items():
        print(f"{k}: {v}")

    return equity_curve, trade_log, restriction_log, performance


if __name__ == "__main__":
    run_once(
        start="2020-01-01",
        end="2020-12-31",
        lookback=60,
        top_n=50,
        initial_cash=1_000_000,
        rebalance_frequency="monthly",
    )