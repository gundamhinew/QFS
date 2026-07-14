# A 股多因子研究平台分阶段实施计划

本文档把目标架构拆分为六个工作包。每次只能实施一个工作包；每个工作包完成后必须停止，并等待用户确认后才能进入下一包。

本计划不代表本次要实施这些工作包。本次仅新增文档。

## 总体原则

- 保留当前可运行链路：`DataManager -> UniverseBuilder -> MomentumFactor -> FactorProcessor -> TopNEqualWeightStrategy -> BacktestEngine -> PerformanceAnalyzer`。
- 以 `target_positions` 作为研究、回测和未来执行的统一边界。
- 单因子和多因子共享同一套回测体系，不建立两套 BacktestEngine。
- 先补契约和兼容层，再扩展研究、模型、组合、CLI 和报告能力。
- 不修改 `data/raw`、`data/meta`，不手工修改 parquet，不提交 token 或真实账户信息。
- 单元测试和验收不得调用真实 Tushare。
- 每个工作包都要有清晰回滚路径。

## 工作包一：架构基础、数据契约、FactorRegistry 和兼容迁移

### 目标

建立目标架构的最小骨架和数据契约，让后续模块有稳定边界，同时保持现有回测完全可运行。

### 输入

- 当前 `README.md`。
- 当前 `src/datahub/`。
- 当前 `src/universe/`。
- 当前 `src/factors/`。
- 当前 `src/strategies/`。
- 当前 `src/backtest/`。
- 当前 `src/runner/backtest_runner.py`。
- 当前 `configs/strategies/momentum_top50_monthly.yaml`。

### 输出

- `src/contracts/` 中的标准数据契约定义。
- RawFactorFrame、ProcessedFactorFrame、ModelScoreFrame、TimingFrame、TargetPositions 的字段说明和校验入口。
- 保留 `FACTOR_REGISTRY` 的兼容适配层。
- 明确 `factor_id` 和当前 `factor_name` 的迁移关系。
- 保留旧 `target_positions.strategy_name`，同时为未来 `strategy_id` 做兼容准备。

### 文件变更范围

允许新增或修改：

```text
src/contracts/
src/factors/registry.py
src/factors/base.py
src/strategies/base.py
docs/
tests/ 或项目现有测试目录
```

谨慎修改：

```text
src/runner/backtest_runner.py
```

不得修改：

```text
data/raw/
data/meta/
configs/strategies/momentum_top50_monthly.yaml
src/backtest/engine.py
```

除非用户明确批准，否则第一包不改 `BacktestEngine`。

### 依赖关系

无前置工作包。它是后续所有工作包的基础。

### 验收标准

- 当前命令仍可运行：

```bash
python -m src.backtest.backtest_runner --config configs/strategies/momentum_top50_monthly.yaml
```

- 当前 `MomentumFactor` 仍可通过 `FACTOR_REGISTRY["momentum"]` 创建。
- 当前 `TopNEqualWeightStrategy` 仍可通过 `STRATEGY_REGISTRY["top_n_equal_weight"]` 创建。
- 新契约校验不会破坏旧输出。
- 文档说明每个标准 DataFrame 的字段、唯一性和日期语义。
- 不产生真实数据写入。

### 回滚和兼容要求

- 新增契约模块应可独立移除，不影响旧 runner。
- 任何兼容适配层不得改变旧字段含义。
- 若迁移失败，回滚新增 `src/contracts/` 和相关适配代码后，旧链路应恢复。

### 停止点

完成后必须停止，提交结果说明，等待用户确认是否进入工作包二。

## 工作包二：新因子创建、因子配置和 FactorChecker

### 目标

建立新因子的标准创建和检查流程，让因子从“代码实现”变成“实现 + 配置 + 数据质量检查”的可管理对象。

### 输入

- 工作包一的数据契约。
- 当前 `BaseFactor`、`MomentumFactor`、`FACTOR_REGISTRY`。
- 目标因子配置路径 `configs/factors/<factor_id>.yaml`。

### 输出

- `configs/factors/` 目录结构。
- 因子配置 schema 或校验逻辑。
- 因子创建模板。
- `FactorChecker`。
- 因子检查命令的底层能力。
- 当前 `MomentumFactor` 的兼容配置样例，前提是不破坏旧策略配置。

