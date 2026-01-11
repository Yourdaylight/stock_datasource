# 持仓管理表分区策略

## 分区设计原则

基于ClickHouse的特性，我们采用时间分区策略来优化查询性能和数据管理。

## 表分区策略

### 1. user_positions (用户持仓表)
- **分区键**: `toYYYYMM(buy_date)`
- **排序键**: `(user_id, ts_code, id)`
- **分区原理**: 按买入日期的年月分区，便于按时间范围查询历史持仓
- **优势**: 
  - 支持高效的时间范围查询
  - 便于数据归档和清理
  - 优化JOIN操作性能

### 2. portfolio_analysis (投资组合分析表)
- **分区键**: `toYYYYMM(analysis_date)`
- **排序键**: `(user_id, analysis_date, analysis_type, id)`
- **分区原理**: 按分析日期的年月分区
- **优势**:
  - 快速检索特定时期的分析报告
  - 支持按用户和时间的复合查询
  - 便于历史数据管理

### 3. technical_indicators (技术指标表)
- **分区键**: `toYYYYMM(indicator_date)`
- **排序键**: `(ts_code, indicator_date, id)`
- **分区原理**: 按指标日期的年月分区
- **优势**:
  - 优化技术指标的时间序列查询
  - 支持股票代码和时间的复合索引
  - 便于批量计算和更新

### 4. portfolio_risk_metrics (风险指标表)
- **分区键**: `toYYYYMM(metric_date)`
- **排序键**: `(user_id, metric_date, id)`
- **分区原理**: 按指标日期的年月分区
- **优势**:
  - 快速计算用户风险指标趋势
  - 支持跨时间段的风险分析
  - 优化聚合查询性能

### 5. position_alerts (持仓预警表)
- **分区键**: `toYYYYMM(created_at)`
- **排序键**: `(user_id, ts_code, alert_type, id)`
- **分区原理**: 按创建时间的年月分区
- **优势**:
  - 快速查询最近的预警信息
  - 支持按用户和股票的预警管理
  - 便于清理过期预警数据

## 性能优化策略

### 1. 物化视图优化
- `mv_daily_portfolio_summary`: 每日持仓汇总
- `mv_stock_performance`: 股票表现统计

### 2. 查询优化建议
- 查询时尽量包含分区键条件
- 使用ORDER BY键进行范围查询
- 避免跨分区的大范围扫描

### 3. 数据维护策略
- 定期执行OPTIMIZE TABLE操作
- 按需清理历史分区数据
- 监控分区大小和查询性能

## 示例查询

```sql
-- 查询用户最近3个月的持仓
SELECT * FROM user_positions 
WHERE user_id = 'user123' 
AND buy_date >= today() - INTERVAL 3 MONTH;

-- 查询股票最近30天的技术指标
SELECT * FROM technical_indicators 
WHERE ts_code = '000001.SZ' 
AND indicator_date >= today() - INTERVAL 30 DAY;

-- 查询用户最近一年的风险指标趋势
SELECT * FROM portfolio_risk_metrics 
WHERE user_id = 'user123' 
AND metric_date >= today() - INTERVAL 1 YEAR
ORDER BY metric_date;
```