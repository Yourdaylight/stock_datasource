# 策略竞争机制规范

## ADDED Requirements

### Requirement: Progressive Competition Pipeline
系统 SHALL 实现回测→模拟盘→实盘的递进式竞争流程，策略需通过前一阶段验证才能进入下一阶段。

#### Scenario: Strategy enters backtest stage
- **WHEN** Agent生成新策略
- **THEN** 策略自动进入回测阶段
- **AND** 系统执行历史数据回测
- **AND** 计算绩效指标

#### Scenario: Strategy qualifies for simulated trading
- **WHEN** 策略在回测阶段达到准入标准
- **THEN** 系统将策略提升至模拟盘阶段
- **AND** 开始模拟交易执行
- **AND** 每日更新模拟持仓和收益

#### Scenario: Live trading extension point
- **WHEN** 策略在模拟盘阶段表现优秀
- **THEN** 系统标记策略为"可升级实盘"状态
- **AND** 预留实盘交易接口（暂不实现）

### Requirement: Comprehensive Scoring System
系统 SHALL 使用多维度综合评分系统评估策略表现，权重可配置。

#### Scenario: Calculate profitability score (30% weight)
- **WHEN** 系统评估策略收益性
- **THEN** 计算年化收益率和累计收益率
- **AND** 按配置权重计入总分

#### Scenario: Calculate risk control score (30% weight)
- **WHEN** 系统评估策略风险控制
- **THEN** 计算最大回撤、夏普比率、Sortino比率
- **AND** 按配置权重计入总分

#### Scenario: Calculate stability score (20% weight)
- **WHEN** 系统评估策略稳定性
- **THEN** 计算收益波动率、胜率、盈亏比
- **AND** 按配置权重计入总分

#### Scenario: Calculate adaptability score (20% weight)
- **WHEN** 系统评估策略适应性
- **THEN** 分析策略在不同市场环境下的表现
- **AND** 按配置权重计入总分

### Requirement: Periodic Elimination Mechanism
系统 SHALL 按日/周/月周期评估并淘汰表现差的策略。

#### Scenario: Daily evaluation (no elimination)
- **WHEN** 达到每日评估时间点
- **THEN** 系统更新所有策略的实时评分
- **AND** 刷新排行榜
- **AND** 不触发淘汰

#### Scenario: Weekly elimination (bottom 20%)
- **WHEN** 达到每周评估时间点
- **THEN** 系统综合评估周表现
- **AND** 淘汰排名末位20%的策略
- **AND** 记录淘汰原因和历史

#### Scenario: Monthly elimination (bottom 10%)
- **WHEN** 达到每月评估时间点
- **THEN** 系统全面评估月度表现
- **AND** 淘汰排名末位10%的策略
- **AND** 生成月度竞争报告

#### Scenario: Strategy replenishment after elimination
- **WHEN** 策略被淘汰后
- **THEN** 系统触发策略补充机制
- **AND** 70%概率生成全新Agent策略
- **AND** 30%概率复活历史优秀Agent策略
- **AND** 保持策略池维持在配置的Agent数量
- **AND** 新/复活策略从回测阶段重新开始

#### Scenario: Revive historical excellent strategy
- **WHEN** 系统决定复活历史策略
- **THEN** 从淘汰历史中选择综合评分最高的策略
- **AND** 策略评分需高于当前存活策略平均分
- **AND** 无符合条件策略时改为生成新策略

### Requirement: Leaderboard Management
系统 SHALL 维护实时更新的策略排行榜。

#### Scenario: View real-time leaderboard
- **WHEN** 用户请求排行榜
- **THEN** 系统返回按综合评分排序的策略列表
- **AND** 包含各维度分项评分
- **AND** 标识策略当前阶段

#### Scenario: View historical rankings
- **WHEN** 用户查询历史排名
- **THEN** 系统返回指定时间段的排名变化
- **AND** 包含淘汰记录

### Requirement: Anti-overfitting Validation
系统 SHALL 实施防过拟合验证机制。

#### Scenario: Rolling window backtest
- **WHEN** 系统验证策略有效性
- **THEN** 使用滚动窗口方式进行多次回测
- **AND** 综合多窗口结果评估

#### Scenario: Out-of-sample validation
- **WHEN** 策略准备进入模拟盘
- **THEN** 在未参与训练的样本外数据上验证
- **AND** 样本外表现需达到阈值

### Requirement: Simulated Trading Engine
系统 SHALL 提供模拟交易引擎，支持策略的实时验证。

#### Scenario: Initialize simulated account
- **WHEN** 策略进入模拟盘阶段
- **THEN** 系统为策略分配虚拟资金账户（默认10万元）
- **AND** 初始化持仓为空
- **AND** 仓位无上限限制

#### Scenario: Execute simulated trades
- **WHEN** 策略产生交易信号
- **THEN** 系统模拟执行订单
- **AND** 考虑滑点和手续费
- **AND** 更新虚拟持仓和资金

#### Scenario: Daily settlement
- **WHEN** 每个交易日结束
- **THEN** 系统计算模拟盘日收益
- **AND** 更新策略评分
- **AND** 记录持仓快照

### Requirement: Live Trading Extension (Reserved)
系统 SHALL 预留实盘交易接口设计，暂不实现具体功能。

#### Scenario: Trading executor interface
- **WHEN** 需要扩展实盘功能
- **THEN** 系统提供标准化的TradingExecutor接口
- **AND** 支持下单、查询持仓、撤单等操作

#### Scenario: Risk control hooks
- **WHEN** 策略准备进入实盘
- **THEN** 系统预留风控检查钩子
- **AND** 支持仓位限制、止损止盈等配置