### 文件变更范围

允许新增或修改：

```text
configs/factors/
src/factor_lab/
src/factors/
src/contracts/
docs/
tests/ 或项目现有测试目录
```

谨慎修改：

```text
src/runner/
```

不得修改：

```text
data/raw/
data/meta/
src/backtest/
```

### 依赖关系

依赖工作包一完成的数据契约和兼容入口。

### 验收标准

- 能基于配置定位因子实现。
- `FactorChecker` 能检查字段存在性、唯一性、数值类型、`inf`、缺失率和覆盖率。
- 检查结果能清晰区分 error 和 warning。
- 当前旧回测配置仍能运行。
- 不自动批准任何因子。
- 不调用真实 Tushare。

### 回滚和兼容要求

- 删除 `configs/factors/` 和 `src/factor_lab/` 新增内容后，旧回测链路仍可运行。
- 旧 `factor.type: momentum` 不能被强制迁移。
- 因子配置失败不能影响已有 runner。

### 停止点

完成后必须停止，提交结果说明，等待用户确认是否进入工作包三。

## 工作包三：FactorEvaluator、FactorStore 和 FactorCatalog

### 目标

建立单因子研究闭环：评估因子预测能力，保存评估结果和研究报告，并用人工状态管理纳入因子库。

### 输入

- 工作包一的数据契约。
- 工作包二的因子配置和 `FactorChecker`。
- 本地行情数据读取能力。
- 当前 `FactorProcessor`。

### 输出

- `FactorEvaluator`。
- `FactorStore`。
- `FactorCatalog`。
- 因子状态管理：`draft / tested / approved / deprecated`。
- 单因子评估报告结构。
- 因子最近评估结果索引。

### 文件变更范围

允许新增或修改：

```text
src/factor_lab/
src/factors/
src/contracts/
artifacts/factor_runs/ 或其创建逻辑
configs/factors/
docs/
tests/ 或项目现有测试目录
```

谨慎修改：

```text
src/runner/
```

不得修改：

```text
data/raw/
data/meta/
src/backtest/engine.py
configs/strategies/momentum_top50_monthly.yaml
```

### 依赖关系

依赖工作包二完成。没有 `FactorChecker` 和因子配置前，不应实现完整 `FactorCatalog`。

### 验收标准

- 能对单因子输出覆盖率、IC、Rank IC、ICIR、分层收益、Top-Bottom 收益、衰减、换手和年度稳定性中的核心指标。
- 评估完成后状态最多进入 `tested`，不得自动进入 `approved`。
- `approved` 必须由用户显式命令或显式操作触发。
- 评估结果可复现，并记录配置、日期区间和版本信息。
- 当前旧回测配置仍能运行。

### 回滚和兼容要求

- `FactorEvaluator`、`FactorStore`、`FactorCatalog` 的失败不得阻断旧 runner。
- 运行结果应写入 `artifacts/factor_runs/`，不得写入 `data/raw` 或 `data/meta`。
- 回滚时移除新增评估和 catalog 模块后，因子计算与旧回测保持可用。

### 停止点

完成后必须停止，提交结果说明，等待用户确认是否进入工作包四。

## 工作包四：AlphaModel、FactorAligner 和 ModelEvaluator

### 目标

建立多因子模型层，把多个已处理因子组合成标准 `model_score`，并评估模型效果。

### 输入

- 已检查或已评估的因子。
- `ProcessedFactorFrame`。
- `configs/models/<model_id>.yaml` 目标结构。
- 工作包三的因子 catalog 和评估结果。

### 输出

- `src/alpha_models/`。
- `src/model_lab/`。
- `FactorAligner`。
- `SingleFactorAlphaModel`。
- `EqualWeightAlphaModel`。
- `WeightedScoreAlphaModel`。
- 可扩展的模型 registry。
- `ModelEvaluator`。
- `ModelScoreFrame`。
- 模型评估报告和运行结果。

### 文件变更范围

允许新增或修改：

```text
configs/models/
src/alpha_models/
src/model_lab/
src/contracts/
artifacts/model_runs/ 或其创建逻辑
docs/
tests/ 或项目现有测试目录
```

谨慎修改：

