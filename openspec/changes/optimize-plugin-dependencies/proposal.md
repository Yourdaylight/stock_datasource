# Proposal: optimize-plugin-dependencies

## Summary
优化数据插件系统，实现全局交易日历配置、插件依赖关系管理、插件分类筛选、批量任务触发和**定时调度任务管理**，确保数据获取的正确顺序和完整性，支持每日自动增量同步所有数据。

## Problem Statement

### 当前问题

1. **交易日历管理分散** ✅ 已解决
   - 已实现 `TradeCalendarService` 全局服务

2. **插件依赖关系不完整** ✅ 已解决
   - 已完善插件依赖声明

3. **数据获取顺序无保障** ✅ 已解决
   - 已实现依赖检查机制

4. **插件管理功能不足** (部分完成)
   - ✅ 已支持 category/role 筛选
   - ✅ 已支持批量同步 API
   - ⬜ 缺少港股分类（当前只有 stock/index/etf_fund/system）
   - ⬜ 前端筛选 UI 未完善

5. **缺少定时调度任务管理** 🆕
   - 无法配置每日自动增量同步所有插件
   - 无法按插件依赖顺序调度执行
   - 无法控制单个插件是否加入全量扫描
   - 无法通过界面管理定时任务开关

## Proposed Solution

### 1-4. 已完成功能 ✅
- 全局交易日历配置化
- 插件依赖关系强化
- 依赖检查机制
- 插件分类与角色标识（基础框架）

### 5. 插件分类优化 🆕

调整分类以支持港股和A股区分：

**分类 (category)**:
- `cn_stock` - A股相关（原 `stock`）
- `hk_stock` - 港股相关 🆕
- `index` - 指数相关  
- `etf_fund` - ETF/基金相关
- `system` - 系统数据（如交易日历）

**市场 (market)** - 新增属性:
- `CN` - A股市场
- `HK` - 港股市场
- `ALL` - 全市场

### 6. 定时调度任务管理 🆕

实现可配置的定时调度系统：

#### 6.1 调度配置模型

```python
class ScheduleConfig:
    """定时调度配置"""
    enabled: bool = True                    # 是否启用定时调度
    cron_expression: str = "0 18 * * 1-5"   # Cron表达式（默认工作日18:00）
    include_optional_deps: bool = True       # 是否包含可选依赖
    
class PluginScheduleConfig:
    """单个插件的调度配置"""
    plugin_name: str
    enabled: bool = True                     # 是否加入定时任务
    full_scan_enabled: bool = False          # 是否启用全量扫描
    priority: int = 0                        # 执行优先级（依赖关系自动计算）
```

#### 6.2 调度执行流程

```
每日18:00（工作日）
    │
    ▼
1. 检查是否为交易日
    │
    ├─ 非交易日 → 跳过执行
    │
    ▼
2. 获取启用的插件列表
    │
    ▼
3. 按依赖关系拓扑排序
    │
    ├─ basic 插件优先（stock_basic, index_basic, etf_basic）
    │   │
    │   ▼
    ├─ primary 插件（daily 行情）
    │   │
    │   ▼
    └─ derived/auxiliary 插件（复权因子、权重等）
    │
    ▼
4. 按顺序创建同步任务
    │
    ├─ full_scan_enabled=true → 创建 FULL 类型任务
    │
    └─ full_scan_enabled=false → 创建 INCREMENTAL 类型任务
```

#### 6.3 API 设计

```python
# 获取调度配置
GET /api/datamanage/schedule/config

# 更新调度配置
PUT /api/datamanage/schedule/config

# 获取插件调度状态列表
GET /api/datamanage/schedule/plugins

# 更新单个插件调度配置
PUT /api/datamanage/schedule/plugins/{name}

# 手动触发全量调度（立即执行一次）
POST /api/datamanage/schedule/trigger

# 获取调度执行历史
GET /api/datamanage/schedule/history
```

### 7. 前端界面优化 🆕

#### 7.1 插件列表增强

