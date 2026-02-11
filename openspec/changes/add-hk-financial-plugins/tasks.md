# Tasks: Add HK Financial Plugins

## Overview

本文档列出实现港股财务数据插件的具体任务清单。

## Phase 1: 数据库 Schema 设计 (Day 1)

### 1.1 创建 Schema 文件
- [ ] 创建 `tushare_hk_fina_indicator/schema.json`（宽表，~60 字段）
- [ ] 创建 `tushare_hk_balancesheet/schema.json`（纵表）
- [ ] 创建 `tushare_hk_income/schema.json`（纵表）
- [ ] 创建 `tushare_hk_cashflow/schema.json`（纵表）

### 1.2 验证 Schema
- [ ] 使用 schema_manager.py 验证 Schema 格式
- [ ] 在开发环境创建测试表
- [ ] 验证分区和排序键设计

## Phase 2: hk_fina_indicator 插件 (Day 2)

### 2.1 插件骨架
- [ ] 创建 `tushare_hk_fina_indicator/` 目录结构
- [ ] 创建 `__init__.py`
- [ ] 创建 `config.json`（调度、限频配置）

### 2.2 Extractor 实现
- [ ] 创建 `extractor.py`
- [ ] 实现 TuShare `hk_fina_indicator` API 调用
- [ ] 实现分页和限频逻辑
- [ ] 添加单元测试

### 2.3 Plugin 实现
- [ ] 创建 `plugin.py`
- [ ] 继承 BasePlugin
- [ ] 实现 extract_data 方法
- [ ] 实现 transform_data 方法
- [ ] 实现 load_data 方法
- [ ] 支持单股票和批量模式

### 2.4 Service 实现
- [ ] 创建 `service.py`
- [ ] 实现基础查询方法
- [ ] 添加查询参数验证

### 2.5 验证
- [ ] 测试数据提取（00700.HK）
- [ ] 验证数据入库
- [ ] 验证查询功能

## Phase 3: hk_balancesheet 插件 (Day 3)

### 3.1 插件骨架
- [ ] 创建 `tushare_hk_balancesheet/` 目录结构
- [ ] 创建配置文件

### 3.2 Extractor 实现
- [ ] 实现 TuShare `hk_balancesheet` API 调用
- [ ] 处理纵表数据格式

### 3.3 Plugin 实现
- [ ] 继承 BasePlugin
- [ ] 实现纵表数据转换逻辑

### 3.4 Service 实现
- [ ] 实现纵表查询方法
- [ ] 实现 PIVOT 转换方法
- [ ] 支持指定科目查询

### 3.5 验证
- [ ] 测试数据提取
- [ ] 验证纵表查询
- [ ] 验证 PIVOT 转换

## Phase 4: hk_income 插件 (Day 4)

### 4.1 插件骨架
- [ ] 创建 `tushare_hk_income/` 目录结构
- [ ] 创建配置文件

### 4.2 Extractor 实现
- [ ] 实现 TuShare `hk_income` API 调用

### 4.3 Plugin 实现
- [ ] 继承 BasePlugin
- [ ] 实现纵表数据转换逻辑

### 4.4 Service 实现
- [ ] 实现纵表查询方法
- [ ] 实现 PIVOT 转换方法

### 4.5 验证
- [ ] 测试数据提取
- [ ] 验证查询功能

## Phase 5: hk_cashflow 插件 (Day 5)

### 5.1 插件骨架
- [ ] 创建 `tushare_hk_cashflow/` 目录结构
- [ ] 创建配置文件

### 5.2 Extractor 实现
- [ ] 实现 TuShare `hk_cashflow` API 调用

### 5.3 Plugin 实现
- [ ] 继承 BasePlugin
- [ ] 实现纵表数据转换逻辑

### 5.4 Service 实现
- [ ] 实现纵表查询方法
- [ ] 实现 PIVOT 转换方法

### 5.5 验证
- [ ] 测试数据提取
- [ ] 验证查询功能

## Phase 6: 服务层集成 (Day 6-7)

### 6.1 统一服务层
- [ ] 创建 `HKFinancialService` 统一服务类
- [ ] 集成四个插件的查询能力
- [ ] 提供统一的查询接口

### 6.2 API 集成
- [ ] 添加 FastAPI 路由
- [ ] 实现 REST API 端点
- [ ] 添加 API 文档

### 6.3 Agent 集成
- [ ] 注册港股财务查询工具
- [ ] 添加自然语言查询支持

### 6.4 文档和测试
- [ ] 更新 README
- [ ] 编写集成测试
- [ ] 端到端验证

## Dependencies

### 前置依赖
- TuShare Pro API Token（15000 积分权限）
- 港股基础数据表 `ods_hk_stock_list`

### 并行化
- Phase 2/3/4/5 的插件开发可部分并行
- Schema 设计完成后可并行开发 Extractor

## Acceptance Criteria

### 功能验收
- [ ] 四个插件能正常提取数据
- [ ] 数据正确存入 ClickHouse
- [ ] 查询 API 正常工作
- [ ] Agent 能回答港股财务相关问题

