# A 股多因子研究平台目标架构

本文档用于描述 `quant_factor_selection` 的当前状态、目标架构、模块边界和迁移原则。它是整体架构说明，不是一次性施工单。本次文档变更不实现新功能、不重构生产代码、不修改配置和测试。

## 1. 当前架构概述

当前项目已经形成一条可运行的单因子、配置驱动回测链路：

```text
DataManager
-> UniverseBuilder
-> FACTOR_REGISTRY
-> BaseFactor / MomentumFactor
-> FactorProcessor
-> STRATEGY_REGISTRY
-> TopNEqualWeightStrategy
-> target_positions
-> BacktestEngine
-> PerformanceAnalyzer
```

主要目录和职责如下：

```text
src/
├── datahub/       # 本地 Parquet / SQLite 数据层、Tushare 下载任务、DataManager
├── universe/      # 股票池构建和过滤
├── factors/       # BaseFactor、MomentumFactor、FactorProcessor、FACTOR_REGISTRY
├── strategies/    # BaseStrategy、TopNEqualWeightStrategy、STRATEGY_REGISTRY
├── backtest/      # BacktestEngine、Broker、Account、交易规则、绩效分析
├── runner/        # 配置加载和 backtest_runner
├── qmt/           # 预留目录，当前未实现正式执行层
└── cli/data.py    # 数据维护命令入口
```

配置和数据入口如下：

```text
configs/
├── datahub.yaml
└── strategies/
    └── momentum_top50_monthly.yaml

data/
├── raw/           # 原始行情和基础数据，不应手工修改
├── factor/        # 因子数据预留目录
└── meta/          # 元数据库，不应手工修改
```

当前推荐运行方式是：

```bash
python -m src.backtest.backtest_runner --config configs/strategies/momentum_top50_monthly.yaml
```

当前链路的关键行为：

- `DataManager` 从本地 `data/raw` 读取行情、复权因子、日行情指标和股票基础信息。
- `UniverseBuilder` 在日期区间内过滤可交易股票池，保留 `trade_date + ts_code`。
- `MomentumFactor` 基于复权收盘价生成单因子原始值。
- `FactorProcessor` 支持缺失处理、去极值、Z-score、方向统一、排名和百分位。
- `TopNEqualWeightStrategy` 基于 `factor_percentile` 选择 Top N 股票并等权生成 `target_positions`。
- `BacktestEngine` 消费 `target_positions`，将 T 日信号映射到 T+1 open 执行，并按每日 close 估值。
- `PerformanceAnalyzer` 输出净值、收益、波动、夏普、回撤、换手和成交笔数等指标。

## 2. 当前系统存在的问题

当前系统能够完成单因子动量策略回测，但距离可扩展的多因子研究平台仍有明显差距。

### 2.1 概念层次尚未完全拆开

- `TopNEqualWeightStrategy` 同时承担选股和权重分配职责，实际更接近未来的 `PortfolioBuilder`。
- 当前 `Strategy` 直接从处理后的单因子数据生成权重，尚未区分 `AlphaModel`、`RebalancePolicy`、`PortfolioBuilder`、`TimingOverlay` 和 `RiskOverlay`。
- 单因子策略和未来多因子策略还没有统一到“先生成 `model_score`，再生成 `target_positions`”的主链路。

### 2.2 因子研究生命周期缺失

- 尚无标准因子创建模板。
- 尚无 `FactorChecker` 检查 RawFactorFrame 的唯一性、缺失率、inf 和覆盖率。
- 尚无 `FactorEvaluator` 计算 IC、Rank IC、ICIR、分层收益、Top-Bottom 收益、衰减、换手和年度稳定性。
- 尚无 `FactorCatalog` 管理因子实现、配置、版本、状态、最近评估结果和研究报告。
- 因子状态 `draft / tested / approved / deprecated` 尚未落地，人工批准流程尚未实现。

### 2.3 多因子模型层缺失

