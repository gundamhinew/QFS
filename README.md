# quant_factor_selection

A-share multi-factor quantitative research, backtesting, and QMT execution framework.

This project is not intended to be a one-off factor experiment.  
Its goal is to build a reusable, extensible, and production-oriented quantitative research and trading system for the Chinese A-share market.

The framework is designed around:

```text
Local Data Warehouse
+ Standardized Factor Interface
+ Strategy Layer
+ Portfolio Construction
+ Backtest Engine
+ QMT Execution Adapter
```

The project will be continuously extended with Codex Agent to:

- reproduce academic factors and trading strategies;
- test and iterate multi-factor models;
- simulate realistic A-share trading constraints;
- incorporate transaction frictions;
- eventually generate outputs directly executable in QMT.

---

# 1. Project Goals

The framework focuses on medium- and low-frequency A-share equity strategies.

Main objectives:

1. Build a local A-share data warehouse;
2. Create unified data access interfaces;
3. Standardize factor research workflows;
4. Support multi-factor strategy development;
5. Build a reusable backtesting framework;
6. Simulate realistic portfolio/account behavior;
7. Model realistic Chinese market constraints and frictions;
8. Eventually generate QMT-compatible execution outputs.

---

# 2. Overall Architecture

```text
Tushare
↓
DataHub / Parquet / SQLite
↓
DataManager
↓
Factor Layer
↓
FactorProcessor
↓
Strategy Layer
↓
Target Positions
↓
Backtest Engine
↓
Account / Broker / Performance
↓
QMT Adapter (future)
```

Core design principles:

- Separate data, factor, strategy, backtest, and execution layers;
- Share logic between backtest and live trading whenever possible;
- Use QMT as execution infrastructure only;
- Keep research logic outside QMT;
- Ensure all strategies output standardized target positions;
- Avoid rewriting infrastructure when adding new factors or strategies.

---

# 3. Project Structure

```text
quant_factor_selection/
├── config/
│   └── settings.yaml
│
├── data/
│   ├── raw/
│   ├── factor/
│   └── meta/
│
├── examples/
│
├── src/
│   ├── main.py
│   │
│   ├── datahub/
│   │   ├── client.py
│   │   ├── storage.py
│   │   ├── meta_db.py
│   │   ├── schemas.py
│   │   ├── data_manager.py
│   │   ├── downloaders/
│   │   └── jobs/
│   │
│   ├── factors/
│   │   ├── base.py
│   │   ├── processor.py
│   │   ├── registry.py
│   │   └── momentum.py
│   │
│   ├── strategies/
│   │   ├── base.py
│   │   ├── registry.py
│   │   └── top_n_strategy.py
│   │
│   ├── backtest/
│   │   ├── account.py
│   │   ├── broker.py
│   │   ├── engine.py
│   │   ├── performance.py
│   │   └── result.py
│   │
│   └── qmt/
│
├── requirements.txt
├── .gitignore
└── README.md
```

---

# 4. Data Layer

The data layer converts external financial data into reusable local structured assets.

Current data source:

```text
Tushare
```

Currently supported datasets:

| Dataset | Description |
|---|---|
| stock_basic | Stock master table |
| trade_calendar | Trading calendar |
| daily_price | Daily OHLCV data |
| adj_factor | Adjustment factors |
| daily_basic | Daily valuation and market data |

Storage design:

```text
SQLite:
    metadata, job status, task tracking

Parquet:
    market data, factor data, fundamentals
```

Git does NOT manage raw market data.

---

# 5. Usage

The project currently uses:

```bash
python -m src.main <job_name>
```

as the unified CLI entry point.

---

## 5.1 Bootstrap Base Data

Downloads:

- stock master table;
- trading calendar.

```bash
python -m src.main bootstrap
```

Usually only needed once.

---

## 5.2 Daily Market Update

Downloads:

- daily prices;
- adjustment factors;
- daily fundamentals.

```bash
python -m src.main daily_update
```

Recommended to run once per trading day.

Supports resumable incremental updates.

---

## 5.3 Financial Statement Update

Downloads:

- income statement;
- balance sheet;
- cash flow statement;
- financial indicators.

```bash
python -m src.main financial_update
```

Limit update size:

```bash
python -m src.main financial_update --limit 100
```

---

# 6. DataManager

`DataManager` is the unified data access layer.

Responsibilities:

- read parquet partitions;
- merge multiple partitions;
- standardize datetime formats;
- load price/fundamental datasets;
- generate adjusted prices.

Example:

```python
from src.datahub.data_manager import DataManager

dm = DataManager()

price = dm.get_adjusted_price(
    start="2020-01-01",
    end="2020-12-31",
    ts_codes=["000001.SZ"],
    adjust="total_return"
)
```

---

# 7. Factor Layer

All factors must inherit from:

```python
BaseFactor
```

and implement:

```python
build(start, end, universe)
```

Standard output schema:

```text
ts_code
trade_date
factor_value
factor_name
```

---

## Current Example Factor

### 60-Day Momentum

```python
mom_60 = adj_close / adj_close.shift(60) - 1
```

---

# 8. Factor Processor

Raw factors should NOT be directly used for trading.

Current processing pipeline:

```text
Raw Factor
↓
Drop Missing Values
↓
Winsorization
↓
Z-score Standardization
↓
Direction Alignment
↓
Cross-sectional Ranking
↓
Percentile Score
```

Core outputs:

| Field | Description |
|---|---|
| factor_value | Raw factor |
| factor_winsorized | Winsorized factor |
| factor_zscore | Standardized factor |
| factor_score | Direction-aligned factor |
| factor_rank | Cross-sectional rank |
| factor_percentile | Cross-sectional percentile |

