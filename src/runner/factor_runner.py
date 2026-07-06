from __future__ import annotations

import json
from typing import Any

import pandas as pd

from src.datahub.data_manager import DataManager
from src.factor_lab.catalog import FactorCatalog
from src.factor_lab.checker import FAIL, FactorCheckReport, FactorChecker
from src.factor_lab.evaluator import FactorEvaluator
from src.factor_lab.forward_returns import DEFAULT_FORWARD_PERIODS, calculate_forward_returns
from src.factor_lab.report import write_json, write_parquet, write_yaml_snapshot
from src.factor_lab.store import FactorStore
from src.factors.processor import FactorProcessor
from src.factors.registry import DEFAULT_FACTOR_REGISTRY
from src.runner.config_loader import load_factor_config, resolve_project_path
from src.runner.run_metadata import base_run_manifest, make_run_id, row_counts, utc_now_iso
from src.universe.universe_builder import UniverseBuilder


def _get_mapping(
    config: dict,
    section: str,
) -> dict:
    value = config.get(section, {})
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise ValueError(f"Config section '{section}' must be a mapping")
    return value


def _build_universe(
    config: dict,
    dm: DataManager,
) -> pd.DataFrame:
    period = _get_mapping(config, "period")
    universe_config = _get_mapping(config, "universe")

    builder = UniverseBuilder(
        dm=dm,
        min_list_days=universe_config.get("min_list_days", 120),
        min_close=universe_config.get("min_close", 2.0),
        min_amount=universe_config.get(
            "min_amount_yuan",
            universe_config.get("min_amount", 30_000_000),
        ),
    )
    return builder.build(
        start=period["start"],
        end=period["end"],
    )


def _adapt_raw_factor(
    raw_factor: pd.DataFrame,
    factor_id: str,
) -> pd.DataFrame:
    result = raw_factor.copy()

    if "factor_id" not in result.columns:
        result["factor_id"] = factor_id

    return result


def run_factor_check_from_config(
    config_path: str,
    dm: DataManager | None = None,
    checker: FactorChecker | None = None,
) -> dict[str, Any]:
    """
    Run a factor data quality check from a factor config.
    """

    config = load_factor_config(config_path)
    checker = checker or FactorChecker()
    report = checker.check(config)

    if report.status == FAIL:
        return {
            "config": config,
            "universe": pd.DataFrame(),
            "raw_factor": pd.DataFrame(),
            "report": report,
        }

    data_config = _get_mapping(config, "data")
    period = _get_mapping(config, "period")
    params = _get_mapping(config, "params")

    raw_root = resolve_project_path(
        data_config.get("raw_root", "data/raw")
    )
    dm = dm or DataManager(raw_root=str(raw_root))

    universe = _build_universe(
        config=config,
        dm=dm,
    )
    universe_codes = (
        sorted(universe["ts_code"].dropna().unique().tolist())
        if not universe.empty and "ts_code" in universe.columns
        else None
    )

    implementation = config["implementation"]
    factor_cls = DEFAULT_FACTOR_REGISTRY.get(implementation)
    factor = factor_cls(
        dm=dm,
        params=params,
    )

    try:
        raw_factor = factor.build(
            start=period["start"],
            end=period["end"],
            universe=universe_codes,
        )
    except Exception as exc:
        report.fail(
            "FACTOR_BUILD_FAILED",
            f"Factor build failed for implementation '{implementation}': {exc}",
        )
        raw_factor = pd.DataFrame()
    else:
        report.info(
            "FACTOR_BUILD_SUCCEEDED",
            f"Factor build succeeded for implementation '{implementation}'",
        )

    if isinstance(raw_factor, pd.DataFrame):
        raw_factor = _adapt_raw_factor(
            raw_factor=raw_factor,
            factor_id=config["factor_id"],
        )

    report = checker.check(
        config=config,
        raw_factor=raw_factor,
        universe=universe,
        factor_cls=factor_cls,
    )

    if report.status != FAIL:
        report.info(
            "FACTOR_BUILD_SUCCEEDED",
            f"Factor build succeeded for implementation '{implementation}'",
        )

    return {
        "config": config,
        "universe": universe,
        "raw_factor": raw_factor,
        "report": report,
    }


