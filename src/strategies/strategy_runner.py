from __future__ import annotations

from typing import Any

import pandas as pd

from src.alpha_models import ALPHA_MODEL_REGISTRY
from src.backtest.engine import BacktestEngine
from src.backtest.performance import PerformanceAnalyzer
from src.datahub.data_manager import DataManager
from src.factors.store import FactorStore
from src.alpha_models.checker import ModelChecker
from src.core.config_loader import (
    load_factor_config,
    load_model_config,
    load_strategy_config,
    resolve_project_path,
)
from src.factors.factor_runner import _build_factor_data
from src.alpha_models.model_runner import _factor_alias
from src.core.run_metadata import base_run_manifest, make_run_id, row_counts, utc_now_iso
from src.strategies.pipeline import StrategyPipeline
from src.core.artifact_store import write_json, write_parquet, write_yaml_snapshot


def _get_mapping(config: dict, section: str) -> dict:
    value = config.get(section, {})
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise ValueError(f"Config section '{section}' must be a mapping")
    return value


def _load_or_build_processed_factors(
    model_config: dict,
    dm: DataManager,
    store: FactorStore,
) -> dict[str, pd.DataFrame]:
    processed = {}

    for item in model_config.get("factors", []):
        alias = _factor_alias(item)
        factor_config = load_factor_config(item["config"])

        if store.has_cache(factor_config):
            cached = store.load(factor_config)
            processed[alias] = cached["processed_factor"]
            continue

        built = _build_factor_data(config=factor_config, dm=dm)
        store.save(
            config=factor_config,
            raw_factor=built["raw_factor"],
            processed_factor=built["processed_factor"],
        )
        processed[alias] = built["processed_factor"]

    return processed


def _build_model_scores(
    model_config: dict,
    processed_factors: dict[str, pd.DataFrame],
) -> pd.DataFrame:
    model_type = model_config["model_type"]

    if model_type not in ALPHA_MODEL_REGISTRY:
        raise ValueError(
            f"Unknown model_type '{model_type}'. "
            f"Available: {sorted(ALPHA_MODEL_REGISTRY)}"
        )

    model = ALPHA_MODEL_REGISTRY[model_type]()
    return model.build(
        processed_factors=processed_factors,
        config=model_config,
    )