```text
src/factor_lab/
src/runner/
```

不得修改：

```text
data/raw/
data/meta/
src/backtest/engine.py
```

### 依赖关系

依赖工作包三完成。多因子模型应只消费 `ProcessedFactorFrame` 或 catalog 中可复现的因子结果。

### 验收标准

- 单因子也可以通过 `SingleFactorAlphaModel` 生成 `model_score`。
- 多因子模型可以对齐日期和股票池。
- 缺失因子的处理策略可配置。
- 模型评估能输出因子相关矩阵、因子覆盖率、模型 IC、模型 Rank IC、分层收益和稳定性中的核心指标。
- `AlphaModel` 不直接生成股票权重。
- 当前旧回测配置仍能运行。

### 回滚和兼容要求

- 删除 `src/alpha_models/` 和 `src/model_lab/` 后，旧单因子回测不受影响。
- 模型配置不得替代或破坏旧策略配置。
- 模型运行结果写入 `artifacts/model_runs/`，不得写入原始数据目录。

### 停止点

完成后必须停止，提交结果说明，等待用户确认是否进入工作包五。

## 工作包五：PortfolioBuilder、RebalancePolicy、StrategyPipeline 和正式策略回测

### 目标

把策略层改造成由模型分数、调仓策略、组合构建、择时和风险约束组成的正式 pipeline，并继续统一输出 `target_positions` 给现有回测引擎。

### 输入

- `ModelScoreFrame`。
- `configs/strategies/<strategy_id>.yaml` 目标结构。
- 当前 `TopNEqualWeightStrategy`。
- 当前 `BacktestEngine`。
- 当前 `filter_target_positions_by_rebalance` 逻辑。

### 输出

- `src/portfolio/`。
- `src/timing/`。
- `src/risk/`。
- 独立 `RebalancePolicy`。
- `StrategyPipeline`。
- `TopNEqualWeightPortfolio`。
- 旧 `TopNEqualWeightStrategy` 到新 PortfolioBuilder 的兼容路径。
- 标准 `TargetPositions`。

### 文件变更范围

允许新增或修改：

```text
src/portfolio/
src/timing/
src/risk/
src/strategies/
src/contracts/
configs/strategies/
artifacts/strategy_runs/ 或其创建逻辑
docs/
tests/ 或项目现有测试目录
```

谨慎修改：

```text
src/backtest/rebalance.py
src/runner/backtest_runner.py
src/backtest/engine.py
```

不得修改：

```text
data/raw/
data/meta/
```

如需修改 `BacktestEngine`，必须严格限定在兼容 `strategy_id` 或标准 TargetPositions 字段，不改变 T+1 open 和每日 close 估值语义。

### 依赖关系

依赖工作包四完成。没有 `ModelScoreFrame` 前，不应正式切换 PortfolioBuilder 链路。

### 验收标准

- `PortfolioBuilder` 只负责从 `model_score` 到基础权重。
- `StrategyPipeline` 最终只输出 `target_positions`。
- `TimingOverlay` 和 `RiskOverlay` 可以为空实现或 pass-through，但接口边界清晰。
- 当前 `BacktestEngine` 继续只消费 `target_positions`。
- 旧 `TopNEqualWeightStrategy` 兼容入口仍存在。
- T 日信号、T+1 open 执行、每日 close 估值不变。

### 回滚和兼容要求

- 新 pipeline 可关闭或绕过，旧 runner 仍可直接使用旧策略生成 `target_positions`。
- 旧 `strategy_name` 字段仍被兼容。
- 回滚时删除新增 portfolio/timing/risk/pipeline 模块后，旧回测链路仍可运行。

### 停止点

完成后必须停止，提交结果说明，等待用户确认是否进入工作包六。

## 工作包六：统一 CLI、运行结果管理、旧配置迁移、文档和端到端验证

### 目标

把前五个工作包形成统一用户入口、统一运行结果管理和可复现端到端工作流，同时保留旧入口。

### 输入

- 工作包一至五全部结果。
- 当前 `src.cli.data` 数据维护命令。
- 当时的 `src.runner.backtest_runner`（现为 `src.backtest.backtest_runner`）。
- 当前 README 和 docs。

### 输出

- `src/cli/research.py` 统一研究入口。
- 因子命令：

