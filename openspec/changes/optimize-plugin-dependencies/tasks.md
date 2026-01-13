# Tasks: optimize-plugin-dependencies

## Phase 1: 交易日历配置化 ✅

### 1.1 创建配置目录和服务
- [x] 创建 `src/stock_datasource/config/` 目录
- [x] 将 `modules/datamanage/trade_calendar.csv` 复制到 `config/trade_calendar.csv`
- [x] 创建 `src/stock_datasource/core/trade_calendar.py`
  - 实现 `TradeCalendarService` 单例类
  - 实现 `get_trading_days(n, end_date)` 方法
  - 实现 `is_trading_day(date)` 方法
  - 实现 `get_prev_trading_day(date)` 方法
  - 实现 `get_next_trading_day(date)` 方法
  - 实现 `get_trading_days_between(start, end)` 方法
  - 实现 `refresh_calendar()` 方法（从 TuShare 更新）

### 1.2 集成交易日历服务
- [x] 更新 `modules/datamanage/service.py`
  - 使用 `TradeCalendarService` 替代内部实现
  - 保持现有 API 接口不变
- [x] 更新 `core/__init__.py` 导出 `TradeCalendarService`

### 1.3 验证
- [x] 验证 TradeCalendarService 功能正常
- [x] 验证现有功能不受影响

---

## Phase 2: 插件依赖声明完善 ✅

### 2.1 更新 stock 相关插件
- [x] `tushare_daily/plugin.py`: 添加 `["tushare_stock_basic"]` 依赖
- [x] `tushare_daily_basic/plugin.py`: 添加 `["tushare_stock_basic"]` 依赖
- [x] `tushare_adj_factor/plugin.py`: 添加 `["tushare_stock_basic"]` 依赖

### 2.2 更新 index 相关插件
- [x] `tushare_index_weight/plugin.py`: 添加 `["tushare_index_basic"]` 依赖
- [x] `tushare_idx_factor_pro/plugin.py`: 添加 `["tushare_index_basic"]` 依赖

### 2.3 验证 ETF 插件依赖
- [x] 确认 `tushare_etf_fund_daily` 已正确声明依赖 ✓
- [x] 确认 `tushare_etf_fund_adj` 已正确声明依赖 ✓

---

## Phase 3: 插件管理器增强 ✅

### 3.1 添加基础设施
- [x] 在 `core/base_plugin.py` 添加 `has_data()` 方法
  - 默认实现：检查对应表是否有数据
  - 支持子类覆盖自定义检查逻辑

### 3.2 增强 PluginManager
- [x] 创建 `DependencyCheckResult` 数据类
- [x] 实现 `check_dependencies(plugin_name)` 方法
  - 检查依赖插件是否已注册
  - 检查依赖插件数据是否存在
- [x] 实现 `execute_with_dependencies(plugin_name, auto_run_deps, **kwargs)` 方法
  - 依赖满足时直接执行
  - `auto_run_deps=True` 时自动执行依赖
  - `auto_run_deps=False` 时返回错误提示
- [x] 实现 `get_dependency_graph()` 方法
- [x] 实现 `get_reverse_dependencies(plugin_name)` 方法

### 3.3 添加异常类
- [x] 创建 `DependencyNotSatisfiedError` 异常
- [x] 在依赖检查失败时抛出清晰的错误信息

---

## Phase 4: 前端/API 集成 ✅

### 4.1 更新数据管理 API
- [x] 在 `modules/datamanage/router.py` 添加依赖检查端点
  - `GET /api/datamanage/plugins/{name}/dependencies` - 获取插件依赖
  - `GET /api/datamanage/plugins/{name}/check-dependencies` - 检查依赖状态
  - `GET /api/datamanage/plugins/dependency-graph` - 获取依赖图
- [x] 更新 `POST /api/datamanage/sync/trigger` 响应
  - 依赖未满足时返回 400 错误和缺失依赖列表