Definitions:

```text
factor_rank:
    1 = best stock

factor_percentile:
    closer to 1 = better
```

---

# 9. Strategy Layer

The strategy layer converts processed factor signals into target portfolios.

Responsibilities:

- portfolio selection;
- portfolio weighting;
- rebalance logic.

Does NOT handle:

- raw data download;
- factor calculation;
- order execution;
- account simulation.

Standard output schema:

```text
trade_date
ts_code
target_weight
strategy_name
```

---

## Current Example Strategy

### TopNEqualWeightStrategy

Logic:

```text
Select top N stocks ranked by factor percentile
and assign equal weights.
```

This output becomes the unified input for:

- backtesting;
- QMT execution.

---

# 10. Backtest Layer

The backtest system simulates realistic account behavior instead of merely computing returns.

---

## 10.1 Account

Stores:

- cash;
- positions;
- market value;
- total equity;
- NAV history.

---

## 10.2 Broker

Handles:

- buy/sell execution;
- cash updates;
- position updates;
- commissions;
- stamp tax;
- slippage.

---

## 10.3 BacktestEngine

Handles:

- time iteration;
- rebalancing;
- broker interaction;
- account updates;
- NAV generation;
- trade logs.

---

# 11. Currently Implemented Trading Frictions

Currently supported:

- commissions;
- stamp tax;
- slippage;
- cash constraints.

Planned future additions:

- suspension handling;
- price limit handling;
- T+1 restrictions;
- lot size constraints;
- volume constraints;
- rebalance frequency control;
- industry neutrality;
- risk exposure constraints.

---

# 12. Current Working Pipeline

The following full pipeline has already been successfully implemented:

```text
DataManager
↓
MomentumFactor
↓
FactorProcessor
↓
TopNEqualWeightStrategy
↓
BacktestEngine
↓
Equity Curve / Trade Log
```

The project already functions as an initial quantitative trading system prototype.

---

# 13. QMT Direction

The final goal is to generate outputs executable in broker QMT environments.

Target architecture:

```text
Local Research System
↓
Generate target_positions
↓
QMT Adapter reads target_positions
↓
Query live account positions
↓
Compute rebalance differences
↓
Generate orders
↓
QMT executes trades
```

Core principle:

```text
Research System ≠ Execution System
```

Research components:

- factor research;
- strategy logic;
- portfolio construction;
- backtesting;

should remain outside QMT.

QMT should only handle:

- account querying;
- position querying;
- order generation;
- order execution.

---

# 14. Future Development Roadmap

## 14.1 Universe Filtering

Planned module:

```text
src/universe/
```

Filters:

- ST stocks;
- Beijing Exchange stocks;
- newly listed stocks;
- suspended stocks;
- illiquid stocks;
- penny stocks.

---

## 14.2 Rebalance Frequency Control

Support:

- daily rebalance;
- weekly rebalance;
- monthly rebalance.

---

## 14.3 Performance Analyzer

Planned metrics:

- annualized return;
- annualized volatility;
- Sharpe ratio;
- maximum drawdown;
- turnover;
- excess return.

---

## 14.4 Benchmarks

Planned benchmarks:

- CSI300;
- CSI500;
- CSI1000;
- broad market benchmarks.

---

## 14.5 Multi-Factor Models

Planned support:

- factor combination;
- IC weighting;
- rank IC weighting;
- industry neutrality;
- market-cap neutrality;
- risk-constrained optimization.

---

## 14.6 Additional Factors

Planned factor categories:

- valuation;
- quality;
- growth;
- low volatility;
- turnover;
- earnings quality;
- NLP/text factors;
- academic paper replications.

---

## 14.7 QMT Execution Layer

Planned features:

- target position synchronization;
- rebalance computation;
- auto order generation;
- paper trading;
- live trading.

---

# 15. Codex Agent Development Rules

Codex Agent will be continuously used to extend this project.

Codex modifications must follow these rules:

1. Do NOT write one-off scripts;
2. Do NOT bypass existing architecture;
3. New factors must inherit `BaseFactor`;
4. New strategies must inherit `BaseStrategy`;
5. Reuse logic between backtest and live trading whenever possible;
6. Do NOT directly modify parquet files;
7. Do NOT commit tokens or databases;
8. Preserve meaningful comments and documentation;
9. All execution outputs should revolve around `target_positions`.

Recommended factor development flow:

```text
Read factor definition
↓
Identify required datasets
↓
Check DataManager support
↓
Implement Factor
↓
Register Factor
↓
Process Factor
↓
Attach Strategy
↓
Run Backtest
↓
Validate Results
```

Recommended strategy development flow:

```text
Define strategy input
↓
Define rebalance frequency
↓
Define selection logic
↓
Define weighting scheme
↓
Implement Strategy
↓
Generate target_positions
↓
Run Backtest
↓
Analyze turnover and NAV
```

---

# 16. Git Management Rules

Git manages CODE only.

Do NOT commit:

```text
data/raw/**/*.parquet
data/factor/**/*.parquet
data/meta/*.db
.venv/
logs/
tokens
real account information
```

Commit:

```text
src/
config/
README.md
requirements.txt
.gitignore
```

---

# 17. Final Goal

The final goal is NOT a one-off factor experiment.

The goal is to build a long-term extensible A-share quantitative research and trading system capable of:

- continuously reproducing academic factors;
- researching new strategies;
- simulating realistic trading;
- modeling transaction frictions;
- generating QMT-compatible outputs;
- supporting both paper trading and live trading.