def _process_factor(
    config: dict,
    raw_factor: pd.DataFrame,
) -> pd.DataFrame:
    preprocess = _get_mapping(config, "preprocess")
    evaluation = _get_mapping(config, "evaluation")
    processor = FactorProcessor()

    processed = processor.process_single_factor(
        raw_factor,
        direction=preprocess.get("direction", "positive"),
        winsorize=preprocess.get("winsorize", True),
        standardize=preprocess.get("standardize", True),
        rank=True,
        lower_quantile=preprocess.get("lower_quantile", 0.01),
        upper_quantile=preprocess.get("upper_quantile", 0.99),
        drop_na=preprocess.get("drop_na", True),
        min_count=evaluation.get("min_cross_section_count"),
    )

    if not processed.empty:
        processed["factor_id"] = config["factor_id"]
        processed["raw_value"] = processed["factor_value"]

    return processed


def _build_factor_data(
    config: dict,
    dm: DataManager,
) -> dict[str, Any]:
    period = _get_mapping(config, "period")
    params = _get_mapping(config, "params")
    universe = _build_universe(config=config, dm=dm)
    universe_codes = (
        sorted(universe["ts_code"].dropna().unique().tolist())
        if not universe.empty and "ts_code" in universe.columns
        else None
    )

    factor_cls = DEFAULT_FACTOR_REGISTRY.get(config["implementation"])
    factor = factor_cls(dm=dm, params=params)
    raw_factor = factor.build(
        start=period["start"],
        end=period["end"],
        universe=universe_codes,
    )
    raw_factor = _adapt_raw_factor(
        raw_factor=raw_factor,
        factor_id=config["factor_id"],
    )
    processed_factor = _process_factor(
        config=config,
        raw_factor=raw_factor,
    )

    return {
        "universe": universe,
        "raw_factor": raw_factor,
        "processed_factor": processed_factor,
    }


def _write_evaluation_artifacts(
    config: dict,
    checker_report: FactorCheckReport,
    evaluation_result,
    run_manifest: dict[str, Any],
    run_dir,
) -> None:
    write_yaml_snapshot(
        run_dir / "config_snapshot.yaml",
        config,
    )
    write_json(
        run_dir / "run_manifest.json",
        run_manifest,
    )
    write_json(
        run_dir / "summary.json",
        evaluation_result.summary,
    )
    write_json(
        run_dir / "checker_report.json",
        checker_report.to_dict(),
    )
    write_parquet(
        run_dir / "ic_series.parquet",
        evaluation_result.ic_series,
    )
    write_parquet(
        run_dir / "quantile_returns.parquet",
        evaluation_result.quantile_returns,
    )
    write_parquet(
        run_dir / "quantile_nav.parquet",
        evaluation_result.quantile_nav,
    )
    write_parquet(
        run_dir / "coverage.parquet",
        evaluation_result.coverage,
    )


