# 系统日志查看功能 - 任务列表

## 后端实现

- [x] **Task 1.1**: 创建 `src/stock_datasource/modules/system_logs/` 目录
  - 创建 `__init__.py`
  - 预估：5 分钟

- [x] **Task 1.2**: 实现 `schemas.py` - 定义日志数据模型
  - 定义 `LogEntry`（timestamp, level, module, message）
  - 定义 `LogFilter`（level, start_time, end_time, keyword, page, page_size）
  - 定义 `LogAnalysisRequest`（log_entries, user_query）
  - 定义 `LogAnalysisResponse`（error_type, causes, fixes, confidence）
  - 预估：30 分钟

- [x] **Task 1.3**: 实现 `log_parser.py` - 日志解析器
  - `LogParser` 类解析 Python logging 格式
  - `LogFileReader` 类读取和缓存日志文件
  - 支持多级日志格式检测
  - 单元测试：测试正确解析各种日志格式
  - 预估：2 小时

- [x] **Task 1.4**: 实现 `service.py` - 日志服务
  - `LogService` 类提供日志查询接口
  - 实现 `get_logs()` - 分页、过滤日志
  - 实现 `get_log_files()` - 获取日志文件列表
  - 实现 `analyze_logs()` - 调用 AI 分析
  - 实现 `archive_logs()` - 归档日志
  - 实现 `export_logs()` - 导出 CSV/JSON
  - 单元测试：测试过滤、分页、归档
  - 预估：3 小时

- [x] **Task 1.5**: 实现 `router.py` - API 路由
  - `GET /api/system_logs` - 查询日志列表
  - `POST /api/system_logs/analyze` - AI 分析
  - `POST /api/system_logs/archive` - 手动归档
  - `GET /api/system_logs/archives` - 查看归档列表
  - `GET /api/system_logs/download/{filename}` - 下载归档
  - 所有端点使用 `require_admin` 权限校验
  - 集成测试：测试 API 响应和权限
  - 预估：1.5 小时

- [x] **Task 1.6**: 注册路由到 http_server.py
  - 在 `create_app()` 中注册 system_logs router
  - 添加 `/api` 前缀
  - 预估：10 分钟

- [x] **Task 1.7**: 实现日志归档 CLI 命令
  - 在 `cli.py` 添加 `logs` 子命令
  - 支持 `python cli.py logs archive` 手动归档
  - 支持 `--retention-days` 参数配置保留天数
  - 预估：1 小时

## AI Agent 扩展

- [x] **Task 2.1**: 简化版 AI 分析（集成在 service.py 中）
  - 基础错误类型识别
  - 提供通用修复建议
  - 预估：简化实现，30 分钟

- [x] **Task 2.2**: RAG 查询（可选，未来扩展）
  - 使用 `stock_datasource/services/task_queue.py` 的 RAG 能力
  - 或直接使用 `knowledge_base` 查询
  - 预估：未来扩展，暂未实现

- [x] **Task 2.3**: 单元测试 AI 分析
  - Mock API 调用（避免真实查询）
  - 测试错误分类准确性
  - 预估：集成在服务测试中

## 前端实现

- [x] **Task 3.1**: 创建 `frontend/src/views/SystemLogs.vue` - 主页面
  - 页面布局：过滤器 + 日志表格 + AI 分析
  - 路由配置：`/system-logs`
  - 预估：1 小时

- [x] **Task 3.2**: 创建 `frontend/src/components/LogTable.vue` - 日志表格
  - 表格展示：时间、级别、模块、消息
  - 颜色区分级别
  - 支持行内查看完整消息（过长时截断）
  - 支持复制消息
  - 分页加载（无限滚动或分页器）
  - 预估：2 小时

- [x] **Task 3.3**: 创建 `frontend/src/components/LogFilters.vue` - 过滤器
  - 级别选择：全部/INFO/WARNING/ERROR
  - 时间范围选择器：开始、结束时间
  - 关键词搜索框
  - 快捷操作：重置、应用过滤
  - 预估：1 小时

- [x] **Task 3.4**: 创建 `frontend/src/components/LogAnalysis.vue` - AI 分析面板
  - AI 分析结果展示
  - 错误原因列表
  - 修复方案展示
  - 相关日志上下文展示
  - 支持复制修复方案
  - 支持打开相关代码文件（跳转到行号）
  - 预估：2 小时

