from __future__ import annotations

import argparse
import sys

from src.factor_lab.catalog import FactorCatalog
from src.factor_lab.scaffold import create_factor_template
from src.runner.factor_runner import (
    format_factor_evaluation_summary,
    format_factor_check_report,
    run_factor_evaluate_from_config,
    run_factor_check_from_config,
)
from src.runner.model_runner import (
    format_model_evaluation_summary,
    run_model_evaluate_from_config,
)
from src.runner.strategy_runner import (
    format_strategy_backtest_summary,
    run_strategy_backtest_from_config,
)


def _add_factor_create_parser(subparsers):
    parser = subparsers.add_parser(
        "create",
        help="Create a new factor implementation template.",
    )
    parser.add_argument("--factor-id", required=True)
    parser.add_argument("--implementation", required=True)
    parser.add_argument("--class-name", required=True)
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite generated files if they already exist.",
    )
    parser.set_defaults(command="factor_create")


def _add_factor_check_parser(subparsers):
    parser = subparsers.add_parser(
        "check",
        help="Check factor configuration and raw factor output quality.",
    )
    parser.add_argument("--config", required=True)
    parser.set_defaults(command="factor_check")


def _add_factor_evaluate_parser(subparsers):
    parser = subparsers.add_parser(
        "evaluate",
        help="Evaluate a single factor research report.",
    )
    parser.add_argument("--config", required=True)
    parser.add_argument(
        "--refresh",
        action="store_true",
        help="Ignore exact-match factor cache and rebuild factor data.",
    )
    parser.set_defaults(command="factor_evaluate")


def _add_factor_list_parser(subparsers):
    parser = subparsers.add_parser(
        "list",
        help="List factor catalog entries.",
    )
    parser.set_defaults(command="factor_list")


def _add_factor_show_parser(subparsers):
    parser = subparsers.add_parser(
        "show",
        help="Show one factor catalog entry.",
    )
    parser.add_argument("--factor-id", required=True)
    parser.set_defaults(command="factor_show")


def _add_factor_set_status_parser(subparsers):
    parser = subparsers.add_parser(
        "set-status",
        help="Set factor catalog status.",
    )
    parser.add_argument("--factor-id", required=True)
    parser.add_argument("--status", required=True)
    parser.add_argument(
        "--force",
        action="store_true",
        help="Explicitly override report preconditions.",
    )
    parser.set_defaults(command="factor_set_status")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="QFS research command line interface."
    )
    top_subparsers = parser.add_subparsers(dest="domain", required=True)

    factor_parser = top_subparsers.add_parser(
        "factor",
        help="Factor research commands.",
    )
    factor_subparsers = factor_parser.add_subparsers(
        dest="factor_command",
        required=True,
    )
    _add_factor_create_parser(factor_subparsers)
    _add_factor_check_parser(factor_subparsers)
    _add_factor_evaluate_parser(factor_subparsers)
    _add_factor_list_parser(factor_subparsers)
    _add_factor_show_parser(factor_subparsers)
    _add_factor_set_status_parser(factor_subparsers)

    model_parser = top_subparsers.add_parser(
        "model",
        help="Model research commands.",
    )
    model_subparsers = model_parser.add_subparsers(
        dest="model_command",
        required=True,
    )
    model_evaluate = model_subparsers.add_parser(
        "evaluate",
        help="Evaluate an alpha model.",
    )
    model_evaluate.add_argument("--config", required=True)
    model_evaluate.set_defaults(command="model_evaluate")

    strategy_parser = top_subparsers.add_parser(
        "strategy",
        help="Strategy research and backtest commands.",
    )
    strategy_subparsers = strategy_parser.add_subparsers(
        dest="strategy_command",
        required=True,
    )
    strategy_backtest = strategy_subparsers.add_parser(
        "backtest",
        help="Run a StrategyPipeline backtest.",
    )
    strategy_backtest.add_argument("--config", required=True)
    strategy_backtest.set_defaults(command="strategy_backtest")

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        return _dispatch(args, parser)
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


def _dispatch(args: argparse.Namespace, parser: argparse.ArgumentParser) -> int:
    if args.command == "factor_create":
        created = create_factor_template(
            factor_id=args.factor_id,
            implementation=args.implementation,
            class_name=args.class_name,
            force=args.force,
        )
        print("Created factor template:")
        print(f"factor_file: {created.factor_file}")
        print(f"config_file: {created.config_file}")
        print(f"test_file: {created.test_file}")
        return 0

    if args.command == "factor_check":
        result = run_factor_check_from_config(args.config)
        report = result["report"]
        print(format_factor_check_report(report))
        return 1 if report.status == "FAIL" else 0

    if args.command == "factor_evaluate":
        result = run_factor_evaluate_from_config(
            args.config,
            refresh=args.refresh,
        )
        print(format_factor_evaluation_summary(result))
        return 0

    if args.command == "factor_list":
        catalog = FactorCatalog()
        entries = catalog.list_entries()

        if not entries:
            print("No factors found.")
            return 0

        print("factor_id\timplementation\tversion\tstatus\thas_report")
        for entry in entries:
            print(
                f"{entry.factor_id}\t{entry.implementation}\t"
                f"{entry.version}\t{entry.status}\t{entry.has_report}"
            )
        return 0

    if args.command == "factor_show":
        catalog = FactorCatalog()
        entry = catalog.get_entry(args.factor_id)
        print(f"factor_id: {entry.factor_id}")
        print(f"implementation: {entry.implementation}")
        print(f"version: {entry.version}")
        print(f"status: {entry.status}")
        print(f"config_path: {entry.config_path}")
        print(f"has_report: {entry.has_report}")
        print(f"metadata: {entry.metadata}")
        return 0

    if args.command == "factor_set_status":
        catalog = FactorCatalog()
        entry = catalog.set_status(
            factor_id=args.factor_id,
            status=args.status,
            force=args.force,
        )
        print(f"factor_id: {entry.factor_id}")
        print(f"status: {entry.status}")
        print(f"has_report: {entry.has_report}")
        return 0

    if args.command == "model_evaluate":
        result = run_model_evaluate_from_config(args.config)
        print(format_model_evaluation_summary(result))
        return 0

    if args.command == "strategy_backtest":
        result = run_strategy_backtest_from_config(args.config)
        print(format_strategy_backtest_summary(result))
        return 0

    parser.error("Unknown command")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
