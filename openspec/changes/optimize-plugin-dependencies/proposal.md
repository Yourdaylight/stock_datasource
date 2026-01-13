# Proposal: optimize-plugin-dependencies

## Summary
优化数据插件系统，实现全局交易日历配置、插件依赖关系管理、插件分类筛选和批量任务触发，确保数据获取的正确顺序和完整性。

## Problem Statement

### 当前问题

1. **交易日历管理分散**
   - 交易日历数据存储在数据库表 `ods_trade_calendar` 中
   - 同时在 `modules/datamanage/trade_calendar.csv` 有一份缓存
   - 需要手动触发同步，但实际上交易日历是相对稳定的数据
   - 各模块获取交易日期的方式不统一

2. **插件依赖关系不完整**
   - `tushare_daily` 插件的 `get_dependencies()` 返回空列表，但实际上需要 `tushare_stock_basic` 提供股票代码列表
   - `tushare_etf_fund_daily` 已正确声明依赖 `tushare_etf_basic`
   - 指数日线数据插件尚未实现完整的依赖关系
   - 插件管理器未强制执行依赖检查
   - **复权因子应在每日数据更新时一并获取，但目前没有关联机制**

3. **数据获取顺序无保障**
   - 用户可能在未同步 basic 数据的情况下尝试同步 daily 数据
   - 导致数据不完整或同步失败

4. **插件管理功能不足**
   - 无法按类别（股票/指数/ETF）筛选插件
   - 不支持批量触发同步任务
   - 无法区分主数据插件和依赖数据插件

## Proposed Solution

### 1. 全局交易日历配置化

将交易日历作为全局配置文件，而非数据库数据：

- 将 `trade_calendar.csv` 移至 `src/stock_datasource/config/trade_calendar.csv`
- 提供统一的 `TradeCalendarService` 全局访问接口
- 交易日历数据不入库，仅作为配置文件使用
- 保留手动更新接口，但默认使用本地 CSV 文件

### 2. 插件依赖关系强化

完善插件依赖声明和执行检查，引入**可选依赖**概念：

| 插件 | 必需依赖 | 可选依赖 | 说明 |
|------|---------|---------|------|
| `tushare_daily` | `tushare_stock_basic` | `tushare_adj_factor` | 每日行情，可选同步复权因子 |
| `tushare_daily_basic` | `tushare_stock_basic` | - | 每日指标 |
| `tushare_etf_fund_daily` | `tushare_etf_basic` | `tushare_etf_fund_adj` | ETF每日行情，可选同步复权因子 |
| `tushare_index_daily` | `tushare_index_basic` | - | 指数每日行情 |
| `tushare_index_weight` | `tushare_index_basic` | - | 指数成分股权重 |
| `tushare_adj_factor` | `tushare_stock_basic` | - | 股票复权因子 |

**可选依赖**：在同步主数据时，默认关联同步可选依赖数据（如复权因子），用户可选择关闭。

### 3. 依赖检查机制

在 `PluginManager` 中添加依赖验证：

- 执行插件前检查依赖是否满足
- 提供依赖数据是否存在的快速检查方法
- 支持级联执行（自动执行依赖插件）选项
- **支持可选依赖的关联执行**

### 4. 插件分类与标识

为插件添加分类和角色标识：

**分类 (category)**:
- `stock` - 股票相关
- `index` - 指数相关  
- `etf_fund` - ETF/基金相关（合并为一类）
- `system` - 系统数据（如交易日历）

**角色 (role)**:
- `primary` - 主数据（如 daily 行情）
- `basic` - 基础数据（如 stock_basic）
- `derived` - 衍生数据（如复权因子）
- `auxiliary` - 辅助数据（如指数权重）

### 5. 批量任务触发

支持按分类批量触发同步任务：

- 按类别筛选插件列表
- 批量选择多个插件触发同步
- 自动处理依赖顺序

## Scope

### In Scope
- 交易日历配置化重构
- 插件依赖关系声明完善（含可选依赖）
- 插件管理器依赖检查增强
- 插件分类和角色标识
- 批量任务触发 API
- 前端插件筛选和批量操作
- 相关单元测试

### Out of Scope
- 新数据插件开发
- 数据库表结构变更

## Impact Analysis

### 受影响组件
- `src/stock_datasource/config/` - 新增配置目录
- `src/stock_datasource/core/trade_calendar.py` - 新增全局服务
- `src/stock_datasource/core/plugin_manager.py` - 增强依赖检查
- `src/stock_datasource/core/base_plugin.py` - 添加分类/角色属性
- `src/stock_datasource/plugins/*/plugin.py` - 添加依赖和分类
- `src/stock_datasource/modules/datamanage/router.py` - 新增批量API
- `frontend/src/` - 前端筛选和批量操作

### 兼容性
- 向后兼容：现有 API 接口不变
- 数据兼容：不影响已有数据

## Success Criteria

1. 交易日历可通过全局服务统一访问
2. 所有 daily 类插件正确声明 basic 依赖
3. 插件执行前自动检查依赖是否满足
4. 依赖未满足时给出清晰的错误提示
5. **支持按类别筛选插件（股票/指数/ETF基金）**
6. **支持批量触发同步任务**
7. **可选依赖（如复权因子）可关联同步**
8. **插件列表显示主数据/依赖数据标识**

## Timeline Estimate

- 设计评审：0.5 天
- 实现：3 天
- 测试：0.5 天
- 总计：4 天
