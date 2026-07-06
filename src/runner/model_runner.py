from __future__ import annotations

from typing import Any

import pandas as pd

from src.alpha_models import ALPHA_MODEL_REGISTRY
from src.alpha_models.aligner import FactorAligner
from src.datahub.data_manager import DataManager
from src.factor_lab.forward_returns import calculate_forward_returns
from src.factor_lab.store import FactorStore
from src.model_lab.checker import ModelChecker
from src.model_lab.evaluator import ModelEvaluator
from src.model_lab.report import write_json, write_parquet, write_yaml_snapshot
from src.runner.config_loader import (
    load_factor_config,
    load_model_config,
    resolve_project_path,
)
from src.runner.run_metadata import base_run_manifest, make_run_id, row_counts, utc_now_iso


def _factor_alias(item: dict) -> str:
    return item.get("alias") or item.get("factor_id")


def load_processed_factors(
    model_config: dict,
    store: FactorStore | None = None,
) -> tuple[dict[str, pd.DataFrame], dict[str, dict]]:
    store = store or FactorStore()
    processed: dict[str, pd.DataFrame] = {}
    factor_configs: dict[str, dict] = {}

    for item in model_config.get("factors", []):
        alias = _factor_alias(item)
        factor_config = load_factor_config(item["config"])
        cached = store.load(factor_config)
        processed[alias] = cached["processed_factor"]
        factor_configs[alias] = factor_config

    return processed, factor_configs


def run_model_evaluate_from_config(
    config_path: str,
    dm: DataManager | None = None,
    checker: ModelChecker | None = None,
    store: FactorStore | None = None,
) -> dict[str, Any]:
    config = load_model_config(config_path)
    run_id = make_run_id()
    started_at = utc_now_iso()
    checker = checker or ModelChecker()
    checker.check(config)

    model_type = config["model_type"]
    if model_type not in ALPHA_MODEL_REGISTRY:
        raise ValueError(
            f"Unknown model_type '{model_type}'. "
            f"Available: {sorted(ALPHA_MODEL_REGISTRY)}"
        )

    processed_factors, factor_configs = load_processed_factors(
        config,
        store=store,
    )
    model = ALPHA_MODEL_REGISTRY[model_type]()
    model_scores = model.build(
        processed_factors=processed_factors,
        config=config,
    )

    alignment = config.get("alignment", {})
    aligned_factors = FactorAligner().align(
        processed_factors,
        missing_policy=alignment.get("missing_policy", "intersection"),
        min_factor_count=alignment.get("min_factor_count"),
    )

    first_factor_config = next(iter(factor_configs.values()))
    data_config = first_factor_config.get("data", {})
    period = first_factor_config.get("period", {})
    raw_root = resolve_project_path(data_config.get("raw_root", "data/raw"))
    dm = dm or DataManager(raw_root=str(raw_root))
    price = dm.get_daily_price(
        start=period["start"],
        end=period["end"],
        ts_codes=None,
    )

    evaluation_config = config.get("evaluation", {})
    periods = evaluation_config.get("forward_periods", [1, 5, 20])
    quantiles = evaluation_config.get("quantiles", 5)
    forward_returns = calculate_forward_returns(
        price,
        periods=periods,
        price_col="close",
    )

    evaluation = ModelEvaluator(
        periods=periods,
        quantiles=quantiles,
    ).evaluate(
        model_scores=model_scores,
        aligned_factors=aligned_factors,
        forward_returns=forward_returns,
        config=config,
    )

    output_root = config.get("output", {}).get("output_root", "artifacts/model_runs")
    run_dir = resolve_project_path(output_root) / config["model_id"] / run_id
    run_manifest = base_run_manifest(
        run_id=run_id,
        run_type="model",
        started_at=started_at,
        finished_at=utc_now_iso(),
        config_path=config_path,
        config=config,
        status="success",
        error_message=None,
        rows=row_counts(
            model_scores=model_scores,
            aligned_factors=aligned_factors,
            factor_correlation=evaluation.factor_correlation,
            factor_contribution=evaluation.factor_contribution,
            model_ic_series=evaluation.model_ic_series,
            model_quantile_returns=evaluation.model_quantile_returns,
        ),
        extra={
            "model_id": config["model_id"],
            "model_type": config["model_type"],
            "version": config.get("version"),
            "factor_ids": [
                item["factor_id"]
                for item in config.get("factors", [])
            ],
            "produced_target_positions": False,
        },
    )
    run_manifest["start"] = period.get("start")
    run_manifest["end"] = period.get("end")

    write_yaml_snapshot(run_dir / "config_snapshot.yaml", config)
    write_json(run_dir / "run_manifest.json", run_manifest)
    write_json(run_dir / "summary.json", evaluation.summary)
    write_parquet(run_dir / "factor_correlation.parquet", evaluation.factor_correlation)
    write_parquet(run_dir / "factor_contribution.parquet", evaluation.factor_contribution)
    write_parquet(run_dir / "model_ic_series.parquet", evaluation.model_ic_series)
    write_parquet(run_dir / "model_quantile_returns.parquet", evaluation.model_quantile_returns)
    write_parquet(run_dir / "model_scores.parquet", model_scores)

    return {
        "config": config,
        "processed_factors": processed_factors,
        "aligned_factors": aligned_factors,
        "model_scores": model_scores,
        "evaluation": evaluation,
        "run_manifest": run_manifest,
        "run_dir": run_dir,
    }


def format_model_evaluation_summary(result: dict[str, Any]) -> str:
    summary = result["evaluation"].summary
    manifest = result["run_manifest"]
    research = summary.get("model_research", {})

    lines = [
        "===== model evaluation summary =====",
        f"model_id: {manifest['model_id']}",
        f"model_type: {manifest['model_type']}",
        f"run_id: {manifest['run_id']}",
        f"run_dir: {result['run_dir']}",
        "produced_target_positions: False",
        "",
        "===== core metrics =====",
        f"row_count: {summary.get('row_count')}",
        f"model_score_mean: {summary.get('model_score_mean')}",
        f"model_score_std: {summary.get('model_score_std')}",
        f"missing_policy: {summary.get('missing_policy')}",
        f"missing_policy_impact: {summary.get('missing_policy_impact')}",
    ]

    for period, metrics in research.get("ic", {}).items():
        lines.append(
            f"period {period}d: ic_mean={metrics.get('ic_mean')}, "
            f"rank_ic_mean={metrics.get('rank_ic_mean')}, "
            f"icir={metrics.get('icir')}"
        )

    return "\n".join(lines)
