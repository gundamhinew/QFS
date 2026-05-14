# quant_factor_selection

multi-factor quantitative research framework.

## Features

- Local parquet data warehouse
- SQLite metadata management
- Incremental daily updates
- Tushare integration
- Future QMT integration

## Structure

- `src/datahub` : data layer
- `src/factors` : factor layer
- `src/backtest` : backtest engine
- `src/qmt` : execution layer

## Usage

### Bootstrap

```bash
python -m src.main bootstrap

Daily update
python -m src.main daily_update