- 尚无 `AlphaModel` 把多个 `factor_score` 合成为 `model_score`。
- 尚无 `ModelEvaluator` 分析因子相关性、实际贡献、模型 IC、模型 Rank IC、模型分层收益和稳定性。
- 尚无 `FactorAligner` 对齐多个因子的交易日、股票池、缺失值策略和方向口径。

### 2.4 数据契约尚未显式化

- 当前因子输出主要使用 `factor_name`，目标架构需要稳定的 `factor_id`。
- 当前 `target_positions` 使用 `strategy_name`，目标架构建议使用 `strategy_id`，并可附带 `model_score`、`raw_target_weight`、`exposure`。
- RawFactorFrame、ProcessedFactorFrame、ModelScoreFrame、TimingFrame 和 TargetPositions 的字段、唯一性和含义尚未集中定义。
- `trade_date` 作为信号日期、T+1 open 执行的语义虽已在回测实现中存在，但尚未作为跨模块数据契约统一沉淀。

### 2.5 配置体系仍是单策略配置

- 当前 `configs/strategies/<strategy>.yaml` 同时包含 data、backtest、universe、factor、portfolio 和 output。
- 尚无独立的 `configs/factors/<factor_id>.yaml`。
- 尚无独立的 `configs/models/<model_id>.yaml`。
- 尚无策略配置引用模型配置、调仓、组合构建、择时、风险和回测参数的分层关系。

### 2.6 运行结果和报告体系缺失

- 当前 `output.save_result` 尚未实现落盘。
- 尚无 `artifacts/factor_runs`、`artifacts/model_runs`、`artifacts/strategy_runs`。
- 尚无可复现的因子研究报告、多因子模型报告和策略回测报告。

## 3. 最终目标架构

最终项目应形成一套完整、流畅、可扩展的 A 股多因子研究和策略回测平台。

目标主链路如下：

```text
DataManager
-> UniverseBuilder
-> Factor Engine
-> Factor Processor
-> Factor Evaluator
-> Factor Catalog
-> Alpha Model
-> Model Evaluator
-> Rebalance Policy
-> Portfolio Builder
-> Timing Overlay
-> Risk Overlay
-> target_positions
-> BacktestEngine
-> PerformanceAnalyzer
```

标准用户流程如下：

```text
学习或发现新因子
-> 创建新因子模板
-> 实现因子计算逻辑
-> 检查因子数据质量
-> 评估因子预测能力
-> 建立单因子研究报告
-> 人工审核并纳入因子库
-> 选择多个已审核因子
-> 构建多因子 Alpha Model
-> 评估多因子模型
-> 通过 PortfolioBuilder 生成基础权重
-> 叠加调仓、择时和风险约束
-> 生成 target_positions
-> 使用 BacktestEngine 回测
-> 输出绩效、净值、交易记录和可复现报告
```

目标目录结构如下：

```text
src/
├── datahub/
├── universe/
├── contracts/
├── factors/
├── factor_lab/
├── alpha_models/
├── model_lab/
├── portfolio/
├── timing/
├── risk/
├── strategies/
├── backtest/
├── execution/
├── runner/
└── cli/research.py
```

目标配置结构如下：

```text
configs/
├── datahub.yaml
├── factors/
├── models/
└── strategies/
```

目标运行结果结构如下：

```text
artifacts/
├── factor_runs/
├── model_runs/
└── strategy_runs/
```

## 4. 各模块职责

### 4.1 DataManager

`DataManager` 负责统一读取本地数据，屏蔽底层 Parquet 和元数据库细节。

保留原则：

- 保留当前 `DataManager` 公开接口。
- 不让上层模块直接读取或手工修改 `data/raw` 和 `data/meta`。
- 后续扩展字段或数据源时保持向后兼容。

### 4.2 UniverseBuilder

`UniverseBuilder` 负责构建指定日期范围内的可选股票池。

职责包括：

- 过滤停牌或缺行情股票。
- 排除北交所、ST、新股、低价、低成交额等不满足交易要求的股票。
- 输出可被因子计算、模型和组合构建复用的 `trade_date + ts_code` 股票池。

