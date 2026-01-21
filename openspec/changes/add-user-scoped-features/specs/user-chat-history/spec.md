# User Chat History Specification

## ADDED Requirements

### Requirement: Chat Session User Binding
对话会话 MUST 与用户ID绑定，用户 SHALL 只能访问自己创建的会话。

#### Scenario: Create session for authenticated user
- **GIVEN** 用户已登录
- **WHEN** 用户创建新会话
- **THEN** 会话绑定当前用户ID
- **AND** 会话ID返回给用户

#### Scenario: List user sessions
- **GIVEN** 用户A有3个会话，用户B有2个会话
- **WHEN** 用户A请求会话列表
- **THEN** 系统只返回用户A的3个会话

#### Scenario: Access other user's session
- **GIVEN** 用户A创建的会话 session_001
- **WHEN** 用户B尝试访问 session_001 的历史
- **THEN** 系统返回 403 Forbidden

### Requirement: Chat Message Persistence
对话消息 MUST 持久化到数据库，SHALL 支持历史查询。

#### Scenario: Save message to database
- **GIVEN** 用户在会话中发送消息
- **WHEN** 消息发送成功
- **THEN** 消息持久化到 `chat_messages` 表
- **AND** 包含 session_id, user_id, role, content, metadata, created_at

#### Scenario: Query message history
- **GIVEN** 会话有10条历史消息
- **WHEN** 用户请求会话历史
- **THEN** 系统从数据库查询并返回所有消息
- **AND** 消息按时间顺序排列

#### Scenario: Session message count update
- **GIVEN** 会话当前有5条消息
- **WHEN** 用户发送新消息
- **THEN** `chat_sessions` 表的 `message_count` 增加1
- **AND** `last_message_at` 更新为当前时间

### Requirement: Session Management
用户 SHALL 能够管理自己的会话，MUST 支持查看列表和删除会话功能。

#### Scenario: Delete own session
- **GIVEN** 用户有会话 session_001
- **WHEN** 用户删除该会话
- **THEN** 会话从 `chat_sessions` 表删除
- **AND** 关联的消息从 `chat_messages` 表删除

#### Scenario: Delete other user's session
- **GIVEN** 用户A的会话 session_001
- **WHEN** 用户B尝试删除该会话
- **THEN** 系统返回 403 Forbidden

#### Scenario: List sessions with summary
- **WHEN** 用户请求会话列表
- **THEN** 返回每个会话的摘要信息
- **AND** 包含 session_id, title, created_at, last_message_at, message_count

### Requirement: Stream API Session Validation
流式对话API MUST 验证会话归属当前用户。

#### Scenario: Stream with valid session
- **GIVEN** 用户A的会话 session_001
- **WHEN** 用户A向 session_001 发送流式消息
- **THEN** 系统正常处理并流式返回响应

#### Scenario: Stream with invalid session
- **GIVEN** 用户A的会话 session_001
- **WHEN** 用户B尝试向 session_001 发送流式消息
- **THEN** 系统返回 403 Forbidden
- **AND** 不处理该请求
