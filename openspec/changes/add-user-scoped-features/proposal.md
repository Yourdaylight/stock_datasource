# Change: 添加用户维度的功能完善

## Why

当前系统已完成用户认证功能，但以下关键模块尚未实现用户维度隔离：
1. AI对话历史存储在内存中，没有持久化且没有绑定用户
2. 数据管理模块所有用户均可访问，缺少权限控制
3. 数据同步任务历史没有记录操作用户
4. 持仓AI分析可能跨用户访问数据

为保障数据安全和用户体验，需要从用户维度完善这些能力。

## What Changes

### 1. 用户级AI对话历史
- 对话会话（session）与用户ID绑定
- 对话历史持久化到数据库（ClickHouse）
- 用户只能查看/操作自己的会话

### 2. 数据管理权限控制
- **BREAKING**: 数据管理API仅限白名单用户访问
- 新增 `is_admin` 用户属性区分管理员
- 未授权用户访问数据管理返回 403

### 3. 任务历史用户绑定
- 同步任务历史记录触发用户ID
- 任务列表支持按用户筛选
- 日志中记录操作用户信息

### 4. 持仓AI分析用户隔离
- Agent工具调用强制传递用户ID
- 确保分析工具只访问当前用户持仓

## Impact

- Affected specs: `user-auth`, `user-chat-history` (new), `user-data-isolation` (new)
- Affected code:
  - `src/stock_datasource/modules/chat/` (service, router, schemas, schema.sql)
  - `src/stock_datasource/modules/auth/` (schemas, service, schema.sql)
  - `src/stock_datasource/modules/datamanage/` (router, service, schemas)
  - `src/stock_datasource/agents/` (orchestrator, base_agent, enhanced_portfolio_agent)
- Database: 新增 `chat_sessions`, `chat_messages` 表; 修改 `users` 表增加 `is_admin`; 修改 `sync_history` 表增加 `user_id`
