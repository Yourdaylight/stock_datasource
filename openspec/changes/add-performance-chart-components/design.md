## Context

当前系统已具备完整的策略回测功能和29个绩效指标计算，但在可视化方面缺少三个关键图表：回撤曲线图、每日盈亏图和收益分布图。这些图表是专业量化分析的标准配置，需要在现有架构基础上进行增量开发。

**技术约束**:
- 必须与现有ECharts技术栈保持一致
- 需要复用现有的回测数据模型和API
- 前端组件需要支持TDesign设计规范
- 图表性能需要支持大数据量（1000+交易日）

## Goals / Non-Goals

**Goals**:
- 提供专业级的策略绩效可视化能力
- 增强用户对策略风险特征的理解
- 保持与现有UI风格的一致性
- 确保图表的交互性和响应式设计

**Non-Goals**:
- 不改变现有的回测计算逻辑
- 不重构现有的数据模型结构
- 不添加新的第三方图表库依赖

## Decisions

### Decision 1: 图表技术选型

**选择**: 继续使用ECharts 5.x
**原因**:
- 与现有技术栈一致（ReturnCurveChart.vue已使用）
- 丰富的图表类型和配置选项
- 良好的性能表现和社区支持
- 支持响应式和主题定制

**替代方案考虑**:
- Chart.js: 轻量但功能相对有限
- D3.js: 灵活性高但开发复杂度大

### Decision 2: 数据流设计

**选择**: 扩展现有BacktestResult模型，添加图表专用数据字段
**原因**:
- 最小化对现有代码的影响
- 保持数据的一致性和完整性
- 便于后续维护和扩展

**数据结构设计**:
```typescript
interface BacktestResult {
  // 现有字段...
  performance_metrics: PerformanceMetrics
  
  // 新增图表数据字段
  chart_data: {
    drawdown_series: Array<{date: string, drawdown: number}>
    daily_returns: Array<{date: string, return: number, cumulative: number}>
    return_distribution: {
      bins: number[]
      frequencies: number[]
      statistics: {
        mean: number
        std: number
        skewness: number
        kurtosis: number
      }
    }
  }
}
```

### Decision 3: 组件架构设计

**选择**: 独立组件 + 统一容器的架构模式
**原因**:
- 组件职责单一，便于测试和维护
- 支持按需加载和复用
- 便于后续功能扩展

**组件层次结构**:
```
BacktestResults.vue (容器组件)
├── DrawdownChart.vue (回撤图)
├── DailyPnLChart.vue (盈亏图)  
└── ReturnDistributionChart.vue (分布图)
```

### Decision 4: 图表交互设计

**选择**: 统一的交互模式和配置选项
**交互功能**:
- 缩放和平移支持
- Tooltip数据展示
- 图例控制显示/隐藏
- 导出功能（PNG/PDF）
- 时间范围筛选

## Risks / Trade-offs

### Risk 1: 大数据量性能问题
**风险**: 长期回测数据可能导致图表渲染缓慢
**缓解措施**: 
- 实现数据采样和分页加载
- 使用ECharts的数据缓存机制
- 添加加载状态和进度提示

### Risk 2: 移动端适配复杂性
**风险**: 复杂图表在小屏幕上显示效果差
**缓解措施**:
- 响应式图表尺寸调整
- 移动端简化显示模式
- 触摸友好的交互设计

### Risk 3: 数据一致性问题
**风险**: 图表数据与指标数据不一致
**缓解措施**:
- 统一的数据计算源
- 添加数据验证机制
- 完善的单元测试覆盖

## Migration Plan

### Phase 1: 后端数据准备 (1-2天)
1. 扩展BacktestResult模型
2. 更新回测引擎数据生成
3. 修改API接口返回格式

### Phase 2: 核心组件开发 (3-4天)
1. 开发DrawdownChart组件
2. 开发DailyPnLChart组件
3. 开发ReturnDistributionChart组件

### Phase 3: 集成和优化 (2-3天)
1. 集成到BacktestResults页面
2. 样式和交互优化
3. 性能测试和调优

### Phase 4: 测试和发布 (1-2天)
1. 单元测试和集成测试
2. 用户验收测试
3. 文档更新和发布

**回滚计划**: 
- 新组件独立开发，不影响现有功能
- 可通过功能开关控制图表显示
- 数据模型向后兼容，支持渐进式升级

## Open Questions

1. **图表数据缓存策略**: 是否需要在前端缓存图表数据以提升性能？
2. **自定义配置需求**: 用户是否需要自定义图表的显示参数（如分箱数量、时间范围等）？
3. **导出格式支持**: 除了PNG/PDF，是否需要支持SVG或数据CSV导出？
4. **实时更新机制**: 未来是否需要支持实时策略的图表动态更新？