- **分类筛选 Tabs**: 全部 / A股 / 港股 / 指数 / ETF基金
- **角色标签**: 显示 主数据/基础/衍生/辅助 标识
- **定时任务开关**: 每个插件行显示"加入定时任务"开关
- **全量扫描开关**: 每个插件行显示"全量扫描"开关

#### 7.2 调度管理面板（新增）

```
┌─────────────────────────────────────────────────────────┐
│ 定时调度配置                                              │
├─────────────────────────────────────────────────────────┤
│ 启用定时调度: [开关]                                      │
│ 执行时间: [18:00 ▼] 每天/仅工作日 [▼]                     │
│ 包含可选依赖（复权因子等）: [开关]                          │
│                                                         │
│ [立即执行一次]  [查看执行历史]                             │
├─────────────────────────────────────────────────────────┤
│ 💡 操作说明：                                             │
│ • 定时调度会在每个交易日自动执行增量同步                    │
│ • 插件按依赖顺序执行：基础数据 → 主数据 → 衍生数据           │
│ • 开启"全量扫描"会重新获取全部历史数据（耗时较长）           │
│ • 建议仅在数据异常时开启全量扫描                            │
└─────────────────────────────────────────────────────────┘
```

#### 7.3 操作说明文案

在关键位置添加帮助提示：

| 位置 | 说明文案 |
|-----|---------|
| 定时任务开关 | "启用后，该插件将加入每日自动同步队列" |
| 全量扫描开关 | "开启后重新获取全部数据，而非仅获取最新数据" |
| 依赖状态 | "依赖未满足时无法同步，请先同步依赖插件" |
| 批量同步 | "将按依赖顺序自动执行，无需手动排序" |

## Scope

### In Scope
- ✅ 交易日历配置化重构（已完成）
- ✅ 插件依赖关系声明完善（已完成）
- ✅ 插件管理器依赖检查增强（已完成）
- ⬜ 插件分类优化（增加港股/A股区分）
- ⬜ 定时调度任务管理后端
- ⬜ 定时调度任务管理前端
- ⬜ 批量同步前端增强
- ⬜ 操作说明和帮助提示

### Out of Scope
- 新数据插件开发
- 数据库表结构变更
- Airflow 等外部调度系统集成

## Impact Analysis

### 受影响组件
- `src/stock_datasource/core/base_plugin.py` - 调整分类枚举
- `src/stock_datasource/core/plugin_manager.py` - 添加调度相关方法
- `src/stock_datasource/modules/datamanage/service.py` - 新增 ScheduleService
- `src/stock_datasource/modules/datamanage/router.py` - 新增调度 API
- `src/stock_datasource/modules/datamanage/schemas.py` - 新增调度相关模型
- `src/stock_datasource/plugins/akshare_hk_*/plugin.py` - 设置港股分类
- `frontend/src/views/datamanage/` - 调度管理 UI
- `frontend/src/stores/datamanage.ts` - 调度状态管理
- `frontend/src/api/datamanage.ts` - 调度 API 接口

### 数据存储
- 新增 `schedule_config` 表存储调度配置
- 调度执行记录复用现有 `sync_task_history` 表

### 兼容性
- 向后兼容：现有 API 接口不变
- 分类变更：`stock` 重命名为 `cn_stock`，需更新前端筛选

## Success Criteria

1. ✅ 交易日历可通过全局服务统一访问
2. ✅ 所有 daily 类插件正确声明 basic 依赖
3. ✅ 插件执行前自动检查依赖是否满足
4. ✅ 依赖未满足时给出清晰的错误提示
5. ⬜ **支持按类别筛选插件（A股/港股/指数/ETF基金）**
6. ⬜ **支持批量触发同步任务（前端完善）**
7. ✅ 可选依赖（如复权因子）可关联同步
8. ⬜ **插件列表显示定时任务/全量扫描开关**
9. ⬜ **定时调度可配置并自动按依赖顺序执行**
10. ⬜ **界面显示操作说明和帮助提示**

## Timeline Estimate

- Phase 1-4（已完成）：约 3 天
- Phase 5（分类优化）：0.5 天
- Phase 6（定时调度后端）：1.5 天
- Phase 7（前端完善）：1.5 天
- 测试：0.5 天
- **剩余工作总计：4 天**
