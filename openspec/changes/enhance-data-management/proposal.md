# Change: 增强数据管理功能 - 基于交易日的数据缺失检测与同步任务管理

## Why

当前数据管理模块存在以下问题：
1. **缺乏数据缺失检测机制**：无法基于交易日历检查各插件数据的完整性
2. **同步任务不可见**：插件执行过程无法在界面上实时展示
3. **插件调度不智能**：不区分每日更新和周期性更新的插件
4. **数据展示不直观**：无法直接跳转查看各插件的数据情况

## What Changes

### 后端改进
- **新增**：基于交易日历的数据缺失检测服务
- **新增**：同步任务管理器（创建、跟踪、历史记录）
- **新增**：插件数据状态API（最新数据日期、缺失日期列表）
- **修改**：插件管理器增加调度频率识别
- **修改**：数据管理API返回真实数据（替换Mock数据）
- **修复**：增量同步使用交易日历获取最近有效交易日，避免使用未来日期或当天未发布数据的日期

### 前端改进
- **新增**：数据缺失检测面板（按交易日展示）
- **新增**：同步任务实时进度展示
- **新增**：插件数据详情弹窗（可跳转数据展示）
- **修改**：插件列表增加调度频率、最新数据日期、缺失天数
- **新增**：数据缺失检测天数可调节（7/15/30/60/90/180/365天选择器）
- **新增**：任务详情弹窗（显示任务ID、进度、处理日期、错误信息等）
- **修复**：进度条百分比保留一位小数显示
- **新增**：检测插件数说明提示（仅检测daily频率插件）

## Impact

### Affected Specs
- data-management（新增）

### Affected Code
- `src/stock_datasource/modules/datamanage/router.py` - API路由
- `src/stock_datasource/modules/datamanage/service.py` - 新增服务层
- `src/stock_datasource/core/plugin_manager.py` - 增强插件信息
- `src/stock_datasource/core/base_plugin.py` - 增加数据状态方法
- `frontend/src/views/datamanage/DataManageView.vue` - 界面重构、进度条小数修复、任务详情入口
- `frontend/src/views/datamanage/components/MissingDataPanel.vue` - 天数选择器、检测插件数说明
- `frontend/src/views/datamanage/components/TaskDetailDialog.vue` - 新增任务详情弹窗组件
- `frontend/src/stores/datamanage.ts` - 状态管理
- `frontend/src/api/datamanage.ts` - API调用

### Dependencies
- 依赖 `ods_trade_calendar` 表提供交易日历数据
- 依赖各插件的 `config.json` 中的 `schedule` 配置