### 4.2 更新前端提示
- [x] 在触发同步前显示依赖状态
- [x] 依赖未满足时提示用户先同步依赖数据

---

## Phase 5: 插件分类与角色标识 (NEW)

### 5.1 添加分类和角色枚举
- [ ] 在 `core/base_plugin.py` 添加 `PluginCategory` 枚举
  - `stock` - 股票相关
  - `index` - 指数相关
  - `etf_fund` - ETF/基金相关（合并为一类）
  - `system` - 系统数据
- [ ] 添加 `PluginRole` 枚举
  - `primary` - 主数据（如 daily 行情）
  - `basic` - 基础数据（如 stock_basic）
  - `derived` - 衍生数据（如复权因子）
  - `auxiliary` - 辅助数据（如指数权重）

### 5.2 更新 BasePlugin
- [ ] 添加 `get_category()` 方法
- [ ] 添加 `get_role()` 方法
- [ ] 添加 `get_optional_dependencies()` 方法

### 5.3 更新所有插件
- [ ] `tushare_stock_basic`: category=stock, role=basic
- [ ] `tushare_daily`: category=stock, role=primary, optional_deps=["tushare_adj_factor"]
- [ ] `tushare_daily_basic`: category=stock, role=derived
- [ ] `tushare_adj_factor`: category=stock, role=derived
- [ ] `tushare_etf_basic`: category=etf_fund, role=basic
- [ ] `tushare_etf_fund_daily`: category=etf_fund, role=primary, optional_deps=["tushare_etf_fund_adj"]
- [ ] `tushare_etf_fund_adj`: category=etf_fund, role=derived
- [ ] `tushare_index_basic`: category=index, role=basic
- [ ] `tushare_index_daily`: category=index, role=primary
- [ ] `tushare_index_weight`: category=index, role=auxiliary
- [ ] `tushare_idx_factor_pro`: category=index, role=derived

---

## Phase 6: 可选依赖支持 (NEW)

### 6.1 更新 PluginManager
- [ ] 更新 `DependencyCheckResult` 添加 `optional_dependencies` 字段
- [ ] 更新 `execute_with_dependencies()` 添加 `include_optional` 参数
- [ ] 实现可选依赖的关联执行逻辑

### 6.2 更新 API
- [ ] 更新 `/plugins/{name}/dependencies` 返回可选依赖
- [ ] 更新 `/sync/trigger` 添加 `include_optional` 参数

### 6.3 更新前端
- [ ] SyncDialog 添加"包含可选依赖（如复权因子）"开关
- [ ] 默认开启，用户可选择关闭

---

## Phase 7: 插件筛选 API (NEW)

### 7.1 更新 PluginManager
- [ ] 实现 `get_plugins_by_category(category)` 方法
- [ ] 实现 `get_plugins_by_role(role)` 方法

### 7.2 更新 API
- [ ] 更新 `GET /plugins` 添加 `category` 和 `role` 查询参数
- [ ] 返回的 PluginInfo 添加 `category` 和 `role` 字段

### 7.3 更新前端
- [ ] 插件列表顶部添加分类筛选 Tabs（全部/股票/指数/ETF基金）
- [ ] 添加角色标签显示（主数据/基础/衍生/辅助）

---

## Phase 8: 批量同步 (NEW)

### 8.1 后端实现
- [ ] 在 PluginManager 实现 `batch_trigger_sync()` 方法
  - 自动按依赖顺序排序
  - 支持 include_optional 参数
- [ ] 添加 `POST /sync/batch` API 端点
- [ ] 添加 `POST /sync/category/{category}` API 端点

### 8.2 前端实现
- [ ] 插件列表添加多选功能
- [ ] 添加"批量同步"按钮
- [ ] 批量同步对话框
  - 显示选中的插件列表
  - 自动显示依赖顺序
  - 包含可选依赖开关

---

## Phase 9: 清理和文档

