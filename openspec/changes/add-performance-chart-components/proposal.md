# Change: 添加策略回测绩效图表组件

## Why

当前系统虽然已经实现了完整的策略回测功能和29个绩效统计指标，但在可视化展示方面存在关键缺失：

1. **缺少回撤曲线图** - 用户无法直观看到策略的回撤变化过程，只能看到最大回撤数值
2. **缺少每日盈亏图** - 虽然有交易记录表格，但缺少每日盈亏的可视化分布
3. **缺少收益分布图** - 无法展示收益率的概率分布特征，影响风险评估

这些图表是专业量化分析的标准配置，对于策略评估和风险管理至关重要。

## What Changes

- **新增**: `DrawdownChart.vue` - 回撤曲线图组件，展示净值回撤的时间序列变化
- **新增**: `DailyPnLChart.vue` - 每日盈亏图组件，展示每日收益的柱状图分布  
- **新增**: `ReturnDistributionChart.vue` - 收益分布图组件，展示收益率的直方图和概率分布
- **修改**: `BacktestResults.vue` - 集成新增的三个图表组件到现有的绩效展示页面
- **修改**: 后端数据接口 - 确保提供新图表所需的数据格式

## Impact

- **受影响的规范**: `intelligent-strategy-system` (回测结果展示部分)
- **受影响的代码**: 
  - `frontend/src/components/strategy/BacktestResults.vue`
  - `frontend/src/views/backtest/BacktestView.vue`
  - `src/stock_datasource/backtest/models.py`
  - `src/stock_datasource/api/strategy_routes.py`
- **用户体验**: 显著提升策略分析的专业性和直观性
- **技术债务**: 无，纯增量功能
- **性能影响**: 轻微增加前端渲染负载，但在可接受范围内