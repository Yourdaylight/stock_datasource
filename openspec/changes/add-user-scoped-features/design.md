# Design: 用户维度功能设计

## Context

系统已有完整的用户认证体系（JWT Token），但关键业务模块未充分利用用户身份进行数据隔离和权限控制。

### 当前状态
- **认证**: JWT Token认证，用户表（users）已有 `id`, `email`, `username`
- **对话**: 内存存储，session_id随机生成，无用户绑定
- **数据管理**: 所有登录用户均可访问
- **任务历史**: 不记录操作用户
- **持仓分析**: Agent工具有user_id参数但默认值为"default_user"

### 约束
- 数据库使用 ClickHouse，需要考虑表结构设计
- 对话历史可能较大，需要考虑存储策略
- Agent执行上下文需要传递用户信息

## Goals / Non-Goals

### Goals
1. 对话历史持久化并按用户隔离
2. 数据管理功能仅管理员可访问
3. 任务历史可追溯到具体用户
4. 持仓分析确保用户数据隔离

### Non-Goals
- 不涉及复杂的RBAC权限系统（仅区分普通用户/管理员）
- 不涉及对话历史的搜索功能
- 不涉及跨用户数据共享

## Decisions

### Decision 1: 对话历史存储方案
**选择**: ClickHouse + 内存缓存混合模式

```
chat_sessions 表:
- session_id (String, PRIMARY KEY)
- user_id (String)
- title (String, 可选)
- created_at (DateTime)
- updated_at (DateTime)
- last_message_at (DateTime)
- message_count (UInt32)

chat_messages 表:
- id (String, UUID)
- session_id (String)
- user_id (String)
- role (String: user/assistant)
- content (String)
- metadata (String, JSON)
- created_at (DateTime)
```

**Rationale**:
- ClickHouse适合追加写入和批量查询
- 内存缓存热会话提升响应速度
- 按用户ID分区便于隔离查询

### Decision 2: 管理员权限方案
**选择**: 用户表增加 `is_admin` 布尔字段

**Rationale**:
- 简单直接，满足当前需求
- 预留可扩展性（未来可改为角色系统）
- 初始管理员可通过白名单邮箱配置

### Decision 3: Agent用户上下文传递
**选择**: 通过 context dict 传递 user_id，Agent强制校验

```python
context = {
    "session_id": session_id,
    "user_id": current_user["id"],
    "history": ...,
}
```

**Rationale**:
- 不改变现有Agent接口
- 在关键工具调用处校验user_id存在性
- 确保持仓相关工具只访问当前用户数据

## Risks / Trade-offs

### Risk 1: 对话历史迁移
- **风险**: 现有内存对话数据丢失
- **缓解**: 上线前清空测试数据，生产环境无需迁移

### Risk 2: 性能影响
- **风险**: 数据库查询增加延迟
- **缓解**: 使用内存缓存热数据，批量写入数据库

### Risk 3: 管理员误操作
- **风险**: 非预期用户获得管理员权限
- **缓解**: 初始仅通过配置文件指定管理员邮箱

## Migration Plan

### Phase 1: 数据库变更
1. 新增 `chat_sessions`, `chat_messages` 表
2. `users` 表增加 `is_admin` 字段 (默认 false)
3. `sync_history` 表增加 `user_id` 字段

### Phase 2: 后端服务
1. 实现 ChatService 持久化逻辑
2. 实现 DataManage 权限检查中间件
3. 更新 SyncTaskManager 记录用户
4. 更新 Agent context 传递

### Phase 3: 前端适配
1. 对话模块使用用户session
2. 数据管理模块显示权限提示
3. 任务历史显示操作用户

## Open Questions

1. 对话历史保留策略？（建议：默认保留90天）
2. 管理员如何初始化？（建议：配置文件指定邮箱列表）