不负责：

- 因子计算。
- 模型合成。
- 组合权重生成。
- 回测成交。

### 4.3 Factor Engine

`Factor Engine` 负责调度具体因子实现，生成原始因子值。

`Factor` 只描述某个交易日、某只股票、某个特征的数值。

Factor 不负责：

- 选 Top N。
- 分配股票权重。
- 控制整体仓位。
- 决定调仓频率。
- 生成交易订单。

当前 `BaseFactor`、`MomentumFactor` 和 `FACTOR_REGISTRY` 应作为兼容入口保留，并逐步迁移到显式 `factor_id` 和配置驱动的实现方式。

### 4.4 FactorProcessor

`FactorProcessor` 负责把 RawFactorFrame 转换为 ProcessedFactorFrame。

职责包括：

- 缺失值处理。
- 去极值。
- 方向统一。
- 标准化。
- 截面排名。
- 百分位。
- 为未来行业和市值中性化预留接口。

处理后统一定义：

```text
factor_score 越高，股票越有吸引力。
```

### 4.5 FactorEvaluator

`FactorEvaluator` 负责单因子研究和评估。

职责包括：

- 数据覆盖率。
- IC。
- Rank IC。
- ICIR。
- 分层收益。
- Top-Bottom 收益。
- 因子衰减。
- 因子换手。
- 年度稳定性。

`FactorEvaluator` 不直接决定股票权重，也不自动批准因子。

### 4.6 FactorCatalog

`FactorCatalog` 管理因子库。

因子库由以下内容共同组成：

- 因子实现。
- 因子配置。
- 因子版本。
- 因子状态。
- 最近评估结果。
- 因子研究报告。

因子状态包括：

```text
draft
tested
approved
deprecated
```

因子评估完成后不得自动变为 `approved`，必须由用户显式确认。

### 4.7 AlphaModel

`AlphaModel` 负责将一个或多个 processed `factor_score` 合成为 `model_score`。

单因子策略也应通过 `SingleFactorAlphaModel` 运行，从而与多因子策略共享后续链路。

可支持的模型类型包括：

- `SingleFactorAlphaModel`
- `EqualWeightAlphaModel`
- `WeightedScoreAlphaModel`
- `CategoryWeightedAlphaModel`
- 未来的 IC 加权、回归和机器学习模型

`AlphaModel` 不负责生成股票权重。

### 4.8 ModelEvaluator

`ModelEvaluator` 负责多因子模型研究。

职责包括：

- 因子覆盖率。
- 因子相关矩阵。
- 因子实际贡献。
- 模型 IC。
- 模型 Rank IC。
- 模型分层收益。
- 模型稳定性。

### 4.9 RebalancePolicy

`RebalancePolicy` 负责定义哪些信号日需要进入组合构建和回测。

职责包括：

- 日频、周频、月频等调仓日选择。
- 未来支持自定义调仓日历。

`BacktestEngine` 可继续保留当前 `rebalance_frequency` 兼容入口，后续再逐步迁移到独立策略组件。

### 4.10 PortfolioBuilder

`PortfolioBuilder` 负责将 `model_score` 转换为基础目标权重。

可支持的组合构建器包括：

- `TopNEqualWeightPortfolio`
- `TopNScoreWeightPortfolio`
- 未来的优化组合

当前 `TopNEqualWeightStrategy` 实际上更接近 `PortfolioBuilder`，迁移时应保留其兼容入口。

### 4.11 TimingOverlay

`TimingOverlay` 负责基于择时信号调整整体风险暴露。

标准输出应接近 TimingFrame：

```text
trade_date
timing_id
exposure
```

该模块不负责个股打分，也不直接处理成交。

### 4.12 RiskOverlay

`RiskOverlay` 负责在基础权重上叠加风险约束。

未来可支持：

- 个股权重上限。
- 行业或板块暴露限制。
- 集中度限制。
- 流动性和成交额约束。
- 风险模型约束。

