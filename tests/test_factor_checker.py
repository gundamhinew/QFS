from __future__ import annotations

import pandas as pd

from src.factors.checker import FAIL, WARNING, FactorChecker
from src.core.config_loader import load_factor_config
from src.factors.factor_runner import run_factor_check_from_config


def _base_config() -> dict:
    return {
        "schema_version": 2,
        "factor_id": "unit_factor",
        "implementation": "momentum",
        "version": 1,
        "status": "draft",
        "metadata": {},
        "data": {"raw_root": "data/raw"},
        "period": {"start": "2020-01-01", "end": "2020-01-05"},
        "universe": {
            "min_list_days": 1,
            "min_close": 2.0,
            "min_amount_yuan": 1,
        },
        "params": {"lookback": 1},
        "preprocess": {},
        "evaluation": {"min_cross_section_count": 1},
        "storage": {},
    }


def _valid_raw_factor() -> pd.DataFrame:
    return pd.DataFrame({
        "trade_date": [
            "2020-01-01",
            "2020-01-01",
            "2020-01-02",
            "2020-01-02",
        ],
        "ts_code": [
            "000001.SZ",
            "000002.SZ",
            "000001.SZ",
            "000002.SZ",
        ],
        "factor_id": [
            "unit_factor",
            "unit_factor",
            "unit_factor",
            "unit_factor",
        ],
        "factor_value": [0.1, 0.2, 0.3, 0.4],
    })


def _universe() -> pd.DataFrame:
    return pd.DataFrame({
        "trade_date": [
            "2020-01-01",
            "2020-01-01",
            "2020-01-02",
            "2020-01-02",
        ],
        "ts_code": [
            "000001.SZ",
            "000002.SZ",
            "000001.SZ",
            "000002.SZ",
        ],
    })


def _issue_codes(report):
    return {
        issue.code
        for issue in report.issues
    }


def test_load_factor_config_parses_momentum_60():
    config = load_factor_config("configs/factors/momentum_60.yaml")

    assert config["schema_version"] == 2
    assert config["factor_id"] == "momentum_60"
    assert config["implementation"] == "momentum"


def test_factor_checker_unregistered_implementation_fails():
    config = _base_config()
    config["implementation"] = "missing_factor"

    report = FactorChecker().check(config)

    assert report.status == FAIL
    assert "IMPLEMENTATION_NOT_REGISTERED" in _issue_codes(report)


def test_factor_checker_missing_required_columns_fails():
    raw = _valid_raw_factor().drop(columns=["factor_value"])

    report = FactorChecker().check(
        config=_base_config(),
        raw_factor=raw,
        universe=_universe(),
    )

    assert report.status == FAIL
    assert "RAW_FACTOR_CONTRACT" in _issue_codes(report)


def test_factor_checker_duplicate_records_fail():
    raw = pd.concat(
        [_valid_raw_factor(), _valid_raw_factor().head(1)],
        ignore_index=True,
    )

    report = FactorChecker().check(
        config=_base_config(),
        raw_factor=raw,
        universe=_universe(),
    )

    assert report.status == FAIL
    assert "RAW_FACTOR_CONTRACT" in _issue_codes(report)


def test_factor_checker_nan_warns():
    raw = _valid_raw_factor()
    raw.loc[0, "factor_value"] = None

    report = FactorChecker().check(
        config=_base_config(),
        raw_factor=raw,
        universe=_universe(),
    )

    assert report.status == WARNING
    assert "RAW_FACTOR_NAN" in _issue_codes(report)


def test_factor_checker_inf_fails():
    raw = _valid_raw_factor()
    raw.loc[0, "factor_value"] = float("inf")

    report = FactorChecker().check(
        config=_base_config(),
        raw_factor=raw,
        universe=_universe(),
    )

    assert report.status == FAIL
    assert "RAW_FACTOR_INF" in _issue_codes(report)


def test_factor_checker_small_cross_section_warns():
    config = _base_config()
    config["evaluation"]["min_cross_section_count"] = 3

    report = FactorChecker().check(
        config=config,
        raw_factor=_valid_raw_factor(),
        universe=_universe(),
    )

    assert report.status == WARNING
    assert "RAW_FACTOR_SMALL_CROSS_SECTION" in _issue_codes(report)


class MockDataManager:
    def __init__(self):
        pass

    def get_daily_price(self, start, end, ts_codes=None):
        rows = []
        dates = pd.date_range(start, end, freq="D")
        codes = ["000001.SZ", "000002.SZ", "000003.SZ"]

        for day_index, trade_date in enumerate(dates):
            for code_index, ts_code in enumerate(codes):
                rows.append({
                    "trade_date": trade_date,
                    "ts_code": ts_code,
                    "open": 10 + day_index + code_index,
                    "close": 10 + day_index + code_index,
                    "amount": 100000,
                    "vol": 1000,
                })

        df = pd.DataFrame(rows)
        if ts_codes is not None:
            df = df[df["ts_code"].isin(ts_codes)]
        return df.reset_index(drop=True)

    def get_stock_basic(self, ts_codes=None, active_only=True):
        df = pd.DataFrame({
            "ts_code": ["000001.SZ", "000002.SZ", "000003.SZ"],
            "name": ["A", "B", "C"],
            "market": ["主板", "主板", "主板"],
            "exchange": ["SZSE", "SZSE", "SZSE"],
            "list_date": ["20100101", "20100101", "20100101"],
            "list_status": ["L", "L", "L"],
            "is_active": [1, 1, 1],
        })
        if ts_codes is not None:
            df = df[df["ts_code"].isin(ts_codes)]
        return df.reset_index(drop=True)

    def get_adjusted_price(
        self,
        start,
        end,
        ts_codes=None,
        price_cols=None,
        adjust="total_return",
    ):
        price = self.get_daily_price(start, end, ts_codes=ts_codes)
        price["adj_close"] = price["close"]
        return price


def test_momentum_factor_checker_runs_with_mock_data(tmp_path):
    config_path = tmp_path / "momentum_mock.yaml"
    config_path.write_text(
        """
schema_version: 2
factor_id: momentum_mock
implementation: momentum
version: 1
status: draft
metadata: {}
data:
  raw_root: "data/raw"
period:
  start: "2020-01-01"
  end: "2020-01-05"
universe:
  min_list_days: 1
  min_close: 2.0
  min_amount_yuan: 1
params:
  lookback: 1
preprocess: {}
evaluation:
  min_cross_section_count: 1
storage: {}
""",
        encoding="utf-8",
    )

    result = run_factor_check_from_config(
        str(config_path),
        dm=MockDataManager(),
    )
    report = result["report"]

    assert report.status != FAIL
    assert report.metrics["valid_stock_count"] == 3
    assert "FACTOR_BUILD_SUCCEEDED" in _issue_codes(report)
