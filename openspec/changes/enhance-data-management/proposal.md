# Change: 增强数据管理功能 - 基于交易日的数据缺失检测与同步任务管理

## Why

当前数据管理模块存在以下问题：
1. **缺乏数据缺失检测机制**：无法基于交易日历检查各插件数据的完整性
2. **同步任务不可见**：插件执行过程无法在界面上实时展示
3. **插件调度不智能**：不区分每日更新和周期性更新的插件
4. **数据展示不直观**：无法直接跳转查看各插件的数据情况
5. **同步任务列表功能不完善**：缺乏分页、排序、搜索和筛选能力
6. **错误信息不详细**：插件报错500时无法获取完整堆栈信息用于调试
7. **任务展示维度单一**：仅以单个插件维度展示，不便于查看批量任务整体执行情况
8. **缺乏自定义组合同步**：无法将多个插件组合成一个批量任务统一触发

## What Changes

### 后端改进
- **新增**：基于交易日历的数据缺失检测服务
- **新增**：同步任务管理器（创建、跟踪、历史记录）
- **新增**：插件数据状态API（最新数据日期、缺失日期列表）
- **新增**：同步任务分页查询API（支持分页、状态筛选、插件名搜索、多字段排序）
- **新增**：详细错误捕获（包含完整堆栈跟踪信息）
- **新增**：批量任务详情API（获取批量任务所有子任务详情及错误汇总）
- **新增**：`BatchExecutionDetail`、`BatchTaskDetail` 数据模型
- **新增**：单插件同步也创建执行记录，统一作为批量任务展示
- **新增**：部分重试API（`/schedule/partial-retry/{execution_id}`），仅重试失败的插件
- **新增**：自定义插件组合管理（`PluginGroup`模型，CRUD + 触发执行）
- **新增**：组合触发API（`/groups/{group_id}/trigger`）
- **修改**：插件管理器增加调度频率识别
- **修改**：数据管理API返回真实数据（替换Mock数据）
- **修改**：`ScheduleExecutionRecord` 增加 `group_name` 字段标识组合触发
- **修改**：`trigger_type` 扩展支持 `group`、`retry` 类型
- **修复**：增量同步使用交易日历获取最近有效交易日，避免使用未来日期或当天未发布数据的日期

### 前端改进
- **新增**：数据缺失检测面板（按交易日展示）
- **新增**：同步任务实时进度展示
- **新增**：插件数据详情弹窗（可跳转数据展示）
- **重构**：同步任务列表改为批量任务维度展示，支持可展开行查看子任务
- **新增**：批量任务详情弹窗，汇总所有失败任务的错误信息，提供一键复制功能
- **新增**：部分重试功能，仅重试批量任务中失败的插件（"重试失败"按钮）
- **新增**：自定义组合管理Tab（创建/编辑/删除/执行组合）
- **新增**：组合编辑对话框，支持多选插件
- **新增**：任务列表分页功能（支持分页大小调整和跳页）
- **新增**：错误堆栈展示（可折叠查看完整堆栈跟踪）
- **修改**：插件列表增加调度频率、最新数据日期、缺失天数
- **新增**：数据缺失检测天数可调节（7/15/30/60/90/180/365天选择器）
- **新增**：任务详情弹窗（显示任务ID、进度、处理日期、错误信息等）
- **修复**：进度条百分比保留一位小数显示
- **新增**：检测插件数说明提示（仅检测daily频率插件）

## Impact

### Affected Specs
- data-management（新增）

### Affected Code
- `src/stock_datasource/modules/datamanage/router.py` - API路由，新增分页排序参数、批量任务详情API、部分重试API、组合管理API
- `src/stock_datasource/modules/datamanage/service.py` - 新增服务层，增强错误捕获
- `src/stock_datasource/modules/datamanage/schedule_service.py` - 新增批量任务详情获取、部分重试、手动执行记录创建
- `src/stock_datasource/modules/datamanage/schemas.py` - 新增分页响应模型、批量任务详情模型、组合管理模型
- `src/stock_datasource/config/runtime_config.py` - 新增plugin_groups存储和管理函数
- `src/stock_datasource/core/plugin_manager.py` - 增强插件信息
- `src/stock_datasource/core/base_plugin.py` - 增加数据状态方法
- `frontend/src/views/datamanage/DataManageView.vue` - 界面重构、批量任务展示、错误汇总弹窗、部分重试、组合管理Tab
- `frontend/src/views/datamanage/components/MissingDataPanel.vue` - 天数选择器、检测插件数说明
- `frontend/src/views/datamanage/components/TaskDetailDialog.vue` - 任务详情弹窗、错误堆栈展示
- `frontend/src/stores/datamanage.ts` - 状态管理，新增批量任务详情获取、部分重试、组合管理
- `frontend/src/api/datamanage.ts` - API调用，新增批量任务详情接口、部分重试接口、组合管理接口

### Dependencies
- 依赖 `ods_trade_calendar` 表提供交易日历数据
- 依赖各插件的 `config.json` 中的 `schedule` 配置