该模块输出仍应保持为 `target_positions` 或其可验证的中间权重表。

### 4.13 Strategy

完整策略由以下组件构成：

```text
AlphaModel
+ RebalancePolicy
+ PortfolioBuilder
+ TimingOverlay
+ RiskOverlay
```

Strategy 最终只输出：

```text
target_positions
```

### 4.14 BacktestEngine

`BacktestEngine` 只消费 `target_positions`。

职责包括：

- 将 T 日信号映射到 T+1 open 执行。
- 按调仓计划生成买卖。
- 处理涨跌停、缺行情、整手约束等交易限制。
- 记录成交和限制日志。
- 每日 close 估值。

不负责：

- 因子怎么算。
- 模型怎么组合。
- 为什么选择这些股票。

### 4.15 Execution

未来 QMT 或其他真实执行层也只消费 `target_positions`。

执行层不应侵入回测 Broker，也不应复用回测 Broker 承担真实交易职责。真实执行需要单独的确认、风控、账户和下单适配层。

## 5. 标准数据接口

### 5.1 RawFactorFrame

至少包含：

```text
trade_date
ts_code
factor_id
factor_value
```

约束：

- `trade_date` 为信号日期。
- `trade_date + ts_code + factor_id` 唯一。
- `factor_value` 为数值。
- 不允许 `inf`。
- `NaN` 可以存在，但必须统计。

### 5.2 ProcessedFactorFrame

至少包含：

```text
trade_date
ts_code
factor_id
raw_value
factor_score
```

可选包含：

```text
factor_rank
factor_percentile
```

约束：

```text
factor_score 越高越好。
```

### 5.3 ModelScoreFrame

至少包含：

```text
trade_date
ts_code
model_id
model_score
```

建议包含：

```text
model_rank
model_percentile
factor_count
missing_factor_count
```

### 5.4 TimingFrame

至少包含：

```text
trade_date
timing_id
exposure
```

### 5.5 TargetPositions

至少包含：

```text
trade_date
ts_code
target_weight
strategy_id
```

建议包含：

```text
model_score
raw_target_weight
exposure
```

语义约束：

- `trade_date` 表示信号日期。
- T+1 open 执行仍由 `BacktestEngine` 处理。
- 每日 close 估值仍由 `BacktestEngine` 处理。
- 当前 `strategy_name` 字段需要在迁移期兼容，不能直接破坏旧链路。

## 6. 配置关系

### 6.1 因子配置

目标路径：

```text
configs/factors/<factor_id>.yaml
```

负责定义：

- `implementation`
- `factor_id`
- 参数
- 数据处理
- 评估参数
- 状态和版本

### 6.2 模型配置

目标路径：

```text
configs/models/<model_id>.yaml
```

负责定义：

- 引用一个或多个因子配置。
- 定义因子权重。
- 定义缺失值策略。
- 定义模型类型。

### 6.3 策略配置

目标路径：

```text
configs/strategies/<strategy_id>.yaml
```

负责定义：

- 引用模型配置。
- 定义调仓频率。
- 定义 `PortfolioBuilder`。
- 定义 `Timing`。
- 定义 `Risk`。
- 定义回测参数。

### 6.4 兼容当前配置

当前 `configs/strategies/momentum_top50_monthly.yaml` 必须保留可运行。

迁移期应支持旧配置中的：

- `strategy_name`
- `data`
- `backtest`
- `universe`
- `factor`
- `portfolio`
- `output`

不得在未提供迁移工具和验收前删除旧字段。

## 7. CLI 流程

目标 CLI 入口：

```bash
python -m src.cli.research factor create ...
python -m src.cli.research factor check --config ...
python -m src.cli.research factor evaluate --config ...
python -m src.cli.research factor list
python -m src.cli.research factor show --factor-id ...
python -m src.cli.research factor set-status --factor-id ... --status approved
python -m src.cli.research model evaluate --config ...
python -m src.cli.research strategy backtest --config ...
```