def run_strategy_backtest_from_config(
    config_path: str,
    dm: DataManager | None = None,
    store: FactorStore | None = None,
) -> dict[str, Any]:
    strategy_config = load_strategy_config(config_path)
    run_id = make_run_id()
    started_at = utc_now_iso()
    output_config = strategy_config.get("output", {})
    output_root = output_config.get("output_root", "artifacts/strategy_runs")
    run_dir = (
        resolve_project_path(output_root)
        / strategy_config["strategy_id"]
        / run_id
    )
    save_result = output_config.get("save_result", True)

    model_config = None
    processed_factors = {}
    model_scores = pd.DataFrame()
    target_positions = pd.DataFrame()
    equity_curve = pd.DataFrame()
    trade_log = pd.DataFrame()
    restriction_log = pd.DataFrame()
    performance = {}

    try:
        model_config = load_model_config(strategy_config["model"]["config"])
        ModelChecker().check(model_config)

        data_config = _get_mapping(strategy_config, "data")
        period = _get_mapping(strategy_config, "period")
        backtest_config = _get_mapping(strategy_config, "backtest")
        raw_root = resolve_project_path(data_config.get("raw_root", "data/raw"))
        dm = dm or DataManager(raw_root=str(raw_root))
        store = store or FactorStore()

        processed_factors = _load_or_build_processed_factors(
            model_config=model_config,
            dm=dm,
            store=store,
        )
        model_scores = _build_model_scores(
            model_config=model_config,
            processed_factors=processed_factors,
        )
        target_positions = StrategyPipeline().build_target_positions(
            model_scores=model_scores,
            config=strategy_config,
        )

        # StrategyPipeline already applies the rebalance policy. The legacy engine
        # is kept on daily frequency here to avoid duplicate signal-date filtering.
        engine = BacktestEngine(
            dm=dm,
            initial_cash=backtest_config.get("initial_cash", 1_000_000),
            rebalance_frequency="daily",
        )
        equity_curve = engine.run_backtest(
            target_positions=target_positions,
            start=period["start"],
            end=period["end"],
        )
        trade_log = engine.get_trade_log()
        restriction_log = engine.get_restriction_log()
        performance = PerformanceAnalyzer().analyze(
            equity_curve=equity_curve,
            trade_log=trade_log,
        )

        run_manifest = base_run_manifest(
            run_id=run_id,
            run_type="strategy",
            started_at=started_at,
            finished_at=utc_now_iso(),
            config_path=config_path,
            config=strategy_config,
            status="success",
            error_message=None,
            rows=row_counts(
                processed_factors=sum(len(df) for df in processed_factors.values()),
                model_scores=model_scores,
                target_positions=target_positions,
                equity_curve=equity_curve,
                trade_log=trade_log,
                restriction_log=restriction_log,
            ),
            extra={
                "strategy_id": strategy_config["strategy_id"],
                "model_id": model_config["model_id"],
                "execution_assumption": strategy_config.get("execution_assumption", {}),
                "used_strategy_pipeline": True,
            },
        )

        if save_result:
            write_yaml_snapshot(run_dir / "config_snapshot.yaml", strategy_config)
            write_yaml_snapshot(run_dir / "model_config_snapshot.yaml", model_config)
            write_json(run_dir / "run_manifest.json", run_manifest)
            write_json(run_dir / "performance.json", performance)
            write_parquet(run_dir / "target_positions.parquet", target_positions)
            write_parquet(run_dir / "equity_curve.parquet", equity_curve)
            write_parquet(run_dir / "trade_log.parquet", trade_log)
            write_parquet(run_dir / "restriction_log.parquet", restriction_log)
    except Exception as exc:
        run_manifest = base_run_manifest(
            run_id=run_id,
            run_type="strategy",
            started_at=started_at,
            finished_at=utc_now_iso(),
            config_path=config_path,
            config=strategy_config,
            status="failed",
            error_message=str(exc),
            rows=row_counts(
                processed_factors=sum(len(df) for df in processed_factors.values()),
                model_scores=model_scores,
                target_positions=target_positions,
                equity_curve=equity_curve,
                trade_log=trade_log,
                restriction_log=restriction_log,
            ),
            extra={
                "strategy_id": strategy_config.get("strategy_id"),
                "model_id": model_config.get("model_id") if model_config else None,
                "execution_assumption": strategy_config.get("execution_assumption", {}),
                "used_strategy_pipeline": True,
            },
        )
        if save_result:
            write_yaml_snapshot(run_dir / "config_snapshot.yaml", strategy_config)
            if model_config is not None:
                write_yaml_snapshot(run_dir / "model_config_snapshot.yaml", model_config)
            write_json(run_dir / "run_manifest.json", run_manifest)
        raise

    return {
        "strategy_config": strategy_config,
        "model_config": model_config,
        "processed_factors": processed_factors,
        "model_scores": model_scores,
        "target_positions": target_positions,
        "equity_curve": equity_curve,
        "trade_log": trade_log,
        "restriction_log": restriction_log,
        "performance": performance,
        "run_manifest": run_manifest,
        "run_dir": run_dir if save_result else None,
    }


def format_strategy_backtest_summary(result: dict[str, Any]) -> str:
    config = result["strategy_config"]
    performance = result["performance"]

    lines = [
        "===== strategy backtest summary =====",
        f"strategy_id: {config['strategy_id']}",
        f"target_positions.shape: {result['target_positions'].shape}",
        f"equity_curve.shape: {result['equity_curve'].shape}",
        f"trade_log.shape: {result['trade_log'].shape}",
        f"restriction_log.shape: {result['restriction_log'].shape}",
        f"run_dir: {result['run_dir']}",
        "",
        "===== performance =====",
    ]
    for key, value in performance.items():
        lines.append(f"{key}: {value}")

    return "\n".join(lines)


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Run a StrategyPipeline backtest."
    )
    parser.add_argument("--config", required=True)
    args = parser.parse_args()

    result = run_strategy_backtest_from_config(args.config)
    print(format_strategy_backtest_summary(result))


if __name__ == "__main__":
    main()