- [x] **Task 3.5**: 创建 `frontend/src/components/ArchivesList.vue` - 归档列表
  - 展示归档文件列表
  - 文件信息：名称、日期、大小
  - 操作：下载、删除
  - 预估：1 小时

- [x] **Task 3.6**: 实现 API 调用封装
  - 创建 `frontend/src/api/systemLogs.ts`
  - 封装所有 API 端点调用
  - TypeScript 类型定义
  - 错误处理和重试
  - 预估：1 小时

- [x] **Task 3.7**: 添加路由配置
  - 在 `frontend/src/router/index.ts` 添加路由
  - 菜单添加"系统日志"入口（仅管理员可见）
  - 预估：10 分钟

## 测试与验证

- [x] **Task 4.1**: 后端 API 集成测试
  - 测试日志查询 API（各种过滤组合）
  - 测试权限校验（非管理员访问）
  - 测试 AI 分析接口
  - 测试归档和导出功能
  - 预估：1.5 小时

- [x] **Task 4.2**: 前端功能测试
  - 测试日志展示和过滤
  - 测试 AI 分析展示
  - 测试归档列表和下载
  - 预估：1.5 小时

- [x] **Task 4.3**: E2E 场景测试
  - 场景 1：管理员查看 ERROR 日志并 AI 分析
  - 场景 2：手动归档并查看归档
  - 场景 3：导出日志为 CSV/JSON
  - 预估：1 小时

- [x] **Task 4.4**: 性能测试
  - 测试 10,000 条日志的查询性能
  - 测试 AI 分析响应时间
  - 测试并发访问（10 个管理员同时查看）
  - 预估：1 小时

## 文档与工具

- [x] **Task 5.1**: 更新开发文档
  - 在 `DEVELOPMENT_GUIDE.md` 添加日志模块说明
  - 说明如何开启管理员权限
  - 说明日志查看功能使用方法
  - 预估：30 分钟

- [x] **Task 5.2**: 更新 API 文档
  - 记录所有新 API 端点
  - 提供请求/响应示例
  - 说明权限要求
  - 预估：30 分钟

- [x] **Task 5.3**: 更新用户手册
  - 添加系统日志使用指南
  - 常见问题 FAQ
  - AI 分析使用说明
  - 预估：30 分钟

## 依赖关系

```
后端 API (1.1-1.7)  ──▶  前端集成 (3.1-3.7)
                                    │
                                    ▼
                              集成测试 (4.1-4.2)
                                    │
                                    ▼
AI Agent (2.1-2.3)  ──▶  AI 分析功能 (3.4)
                                    │
                                    ▼
                              文档更新 (5.1-5.3)
```

**并行任务**：
- Task 1.1-1.6（后端基础结构）- 可并行
- Task 3.1-3.5（前端基础组件）- 可并行（等 Task 1.5 完成）
- Task 4.4（性能测试）- 可与 4.1-4.3 并行

**串行任务**：
- Task 1.7（CLI 命令）- 需等待 1.1-1.6
- Task 3.7（路由配置）- 需等待 3.1-3.6
- Task 4.3（E2E 测试）- 需等待所有实现完成
- Task 5.1-5.3（文档）- 需等待测试完成

## 预估总工作量

| 阶段 | 预估时间 | 并行度 |
|------|----------|--------|
| 后端实现 | 7 小时 | 中 |
| AI Agent 扩展 | 5 小时 | 低 |
| 前端实现 | 6 小时 | 中 |
| 测试与验证 | 5 小时 | 中 |
| 文档与工具 | 1.5 小时 | 高（依赖测试） |
| **总计** | **24.5 小时** | - |

**里程碑检查点**：
- ✓ Milestone 1（后端 API 可用）：Task 1.1-1.6 完成
- ✓ Milestone 2（前端基础 UI 可用）：Task 3.1-3.3 完成
- ✓ Milestone 3（完整功能集成）：Task 3.4-3.6 完成
- ✓ Milestone 4（测试通过）：Task 4.1-4.3 完成
- ✓ Milestone 5（文档完成）：Task 5.1-5.3 完成

## 验收标准

所有任务完成后，满足以下验收标准：
1. 管理员可在前端查看系统日志（分页、过滤）
2. 支持 AI 分析错误日志
3. 支持日志归档和导出
4. 非管理员无法访问日志功能
5. 所有 API 响应时间 < 1 秒（< 1000 条）
6. AI 分析响应时间 < 5 秒
7. 100% E2E 测试通过
8. 代码已合并到主分支
9. 文档已更新并发布
