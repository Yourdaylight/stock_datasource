# 扩展指数数据源插件设计文档

## Context

### 背景
本项目旨在扩展现有的指数数据源插件体系，新增 15 个 TuShare Pro 数据接口的插件实现，覆盖：
- 多周期指数行情（周线、月线）
- 国际指数数据
- 行业分类与成分股数据
- 市场统计数据
- 指数估值数据

### 约束
- 所有插件必须遵循现有的 BasePlugin 架构
- 需要 TuShare Pro API Token
- 部分接口需要较高积分额度（2000+）
- 数据存储使用 ClickHouse

### 利益相关方
- 量化研究人员（需要多维度指数数据）
- 系统管理员（需要维护数据采集）
- API 使用者（通过 MCP/HTTP 接口查询数据）

## Goals / Non-Goals

### Goals
- 实现 15 个 TuShare Pro 数据接口的完整插件
- 统一的数据采集、转换、存储流程
- 提供查询 SDK 供上层应用使用
- 支持 MCP/HTTP 接口访问

### Non-Goals
- 不涉及数据的深度分析或可视化
- 不涉及实时数据推送
- 不涉及跨数据源的数据融合

## Decisions

### 1. 插件目录结构
每个插件采用统一的目录结构：
```
tushare_<api_name>/
├── __init__.py          # 插件注册
├── plugin.py            # 插件主类
├── extractor.py         # API调用器
├── config.json          # 插件配置
├── schema.json          # 表结构定义
└── service.py           # 查询SDK
```

**理由**：与现有插件保持一致，便于维护和扩展。

### 2. 表命名规范
- 行情类数据：`ods_<api_name>` (Operational Data Store)
- 维度类数据：`dim_<api_name>` (Dimension)

**理由**：符合数据仓库分层规范，便于识别数据类型。

### 3. 插件分类
将插件按 PluginCategory 分类：
- `INDEX`：指数行情类（index_weekly、index_monthly、index_global等）
- `MARKET`：市场统计类（sz_daily_info、daily_info）
- `REFERENCE`：参考数据类（index_classify、index_member等）
- `FUNDAMENTAL`：基本面数据类（stk_rewards）

**理由**：便于数据管理和查询过滤。

### 4. 数据采集策略

#### 增量采集（按日期）
适用接口：index_weekly、index_monthly、index_global、index_dailybasic、sw_daily、ci_daily、sz_daily_info、daily_info、index_e

#### 全量采集
适用接口：index_classify（行业分类变动较少）

#### 按需查询
适用接口：index_member、ths_member、stk_rewards（按指定参数查询）

**理由**：根据数据特性选择最优采集策略，平衡效率和完整性。

### 5. 依赖关系处理
```
index_classify ─┬─> sw_daily
                └─> ci_daily

index_basic ─┬─> index_weekly
             ├─> index_monthly  
             └─> index_member

ths_index ───> ths_member
```

**理由**：明确依赖关系，确保数据采集顺序正确。

## Architecture

### 数据流架构
```
┌─────────────┐      ┌─────────────┐      ┌─────────────┐
│ TuShare API │ ──── │  Extractor  │ ──── │   Plugin    │
└─────────────┘      └─────────────┘      └─────────────┘
                                                 │
                                                 ▼
                          ┌─────────────────────────────────┐
                          │          ClickHouse             │
                          │  ┌─────────┐  ┌─────────────┐   │
                          │  │ods_xxx  │  │  dim_xxx    │   │
                          │  └─────────┘  └─────────────┘   │
                          └─────────────────────────────────┘
                                                 │
                                                 ▼
                          ┌─────────────────────────────────┐
                          │         Service Layer           │
                          │  ┌─────────┐  ┌─────────────┐   │
                          │  │  SDK    │  │  MCP/HTTP   │   │
                          │  └─────────┘  └─────────────┘   │
                          └─────────────────────────────────┘
```