```bash
python -m src.cli.research factor create ...
python -m src.cli.research factor check --config ...
python -m src.cli.research factor evaluate --config ...
python -m src.cli.research factor list
python -m src.cli.research factor show --factor-id ...
python -m src.cli.research factor set-status --factor-id ... --status approved
```

- 模型命令：

```bash
python -m src.cli.research model evaluate --config ...
```

- 策略命令：

```bash
python -m src.cli.research strategy backtest --config ...
```

- `artifacts/factor_runs/`、`artifacts/model_runs/`、`artifacts/strategy_runs/` 的标准输出管理。
- 旧配置迁移说明或迁移工具。
- README 和 docs 更新。
- 端到端验证脚本或测试。

### 文件变更范围

允许新增或修改：

```text
src/cli/research.py
src/runner/
src/factor_lab/
src/model_lab/
src/strategies/
artifacts/ 或其 .gitkeep / 输出管理逻辑
configs/
docs/
README.md
tests/ 或项目现有测试目录
```

谨慎修改：

```text
src/cli/data.py
src/backtest/
```

不得修改：

```text
data/raw/
data/meta/
真实账户配置
token 文件
```

### 依赖关系

依赖工作包一至五全部完成。

### 验收标准

- 新 CLI 能覆盖因子创建、检查、评估、列表、详情、状态变更、模型评估和策略回测。
- 旧命令仍可运行：

```bash
python -m src.backtest.backtest_runner --config configs/strategies/momentum_top50_monthly.yaml
python -m src.cli.data daily_update --end ... --token ...
```

- 运行结果可复现，包含配置快照、输入摘要、输出指标和日志。
- 文档解释旧配置如何迁移到新配置。
- 端到端验证不依赖真实 Tushare。
- 未经用户确认，因子不会自动 `approved`。

### 回滚和兼容要求

- `src.cli.research`、`src.cli.data` 与 `src.backtest.backtest_runner` 保持可用。
- 旧配置迁移应是显式操作，不应在读取时隐式改写用户文件。
- 运行结果写入 `artifacts/`，不得污染源数据。

### 停止点

完成后必须停止，提交结果说明，等待用户确认是否进入后续独立优化任务。

## 工作包依赖总览

```text
工作包一
  -> 工作包二
    -> 工作包三
      -> 工作包四
        -> 工作包五
          -> 工作包六
```

每个工作包只允许依赖前置工作包已经验收的结果。不得在工作包二提前实现 `FactorEvaluator`，不得在工作包三提前实现 `AlphaModel`，不得在工作包四提前实现 `PortfolioBuilder`，不得在工作包五提前接入 QMT。

## 工作包六完成状态

工作包一至五已经通过测试并形成以下能力：

- 标准数据契约、FactorRegistry、MomentumFactor 兼容迁移；
- 因子配置、脚手架、FactorChecker；
- FactorEvaluator、FactorStore、FactorCatalog；
- AlphaModel、FactorAligner、ModelEvaluator；
- PortfolioBuilder、RebalancePolicy、Timing/Risk 接口、StrategyPipeline 和统一策略回测；
- `python -m src.cli.research` 统一研究 CLI；
- factor/model/strategy 三类运行产物和 `run_manifest.json`；
- legacy `momentum_top50_monthly.yaml` 和旧 runner 兼容。

工作包六完成后应停止，不得在同一阶段继续新增因子、Alpha 模型、择时算法、组合优化或 QMT 功能。

## 全局验收清单

每个工作包完成时都应确认：

- 当前旧回测命令仍可运行，或明确说明未运行的原因。
- 未修改 `data/raw`。
- 未修改 `data/meta`。
- 未手工修改 parquet。
- 未提交 Tushare token。
- 未提交真实账户信息。
- 未在测试中调用真实 Tushare。
- 未自动批准因子。
- 未实施当前工作包之外的后续内容。
- 已更新必要文档。

## 本次文档任务的完成边界

本次只新增：

```text
docs/multifactor_target_architecture.md
docs/multifactor_implementation_plan.md
```

本次不新增功能代码，不重构 Factor，不修改 BacktestEngine，不新增 AlphaModel，不修改配置，不修改测试逻辑，也不实施任何工作包。
