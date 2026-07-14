# Config Reference

The platform separates factor, model, and strategy configs.

```text
Factor config
-> Model config
-> Strategy config
```

Factor configs define data and factor construction. Model configs combine processed factor scores into model scores. Strategy configs turn model scores into target positions and run backtests.

## Factor Config

Path:

```text
configs/factors/<factor_id>.yaml
```

Required top-level fields:

```yaml
schema_version: 2
factor_id: momentum_60
implementation: momentum
version: 1
status: tested
metadata: {}
data: {}
period: {}
universe: {}
params: {}
preprocess: {}
evaluation: {}
storage: {}
```

Important fields:

`factor_id` is the concrete factor instance, for example `momentum_60`.

`implementation` is the registered factor implementation, for example `momentum`.

`params` are passed to the factor class.

`preprocess` controls `FactorProcessor` behavior such as direction, winsorization, and standardization.

`status` belongs to the factor catalog and can be `draft`, `tested`, `approved`, or `deprecated`.

## Model Config

Path:

```text
configs/models/<model_id>.yaml
```

Example:

```yaml
schema_version: 2
model_id: momentum_single
model_type: single_factor
version: 1
status: research

factors:
  - factor_id: momentum_60
    alias: momentum_60
    config: configs/factors/momentum_60.yaml

alignment:
  missing_policy: intersection
  min_factor_count: 1

evaluation:
  allow_unapproved: true
  forward_periods: [1, 5, 20]
  quantiles: 5

output:
  output_root: artifacts/model_runs
```

`model_type` selects an AlphaModel implementation.

`factors` references factor configs. It does not duplicate factor parameters.

`alignment.missing_policy` can be `intersection`, `fill_zero`, or `renormalize`.

`allow_unapproved: true` is for research. Without it, model checking requires approved factors.

## Strategy Config

Path:

```text
configs/strategies/<strategy_id>.yaml
```

Example:

```yaml
schema_version: 2
strategy_id: momentum_top50_monthly_v2
version: 1
status: research

data:
  raw_root: data/raw

period:
  start: "2020-01-01"
  end: "2020-12-31"

model:
  config: configs/models/momentum_single.yaml

rebalance:
  frequency: monthly

portfolio:
  type: top_n_equal_weight
  params:
    top_n: 50
    max_single_weight: 0.1
    normalize_weights: true

timing:
  type: noop

risk:
  type: basic_weight_constraint
  max_single_weight: 0.1
  normalize_weights: true

backtest:
  initial_cash: 1000000

execution_assumption:
  signal_time: close
  execute_time: next_open

output:
  output_root: artifacts/strategy_runs
  save_result: true
```

The strategy config references a model config and produces `target_positions` through `StrategyPipeline`.

`rebalance.frequency` controls signal dates before portfolio construction. The legacy `BacktestEngine` rebalance setting remains for compatibility.

`execution_assumption` documents the research assumption. The current backtest engine keeps T signal to T+1 open execution and daily close valuation.

## Legacy Strategy Config

`configs/strategies/momentum_top50_monthly.yaml` is still supported by:

```bash
python -m src.backtest.backtest_runner --config configs/strategies/momentum_top50_monthly.yaml
```

It contains factor, universe, portfolio, and backtest settings in one file. New configs should use the separated factor/model/strategy format.
