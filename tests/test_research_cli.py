from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from src.factor_lab.checker import FactorCheckReport
import src.research as research


@dataclass(frozen=True)
class DummyCreated:
    factor_file: Path
    config_file: Path
    test_file: Path


def test_research_factor_create_cli_parses_args(monkeypatch, tmp_path):
    calls = {}

    def fake_create_factor_template(
        factor_id,
        implementation,
        class_name,
        force=False,
    ):
        calls["factor_id"] = factor_id
        calls["implementation"] = implementation
        calls["class_name"] = class_name
        calls["force"] = force
        return DummyCreated(
            factor_file=tmp_path / "factor.py",
            config_file=tmp_path / "factor.yaml",
            test_file=tmp_path / "test_factor.py",
        )

    monkeypatch.setattr(
        research,
        "create_factor_template",
        fake_create_factor_template,
    )

    exit_code = research.main([
        "factor",
        "create",
        "--factor-id",
        "example_factor",
        "--implementation",
        "example",
        "--class-name",
        "ExampleFactor",
        "--force",
    ])

    assert exit_code == 0
    assert calls == {
        "factor_id": "example_factor",
        "implementation": "example",
        "class_name": "ExampleFactor",
        "force": True,
    }


def test_research_factor_check_cli_parses_args(monkeypatch):
    calls = {}

    def fake_run_factor_check_from_config(config):
        calls["config"] = config
        return {
            "report": FactorCheckReport(
                factor_id="example_factor",
                implementation="example",
            )
        }

    monkeypatch.setattr(
        research,
        "run_factor_check_from_config",
        fake_run_factor_check_from_config,
    )

    exit_code = research.main([
        "factor",
        "check",
        "--config",
        "configs/factors/example_factor.yaml",
    ])

    assert exit_code == 0
    assert calls["config"] == "configs/factors/example_factor.yaml"


def test_research_factor_evaluate_cli_parses_args(monkeypatch, tmp_path):
    calls = {}

    def fake_run_factor_evaluate_from_config(config, refresh=False):
        calls["config"] = config
        calls["refresh"] = refresh
        return {
            "run_manifest": {
                "factor_id": "example_factor",
                "implementation": "example",
                "run_id": "run_1",
                "cache_hit": False,
            },
            "run_dir": tmp_path,
            "evaluation": type(
                "Eval",
                (),
                {
                    "summary": {
                        "coverage_ratio": 1.0,
                        "valid_date_count": 1,
                        "nan_ratio": 0.0,
                        "top_quantile_turnover_mean": 0.0,
                        "bottom_quantile_turnover_mean": 0.0,
                        "ic": {},
                    }
                },
            )(),
        }

    monkeypatch.setattr(
        research,
        "run_factor_evaluate_from_config",
        fake_run_factor_evaluate_from_config,
    )

    exit_code = research.main([
        "factor",
        "evaluate",
        "--config",
        "configs/factors/example_factor.yaml",
        "--refresh",
    ])

    assert exit_code == 0
    assert calls == {
        "config": "configs/factors/example_factor.yaml",
        "refresh": True,
    }


def test_research_factor_catalog_cli_commands(monkeypatch):
    class DummyEntry:
        factor_id = "example_factor"
        implementation = "example"
        version = 1
        status = "draft"
        config_path = "configs/factors/example_factor.yaml"
        metadata = {}
        has_report = False

    class DummyCatalog:
        def list_entries(self):
            return [DummyEntry()]

        def get_entry(self, factor_id):
            assert factor_id == "example_factor"
            return DummyEntry()

        def set_status(self, factor_id, status, force=False):
            assert factor_id == "example_factor"
            assert status == "approved"
            assert force is True
            entry = DummyEntry()
            entry.status = status
            entry.has_report = True
            return entry

    monkeypatch.setattr(research, "FactorCatalog", DummyCatalog)

    assert research.main(["factor", "list"]) == 0
    assert research.main(["factor", "show", "--factor-id", "example_factor"]) == 0
    assert research.main([
        "factor",
        "set-status",
        "--factor-id",
        "example_factor",
        "--status",
        "approved",
        "--force",
    ]) == 0


def test_research_strategy_backtest_cli_parses_args(monkeypatch, tmp_path):
    calls = {}

    def fake_run_strategy_backtest_from_config(config):
        calls["config"] = config
        return {
            "strategy_config": {"strategy_id": "unit_strategy"},
            "target_positions": type("Frame", (), {"shape": (1, 4)})(),
            "equity_curve": type("Frame", (), {"shape": (1, 6)})(),
            "trade_log": type("Frame", (), {"shape": (0, 10)})(),
            "restriction_log": type("Frame", (), {"shape": (0, 5)})(),
            "performance": {"final_nav": 1.0},
            "run_dir": tmp_path,
        }

    monkeypatch.setattr(
        research,
        "run_strategy_backtest_from_config",
        fake_run_strategy_backtest_from_config,
    )

    exit_code = research.main([
        "strategy",
        "backtest",
        "--config",
        "configs/strategies/unit.yaml",
    ])

    assert exit_code == 0
    assert calls["config"] == "configs/strategies/unit.yaml"


def test_research_cli_returns_nonzero_on_runner_error(monkeypatch, capsys):
    def fake_run_strategy_backtest_from_config(config):
        raise ValueError("boom")

    monkeypatch.setattr(
        research,
        "run_strategy_backtest_from_config",
        fake_run_strategy_backtest_from_config,
    )

    exit_code = research.main([
        "strategy",
        "backtest",
        "--config",
        "configs/strategies/unit.yaml",
    ])

    captured = capsys.readouterr()
    assert exit_code == 1
    assert "ERROR: boom" in captured.err
