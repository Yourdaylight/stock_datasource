# Tasks: Docker Compose Deployment with Redis Cache

## Phase 1: Docker Infrastructure (可独立交付)

- [ ] 1.1 创建 `docker/` 目录结构
- [ ] 1.2 编写 `docker/Dockerfile.backend`（Python + uv，含开发/生产两阶段）
- [ ] 1.3 编写 `docker/Dockerfile.frontend`（多阶段构建：开发 + 生产）
- [ ] 1.4 编写 `docker/nginx.conf`（前端反向代理 + API 转发）
- [ ] 1.5 编写 `docker/init-clickhouse.sql`（创建 stock_data 数据库）
- [ ] 1.6 编写 `docker-compose.infra.yml`（ClickHouse + Redis + Postgres 基础设施）
- [ ] 1.7 编写 `docker-compose.langfuse.yml`（Langfuse Worker + Web）
- [ ] 1.8 编写 `docker-compose.yml`（主编排：Backend + Frontend）
- [ ] 1.9 编写 `docker-compose.dev.yml`（开发模式：热重载覆盖）
- [ ] 1.10 创建 `.env.docker` 模板（统一环境变量）
- [ ] 1.11 更新 `.dockerignore`（排除不必要文件）
- [ ] 1.12 验证独立部署 `docker compose -f ... up` 能正常启动

## Phase 2: Redis Cache Layer (依赖 Phase 1)

- [ ] 2.1 添加 `redis` 依赖到 `pyproject.toml`
- [ ] 2.2 扩展 `settings.py` 添加 Redis 配置项（host/port/password/db）
- [ ] 2.3 创建 `src/stock_datasource/services/cache_service.py`
  - 命名空间前缀 `stock:`
  - 使用 Redis DB 1（与 Langfuse DB 0 隔离）
  - 优雅降级（Redis 不可用时直接查询）
- [ ] 2.4 实现缓存装饰器 `@cached(key, ttl)`
- [ ] 2.5 实现缓存失效机制 `delete_pattern()`
- [ ] 2.6 添加 Redis 连接状态到 `/health` 端点
- [ ] 2.7 添加缓存统计到 `/health` 响应（hits/misses/keys）
- [ ] 2.8 编写缓存服务单元测试

## Phase 3: API Cache Integration (依赖 Phase 2)

- [ ] 3.1 为 `/api/overview/hot-etfs` 添加缓存（TTL=60s）
- [ ] 3.2 为 `/api/overview/hot-stocks` 添加缓存（TTL=60s）
- [ ] 3.3 为 `/api/overview/market-stats` 添加缓存（TTL=60s）
- [ ] 3.4 为 `/api/stock/{code}/basic` 添加缓存（TTL=1h）
- [ ] 3.5 为 `/api/workflows` 列表添加缓存（TTL=5min）
- [ ] 3.6 实现工作流创建/删除时主动失效缓存
- [ ] 3.7 添加缓存命中日志（debug 级别）

## Phase 4: Scripts & Documentation

- [ ] 4.1 创建 `scripts/docker-start.sh`（支持 --full/--app/--dev/--infra 模式）
- [ ] 4.2 创建 `scripts/docker-stop.sh`
- [ ] 4.3 更新 `.env.example` 添加 Docker 相关配置说明
- [ ] 4.4 在 README 中添加 Docker 部署章节

## Dependencies

```
Phase 1 ───┬──▶ Phase 2 ──▶ Phase 3
           │
           └──▶ Phase 4
```

## Validation Criteria

- [ ] `./scripts/docker-start.sh --full` 完整部署在 3 分钟内所有服务 healthy
- [ ] `./scripts/docker-start.sh --app` 仅应用部署可连接外部基础设施
- [ ] 前端 http://localhost:3001 可访问
- [ ] 后端 http://localhost:8000/health 返回 200 且包含 redis/clickhouse 状态
- [ ] Langfuse http://localhost:3000 可访问
- [ ] Redis 使用 DB 1，与 Langfuse (DB 0) 数据隔离
- [ ] ClickHouse `stock_data` 数据库与 `default` 数据库隔离
- [ ] Redis 内存限制 1GB，暴露 6379 端口
- [ ] 缓存命中时 API 响应 <50ms
