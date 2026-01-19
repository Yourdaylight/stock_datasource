# Capability: Docker Deployment

## ADDED Requirements

### Requirement: One-Command Startup
系统 MUST 支持通过单条命令启动所有服务（前端、后端、数据库、缓存、Langfuse）。

#### Scenario: 完整部署（0 到 1）
**Given** 用户已安装 Docker 和 Docker Compose  
**When** 用户执行 `./scripts/docker-start.sh --full`  
**Then** 所有服务在 180 秒内变为 healthy 状态  
**And** 前端可通过 http://localhost:3001 访问  
**And** 后端 API 可通过 http://localhost:8000 访问  
**And** Langfuse 可通过 http://localhost:3000 访问

#### Scenario: 仅应用部署（复用基础设施）
**Given** ClickHouse/Redis/Postgres 已在外部运行  
**When** 用户执行 `./scripts/docker-start.sh --app`  
**Then** 仅 Backend + Frontend 服务启动  
**And** 服务连接到外部基础设施

#### Scenario: 服务重启
**Given** 系统已在运行  
**When** 用户执行 `docker compose restart`  
**Then** 所有服务在 60 秒内恢复 healthy  
**And** 数据不丢失

### Requirement: Development Mode
开发模式 MUST 支持代码热重载，无需重新构建镜像。

#### Scenario: 后端代码热重载
**Given** 系统以开发模式运行 `./scripts/docker-start.sh --dev`  
**When** 开发者修改 `src/` 目录下的 Python 文件  
**Then** 后端服务在 5 秒内自动重载  
**And** 无需手动重启容器

#### Scenario: 前端代码热重载
**Given** 系统以开发模式运行  
**When** 开发者修改 `frontend/src/` 目录下的 Vue 文件  
**Then** 前端在浏览器中自动更新（HMR）  
**And** 保持当前页面状态

### Requirement: Data Persistence
服务重启后数据 MUST 保持持久化。

#### Scenario: ClickHouse 数据持久化
**Given** 系统已有股票数据存储在 `stock_data` 数据库  
**When** 执行 `docker compose down && docker compose up -d`  
**Then** `stock_data` 数据库中所有数据仍然存在  
**And** 查询返回相同结果

#### Scenario: Redis 数据持久化
**Given** Redis DB 1 中有股票缓存数据  
**When** 执行 `docker compose restart redis`  
**Then** AOF 持久化的数据在重启后恢复

### Requirement: Service Isolation
系统 MUST 支持与 Langfuse 共享基础设施且数据隔离。

#### Scenario: ClickHouse 数据库隔离
**Given** ClickHouse 同时服务 Langfuse 和 Stock Platform  
**When** Stock Platform 写入数据  
**Then** 数据写入 `stock_data` 数据库  
**And** Langfuse 的 `default` 数据库不受影响

#### Scenario: Redis 数据库隔离
**Given** Redis 同时服务 Langfuse 和 Stock Platform  
**When** Stock Platform 写入缓存  
**Then** 缓存写入 DB 1 且 Key 以 `stock:` 为前缀  
**And** Langfuse 的 DB 0 数据不受影响

### Requirement: Health Checks
所有服务 MUST 提供健康检查端点。

#### Scenario: 完整健康状态检查
**Given** 所有服务正常运行  
**When** 调用 `GET /health`  
**Then** 返回包含 ClickHouse、Redis 连接状态  
**And** 包含缓存命中统计信息

#### Scenario: 依赖服务故障
**Given** Redis 服务不可用  
**When** 后端健康检查被调用  
**Then** 返回 degraded 状态  
**And** 服务仍可正常运行（降级模式）

### Requirement: Port Exposure
系统 MUST 暴露指定端口供外部访问和调试。

#### Scenario: Redis 端口暴露
**Given** Docker 服务运行  
**When** 从宿主机连接 localhost:6379  
**Then** 可以成功连接 Redis  
**And** 使用配置的密码认证

#### Scenario: ClickHouse 端口暴露
**Given** Docker 服务运行  
**When** 从宿主机连接 localhost:9000 或 localhost:8123  
**Then** 可以成功连接 ClickHouse
