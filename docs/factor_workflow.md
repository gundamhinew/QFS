# Factor Workflow

This document describes the standard workflow for adding, checking, evaluating, and approving factors.

## 1. Update Data

Use the existing data entry point:

```bash
python -m src.main daily_update --end 20260702 --token YOUR_TUSHARE_TOKEN
```

The research commands read local data through `DataManager`. They do not call Tushare directly.

## 2. Create A Factor Template

```bash
python -m src.research factor create \
  --factor-id example_factor \
  --implementation example \
  --class-name ExampleFactor
```

Generated files:

```text
src/factors/example.py
configs/factors/example_factor.yaml
tests/factors/test_example.py
```

The template inherits `BaseFactor`, uses `register_factor`, and marks the calculation body as user implementation work.

## 3. Implement The Factor

The factor implementation should only calculate raw factor values. It should not:

1. Pick Top N stocks.
2. Allocate portfolio weights.
3. Run a backtest.
4. Use future returns.
5. Approve itself in the catalog.

The raw output must satisfy `RawFactorFrame`:

```text
trade_date
ts_code
factor_id
factor_value
```

## 4. Check The Factor

```bash
python -m src.research factor check --config configs/factors/momentum_60.yaml
```

`FactorChecker` checks config validity, registration, build success, raw frame schema, duplicate keys, NaN and inf counts, date coverage, cross-section size, constant values, and universe match.

This step checks implementation and data quality only. It does not calculate IC or investment value.

## 5. Evaluate The Factor

```bash
python -m src.research factor evaluate --config configs/factors/momentum_60.yaml
```

The evaluator computes research-only forward returns from T close to T+h close. These returns are for factor research and are not executable trading returns.

Outputs are saved to:

```text
artifacts/factor_runs/<factor_id>/<run_id>/
```

The directory includes `config_snapshot.yaml`, `run_manifest.json`, `summary.json`, `checker_report.json`, `ic_series.parquet`, `quantile_returns.parquet`, `quantile_nav.parquet`, and `coverage.parquet`.

## 6. Review The Factor Catalog

```bash
python -m src.research factor list
python -m src.research factor show --factor-id momentum_60
```

After a successful evaluation, a draft factor may become `tested`. It never becomes `approved` automatically.

## 7. Approve Or Deprecate

Approve explicitly:

```bash
python -m src.research factor set-status --factor-id momentum_60 --status approved
```

Valid statuses:

```text
draft
tested
approved
deprecated
```

Approval normally requires an existing successful evaluation report. `--force` can override this intentionally.

## 8. Use In A Model

Model configs reference factor configs instead of copying factor parameters:

```yaml
factors:
  - factor_id: momentum_60
    alias: momentum_60
    config: configs/factors/momentum_60.yaml
```

Production-style model configs should use approved factors. Research configs may set:

```yaml
evaluation:
  allow_unapproved: true
```

## Legacy Notes

The old `configs/strategies/momentum_top50_monthly.yaml` remains supported by `src.runner.backtest_runner`. New factor research should use `src.research`.