### 9.1 清理旧代码
- [x] 移除 `datamanage/service.py` 中的旧交易日历加载逻辑
- [ ] 移除 `modules/datamanage/trade_calendar.csv`（保留 config 版本）- 可选，保留作为备份

### 9.2 更新文档
- [ ] 更新 `PLUGIN_QUICK_START.md` 添加依赖声明说明
- [ ] 更新 `DEVELOPMENT_GUIDE.md` 添加交易日历使用说明
- [ ] 添加插件分类和角色说明

---

## 验收标准

1. ✅ `TradeCalendarService` 可全局访问，提供统一的交易日期查询
2. ✅ 所有 daily 类插件正确声明对应的 basic 依赖
3. ✅ 执行插件前自动检查依赖是否满足
4. ✅ 依赖未满足时返回清晰的错误信息，包含缺失的依赖列表
5. ✅ 现有功能不受影响（向后兼容）
6. ⬜ 支持按类别筛选插件（股票/指数/ETF）
7. ⬜ 支持批量触发同步任务
8. ⬜ 可选依赖（如复权因子）可关联同步
9. ⬜ 插件列表显示主数据/依赖数据标识

---

## 依赖关系

```
Phase 1-4 (已完成) ────────────────────────────┐
                                               │
Phase 5 (分类/角色) ──────────────────────────┤
                                               │
Phase 6 (可选依赖) ◀── Phase 5 ───────────────┤
                                               │
Phase 7 (筛选API) ◀── Phase 5 ────────────────┤
                                               │
Phase 8 (批量同步) ◀── Phase 5, 6, 7 ─────────┤
                                               │
Phase 9 (清理文档) ◀──────────────────────────┘
```

- Phase 1-4 已完成
- Phase 5 是后续功能的基础
- Phase 6, 7 依赖 Phase 5
- Phase 8 依赖 Phase 5, 6, 7
- Phase 9 在所有功能完成后执行

---

## 实施记录

**实施日期**: 2026-01-13

**已完成的主要工作**:

1. **TradeCalendarService** (`core/trade_calendar.py`)
   - 单例模式，从 `config/trade_calendar.csv` 加载数据到内存
   - 提供 `get_trading_days()`, `is_trading_day()`, `get_prev_trading_day()`, `get_next_trading_day()`, `get_trading_days_between()`, `get_trading_day_offset()`, `refresh_calendar()` 方法
   - 支持多种日期格式输入 (str, date, datetime)

2. **插件依赖声明**
   - `tushare_daily` → `tushare_stock_basic`
   - `tushare_daily_basic` → `tushare_stock_basic`
   - `tushare_adj_factor` → `tushare_stock_basic`
   - `tushare_index_weight` → `tushare_index_basic`
   - `tushare_idx_factor_pro` → `tushare_index_basic`

3. **PluginManager 增强** (`core/plugin_manager.py`)
   - `DependencyCheckResult` 数据类
   - `DependencyNotSatisfiedError` 异常类
   - `check_dependencies()` 方法
   - `execute_with_dependencies()` 方法
   - `get_dependency_graph()` 方法
   - `get_reverse_dependencies()` 方法

4. **BasePlugin 增强** (`core/base_plugin.py`)
   - 添加 `has_data()` 方法检查表数据存在性

5. **API 端点** (`modules/datamanage/router.py`)
   - `GET /plugins/{name}/dependencies` - 获取插件依赖详情
   - `GET /plugins/{name}/check-dependencies` - 检查依赖状态
   - `GET /plugins/dependency-graph` - 获取完整依赖图
   - 更新 `POST /sync/trigger` 添加依赖检查

6. **前端更新** (`frontend/src/`)
   - `api/datamanage.ts`: 添加依赖检查 API 接口
   - `stores/datamanage.ts`: 添加依赖检查状态和方法
   - `views/datamanage/components/PluginDetailDialog.vue`: 添加"依赖关系" Tab 显示依赖状态
   - `views/datamanage/components/SyncDialog.vue`: 同步前检查依赖，未满足时禁用同步按钮并显示警告
