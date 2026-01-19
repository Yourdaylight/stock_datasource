# Proposal: Add Docker Compose Deployment with Redis Cache

## Summary
为项目添加 Docker Compose 一键部署能力，并引入 Redis 缓存层提升性能。支持与 Langfuse 共享基础设施。

## Motivation
1. **部署复杂度高**：当前需要手动安装 ClickHouse、Node.js、Python 环境，配置繁琐
2. **性能瓶颈**：频繁的数据库查询导致响应慢，缺乏缓存层
3. **环境一致性**：开发、测试、生产环境配置不一致导致问题难以复现
4. **资源复用**：已有 Langfuse 部署的 ClickHouse/Redis，应复用以减少资源占用

## Goals
- 一条命令启动整个系统（前端 + 后端 + ClickHouse + Redis + Langfuse）
- 支持复用已有 Langfuse 基础设施，实现数据隔离
- 引入 Redis 缓存热点数据，提升 API 响应速度
- 支持开发模式（热重载）和生产模式（构建优化）

## Non-Goals
- 不涉及 Kubernetes 编排
- 不涉及 CI/CD 流程
- 不涉及多机分布式部署

## Key Changes

### 1. Docker 化
- 后端 Dockerfile（Python + uv，开发/生产两阶段）
- 前端 Dockerfile（Node.js + Vite 构建）
- 多个 Compose 文件支持灵活组合

### 2. Redis 缓存集成（1GB 内存，暴露 6379 端口）
- 通用缓存服务层，使用 DB 1 与 Langfuse (DB 0) 隔离
- 缓存策略：行情数据 TTL=60s、基础信息 TTL=1h、工作流 TTL=5min
- 命名空间前缀 `stock:` 防止 Key 冲突

### 3. Langfuse 集成
- 复用 ClickHouse（stock_data 数据库隔离）
- 复用 Redis（DB 隔离）
- 可选完整部署或仅应用部署

### 4. 启动脚本
- `./scripts/docker-start.sh --full` 完整部署
- `./scripts/docker-start.sh --app` 仅应用
- `./scripts/docker-start.sh --dev` 开发模式

## Impact
- **开发体验**：一键启动，环境隔离
- **性能提升**：热点数据响应 <50ms（原 100-500ms）
- **运维简化**：标准化部署流程
- **资源优化**：复用 Langfuse 基础设施，减少 ~2GB 内存占用

## Port Mapping

| 服务 | 端口 | 说明 |
|------|------|------|
| Frontend | 3001 | Vue 应用 |
| Backend | 8000 | FastAPI |
| Langfuse | 3000 | AI 可观测性 |
| Redis | 6379 | 缓存（暴露） |
| ClickHouse HTTP | 8123 | 数据库 HTTP |
| ClickHouse Native | 9000 | 数据库 Native |
