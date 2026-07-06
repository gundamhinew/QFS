# quant_factor_selection

A-share quantitative factor research and backtesting framework.

The current architecture uses `target_positions` as the boundary between research, backtesting, and future execution. QMT integration is still future work and is not implemented in this repository yet.

## Quick Start

The recommended research entry point is:

```bash
python -m src.research --help
```

The complete workflow is:

```text
update data
-> create factor
-> check factor
-> evaluate factor
-> approve factor
-> create model config
-> evaluate model
-> create strategy config
-> backtest strategy
```

## Commands

Update local data with the existing data commands:

```bash
python -m src.main bootstrap --start 20160101 --end 20260702 --token YOUR_TUSHARE_TOKEN
python -m src.main sync_daily_range --start 20160101 --end 20260702 --token YOUR_TUSHARE_TOKEN
python -m src.main daily_update --end 20260702 --token YOUR_TUSHARE_TOKEN
python -m src.main financial_update --start 20160101 --end 20260702 --token YOUR_TUSHARE_TOKEN
```

Create a factor template:

```bash
python -m src.research factor create --factor-id example_factor --implementation example --class-name ExampleFactor
```

Check a factor:

```bash
python -m src.research factor check --config configs/factors/momentum_60.yaml
```

Evaluate a factor:

```bash
python -m src.research factor evaluate --config configs/factors/momentum_60.yaml
```

Review and approve factor catalog state:

```bash
python -m src.research factor list
python -m src.research factor show --factor-id momentum_60
python -m src.research factor set-status --factor-id momentum_60 --status approved
```

Evaluate an alpha model:

```bash
python -m src.research model evaluate --config configs/models/momentum_single.yaml
```

Run the unified strategy pipeline and backtest:

```bash
python -m src.research strategy backtest --config configs/strategies/momentum_top50_monthly_v2.yaml
```

The legacy strategy runner is still supported:

```bash
python -m src.runner.backtest_runner --config configs/strategies/momentum_top50_monthly.yaml
```

`configs/strategies/momentum_top50_monthly.yaml` is the legacy single-factor strategy config. It remains runnable for compatibility, but new research should use separate factor, model, and strategy configs.

## Architecture

```text
DataManager
-> UniverseBuilder
-> FactorRegistry / BaseFactor
-> FactorProcessor
-> FactorChecker / FactorEvaluator / FactorStore / FactorCatalog
-> AlphaModel
-> ModelEvaluator
-> StrategyPipeline
-> PortfolioBuilder
-> TimingOverlay
-> RiskOverlay
-> target_positions
-> BacktestEngine
-> PerformanceAnalyzer
```

Single-factor and multi-factor strategies use the same backtest path:

```text
Factor configs
-> ProcessedFactorFrame
-> AlphaModel
-> ModelScoreFrame
-> StrategyPipeline
-> target_positions
-> BacktestEngine
```

## Configs

```text
configs/
|-- datahub.yaml
|-- factors/
|   `-- momentum_60.yaml
|-- models/
|   `-- momentum_single.yaml
`-- strategies/
    |-- momentum_top50_monthly.yaml
    `-- momentum_top50_monthly_v2.yaml
```

Factor configs define concrete factor instances such as `momentum_60`.

Model configs reference factor configs and produce `model_score`.

Strategy configs reference model configs and produce `target_positions` through `StrategyPipeline`.

See [docs/config_reference.md](docs/config_reference.md) for field details.

## Run Artifacts

Research and backtest outputs are written under:

```text
artifacts/
|-- factor_runs/<factor_id>/<run_id>/
|-- model_runs/<model_id>/<run_id>/
`-- strategy_runs/<strategy_id>/<run_id>/
```

Each run writes a config snapshot and `run_manifest.json`. Strategy runs also write:

```text
performance.json
target_positions.parquet
equity_curve.parquet
trade_log.parquet
restriction_log.parquet
```

Artifacts are ignored by Git.

## Legacy Scripts

`scratch_run_momentum_actual.py` has been moved to `examples/legacy/` as historical reference only. It is not a formal entry point.

`examples/run_momentum_backtest.py` is a demonstration script. For reproducible research, use `python -m src.research` or the legacy runner command above.

## Data Contract Summary

`RawFactorFrame`:

```text
trade_date, ts_code, factor_id, factor_value
```

`ProcessedFactorFrame`:

```text
trade_date, ts_code, factor_id, raw_value, factor_score
```

`ModelScoreFrame`:

```text
trade_date, ts_code, model_id, model_score
```

`TargetPositions`:

```text
trade_date, ts_code, target_weight, strategy_id
```

`trade_date` in `target_positions` is the signal date. `BacktestEngine` maps T-day signals to T+1 open execution and values the account at daily close.

## Git Hygiene

Do not commit:

```text
artifacts/
data/raw/**/*.parquet
data/factor/
data/factor/**/*.parquet
data/meta/*.db
.venv/
logs/
token
real account information
```

## Not Yet Implemented

The following remain outside the current scope:

1. New factor implementations beyond the existing momentum example.
2. New AlphaModel types beyond the implemented basic models.
3. New timing algorithms beyond `NoOpTiming`.
4. Portfolio optimization.
5. QMT or live trading integration.
6. Real account handling.
7. Automated factor approval.