兼容入口必须保留：

```bash
python -m src.cli.data bootstrap --start ... --end ... --token ...
python -m src.cli.data sync_daily_range --start ... --end ... --token ...
python -m src.cli.data daily_update --end ... --token ...
python -m src.cli.data financial_update --start ... --end ... --token ...
python -m src.backtest.backtest_runner --config configs/strategies/momentum_top50_monthly.yaml
```

CLI 迁移原则：

- 先新增统一入口，再逐步将旧 runner 包装到新入口。
- 不在数据更新命令中引入研究和回测逻辑。
- 不在研究命令中写入真实交易或账户信息。

## 8. 回测和未来执行边界

`target_positions` 是研究、回测和未来执行之间的标准边界。

回测边界：

- 输入：`target_positions`、行情、初始资金、交易成本、调仓规则。
- 输出：净值、持仓、成交记录、限制日志、绩效指标。
- 执行语义：T 日信号，T+1 open 执行，每日 close 估值。

未来执行边界：

- 输入同样以 `target_positions` 为核心。
- QMT 适配层不应理解因子计算和模型组合细节。
- 真实交易必须有独立确认、风控和账户保护流程。
- 不应把 QMT 逻辑塞入回测 Broker。

## 9. 向后兼容原则

整个改造过程中必须保留：

1. 当前 `DataManager`。
2. 当前 `UniverseBuilder`。
3. 当前数据更新命令。
4. 当前 `MomentumFactor`。
5. 当前 `FACTOR_REGISTRY` 兼容入口。
6. 当前 `TopNEqualWeightStrategy` 兼容入口。
7. 当前 `backtest_runner`。
8. 当前 `target_positions` 接口。
9. T 日信号。
10. T+1 open 执行。
11. 每日 close 估值。
12. 当前交易限制和交易日志。

禁止事项：

1. 修改 `data/raw`。
2. 修改 `data/meta`。
3. 手工修改 parquet。
4. 修改真实数据库。
5. 提交 Tushare token。
6. 提交真实账户信息。
7. 在单元测试中调用真实 Tushare。
8. 将所有逻辑堆入单个 runner。
9. 为单因子和多因子建立两套回测体系。
10. 提前接入 QMT。
11. 未经用户确认自动批准因子。
12. 一次性完成全部架构改造。

## 10. 当前范围外内容

本文档只做架构分析和分阶段规划。以下内容不在本次范围内：

- 新增功能代码。
- 重构 `Factor`。
- 修改 `BacktestEngine`。
- 新增 `AlphaModel`。
- 修改配置。
- 修改测试逻辑。
- 实施任何施工包。
- 修改原始数据、元数据、真实数据库或 parquet。
- 接入 QMT 或真实账户。
- 自动批准任何因子。

## 11. 工作包六后的落地状态

截至工作包六，项目已经具备统一研究入口：

```bash
python -m src.cli.research --help
```

已落地的主流程为：

```text
factor create/check/evaluate/list/show/set-status
-> model evaluate
-> strategy backtest
```

运行结果统一写入：

```text
artifacts/factor_runs/<factor_id>/<run_id>/
artifacts/model_runs/<model_id>/<run_id>/
artifacts/strategy_runs/<strategy_id>/<run_id>/
```

每次正式运行都保存配置快照和 `run_manifest.json`。策略回测保存 `performance.json`、`target_positions.parquet`、`equity_curve.parquet`、`trade_log.parquet` 和 `restriction_log.parquet`。

旧入口仍保留：

```bash
python -m src.backtest.backtest_runner --config configs/strategies/momentum_top50_monthly.yaml
```

`scratch_run_momentum_actual.py` 已作为历史参考移动到 `examples/legacy/`，不再作为 README 推荐入口。

仍未实现：

- QMT 或真实执行；
- 新的具体择时算法；
- 新的生产因子；
- 自动因子审批；
- 组合优化器；
- 真实账户或真实下单能力。