def run_factor_evaluate_from_config(
    config_path: str,
    refresh: bool = False,
    dm: DataManager | None = None,
    checker: FactorChecker | None = None,
    store: FactorStore | None = None,
    catalog: FactorCatalog | None = None,
) -> dict[str, Any]:
    """
    Run single-factor research evaluation.

    This does not create target positions, run a strategy, or simulate trades.
    """

    config = load_factor_config(config_path)
    run_id = make_run_id()
    started_at = utc_now_iso()
    checker = checker or FactorChecker()
    store = store or FactorStore()
    catalog = catalog or FactorCatalog()

    data_config = _get_mapping(config, "data")
    period = _get_mapping(config, "period")
    raw_root = resolve_project_path(data_config.get("raw_root", "data/raw"))
    dm = dm or DataManager(raw_root=str(raw_root))

    cache_hit = False
    universe = pd.DataFrame()

    if not refresh and store.has_cache(config):
        cached = store.load(config)
        raw_factor = cached["raw_factor"]
        processed_factor = cached["processed_factor"]
        cache_manifest = cached["manifest"]
        config_hash = cached["config_hash"]
        cache_dir = cached["cache_dir"]
        cache_hit = True
        universe = _build_universe(config=config, dm=dm)
    else:
        built = _build_factor_data(config=config, dm=dm)
        universe = built["universe"]
        raw_factor = built["raw_factor"]
        processed_factor = built["processed_factor"]
        saved = store.save(
            config=config,
            raw_factor=raw_factor,
            processed_factor=processed_factor,
        )
        cache_manifest = saved["manifest"]
        config_hash = saved["config_hash"]
        cache_dir = saved["cache_dir"]

    checker_report = checker.check(
        config=config,
        raw_factor=raw_factor,
        universe=universe,
    )

    if checker_report.status == FAIL:
        raise ValueError(
            f"Factor check failed; evaluation aborted: {checker_report.to_dict()}"
        )

    price = dm.get_daily_price(
        start=period["start"],
        end=period["end"],
        ts_codes=None,
    )
    forward_returns = calculate_forward_returns(
        price,
        periods=DEFAULT_FORWARD_PERIODS,
        price_col="close",
    )
    evaluator = FactorEvaluator(periods=DEFAULT_FORWARD_PERIODS, quantiles=5)
    evaluation_result = evaluator.evaluate(
        processed_factor=processed_factor,
        forward_returns=forward_returns,
    )

    run_dir = (
        resolve_project_path("artifacts/factor_runs")
        / config["factor_id"]
        / run_id
    )
    run_manifest = base_run_manifest(
        run_id=run_id,
        run_type="factor",
        started_at=started_at,
        finished_at=utc_now_iso(),
        config_path=config_path,
        config=config,
        status="success",
        error_message=None,
        rows=row_counts(
            raw_factor=raw_factor,
            processed_factor=processed_factor,
            universe=universe,
            forward_returns=forward_returns,
            ic_series=evaluation_result.ic_series,
        ),
        extra={
            "factor_id": config["factor_id"],
            "implementation": config["implementation"],
            "version": config.get("version"),
            "factor_store_config_hash": config_hash,
            "cache_hit": cache_hit,
            "cache_dir": str(cache_dir),
            "store_manifest": cache_manifest,
            "forward_return_definition": "Research-only T close to T+h close; not executable trading return.",
        },
    )
    _write_evaluation_artifacts(
        config=config,
        checker_report=checker_report,
        evaluation_result=evaluation_result,
        run_manifest=run_manifest,
        run_dir=run_dir,
    )

    try:
        catalog.mark_tested_if_draft(config["factor_id"])
    except KeyError:
        pass

    return {
        "config": config,
        "raw_factor": raw_factor,
        "processed_factor": processed_factor,
        "checker_report": checker_report,
        "evaluation": evaluation_result,
        "run_manifest": run_manifest,
        "run_dir": run_dir,
    }


def format_factor_evaluation_summary(result: dict[str, Any]) -> str:
    summary = result["evaluation"].summary
    manifest = result["run_manifest"]

    lines = [
        "===== factor evaluation summary =====",
        f"factor_id: {manifest['factor_id']}",
        f"implementation: {manifest['implementation']}",
        f"run_id: {manifest['run_id']}",
        f"cache_hit: {manifest['cache_hit']}",
        f"run_dir: {result['run_dir']}",
        "",
        "===== core metrics =====",
        f"coverage_ratio: {summary.get('coverage_ratio')}",
        f"valid_date_count: {summary.get('valid_date_count')}",
        f"nan_ratio: {summary.get('nan_ratio')}",
        f"top_quantile_turnover_mean: {summary.get('top_quantile_turnover_mean')}",
        f"bottom_quantile_turnover_mean: {summary.get('bottom_quantile_turnover_mean')}",
    ]

    for period, metrics in summary.get("ic", {}).items():
        lines.append(
            f"period {period}d: ic_mean={metrics.get('ic_mean')}, "
            f"rank_ic_mean={metrics.get('rank_ic_mean')}, "
            f"icir={metrics.get('icir')}"
        )

    return "\n".join(lines)


def format_factor_check_report(report: FactorCheckReport) -> str:
    """
    Format a factor check report for CLI output.
    """

    lines = [
        "===== factor check report =====",
        f"factor_id: {report.factor_id}",
        f"implementation: {report.implementation}",
        f"status: {report.status}",
        "",
        "===== metrics =====",
    ]

    for key in sorted(report.metrics):
        lines.append(f"{key}: {report.metrics[key]}")

    lines.extend([
        "",
        "===== issues =====",
    ])

    if not report.issues:
        lines.append("No issues.")
    else:
        for issue in report.issues:
            lines.append(
                f"[{issue.severity}] {issue.code}: {issue.message}"
            )

    return "\n".join(lines)


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Run a factor implementation check."
    )
    parser.add_argument(
        "--config",
        required=True,
        help="Path to factor YAML config.",
    )
    args = parser.parse_args()

    result = run_factor_check_from_config(args.config)
    report = result["report"]
    print(format_factor_check_report(report))

    if report.status == FAIL:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
