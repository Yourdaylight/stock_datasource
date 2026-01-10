# Tasks: 数据管理功能增强

## 1. 后端基础设施

- [ ] 1.1 创建 `sync_task_history` 表结构（ClickHouse）
- [ ] 1.2 创建 `src/stock_datasource/modules/datamanage/service.py` 服务层
- [ ] 1.3 创建 `src/stock_datasource/modules/datamanage/schemas.py` 数据模型

## 2. 数据缺失检测

- [ ] 2.1 实现交易日历查询服务（获取最近N个交易日）
- [ ] 2.2 实现各插件ODS表数据存在性检查
- [ ] 2.3 实现缺失日期汇总API `/api/datamanage/missing-data`
- [ ] 2.4 添加缓存机制（每小时刷新）

## 3. 插件状态增强

- [ ] 3.1 修改 `base_plugin.py` 添加 `get_data_status()` 方法
- [ ] 3.2 修改 `plugin_manager.py` 添加 `get_plugin_data_status()` 方法
- [ ] 3.3 实现插件详情API `/api/datamanage/plugins/{name}/status`
- [ ] 3.4 实现插件数据预览API `/api/datamanage/plugins/{name}/data`

## 4. 同步任务管理

- [ ] 4.1 创建 `SyncTaskManager` 类（任务创建、状态更新）
- [ ] 4.2 实现任务执行器（调用插件run方法）
- [ ] 4.3 实现任务列表API `/api/datamanage/sync/tasks`
- [ ] 4.4 实现任务触发API `/api/datamanage/sync/trigger`
- [ ] 4.5 实现任务状态API `/api/datamanage/sync/status/{task_id}`
- [ ] 4.6 实现任务历史API `/api/datamanage/sync/history`

## 5. 前端界面重构

- [ ] 5.1 创建数据缺失检测面板组件
- [ ] 5.2 创建同步任务进度组件
- [ ] 5.3 创建插件数据预览弹窗组件
- [ ] 5.4 修改 `DataManageView.vue` 集成新组件
- [ ] 5.5 修改 `datamanage.ts` store 添加新状态和方法
- [ ] 5.6 修改 `datamanage.ts` API 添加新接口

## 6. 测试与验证

- [ ] 6.1 测试数据缺失检测准确性
- [ ] 6.2 测试同步任务执行流程
- [ ] 6.3 测试前端界面交互
- [ ] 6.4 验证插件数据跳转功能
