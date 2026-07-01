# quant_factor_selection

A-share quantitative research and backtesting framework, with future QMT execution integration planned around a standard `target_positions` interface.

This project is not intended to be a one-off factor experiment. The goal is to build a reusable, extensible research and trading system for medium- and low-frequency Chinese A-share equity strategies.

## Architecture

```text
DataManager
-> UniverseBuilder
-> Factor Registry
-> FactorProcessor
-> Strategy Registry
-> target_positions
-> BacktestEngine
-> PerformanceAnalyzer
```

`target_positions` is the standard interface between research, backtesting, and future live execution.

Backtesting consumes `target_positions` directly. Future QMT integration should also be built around `target_positions` and a separate execution layer, not by placing QMT logic inside the backtest broker.

## Recommended Workflow

The project has moved from an example-driven workflow to a config-driven backtest workflow.

Run a strategy backtest with:

```bash
python -m src.runner.backtest_runner --config configs/strategies/momentum_top50_monthly.yaml
```

Strategy configuration files live in:

```text
configs/strategies/
```

Datahub settings live in:

```text
configs/datahub/settings.yaml
```

The current example config is:

```text
configs/strategies/momentum_top50_monthly.yaml
```

`examples/run_momentum_backtest.py` is kept only as a demonstration script. It is no longer the recommended production-style entry point.

## Current Capabilities

The system currently supports:

1. Local A-share data layer based on Parquet and SQLite metadata.
2. `DataManager` unified data access.
3. `UniverseBuilder` for tradable universe filtering.
4. Factor registry and a 60-day momentum factor.
5. `FactorProcessor` for winsorization, z-score, ranking, and percentile score.
6. Strategy registry and `TopNEqualWeightStrategy`.
7. Config-driven backtest runner.
8. `BacktestEngine` with:
   - T-day signal;
   - T+1 open execution;
   - daily close valuation;
   - limit-up / limit-down restrictions;
   - 100-share lot-size handling;
   - daily / weekly / monthly rebalance frequency.
9. `PerformanceAnalyzer` with:
   - `final_nav`
   - `total_return`
   - `annual_return`
   - `annual_volatility`
   - `sharpe`
   - `max_drawdown`
   - `total_turnover`
   - `average_daily_turnover`
   - `annualized_turnover`
   - `number_of_trades`

## Strategy Config

A strategy config defines parameters only. It should not contain Python logic.

Example:

```yaml
strategy_name: momentum_top50_monthly

data:
  raw_root: "data/raw"

backtest:
  start: "2020-01-01"
  end: "2020-12-31"
  initial_cash: 1000000
  rebalance_frequency: "monthly"

universe:
  min_list_days: 120
  min_close: 2.0
  min_amount_yuan: 30000000

factor:
  type: "momentum"
  params:
    lookback: 60
  direction: "positive"
  min_count: 50

portfolio:
  type: "top_n_equal_weight"
  params:
    top_n: 50

output:
  print_detail: true
  save_result: false
```

## Backtest Design

`trade_date` in `target_positions` is the signal date:

```text
signal_date close -> target portfolio is known
next trading day open -> orders execute
every trading day close -> account is valued
```

Rebalance frequency controls which signal dates are used. Valuation frequency is always daily.

`Broker` is responsible for order execution, transaction costs, slippage, cash updates, and position updates.

`Account` is responsible for cash, positions, total equity, NAV, and account history.

Trading rules such as limit-up / limit-down checks, 100-share lot-size handling, and rebalance frequency filtering are handled by `BacktestEngine` before orders reach `Broker`.

## Project Structure

```text
quant_factor_selection/
|-- configs/
|   |-- datahub/
|   |   `-- settings.yaml
|   `-- strategies/
|       `-- momentum_top50_monthly.yaml
|-- data/
|   |-- raw/
|   |-- factor/
|   `-- meta/
|-- examples/
|   `-- run_momentum_backtest.py
|-- src/
|   |-- backtest/
|   |-- datahub/
|   |-- factors/
|   |-- runner/
|   |   |-- config_loader.py
|   |   `-- backtest_runner.py
|   |-- strategies/
|   |-- universe/
|   `-- qmt/
|-- requirements.txt
`-- README.md
```

## Data Update Commands

Bootstrap base data:

```bash
python -m src.main bootstrap --token YOUR_TUSHARE_TOKEN
```

Run daily market updates:

```bash
python -m src.main daily_update --token YOUR_TUSHARE_TOKEN
```

Backfill historical daily market data:

```bash
python -m src.main backfill_daily --start 20160101 --end 20171231 --token YOUR_TUSHARE_TOKEN
```

## Not Yet Implemented

The following items are still future work:

1. Data update panel.
2. Execution layer.
3. QMT dry-run adapter.
4. QMT paper trading.
5. Real trading confirmation workflow.
6. Volume participation constraints.
7. More precise suspension handling.
8. More precise historical price-limit rules.
9. Industry neutrality.
10. Multi-factor combination.
11. Benchmark comparison.

QMT integration is planned, but it has not been implemented yet.

## Development Rules

Codex and contributors should follow these rules:

1. Do not write one-off scripts when the logic belongs in existing modules.
2. Do not bypass the existing architecture.
3. New factors should inherit `BaseFactor` and be exposed through the factor registry.
4. New strategies should inherit `BaseStrategy` and be exposed through the strategy registry.
5. Do not directly modify parquet files, raw market data, metadata databases, or token files.
6. Keep backtest broker and future execution broker responsibilities separate.
7. Keep strategy outputs centered on `target_positions`.

Git should manage source code and documentation only. Do not commit:

```text
data/raw/**/*.parquet
data/factor/**/*.parquet
data/meta/*.db
.venv/
logs/
tokens
real account information
```
