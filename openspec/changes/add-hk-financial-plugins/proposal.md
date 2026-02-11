# Proposal: Add HK Financial Plugins

## Change ID
`add-hk-financial-plugins`

## Summary
为港股市场添加四个财务数据插件，支持港股财务指标、资产负债表、利润表和现金流量表数据的采集和存储。

## Motivation

### Background
当前系统已支持 A 股财务报表数据（利润表、资产负债表、现金流量表、财务指标），但缺少港股财务数据支持。用户需要港股财务数据用于：
- 港股投资分析和研究
- A 股与港股财务数据对比分析
- AH 股溢价分析的数据基础

### Target APIs
基于 TuShare Pro 提供的港股财务数据接口：

| 接口名称 | doc_id | 描述 | 数据结构 |
|---------|--------|------|---------|
| `hk_fina_indicator` | 388 | 港股财务指标 | 宽表（固定字段） |
| `hk_balancesheet` | 390 | 港股资产负债表 | 纵表（ind_name, ind_value） |
| `hk_income` | 389 | 港股利润表 | 纵表（ind_name, ind_value） |
| `hk_cashflow` | 391 | 港股现金流量表 | 纵表（ind_name, ind_value） |

### Key Observation: Data Structure Difference
**重要发现**：港股三大报表（资产负债表、利润表、现金流量表）采用**纵表结构**（每行一个指标），而非 A 股的宽表结构（每行一条完整记录）。

| 对比项 | A 股财务报表 | 港股财务报表 |
|-------|-------------|-------------|
| 表结构 | 宽表（~100-150 字段） | 纵表（5 字段） |
| 数据格式 | ts_code, end_date, field1, field2... | ts_code, end_date, ind_name, ind_value |
| 灵活性 | 固定字段 | 动态指标名称 |
| 查询方式 | 直接 SELECT 字段 | 需要 PIVOT 或条件聚合 |

### 纵表与横表优缺点

**横表（宽表）优点**：
- 查询简单，报表类 SQL 直观
- 前端消费成本低，直接字段映射
- 更易做指标对比和多列展示

**横表（宽表）缺点**：
- 字段变更需要 `ALTER TABLE`
- 指标动态变化时维护成本高
- 不同市场（A/H）科目差异会导致字段冗余或缺失

**纵表（EAV）优点**：
- 指标可扩展性强，无需频繁改表
- 保留原始科目结构，信息不丢失
- 更适合跨市场、跨行业的科目差异

**纵表（EAV）缺点**：
- 查询复杂，需要 PIVOT 或条件聚合
- 性能依赖索引/排序键设计
- 前端展示需要额外转换逻辑

### 为什么这里选择纵表
- **与源数据一致**：港股三大报表接口天然返回 `ind_name + ind_value` 纵表结构，直接存储避免映射损耗。
- **避免字段爆炸**：港股财务科目变化频繁，纵表能承接新增科目而不改表。
- **隔离风险**：不影响既有 A 股宽表体系，降低改造范围。
- **后续可扩展**：可通过物化视图或条件聚合生成“宽表视图”，兼顾灵活性与查询效率。

## Goals

### Primary Goals
1. 实现 4 个港股财务数据采集插件
2. 设计合适的数据库存储方案（处理纵表结构）
3. 提供与现有财务服务层的集成
4. 支持港股财务数据查询 API
5. **新增**: 前端完整展示港股三大报表（利润表、资产负债表、现金流量表），包含概览卡片、分类报表数据表格和趋势图表

### Non-Goals
- 不改变现有 A 股财务数据结构
- 不实现港股与 A 股数据的自动合并视图（可作为后续需求）

## Proposed Solution

### Database Design

#### 1. 港股财务指标表（宽表，与 A 股类似）
```sql
-- ods_hk_fina_indicator（宽表结构）
-- 复用 A 股 ods_fina_indicator 的设计模式
-- 包含 ~60+ 固定字段
```

#### 2. 港股财务报表表（纵表结构）
```sql
-- ods_hk_balancesheet / ods_hk_income / ods_hk_cashflow
-- 统一采用纵表结构：
-- ts_code, end_date, name, ind_name, ind_value
```

### Reusability Analysis

| 组件 | 可复用程度 | 说明 |
|------|-----------|------|
| Plugin 基类 | ✅ 完全复用 | BasePlugin, BaseService |
| Schema 管理 | ✅ 完全复用 | schema_manager.py |
| ClickHouse 引擎 | ✅ 完全复用 | ReplacingMergeTree 模式 |
| 财务指标字段 | ⚠️ 部分复用 | hk_fina_indicator 部分字段与 A 股对应 |
| 服务层 | ⚠️ 部分复用 | 需要适配纵表查询逻辑 |
| 前端组件 | ⚠️ 部分复用 | 需要适配纵表数据格式 |

### Plugin Implementation

参考现有 `tushare_income` / `tushare_finace_indicator` 插件实现模式：
- 继承 BasePlugin
- 标准目录结构（config.json, schema.json, extractor.py, plugin.py, service.py）
- 支持单股票和批量提取模式

## Impact Analysis

### New Components
- 4 个新插件
- 4 个新数据库表
- 港股财务查询服务

### Modified Components
- 无（独立新增）

### Dependencies
- TuShare Pro API（15000 积分权限）
- 现有港股基础数据（`ods_hk_stock_list` 用于批量提取）

## Alternatives Considered

### Alternative 1: 将港股纵表转为宽表存储
**优点**：与 A 股结构一致，查询简单
**缺点**：
- 字段动态变化时需要 ALTER TABLE
- 港股财务科目与 A 股不同，强制映射可能丢失数据
**结论**：不采用

### Alternative 2: 统一 A 股和港股使用纵表
**优点**：结构一致，灵活性高
**缺点**：需要大幅修改现有 A 股数据结构，影响范围过大
**结论**：不采用

### Selected Approach: 港股独立纵表
**优点**：
- 保持数据原始结构，无信息损失
- 不影响现有 A 股数据
- 灵活支持港股财务科目的动态变化
**缺点**：需要额外的查询适配逻辑

## Open Questions

1. **纵表查询性能**：ClickHouse 对纵表结构的 PIVOT 查询是否有性能问题？
   - 建议：预聚合常用指标视图

2. **指标名称映射**：港股财务科目名称（中文）是否需要标准化英文映射？
   - 建议：Phase 1 保持原始中文名称，后续根据需求添加映射

3. **API 限频**：TuShare Pro 港股接口的限频策略？
   - 需确认：单次请求最大 10000 行，需要循环提取

## Timeline

预估工作量：5-7 个工作日

| Phase | 内容 | 预估 |
|-------|------|------|
| Phase 1 | 数据库 Schema 设计 | 1 天 |
| Phase 2 | hk_fina_indicator 插件 | 1 天 |
| Phase 3 | hk_balancesheet 插件 | 1 天 |
| Phase 4 | hk_income 插件 | 1 天 |
| Phase 5 | hk_cashflow 插件 | 1 天 |
| Phase 6 | 服务层集成和测试 | 1-2 天 |

## References

- TuShare 港股财务指标文档: https://tushare.pro/document/2?doc_id=388
- TuShare 港股资产负债表文档: https://tushare.pro/document/2?doc_id=390
- TuShare 港股利润表文档: https://tushare.pro/document/2?doc_id=389
- TuShare 港股现金流量表文档: https://tushare.pro/document/2?doc_id=391
- 现有 A 股财务插件: `openspec/changes/add-financial-statement-plugins/`