### 质量验收
- [ ] 单元测试覆盖率 > 80%
- [ ] 集成测试通过
- [ ] 无 P0/P1 级别 Bug

### 文档验收
- [ ] Schema 文档完整
- [ ] API 文档完整
- [ ] 使用示例文档

## Progress Tracking

| Phase | Status | Start | End | Notes |
|-------|--------|-------|-----|-------|
| Phase 1 | Done | 2026-02-11 | 2026-02-11 | Schema 文件已创建 |
| Phase 2 | Done | 2026-02-11 | 2026-02-11 | hk_fina_indicator 宽表插件完成 |
| Phase 3 | Done | 2026-02-11 | 2026-02-11 | hk_balancesheet 纵表插件完成 |
| Phase 4 | Done | 2026-02-11 | 2026-02-11 | hk_income 纵表插件完成 |
| Phase 5 | Done | 2026-02-11 | 2026-02-11 | hk_cashflow 纵表插件完成 |
| Phase 6 | Done | 2026-02-11 | 2026-02-11 | 统一服务层+API路由+Agent集成完成 |
| Phase 7 | Done | 2026-02-11 | 2026-02-11 | 前端展示三大报表（利润表/资产负债表/现金流量表）+趋势图表 |

## Risk Items

| Risk | Impact | Mitigation |
|------|--------|------------|
| API 权限不足 | 高 | 提前确认积分状态 |
| 纵表查询性能 | 中 | 添加物化视图 |
| 港股科目差异 | 低 | 保持原始中文名称 |

## Phase 7: 港股三大报表前端展示

- [x] 7.1 前端 `HKFinancialReportPanel.vue`：`handleSearch` 扩展为 5 个并发请求（新增 income + balance + cashflow）
- [x] 7.2 前端 `HKFinancialReportPanel.vue`：新增 `incomeData`/`balanceData`/`cashflowData` 响应式数据
- [x] 7.3 前端概览 Tab：新增「利润结构（最新期）」卡片（营业收入/营业成本/毛利/营业利润/净利润/归母净利润）
- [x] 7.4 前端概览 Tab：新增「资产负债（最新期）」卡片（资产总额/负债总额/股东权益/流动资产/流动负债）
- [x] 7.5 前端概览 Tab：新增「现金流量（最新期）」卡片（经营/投资/筹资活动现金流净额/期末现金余额）
- [x] 7.6 前端新增「三大报表」Tab：RadioGroup 子标签切换（利润表/资产负债表/现金流量表）
- [x] 7.7 前端三大报表 Tab：`transformPivotToRows` 将 EAV pivot 数据转换为指标行×报告期列的表格
- [x] 7.8 前端三大报表 Tab：金额亿/万格式化（`formatAmount`），负值标红
- [x] 7.9 前端趋势图表 Tab：新增「利润结构趋势」分组柱状图（营业收入/毛利/营业利润/净利润）
- [x] 7.10 前端趋势图表 Tab：新增「资产负债结构趋势」分组柱状图（资产总额/负债总额/股东权益）
- [x] 7.11 前端趋势图表 Tab：新增「现金流量趋势」分组柱状图（经营/投资/筹资活动）
- [x] 7.12 前端财务指标表格：新增资产负债率(%)、流动比率、权益乘数 3 列

## Known Issues & Fixes

### Issue-1: 插件分类缺失导致前端港股筛选不显示（2026-02-12 已修复）

**现象**：前端「插件管理」页面筛选"港股"时，只显示 `akshare_hk_daily` 和 `akshare_hk_stock_list` 两个插件，4 个 tushare 港股财务插件不可见。

**根因**：`tushare_hk_fina_indicator`、`tushare_hk_balancesheet`、`tushare_hk_income`、`tushare_hk_cashflow` 四个插件的 `plugin.py` 未覆写 `get_category()` 和 `get_role()` 方法，继承了 `BasePlugin` 默认值 `PluginCategory.CN_STOCK`（A股），导致前端按 `hk_stock` 筛选时过滤掉了这些插件。

**修复**：在 4 个插件的 `plugin.py` 中添加：
```python
from stock_datasource.core.base_plugin import PluginCategory, PluginRole

def get_category(self) -> PluginCategory:
    return PluginCategory.HK_STOCK

def get_role(self) -> PluginRole:
    return PluginRole.DERIVED
```

**影响文件**：
- `src/stock_datasource/plugins/tushare_hk_fina_indicator/plugin.py`
- `src/stock_datasource/plugins/tushare_hk_balancesheet/plugin.py`
- `src/stock_datasource/plugins/tushare_hk_income/plugin.py`
- `src/stock_datasource/plugins/tushare_hk_cashflow/plugin.py`

### Issue-2: 任务超时导致数据采集失败（2026-02-11 已修复）

**现象**：港股财务插件同步任务跑到约 250/2720 时被 kill，全部 permanently failed。

**根因**：`task_queue.py` 默认超时 900 秒（15 分钟），但 2720 只港股遍历至少需要 2 小时。

**修复**：将 `task_queue.py` 中 `timeout_seconds` 从 900 改为 14400（4 小时）。
