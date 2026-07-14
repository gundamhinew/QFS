from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest
import yaml

from src.backtest.engine import BacktestEngine
from src.strategies.strategy_runner import run_strategy_backtest_from_config
from src.legacy.strategies.top_n_strategy import TopNEqualWeightStrategy


class MockDataManager:
    def get_daily_price(self, start, end, ts_codes=None):
        dates = pd.date_range(start, end, freq="D")
        rows = []
        for i, date in enumerate(dates):
            for code_index, code in enumerate(["000001.SZ", "000002.SZ"]):
                price = 10.0 + i + code_index
                rows.append({
                    "trade_date": date,
                    "ts_code": code,
                    "open": price,
                    "close": price + 0.5,
                    "pre_close": price - 0.5,
                    "high": price + 1,
                    "low": price - 1,
                    "amount": 100000,
                    "vol": 1000,
                })
        df = pd.DataFrame(rows)
        if ts_codes is not None:
            df = df[df["ts_code"].isin(ts_codes)]
        return df.reset_index(drop=True)

    def get_stock_basic(self, ts_codes=None, active_only=True):
        df = pd.DataFrame({
            "ts_code": ["000001.SZ", "000002.SZ"],
            "name": ["A", "B"],
            "market": ["主板", "主板"],
            "exchange": ["SZSE", "SZSE"],
            "list_date": ["20100101", "20100101"],
            "is_active": [1, 1],
        })
        if ts_codes is not None:
            df = df[df["ts_code"].isin(ts_codes)]
        return df.reset_index(drop=True)


class DummyStore:
    def has_cache(self, factor_config):
        return True

    def load(self, factor_config):
        processed = pd.DataFrame({
            "trade_date": pd.to_datetime(["2020-01-01", "2020-01-01", "2020-01-02", "2020-01-02"]),
            "ts_code": ["000001.SZ", "000002.SZ", "000001.SZ", "000002.SZ"],
            "factor_id": ["unit_factor"] * 4,
            "raw_value": [1.0, 2.0, 2.0, 1.0],
            "factor_score": [1.0, 2.0, 2.0, 1.0],
        })
        return {"processed_factor": processed}


