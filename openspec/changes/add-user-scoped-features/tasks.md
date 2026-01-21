# Tasks: 用户维度功能完善

## 1. 数据库Schema变更

- [ ] 1.1 创建 `chat_sessions` 表 (session_id, user_id, title, created_at, updated_at, last_message_at, message_count)
- [ ] 1.2 创建 `chat_messages` 表 (id, session_id, user_id, role, content, metadata, created_at)
- [ ] 1.3 `users` 表增加 `is_admin` 字段 (UInt8, 默认0)
- [ ] 1.4 更新 `sync_history` 表增加 `user_id` 字段

## 2. 用户管理员功能

- [ ] 2.1 更新 auth/schemas.py 添加 is_admin 字段到 UserResponse
- [ ] 2.2 更新 auth/service.py 支持管理员邮箱配置自动设置 is_admin
- [ ] 2.3 添加 auth/dependencies.py 中的 `require_admin` 依赖
- [ ] 2.4 更新 auth/router.py 的 `/me` 接口返回 is_admin

## 3. 对话历史持久化

- [ ] 3.1 更新 chat/schemas.py 添加 Session/Message 模型
- [ ] 3.2 重构 chat/service.py 实现数据库持久化
  - [ ] 3.2.1 create_session 写入数据库并绑定 user_id
  - [ ] 3.2.2 add_message 写入数据库
  - [ ] 3.2.3 get_session_history 从数据库查询
  - [ ] 3.2.4 get_user_sessions 获取用户所有会话列表
- [ ] 3.3 更新 chat/router.py 添加用户认证和会话管理接口
  - [ ] 3.3.1 POST /session 需要登录，绑定 user_id
  - [ ] 3.3.2 GET /sessions 获取当前用户所有会话
  - [ ] 3.3.3 DELETE /session/{session_id} 删除会话
  - [ ] 3.3.4 流式接口验证 session 归属当前用户

## 4. 数据管理权限控制

- [ ] 4.1 datamanage/router.py 所有路由添加 `require_admin` 依赖
- [ ] 4.2 更新前端数据管理页面显示无权限提示（非管理员）
- [ ] 4.3 sync_task_manager 创建任务时记录 user_id

## 5. 任务历史用户追踪

- [ ] 5.1 更新 datamanage/schemas.py SyncHistory 添加 user_id, username
- [ ] 5.2 更新 datamanage/service.py SyncTaskManager
  - [ ] 5.2.1 create_task 接收并存储 user_id
  - [ ] 5.2.2 get_tasks_paginated 支持 user_id 筛选
- [ ] 5.3 任务历史API返回操作用户信息

## 6. Agent用户上下文

- [ ] 6.1 chat/router.py 流式接口 context 添加 user_id
- [ ] 6.2 orchestrator.py 将 user_id 传递给子Agent
- [ ] 6.3 enhanced_portfolio_agent.py 工具调用校验 user_id 必须存在且使用 context 中的值
- [ ] 6.4 portfolio_agent.py 同样确保 user_id 从 context 获取

## 7. 测试验证

- [ ] 7.1 测试对话历史创建、查询、删除
- [ ] 7.2 测试非管理员访问数据管理返回 403
- [ ] 7.3 测试任务历史记录包含用户信息
- [ ] 7.4 测试持仓分析只返回当前用户数据
