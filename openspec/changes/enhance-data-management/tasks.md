# Tasks: 数据管理功能增强

## 1. 后端基础设施

- [x] 1.1 创建 `sync_task_history` 表结构（ClickHouse）
- [x] 1.2 创建 `src/stock_datasource/modules/datamanage/service.py` 服务层
- [x] 1.3 创建 `src/stock_datasource/modules/datamanage/schemas.py` 数据模型

## 2. 数据缺失检测

- [x] 2.1 实现交易日历查询服务（获取最近N个交易日）
- [x] 2.2 实现各插件ODS表数据存在性检查
- [x] 2.3 实现缺失日期汇总API `/api/datamanage/missing-data`
- [ ] 2.4 添加每日16:00定时检测任务（使用APScheduler）
- [x] 2.5 实现手动触发检测API

## 3. 插件状态与详情

- [x] 3.1 修改 `base_plugin.py` 添加 `get_schedule()` 方法
- [x] 3.2 修改 `plugin_manager.py` 添加 `get_plugin_config/schema()` 方法
- [x] 3.3 实现插件详情API `/api/datamanage/plugins/{name}/detail`（返回config+schema+status）
- [x] 3.4 实现插件数据预览API `/api/datamanage/plugins/{name}/data`
- [x] 3.5 实现插件状态API `/api/datamanage/plugins/{name}/status`

## 4. 同步任务管理

- [x] 4.1 创建 `SyncTaskManager` 类（任务创建、状态更新、并行队列，支持至少3个任务并行）
- [x] 4.2 实现任务执行器（调用插件run方法，使用信号量控制任务并发数）
- [x] 4.3 实现单任务内多日期并行处理（根据rate_limit动态计算日期并发数）
- [x] 4.4 实现任务列表API `/api/datamanage/sync/tasks`
- [x] 4.5 实现任务触发API `/api/datamanage/sync/trigger`
- [x] 4.6 实现任务状态API `/api/datamanage/sync/status/{task_id}`
- [x] 4.7 实现任务历史API `/api/datamanage/sync/history`
- [x] 4.8 实现30天历史自动清理（cleanup_old_tasks方法）

## 5. 前端界面重构

- [x] 5.1 创建数据缺失检测面板组件 `MissingDataPanel.vue`
- [x] 5.2 创建同步任务进度组件 `SyncTaskPanel.vue`
- [x] 5.3 创建插件数据预览弹窗组件 `PluginDataDialog.vue`
- [x] 5.4 创建插件详情弹窗组件 `PluginDetailDialog.vue`（展示config/schema/status）
- [x] 5.5 修改 `DataManageView.vue` 集成新组件
- [x] 5.6 修改 `datamanage.ts` store 添加新状态和方法
- [x] 5.7 修改 `datamanage.ts` API 添加新接口

## 6. 插件包导入导出（预留）

- [ ] 6.1 定义插件包manifest.json格式
- [ ] 6.2 实现插件导出API `/api/datamanage/plugins/{name}/export`（预留）
- [ ] 6.3 实现插件导入API `/api/datamanage/plugins/import`（预留）
- [ ] 6.4 前端导入导出按钮（预留，暂不实现）

## 7. AI诊断功能

- [x] 7.1 创建 `DiagnosisService` 类（日志读取、模式匹配、建议生成）
- [x] 7.2 定义已知错误模式和解决方案
- [x] 7.3 实现诊断API `/api/datamanage/diagnosis`
- [x] 7.4 创建前端诊断面板组件 `DiagnosisPanel.vue`
- [x] 7.5 集成到数据管理页面

## 8. 测试与验证

- [ ] 8.1 测试数据缺失检测准确性
- [ ] 8.2 测试同步任务执行流程
- [ ] 8.3 测试插件详情展示完整性
- [ ] 8.4 测试前端界面交互
- [ ] 8.5 验证插件数据跳转功能
- [ ] 8.6 测试AI诊断准确性
