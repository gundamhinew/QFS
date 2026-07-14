from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from src.core.config_loader import (
    ConfigError,
    get_schema_version,
    load_strategy_config,
    resolve_project_path,
)


def test_get_schema_version_defaults_legacy_config_to_v1():
    assert get_schema_version({}) == 1


def test_get_schema_version_accepts_supported_versions():
    assert get_schema_version({"schema_version": 1}) == 1
    assert get_schema_version({"schema_version": 2}) == 2


def test_get_schema_version_rejects_unsupported_version():
    with pytest.raises(ConfigError, match="Unsupported schema_version"):
        get_schema_version({"schema_version": 99})


def test_resolve_project_path_resolves_relative_to_project_root():
    path = resolve_project_path("configs/datahub.yaml")

    assert path.is_absolute()
    assert path.name == "datahub.yaml"


def test_load_strategy_config_adds_schema_version_for_legacy_config():
    config = load_strategy_config(
        "configs/strategies/momentum_top50_monthly.yaml"
    )

    assert config["schema_version"] == 1


class FakeDataManager:
    def __init__(self, raw_root):
        self.raw_root = raw_root

    def get_daily_price(self, start, end, ts_codes=None):
        rows = []
        dates = pd.date_range("2020-01-01", periods=5, freq="D")
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


class FakeBacktestEngine:
    def __init__(self, dm, initial_cash=1_000_000, rebalance_frequency="daily"):
        self.target_positions = None

    def run_backtest(self, target_positions, start, end):
        assert not target_positions.empty
        assert {"trade_date", "ts_code", "target_weight", "strategy_name"}.issubset(
            target_positions.columns
        )
        self.target_positions = target_positions.copy()
        return pd.DataFrame({
            "trade_date": pd.to_datetime(["2020-01-02", "2020-01-03"]),
            "total_equity": [1_000_000, 1_001_000],
            "nav": [1.0, 1.001],
        })

    def get_trade_log(self):
        return pd.DataFrame({
            "trade_date": pd.to_datetime(["2020-01-02"]),
            "trade_value": [1000.0],
        })

    def get_restriction_log(self):
        return pd.DataFrame()


class FakePerformanceAnalyzer:
    def analyze(self, equity_curve, trade_log=None):
        assert not equity_curve.empty
        return {"final_nav": float(equity_curve["nav"].iloc[-1])}


def test_old_backtest_runner_reaches_existing_logic(tmp_path, monkeypatch):
    import src.backtest.backtest_runner as runner

    config_path = tmp_path / "strategy.yaml"
    config_path.write_text(
        """
strategy_name: test_momentum_top2
data:
  raw_root: "data/raw"
backtest:
  start: "2020-01-01"
  end: "2020-01-05"
  initial_cash: 1000000
  rebalance_frequency: "daily"
universe:
  min_list_days: 1
  min_close: 2.0
  min_amount_yuan: 1
factor:
  type: "momentum"
  params:
    lookback: 1
  direction: "positive"
  min_count: 1
portfolio:
  type: "top_n_equal_weight"
  params:
    top_n: 2
output:
  print_detail: false
  save_result: false
""",
        encoding="utf-8",
    )

    monkeypatch.setattr(runner, "DataManager", FakeDataManager)
    monkeypatch.setattr(runner, "BacktestEngine", FakeBacktestEngine)
    monkeypatch.setattr(runner, "PerformanceAnalyzer", FakePerformanceAnalyzer)

    result = runner.run_backtest_from_config(str(config_path))

    assert not result["target_positions"].empty
    assert result["performance"]["final_nav"] == pytest.approx(1.001)
