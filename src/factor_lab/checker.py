from __future__ import annotations

from dataclasses import dataclass, field
import math
from typing import Any

import numpy as np
import pandas as pd

from src.contracts.factor_frames import validate_raw_factor_frame
from src.factors.base import BaseFactor
from src.factors.registry import DEFAULT_FACTOR_REGISTRY, FactorRegistry


PASS = "PASS"
WARNING = "WARNING"
FAIL = "FAIL"


@dataclass(frozen=True)
class FactorCheckIssue:
    severity: str
    code: str
    message: str


@dataclass
class FactorCheckReport:
    factor_id: str = ""
    implementation: str = ""
    status: str = PASS
    issues: list[FactorCheckIssue] = field(default_factory=list)
    metrics: dict[str, Any] = field(default_factory=dict)

    def add_issue(
        self,
        severity: str,
        code: str,
        message: str,
    ) -> None:
        self.issues.append(
            FactorCheckIssue(
                severity=severity,
                code=code,
                message=message,
            )
        )
        self._refresh_status()

    def fail(self, code: str, message: str) -> None:
        self.add_issue(FAIL, code, message)

    def warn(self, code: str, message: str) -> None:
        self.add_issue(WARNING, code, message)

    def info(self, code: str, message: str) -> None:
        self.add_issue(PASS, code, message)

    def _refresh_status(self) -> None:
        severities = {
            issue.severity
            for issue in self.issues
        }
        if FAIL in severities:
            self.status = FAIL
        elif WARNING in severities:
            self.status = WARNING
        else:
            self.status = PASS

    def to_dict(self) -> dict[str, Any]:
        return {
            "factor_id": self.factor_id,
            "implementation": self.implementation,
            "status": self.status,
            "metrics": self.metrics,
            "issues": [
                {
                    "severity": issue.severity,
                    "code": issue.code,
                    "message": issue.message,
                }
                for issue in self.issues
            ],
        }


