# quant_factor_selection

A-share quantitative research, backtesting, and future QMT execution framework.

This project is not intended to be a one-off factor experiment. The goal is to build a reusable, extensible research and trading system for medium- and low-frequency Chinese A-share equity strategies.

## Architecture

```text
Local Data Warehouse
-> DataManager
-> UniverseBuilder
-> Factor Layer
-> FactorProcessor
-> Strategy Layer
-> BacktestEngine
-> Account / Broker / PerformanceAnalyzer
-> QMT Adapter (future)
```

Core principles:

- Keep data, factor, strategy, backtest, and execution responsibilities separate.
- Keep research logic outside QMT.
- Use standardized `target_positions` as the interface between strategy, backtest, and future execution.
- Do not modify local raw market data, parquet files, metadata databases, or tokens during research runs.

## Current Capabilities

The system currently supports:

1. Local A-share data layer based on Parquet and SQLite metadata.
2. `DataManager` unified data access.
3. `UniverseBuilder` for tradable universe filtering.
4. Factor framework and a 60-day momentum example.
5. `FactorProcessor` for winsorization, z-score, ranking, and percentile score.
6. Strategy layer with `TopNEqualWeightStrategy`.
7. `BacktestEngine` with:
   - T-day signal;
   - T+1 open execution;
   - T+1 close valuation;
   - limit-up / limit-down restrictions;
   - 100-share lot-size handling;
   - daily / weekly / monthly rebalance frequency.
8. `PerformanceAnalyzer` with:
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

## Project Structure

```text
quant_factor_selection/
|-- config/
|-- data/
|   |-- raw/
|   |-- factor/
|   `-- meta/
|-- examples/
|   `-- run_momentum_backtest.py
|-- src/
|   |-- backtest/
|   |   |-- account.py
|   |   |-- broker.py
|   |   |-- engine.py
|   |   |-- order_utils.py
|   |   |-- performance.py
|   |   |-- rebalance.py
|   |   `-- trading_rules.py
|   |-- datahub/
|   |-- factors/
|   |-- strategies/
|   |-- universe/
|   `-- qmt/
|-- requirements.txt
`-- README.md
```

## Usage

Bootstrap base data:

```bash
python -m src.main bootstrap
```

Run daily market updates:

```bash
python -m src.main daily_update
```

Run the 60-day momentum TopN backtest example:

```bash
python examples/run_momentum_backtest.py
```

The example prints key parameters, intermediate dataset shapes, equity curve tail, trade log head, restriction log head, and the performance summary.

## Backtest Design

`BacktestEngine` consumes strategy-generated `target_positions`.

`trade_date` in `target_positions` is the signal date:

```text
signal_date close -> target portfolio is known
next trading day open -> orders execute
next trading day close -> account is valued
```

Trading rules such as limit-up / limit-down checks, 100-share lot-size handling, and rebalance frequency filtering are handled in the backtest layer before orders reach `Broker`.

`Broker` is responsible for order execution, transaction costs, slippage, cash updates, and position updates.

`Account` is responsible for cash, positions, total equity, NAV, and account history.

## Rebalance Frequency

`BacktestEngine` supports:

- `daily`: use every available signal date;
- `weekly`: use the last available signal date in each natural week;
- `monthly`: use the last available signal date in each natural month.

The rebalance frequency controls which signal dates are used. Execution still follows T+1 open execution and T+1 close valuation.

## Performance Metrics

Turnover is reported with three fields:

- `total_turnover`: total absolute traded value divided by average total equity over the backtest period;
- `average_daily_turnover`: average of daily traded value divided by that day's total equity;
- `annualized_turnover`: `average_daily_turnover * annualization`, with annualization defaulting to 252.

## Not Yet Implemented

The following items are still future work:

1. Volume participation constraints.
2. More precise suspension handling.
3. More precise historical price-limit rules.
4. Industry neutrality.
5. Multi-factor combination.
6. Benchmark comparison.
7. QMT Adapter.

## Development Rules

Codex and contributors should follow these rules:

1. Do not write one-off scripts when the logic belongs in existing modules.
2. Do not bypass the existing architecture.
3. New factors should inherit `BaseFactor`.
4. New strategies should inherit `BaseStrategy`.
5. Do not directly modify parquet files, raw market data, metadata databases, or token files.
6. Keep `Broker` and `Account` responsibilities separate.
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
