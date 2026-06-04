from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from src.backtest.engine import BacktestEngine
from src.backtest.performance import PerformanceAnalyzer
from src.datahub.data_manager import DataManager
from src.factors.processor import FactorProcessor
from src.factors.registry import FACTOR_REGISTRY
from src.runner.config_loader import load_strategy_config
from src.strategies.registry import STRATEGY_REGISTRY
from src.universe.universe_builder import UniverseBuilder


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _resolve_project_path(path_value: str) -> Path:
    """
    将配置中的相对路径解析到项目根目录。
    """

    path = Path(path_value)

    if path.is_absolute():
        return path

    return PROJECT_ROOT / path


def _get_required_section(
    config: dict,
    section_name: str
) -> dict:
    """
    获取必需配置段，并给出清晰错误。
    """

    section = config.get(section_name)

    if not isinstance(section, dict):
        raise ValueError(
            f"Config section '{section_name}' is required and must be a mapping"
        )

    return section


def _build_factor(
    factor_config: dict,
    dm: DataManager
):
    """
    根据 factor.type 从 FACTOR_REGISTRY 创建因子对象。
    """

    factor_type = factor_config.get("type")

    if factor_type not in FACTOR_REGISTRY:
        available = ", ".join(sorted(FACTOR_REGISTRY.keys()))
        raise ValueError(
            f"Unknown factor.type '{factor_type}'. Available factors: {available}"
        )

    factor_cls = FACTOR_REGISTRY[factor_type]

    return factor_cls(
        dm=dm,
        params=factor_config.get("params", {})
    )


def _build_strategy(
    portfolio_config: dict
):
    """
    根据 portfolio.type 从 STRATEGY_REGISTRY 创建策略对象。
    """

    portfolio_type = portfolio_config.get("type")

    if portfolio_type not in STRATEGY_REGISTRY:
        available = ", ".join(sorted(STRATEGY_REGISTRY.keys()))
        raise ValueError(
            f"Unknown portfolio.type '{portfolio_type}'. "
            f"Available strategies: {available}"
        )

    strategy_cls = STRATEGY_REGISTRY[portfolio_type]

    return strategy_cls(
        params=portfolio_config.get("params", {})
    )


def run_backtest_from_config(config_path: str) -> dict:
    """
    使用策略配置文件运行完整回测流程。
    """

    config = load_strategy_config(config_path)

    data_config = _get_required_section(config, "data")
    backtest_config = _get_required_section(config, "backtest")
    universe_config = _get_required_section(config, "universe")
    factor_config = _get_required_section(config, "factor")
    portfolio_config = _get_required_section(config, "portfolio")
    output_config = config.get("output", {})

    strategy_name = config.get("strategy_name", Path(config_path).stem)
    start = backtest_config["start"]
    end = backtest_config["end"]
    initial_cash = backtest_config.get("initial_cash", 1_000_000)
    rebalance_frequency = backtest_config.get("rebalance_frequency", "daily")

    print("===== strategy config =====")
    print(f"strategy_name: {strategy_name}")
    print(f"start: {start}")
    print(f"end: {end}")
    print(f"factor.type: {factor_config.get('type')}")
    print(f"factor.params: {factor_config.get('params', {})}")
    print(f"portfolio.type: {portfolio_config.get('type')}")
    print(f"portfolio.params: {portfolio_config.get('params', {})}")
    print(f"initial_cash: {initial_cash}")
    print(f"rebalance_frequency: {rebalance_frequency}")

    raw_root = _resolve_project_path(
        data_config.get("raw_root", "data/raw")
    )

    dm = DataManager(raw_root=str(raw_root))

    universe_builder = UniverseBuilder(
        dm=dm,
        min_list_days=universe_config.get("min_list_days", 120),
        min_close=universe_config.get("min_close", 2.0),
        min_amount=universe_config.get(
            "min_amount_yuan",
            universe_config.get("min_amount", 30_000_000)
        )
    )
    universe = universe_builder.build(
        start=start,
        end=end
    )

    print("\n===== universe.shape =====")
    print(universe.shape)

    if universe.empty:
        raise ValueError("Universe is empty.")

    universe_codes = sorted(
        universe["ts_code"].dropna().unique().tolist()
    )

    factor = _build_factor(
        factor_config=factor_config,
        dm=dm
    )
    raw_factor = factor.build(
        start=start,
        end=end,
        universe=universe_codes
    )

    print("\n===== raw_factor.shape =====")
    print(raw_factor.shape)

    if raw_factor.empty:
        raise ValueError("Raw factor is empty.")

    raw_factor = raw_factor.copy()
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
        direction=factor_config.get("direction", "positive"),
        min_count=factor_config.get("min_count")
    )

    print("\n===== processed_factor.shape =====")
    print(processed_factor.shape)

    strategy = _build_strategy(
        portfolio_config=portfolio_config
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

    print("\n===== execution diagnostics =====")
    print(f"equity_curve.shape: {equity_curve.shape}")
    print(f"trade_date_count: {equity_curve['trade_date'].nunique() if not equity_curve.empty else 0}")
    print(f"trade_execution_date_count: {trade_log['trade_date'].nunique() if not trade_log.empty else 0}")

    print("\n===== performance summary =====")
    for key, value in performance.items():
        print(f"{key}: {value}")

    # 当前版本只打印结果，不落盘，避免生成额外输出文件。
    if output_config.get("save_result", False):
        print("save_result=true is configured, but file output is not implemented yet.")

    return {
        "config": config,
        "universe": universe,
        "raw_factor": raw_factor,
        "factor_in_universe": factor_in_universe,
        "processed_factor": processed_factor,
        "target_positions": target_positions,
        "equity_curve": equity_curve,
        "trade_log": trade_log,
        "restriction_log": restriction_log,
        "performance": performance,
    }


def main():
    """
    命令行入口。
    """

    parser = argparse.ArgumentParser(
        description="Run a config-driven QFS backtest."
    )
    parser.add_argument(
        "--config",
        required=True,
        help="Path to strategy YAML config."
    )

    args = parser.parse_args()

    run_backtest_from_config(
        config_path=args.config
    )


if __name__ == "__main__":
    main()