class FactorChecker:
    """
    Check factor configuration, implementation wiring, and raw output quality.

    This class intentionally does not calculate IC, Rank IC, layered returns,
    factor catalog state, alpha models, or strategy backtests.
    """

    REQUIRED_CONFIG_KEYS = [
        "schema_version",
        "factor_id",
        "implementation",
        "version",
        "status",
        "metadata",
        "data",
        "period",
        "universe",
        "params",
        "preprocess",
        "evaluation",
        "storage",
    ]

    VALID_STATUSES = {
        "draft",
        "tested",
        "approved",
        "deprecated",
    }

    def __init__(
        self,
        registry: FactorRegistry | None = None,
    ):
        self.registry = registry or DEFAULT_FACTOR_REGISTRY

    def check(
        self,
        config: dict,
        raw_factor: pd.DataFrame | None = None,
        universe: pd.DataFrame | None = None,
        factor_cls: type[BaseFactor] | None = None,
    ) -> FactorCheckReport:
        report = FactorCheckReport(
            factor_id=str(config.get("factor_id", "")),
            implementation=str(config.get("implementation", "")),
        )

        self.check_config(config, report)
        self.check_implementation(config, report, factor_cls=factor_cls)

        if raw_factor is not None:
            self.check_raw_factor(
                config=config,
                raw_factor=raw_factor,
                universe=universe,
                report=report,
            )

        return report

    def check_config(
        self,
        config: dict,
        report: FactorCheckReport,
    ) -> None:
        if not isinstance(config, dict):
            report.fail("CONFIG_NOT_MAPPING", "Factor config must be a mapping")
            return

        missing = [
            key
            for key in self.REQUIRED_CONFIG_KEYS
            if key not in config
        ]
        if missing:
            report.fail(
                "CONFIG_MISSING_KEYS",
                f"Factor config is missing required keys: {missing}",
            )

        if config.get("schema_version") != 2:
            report.fail(
                "CONFIG_SCHEMA_VERSION",
                "Factor config must use schema_version: 2",
            )

        factor_id = config.get("factor_id")
        if not isinstance(factor_id, str) or not factor_id.strip():
            report.fail(
                "CONFIG_FACTOR_ID",
                "factor_id must be a non-empty string",
            )

        implementation = config.get("implementation")
        if not isinstance(implementation, str) or not implementation.strip():
            report.fail(
                "CONFIG_IMPLEMENTATION",
                "implementation must be a non-empty string",
            )

        status = config.get("status")
        if status is not None and status not in self.VALID_STATUSES:
            report.warn(
                "CONFIG_STATUS",
                f"status should be one of {sorted(self.VALID_STATUSES)}",
            )

        period = config.get("period")
        if not isinstance(period, dict):
            report.fail("CONFIG_PERIOD", "period must be a mapping")
        else:
            for key in ["start", "end"]:
                if key not in period:
                    report.fail(
                        "CONFIG_PERIOD",
                        f"period.{key} is required",
                    )
            if "start" in period and "end" in period:
                try:
                    start = pd.to_datetime(period["start"], errors="raise")
                    end = pd.to_datetime(period["end"], errors="raise")
                    if start > end:
                        report.fail(
                            "CONFIG_PERIOD_ORDER",
                            "period.start must be on or before period.end",
                        )
                except Exception as exc:
                    report.fail(
                        "CONFIG_PERIOD_DATE",
                        f"period.start/end must be parseable dates: {exc}",
                    )

        for key in ["metadata", "data", "universe", "params", "preprocess", "evaluation", "storage"]:
            if key in config and not isinstance(config[key], dict):
                report.fail(
                    "CONFIG_SECTION_TYPE",
                    f"{key} must be a mapping",
                )

    def check_implementation(
        self,
        config: dict,
        report: FactorCheckReport,
        factor_cls: type[BaseFactor] | None = None,
    ) -> None:
        implementation = config.get("implementation")

        if not isinstance(implementation, str) or not implementation.strip():
            return

        if not self.registry.contains(implementation):
            report.fail(
                "IMPLEMENTATION_NOT_REGISTERED",
                f"implementation '{implementation}' is not registered",
            )
            return

        resolved_cls = factor_cls or self.registry.get(implementation)

        if not issubclass(resolved_cls, BaseFactor):
            report.fail(
                "IMPLEMENTATION_NOT_FACTOR",
                f"{resolved_cls} must inherit BaseFactor",
            )
        else:
            report.info(
                "IMPLEMENTATION_REGISTERED",
                f"implementation '{implementation}' is registered",
            )

    def check_raw_factor(
        self,
        config: dict,
        raw_factor: pd.DataFrame,
        universe: pd.DataFrame | None,
        report: FactorCheckReport,
    ) -> None:
        if raw_factor is None:
            report.fail("RAW_FACTOR_MISSING", "Factor build did not return a DataFrame")
            return

        if not isinstance(raw_factor, pd.DataFrame):
            report.fail(
                "RAW_FACTOR_TYPE",
                f"Factor build must return a pandas DataFrame, got {type(raw_factor)}",
            )
            return

        if raw_factor.empty:
            report.fail("RAW_FACTOR_EMPTY", "Raw factor output is empty")
            return

        self._collect_raw_metrics(raw_factor, report)

        try:
            normalized = validate_raw_factor_frame(raw_factor)
        except ValueError as exc:
            report.fail("RAW_FACTOR_CONTRACT", str(exc))
            return

        self._check_factor_id(config, normalized, report)
        self._check_date_range(config, normalized, report)
        self._check_nan_stats(normalized, report)
        self._check_cross_section_stats(config, normalized, report)
        self._check_constant_values(normalized, report)
        self._check_universe_match(normalized, universe, report)

    def _collect_raw_metrics(
        self,
        raw_factor: pd.DataFrame,
        report: FactorCheckReport,
    ) -> None:
        report.metrics["row_count"] = int(len(raw_factor))

        if "factor_value" in raw_factor.columns:
            numeric = pd.to_numeric(
                raw_factor["factor_value"],
                errors="coerce",
            )
            values = numeric.to_numpy(dtype=float, na_value=np.nan)
            report.metrics["nan_count"] = int(numeric.isna().sum())
            report.metrics["nan_ratio"] = float(numeric.isna().mean())
            report.metrics["inf_count"] = int(np.isinf(values).sum())

            if report.metrics["inf_count"] > 0:
                report.fail(
                    "RAW_FACTOR_INF",
                    f"factor_value contains {report.metrics['inf_count']} inf values",
                )

    def _check_factor_id(
        self,
        config: dict,
        raw_factor: pd.DataFrame,
        report: FactorCheckReport,
    ) -> None:
        expected = config.get("factor_id")
        observed = set(raw_factor["factor_id"].dropna().astype(str))

        if observed != {expected}:
            report.fail(
                "RAW_FACTOR_ID_MISMATCH",
                f"factor_id values must be exactly {{{expected!r}}}, got {sorted(observed)}",
            )

    def _check_date_range(
        self,
        config: dict,
        raw_factor: pd.DataFrame,
        report: FactorCheckReport,
    ) -> None:
        min_date = raw_factor["trade_date"].min()
        max_date = raw_factor["trade_date"].max()
        report.metrics["date_min"] = str(min_date.date())
        report.metrics["date_max"] = str(max_date.date())

        period = config.get("period", {})
        if not isinstance(period, dict):
            return

        start = pd.to_datetime(period.get("start"), errors="coerce")
        end = pd.to_datetime(period.get("end"), errors="coerce")

        if pd.notna(start) and min_date < start:
            report.warn(
                "RAW_FACTOR_START_BEFORE_CONFIG",
                "raw factor contains dates before period.start",
            )

        if pd.notna(end) and max_date > end:
            report.warn(
                "RAW_FACTOR_END_AFTER_CONFIG",
                "raw factor contains dates after period.end",
            )

    def _check_nan_stats(
        self,
        raw_factor: pd.DataFrame,
        report: FactorCheckReport,
    ) -> None:
        value = pd.to_numeric(raw_factor["factor_value"], errors="coerce")
        nan_count = int(value.isna().sum())
        nan_ratio = float(value.isna().mean())
        report.metrics["nan_count"] = nan_count
        report.metrics["nan_ratio"] = nan_ratio

        if nan_count > 0:
            report.warn(
                "RAW_FACTOR_NAN",
                f"factor_value contains {nan_count} NaN values ({nan_ratio:.2%})",
            )

    def _check_cross_section_stats(
        self,
        config: dict,
        raw_factor: pd.DataFrame,
        report: FactorCheckReport,
    ) -> None:
        valid = raw_factor.dropna(subset=["factor_value"])
        cross_section = (
            valid.groupby("trade_date")["ts_code"]
            .nunique()
            .sort_index()
        )

        report.metrics["valid_stock_count"] = int(valid["ts_code"].nunique())

        if cross_section.empty:
            report.fail(
                "RAW_FACTOR_ALL_EMPTY",
                "No date has a non-NaN factor_value",
            )
            return

        report.metrics["cross_section_count_mean"] = float(cross_section.mean())
        report.metrics["cross_section_count_median"] = float(cross_section.median())
        report.metrics["cross_section_count_min"] = int(cross_section.min())

        all_dates = set(raw_factor["trade_date"].dropna().unique())
        valid_dates = set(valid["trade_date"].dropna().unique())
        all_empty_dates = sorted(all_dates - valid_dates)
        report.metrics["all_empty_date_count"] = len(all_empty_dates)

        if all_empty_dates:
            report.warn(
                "RAW_FACTOR_EMPTY_DATES",
                f"{len(all_empty_dates)} dates have all factor values missing",
            )

        evaluation = config.get("evaluation", {})
        min_cross_section = 10
        if isinstance(evaluation, dict):
            min_cross_section = int(
                evaluation.get("min_cross_section_count", min_cross_section)
            )

        if cross_section.min() < min_cross_section:
            report.warn(
                "RAW_FACTOR_SMALL_CROSS_SECTION",
                "Minimum valid cross-section count is "
                f"{int(cross_section.min())}, below threshold {min_cross_section}",
            )

    def _check_constant_values(
        self,
        raw_factor: pd.DataFrame,
        report: FactorCheckReport,
    ) -> None:
        value = pd.to_numeric(raw_factor["factor_value"], errors="coerce")
        finite = value[np.isfinite(value)].dropna()

        if finite.empty:
            return

        unique_count = int(finite.nunique(dropna=True))
        report.metrics["factor_value_unique_count"] = unique_count

        if unique_count <= 1 and len(finite) > 1:
            report.warn(
                "RAW_FACTOR_NEARLY_CONSTANT",
                "factor_value is nearly constant across valid observations",
            )
            return

        std = float(finite.std(ddof=0))
        mean_abs = float(finite.abs().mean())
        report.metrics["factor_value_std"] = std

        if mean_abs > 0 and math.isclose(std / mean_abs, 0.0, abs_tol=1e-12):
            report.warn(
                "RAW_FACTOR_NEARLY_CONSTANT",
                "factor_value has almost no variation",
            )

    def _check_universe_match(
        self,
        raw_factor: pd.DataFrame,
        universe: pd.DataFrame | None,
        report: FactorCheckReport,
    ) -> None:
        if universe is None or universe.empty:
            report.warn(
                "UNIVERSE_EMPTY",
                "Universe is empty or unavailable; universe matching was skipped",
            )
            return

        required_cols = {"trade_date", "ts_code"}
        if not required_cols.issubset(universe.columns):
            report.warn(
                "UNIVERSE_COLUMNS",
                "Universe must contain trade_date and ts_code for matching",
            )
            return

        universe_keys = universe[["trade_date", "ts_code"]].copy()
        universe_keys["trade_date"] = pd.to_datetime(universe_keys["trade_date"])
        universe_keys["_in_universe"] = True

        factor_keys = raw_factor[["trade_date", "ts_code"]].copy()
        factor_keys["trade_date"] = pd.to_datetime(factor_keys["trade_date"])
        matched = factor_keys.merge(
            universe_keys.drop_duplicates(),
            on=["trade_date", "ts_code"],
            how="left",
        )

        outside_count = int(matched["_in_universe"].isna().sum())
        report.metrics["universe_outside_count"] = outside_count
        report.metrics["universe_match_ratio"] = float(
            1.0 - outside_count / max(len(matched), 1)
        )

        if outside_count > 0:
            report.warn(
                "UNIVERSE_OUTSIDE_STOCKS",
                f"{outside_count} raw factor rows are outside the configured universe",
            )