def _write_yaml(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        yaml.safe_dump(data, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )


def test_strategy_runner_single_factor_pipeline_with_mock_data(tmp_path):
    factor_path = tmp_path / "factor.yaml"
    model_path = tmp_path / "model.yaml"
    strategy_path = tmp_path / "strategy.yaml"
    output_root = tmp_path / "strategy_runs"

    _write_yaml(
        factor_path,
        {
            "schema_version": 2,
            "factor_id": "unit_factor",
            "implementation": "momentum",
            "version": 1,
            "status": "approved",
            "metadata": {},
            "data": {"raw_root": "data/raw"},
            "period": {"start": "2020-01-01", "end": "2020-01-03"},
            "universe": {},
            "params": {},
            "preprocess": {},
            "evaluation": {},
            "storage": {},
        },
    )
    _write_yaml(
        model_path,
        {
            "schema_version": 2,
            "model_id": "unit_model",
            "model_type": "single_factor",
            "version": 1,
            "status": "research",
            "factors": [{"factor_id": "unit_factor", "alias": "unit_factor", "config": str(factor_path)}],
            "alignment": {"missing_policy": "intersection", "min_factor_count": 1},
            "evaluation": {"allow_unapproved": False},
            "output": {},
        },
    )
    _write_yaml(
        strategy_path,
        {
            "schema_version": 2,
            "strategy_id": "unit_strategy",
            "version": 1,
            "status": "research",
            "data": {"raw_root": "data/raw"},
            "period": {"start": "2020-01-01", "end": "2020-01-03"},
            "model": {"config": str(model_path)},
            "rebalance": {"frequency": "daily"},
            "portfolio": {"type": "top_n_equal_weight", "params": {"top_n": 1, "normalize_weights": True}},
            "timing": {"type": "noop"},
            "risk": {"type": "basic_weight_constraint", "max_single_weight": 1.0, "normalize_weights": True},
            "backtest": {"initial_cash": 100000},
            "execution_assumption": {"signal_time": "close", "execute_time": "next_open"},
            "output": {"save_result": True, "output_root": str(output_root)},
        },
    )

    result = run_strategy_backtest_from_config(
        str(strategy_path),
        dm=MockDataManager(),
        store=DummyStore(),
    )

    assert not result["target_positions"].empty
    assert result["target_positions"]["strategy_id"].unique().tolist() == ["unit_strategy"]
    assert not result["equity_curve"].empty
    assert result["run_dir"] is not None
    assert (result["run_dir"] / "target_positions.parquet").exists()
    manifest = result["run_manifest"]
    assert manifest["run_type"] == "strategy"
    assert manifest["status"] == "success"
    assert manifest["config_path"] == str(strategy_path)
    assert manifest["error_message"] is None
    assert manifest["row_counts"]["target_positions"] == len(result["target_positions"])
    assert (result["run_dir"] / "run_manifest.json").exists()


def test_strategy_runner_writes_failed_manifest(tmp_path):
    strategy_path = tmp_path / "strategy.yaml"
    output_root = tmp_path / "strategy_runs"
    missing_model = tmp_path / "missing_model.yaml"

    _write_yaml(
        strategy_path,
        {
            "schema_version": 2,
            "strategy_id": "bad_strategy",
            "version": 1,
            "status": "research",
            "data": {"raw_root": "data/raw"},
            "period": {"start": "2020-01-01", "end": "2020-01-03"},
            "model": {"config": str(missing_model)},
            "rebalance": {"frequency": "daily"},
            "portfolio": {"type": "top_n_equal_weight", "params": {"top_n": 1}},
            "timing": {"type": "noop"},
            "risk": {"type": "basic_weight_constraint"},
            "backtest": {"initial_cash": 100000},
            "execution_assumption": {"signal_time": "close", "execute_time": "next_open"},
            "output": {"save_result": True, "output_root": str(output_root)},
        },
    )

    with pytest.raises(FileNotFoundError):
        run_strategy_backtest_from_config(str(strategy_path), dm=MockDataManager())

    manifests = list((output_root / "bad_strategy").glob("*/run_manifest.json"))
    assert len(manifests) == 1
    manifest = json.loads(manifests[0].read_text(encoding="utf-8"))
    assert manifest["run_type"] == "strategy"
    assert manifest["status"] == "failed"
    assert manifest["error_message"]


def test_backtest_engine_t_signal_t_plus_one_open_and_daily_close():
    dm = MockDataManager()
    targets = pd.DataFrame({
        "trade_date": pd.to_datetime(["2020-01-01"]),
        "ts_code": ["000001.SZ"],
        "target_weight": [1.0],
        "strategy_id": ["unit_strategy"],
    })
    engine = BacktestEngine(dm=dm, initial_cash=100000, rebalance_frequency="daily")
    equity = engine.run_backtest(targets, start="2020-01-01", end="2020-01-03")
    trades = engine.get_trade_log()

    assert trades["trade_date"].min() == pd.Timestamp("2020-01-02")
    assert not equity.empty
    assert equity["trade_date"].tolist() == list(pd.date_range("2020-01-01", "2020-01-03"))


def test_legacy_top_n_equal_weight_strategy_still_works():
    factor_df = pd.DataFrame({
        "trade_date": pd.to_datetime(["2020-01-01", "2020-01-01"]),
        "ts_code": ["000001.SZ", "000002.SZ"],
        "factor_percentile": [0.9, 0.8],
    })

    target = TopNEqualWeightStrategy(params={"top_n": 1}).generate_target_positions(factor_df)

    assert target["strategy_name"].unique().tolist() == ["top_n_equal_weight"]
    assert target["ts_code"].tolist() == ["000001.SZ"]
