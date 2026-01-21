# User Data Isolation Specification

## ADDED Requirements

### Requirement: Admin User Role
系统 MUST 支持管理员角色，SHALL 区分普通用户和管理员。

#### Scenario: Admin user in database
- **GIVEN** 用户表 `users`
- **THEN** 表包含 `is_admin` 字段 (UInt8, 默认0)
- **AND** is_admin=1 表示管理员，is_admin=0 表示普通用户

#### Scenario: Auto-grant admin for configured emails
- **GIVEN** 配置文件指定管理员邮箱列表 `admin@company.com`
- **WHEN** 用户使用 `admin@company.com` 注册或登录
- **THEN** 该用户的 `is_admin` 自动设置为 1

#### Scenario: Get user info includes admin status
- **GIVEN** 管理员用户已登录
- **WHEN** 用户请求 `/api/auth/me`
- **THEN** 返回的用户信息包含 `is_admin: true`

### Requirement: Data Management Access Control
数据管理功能 MUST 仅限管理员用户访问。

#### Scenario: Admin access data management
- **GIVEN** 管理员用户已登录
- **WHEN** 管理员访问 `/api/datamanage/*` 接口
- **THEN** 系统正常处理请求并返回数据

#### Scenario: Non-admin access data management
- **GIVEN** 普通用户已登录
- **WHEN** 用户访问 `/api/datamanage/plugins` 接口
- **THEN** 系统返回 403 Forbidden
- **AND** 返回错误信息 "仅管理员可访问数据管理功能"

#### Scenario: Unauthenticated access data management
- **WHEN** 未登录用户访问 `/api/datamanage/*` 接口
- **THEN** 系统返回 401 Unauthorized

### Requirement: Sync Task User Tracking
同步任务 MUST 记录触发用户，SHALL 支持审计追踪。

#### Scenario: Record user on task creation
- **GIVEN** 管理员 user_001 已登录
- **WHEN** 管理员触发同步任务
- **THEN** 任务记录包含 `user_id: user_001`

#### Scenario: Query task history by user
- **GIVEN** 用户A触发了3个任务，用户B触发了2个任务
- **WHEN** 管理员查询任务历史，筛选 user_id=A
- **THEN** 系统只返回用户A的3个任务

#### Scenario: Task history shows operator
- **WHEN** 管理员查看任务历史列表
- **THEN** 每条记录显示操作用户名称

### Requirement: Portfolio Analysis User Isolation
持仓AI分析 MUST 确保用户数据隔离。

#### Scenario: Agent context includes user_id
- **GIVEN** 用户A已登录并发起持仓分析
- **WHEN** AI Agent执行分析
- **THEN** Agent上下文必须包含 `user_id: A`
- **AND** Agent只访问用户A的持仓数据

#### Scenario: Portfolio tool validates user_id
- **GIVEN** Agent工具需要查询持仓数据
- **WHEN** 工具被调用
- **THEN** 工具必须从上下文获取 user_id
- **AND** 不使用默认值 "default_user"

#### Scenario: Analysis result for current user only
- **GIVEN** 用户A有持仓股票 [600519.SH, 000858.SZ]
- **GIVEN** 用户B有持仓股票 [601318.SH]
- **WHEN** 用户A请求持仓分析
- **THEN** 分析结果只包含 600519.SH 和 000858.SZ
- **AND** 不包含用户B的持仓