### 插件继承关系
```
BasePlugin
    │
    ├── TuShareIndexWeeklyPlugin
    ├── TuShareIndexMonthlyPlugin
    ├── TuShareIndexGlobalPlugin
    ├── TuShareIndexDailybasicPlugin
    ├── TuShareIndexClassifyPlugin
    ├── TuShareIndexMemberPlugin
    ├── TuShareSwDailyPlugin
    ├── TuShareCiDailyPlugin
    ├── TuShareThsMemberPlugin
    ├── TuShareSzDailyInfoPlugin
    ├── TuShareDailyInfoPlugin
    ├── TuShareIndexEPlugin
    └── TuShareStkRewardsPlugin
```

## Schema Design

### 指数周线行情表 (ods_index_weekly)
| 字段 | 类型 | 说明 |
|------|------|------|
| ts_code | String | 指数代码 |
| trade_date | Date | 交易日期 |
| close | Float64 | 收盘点位 |
| open | Float64 | 开盘点位 |
| high | Float64 | 最高点位 |
| low | Float64 | 最低点位 |
| vol | Float64 | 成交量 |
| amount | Float64 | 成交额 |
| pct_chg | Float64 | 涨跌幅 |

### 申万行业分类表 (dim_index_classify)
| 字段 | 类型 | 说明 |
|------|------|------|
| index_code | String | 指数代码 |
| industry_name | String | 行业名称 |
| level | String | 行业层级(L1/L2/L3) |
| industry_code | String | 行业代码 |
| is_pub | String | 是否发布指数 |
| parent_code | String | 父级代码 |

### 指数成分股表 (ods_index_member)
| 字段 | 类型 | 说明 |
|------|------|------|
| index_code | String | 指数代码 |
| con_code | String | 成分股代码 |
| in_date | Date | 纳入日期 |
| out_date | Date | 剔除日期 |
| is_new | String | 是否最新 |

### 中证指数估值表 (ods_index_e)
| 字段 | 类型 | 说明 |
|------|------|------|
| ts_code | String | 指数代码 |
| trade_date | Date | 交易日期 |
| pe | Float64 | 市盈率 |
| pb | Float64 | 市净率 |
| pe_ttm | Float64 | 市盈率TTM |
| turnover_rate | Float64 | 换手率 |
| dividend_yield | Float64 | 股息率 |
| total_mv | Float64 | 总市值 |
| float_mv | Float64 | 流通市值 |

## Risks / Trade-offs

### 风险
1. **API 限流风险**
   - 风险：TuShare Pro 有接口调用频率限制
   - 缓解：实现请求队列和限流机制

2. **积分不足风险**
   - 风险：部分高级接口需要 2000+ 积分
   - 缓解：按优先级分批实现，先实现低积分要求的接口

3. **数据一致性风险**
   - 风险：行业分类可能调整，导致历史数据不一致
   - 缓解：保留历史版本，增加版本字段

### 权衡
1. **全量 vs 增量采集**
   - 选择：增量采集为主，定期全量校验
   - 原因：平衡数据完整性和 API 调用效率

2. **实时 vs 延迟数据**
   - 选择：延迟数据（T+1）
   - 原因：TuShare Pro 主要提供延迟数据，实时数据需要其他数据源

## Migration Plan

### 阶段1：基础设施准备
1. 创建所有数据库表结构
2. 更新插件注册机制

### 阶段2：核心插件实现
1. 实现行业分类插件（基础依赖）
2. 实现指数行情插件（周线、月线）
3. 实现市场统计插件

### 阶段3：扩展插件实现
1. 实现国际指数插件
2. 实现行业行情插件
3. 实现估值数据插件

### 阶段4：验证与发布
1. 集成测试
2. 数据验证
3. 文档更新

### 回滚方案
- 所有新增插件独立部署，不影响现有功能
- 如遇问题，可单独禁用问题插件

## Open Questions

1. **index_member 接口是否与现有 index_weight 功能重复？**
   - 需要确认：index_member 侧重成分股列表，index_weight 侧重权重数据
   - 决策：两个插件都保留，提供不同维度的数据

2. **stk_rewards（管理层薪酬持股）是否属于指数数据范畴？**
   - 讨论：该接口更偏向公司基本面数据
   - 决策：暂时纳入本提案，后续可考虑重新分类

3. **是否需要为国际指数单独设计采集策略？**
   - 考虑：国际指数交易时间与 A 股不同
   - 决策：采用统一的日频采集，在 service 层处理时区问题
