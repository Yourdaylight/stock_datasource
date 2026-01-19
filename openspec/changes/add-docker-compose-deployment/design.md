# Design: Docker Compose Deployment with Redis Cache

## Architecture Overview

### 部署模式

提供两种部署模式：

1. **独立模式** - 0 到 1 完整部署（包含所有基础设施）
2. **复用模式** - 复用已有 Langfuse 的 ClickHouse/Redis

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    Complete Deployment Architecture                      │
│                         (stock_network)                                  │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  ┌─────────────────────── 基础设施层 ───────────────────────┐           │
│  │                                                          │           │
│  │  ┌────────────┐   ┌────────────┐   ┌────────────┐       │           │
│  │  │ ClickHouse │   │   Redis    │   │  Postgres  │       │           │
│  │  │   :9000    │   │   :6379    │   │   :5432    │       │           │
│  │  │   :8123    │   │  (1GB)     │   │ (Langfuse) │       │           │
│  │  └─────┬──────┘   └─────┬──────┘   └─────┬──────┘       │           │
│  │        │                │                │               │           │
│  └────────┼────────────────┼────────────────┼───────────────┘           │
│           │                │                │                            │
│  ┌────────┼────────────────┼────────────────┼───────────────┐           │
│  │        ▼                ▼                ▼    应用层      │           │
│  │  ┌────────────┐   ┌────────────┐   ┌────────────┐       │           │
│  │  │  Backend   │   │  Frontend  │   │  Langfuse  │       │           │
│  │  │  (FastAPI) │   │  (Vue/Vite)│   │    Web     │       │           │
│  │  │   :8000    │   │   :3001    │   │   :3000    │       │           │
│  │  └────────────┘   └────────────┘   └────────────┘       │           │
│  │                                                          │           │
│  └──────────────────────────────────────────────────────────┘           │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘

External Ports:
- 3000: Langfuse Web UI
- 3001: Stock Platform Frontend
- 8000: Stock Platform Backend API
- 6379: Redis (可选暴露)
- 8123: ClickHouse HTTP (可选暴露)
- 9000: ClickHouse Native (可选暴露)
```

---

## Service Components

### 共享基础设施（与 Langfuse 复用）

#### ClickHouse Service
```yaml
clickhouse:
  image: clickhouse/clickhouse-server:24
  restart: always
  user: "101:101"
  environment:
    CLICKHOUSE_DB: default
    CLICKHOUSE_USER: clickhouse
    CLICKHOUSE_PASSWORD: ${CLICKHOUSE_PASSWORD:-clickhouse}
  volumes:
    - clickhouse_data:/var/lib/clickhouse
    - clickhouse_logs:/var/log/clickhouse-server
  ports:
    - "${CLICKHOUSE_HTTP_PORT:-8123}:8123"   # HTTP interface
    - "${CLICKHOUSE_NATIVE_PORT:-9000}:9000" # Native protocol
  healthcheck:
    test: wget --no-verbose --tries=1 --spider http://localhost:8123/ping || exit 1
    interval: 5s
    timeout: 5s
    retries: 10
```

**数据库隔离策略**：
- Langfuse 使用 `default` 数据库
- Stock Platform 使用 `stock_data` 数据库
- 通过不同数据库实现数据隔离

#### Redis Service
```yaml
redis:
  image: redis:7-alpine
  restart: always
  command: >
    --requirepass ${REDIS_PASSWORD:-stockredis123}
    --maxmemory 1gb
    --maxmemory-policy allkeys-lru
    --appendonly yes
  ports:
    - "${REDIS_PORT:-6379}:6379"  # 暴露端口供调试
  volumes:
    - redis_data:/data
  healthcheck:
    test: ["CMD", "redis-cli", "-a", "${REDIS_PASSWORD:-stockredis123}", "ping"]
    interval: 3s
    timeout: 10s
    retries: 10
```

**配置说明**：
- 内存限制：1GB
- 淘汰策略：LRU（最近最少使用）
- 持久化：AOF 模式
- 端口：对外暴露 6379

### 应用服务

#### Backend Service
```yaml
backend:
  build:
    context: .
    dockerfile: docker/Dockerfile.backend
  restart: always
  ports:
    - "${BACKEND_PORT:-8000}:8000"
  environment:
    # ClickHouse
    CLICKHOUSE_HOST: clickhouse
    CLICKHOUSE_PORT: 9000
    CLICKHOUSE_HTTP_PORT: 8123
    CLICKHOUSE_USER: ${CLICKHOUSE_USER:-clickhouse}
    CLICKHOUSE_PASSWORD: ${CLICKHOUSE_PASSWORD:-clickhouse}
    CLICKHOUSE_DATABASE: stock_data
    # Redis
    REDIS_HOST: redis
    REDIS_PORT: 6379
    REDIS_PASSWORD: ${REDIS_PASSWORD:-stockredis123}
    # Langfuse
    LANGFUSE_HOST: ${LANGFUSE_HOST:-http://langfuse-web:3000}
    LANGFUSE_PUBLIC_KEY: ${LANGFUSE_PUBLIC_KEY:-}
    LANGFUSE_SECRET_KEY: ${LANGFUSE_SECRET_KEY:-}
  depends_on:
    clickhouse:
      condition: service_healthy
    redis:
      condition: service_healthy
  healthcheck:
    test: curl -f http://localhost:8000/health || exit 1
    interval: 30s
    timeout: 10s
    retries: 3
```

#### Frontend Service
```yaml
frontend:
  build:
    context: ./frontend
    dockerfile: ../docker/Dockerfile.frontend
    target: ${FRONTEND_TARGET:-production}
  restart: always
  ports:
    - "${FRONTEND_PORT:-3001}:3000"
  environment:
    VITE_API_BASE_URL: http://backend:8000
  depends_on:
    backend:
      condition: service_healthy
```

#### Langfuse Services（完整部署时）
```yaml
langfuse-worker:
  image: langfuse/langfuse-worker:3
  restart: always
  depends_on:
    postgres:
      condition: service_healthy
    redis:
      condition: service_healthy
    clickhouse:
      condition: service_healthy
  environment:
    DATABASE_URL: postgresql://postgres:${POSTGRES_PASSWORD:-postgres}@postgres:5432/postgres
    CLICKHOUSE_URL: http://clickhouse:8123
    CLICKHOUSE_MIGRATION_URL: clickhouse://clickhouse:9000
    CLICKHOUSE_USER: ${CLICKHOUSE_USER:-clickhouse}
    CLICKHOUSE_PASSWORD: ${CLICKHOUSE_PASSWORD:-clickhouse}
    REDIS_HOST: redis
    REDIS_PORT: 6379
    REDIS_AUTH: ${REDIS_PASSWORD:-stockredis123}
    # ... 其他 Langfuse 配置

langfuse-web:
  image: langfuse/langfuse:3
  restart: always
  ports:
    - "${LANGFUSE_PORT:-3000}:3000"
  depends_on:
    - langfuse-worker
  environment:
    NEXTAUTH_URL: ${LANGFUSE_URL:-http://localhost:3000}
    # ... 继承 worker 环境变量
```

---

## Compose File Structure

```
stock_datasource/
├── docker-compose.yml          # 主编排（Backend + Frontend）
├── docker-compose.infra.yml    # 基础设施（ClickHouse + Redis + Postgres）
├── docker-compose.langfuse.yml # Langfuse 服务
├── docker-compose.dev.yml      # 开发模式覆盖
├── docker-compose.override.yml # 本地个性化配置（git ignored）
└── docker/
    ├── Dockerfile.backend
    ├── Dockerfile.frontend
    └── nginx.conf
```

### 使用方式

```bash
# 1. 完整部署（0 到 1，包含 Langfuse）
docker compose -f docker-compose.yml \
               -f docker-compose.infra.yml \
               -f docker-compose.langfuse.yml \
               up -d

# 2. 复用已有 Langfuse 基础设施
# 只启动 Backend + Frontend，连接外部服务
docker compose up -d

# 3. 开发模式（热重载）
docker compose -f docker-compose.yml \
               -f docker-compose.infra.yml \
               -f docker-compose.dev.yml \
               up

# 4. 快捷脚本
./scripts/docker-start.sh         # 完整启动
./scripts/docker-start.sh --dev   # 开发模式
./scripts/docker-start.sh --app   # 仅应用（复用基础设施）
```

---

## Redis Cache Strategy

### Cache Key Design (更新)

| 数据类型 | Key Pattern | TTL | 示例 | Redis DB |
|---------|-------------|-----|------|----------|
| 实时行情 | `stock:quote:{ts_code}` | 60s | `stock:quote:600519.SH` | 1 |
| 日K数据 | `stock:daily:{ts_code}:{date}` | 24h | `stock:daily:600519.SH:20250119` | 1 |
| 股票基础信息 | `stock:basic:{ts_code}` | 1h | `stock:basic:600519.SH` | 1 |
| 市场概览 | `stock:overview:{type}:{date}` | 5min | `stock:overview:hot_etf:20250119` | 1 |
| 工作流 | `stock:workflow:{id}` | 5min | `stock:workflow:template_single_stock` | 1 |
| 用户会话 | `stock:session:{user_id}` | 30min | `stock:session:u123` | 1 |

**注意**：
- 使用 `stock:` 前缀与 Langfuse 数据隔离
- 使用 Redis DB 1（Langfuse 默认使用 DB 0）

### Cache Service Implementation

```python
# src/stock_datasource/services/cache_service.py

import json
import logging
from typing import Any, Optional, Callable
from functools import wraps
from redis import Redis, ConnectionError
from stock_datasource.config.settings import settings

logger = logging.getLogger(__name__)

class CacheService:
    """Redis cache service with Langfuse coexistence support."""
    
    PREFIX = "stock:"  # 命名空间前缀
    
    def __init__(self):
        self._redis: Optional[Redis] = None
        self._available = True
    
    @property
    def redis(self) -> Optional[Redis]:
        if self._redis is None:
            try:
                self._redis = Redis(
                    host=settings.REDIS_HOST,
                    port=settings.REDIS_PORT,
                    password=settings.REDIS_PASSWORD,
                    db=1,  # 使用 DB 1，与 Langfuse (DB 0) 隔离
                    decode_responses=True,
                    socket_connect_timeout=5,
                )
                self._redis.ping()
                logger.info("Redis connected successfully")
            except Exception as e:
                logger.warning(f"Redis connection failed: {e}")
                self._available = False
        return self._redis
    
    def _key(self, key: str) -> str:
        """Add namespace prefix."""
        return f"{self.PREFIX}{key}"
    
    async def get(self, key: str) -> Optional[Any]:
        """Get cached value with graceful degradation."""
        if not self._available:
            return None
        try:
            data = self.redis.get(self._key(key))
            return json.loads(data) if data else None
        except (ConnectionError, Exception) as e:
            logger.warning(f"Cache get failed: {e}")
            return None
    
    async def set(self, key: str, value: Any, ttl: int = 300) -> bool:
        """Set cache with TTL."""
        if not self._available:
            return False
        try:
            return self.redis.setex(
                self._key(key),
                ttl,
                json.dumps(value, ensure_ascii=False, default=str)
            )
        except (ConnectionError, Exception) as e:
            logger.warning(f"Cache set failed: {e}")
            return False
    
    async def delete(self, key: str) -> bool:
        """Delete single key."""
        if not self._available:
            return False
        try:
            return bool(self.redis.delete(self._key(key)))
        except Exception:
            return False
    
    async def delete_pattern(self, pattern: str) -> int:
        """Delete keys matching pattern."""
        if not self._available:
            return 0
        try:
            keys = self.redis.keys(self._key(pattern))
            if keys:
                return self.redis.delete(*keys)
            return 0
        except Exception as e:
            logger.warning(f"Cache delete pattern failed: {e}")
            return 0
    
    def cached(self, key_template: str, ttl: int = 300):
        """Decorator for caching function results."""
        def decorator(func: Callable):
            @wraps(func)
            async def wrapper(*args, **kwargs):
                # Build cache key
                key = key_template.format(**kwargs) if kwargs else key_template
                
                # Try cache first
                cached = await self.get(key)
                if cached is not None:
                    return cached
                
                # Execute function
                result = await func(*args, **kwargs)
                
                # Cache result
                if result is not None:
                    await self.set(key, result, ttl)
                
                return result
            return wrapper
        return decorator
    
    def get_stats(self) -> dict:
        """Get cache statistics."""
        if not self._available:
            return {"available": False}
        try:
            info = self.redis.info("stats")
            return {
                "available": True,
                "hits": info.get("keyspace_hits", 0),
                "misses": info.get("keyspace_misses", 0),
                "keys": self.redis.dbsize(),
            }
        except Exception:
            return {"available": False}


# Singleton instance
_cache_service: Optional[CacheService] = None

def get_cache_service() -> CacheService:
    global _cache_service
    if _cache_service is None:
        _cache_service = CacheService()
    return _cache_service
```

---

## Docker Files

### Backend Dockerfile

```dockerfile
# docker/Dockerfile.backend
FROM python:3.11-slim AS base

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libffi-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install uv
RUN pip install uv

# Copy dependency files
COPY pyproject.toml uv.lock ./

# Install dependencies
RUN uv sync --frozen --no-dev

# Copy source code
COPY src/ ./src/
COPY .env.example ./.env

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --retries=3 --start-period=60s \
    CMD curl -f http://localhost:8000/health || exit 1

# Start server
CMD ["uv", "run", "python", "-m", "stock_datasource.services.http_server"]

# Development stage
FROM base AS development
RUN uv sync --frozen
CMD ["uv", "run", "uvicorn", "stock_datasource.services.http_server:app", "--reload", "--host", "0.0.0.0", "--port", "8000"]
```

### Frontend Dockerfile

```dockerfile
# docker/Dockerfile.frontend

# Development stage
FROM node:20-alpine AS development
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
EXPOSE 3000
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0", "--port", "3000"]

# Build stage
FROM node:20-alpine AS builder
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
RUN npm run build

# Production stage
FROM nginx:alpine AS production
COPY --from=builder /app/dist /usr/share/nginx/html
COPY ../docker/nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 3000
CMD ["nginx", "-g", "daemon off;"]
```

### Nginx Config

```nginx
# docker/nginx.conf
server {
    listen 3000;
    server_name localhost;
    root /usr/share/nginx/html;
    index index.html;

    # Gzip compression
    gzip on;
    gzip_types text/plain text/css application/json application/javascript text/xml;

    # SPA fallback
    location / {
        try_files $uri $uri/ /index.html;
    }

    # API proxy
    location /api {
        proxy_pass http://backend:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_cache_bypass $http_upgrade;
    }

    # Health check
    location /health {
        return 200 'OK';
        add_header Content-Type text/plain;
    }
}
```

---

## Environment Configuration

### .env.docker (模板)

```bash
# ============================================
# Infrastructure Configuration
# ============================================
# ClickHouse
CLICKHOUSE_HOST=clickhouse
CLICKHOUSE_PORT=9000
CLICKHOUSE_HTTP_PORT=8123
CLICKHOUSE_USER=clickhouse
CLICKHOUSE_PASSWORD=clickhouse
CLICKHOUSE_DATABASE=stock_data

# Redis (1GB, 暴露端口)
REDIS_HOST=redis
REDIS_PORT=6379
REDIS_PASSWORD=stockredis123
REDIS_DB=1

# Postgres (for Langfuse)
POSTGRES_PASSWORD=postgres

# ============================================
# Application Ports
# ============================================
BACKEND_PORT=8000
FRONTEND_PORT=3001
LANGFUSE_PORT=3000

# ============================================
# Langfuse Configuration
# ============================================
LANGFUSE_URL=http://localhost:3000
LANGFUSE_PUBLIC_KEY=your_public_key
LANGFUSE_SECRET_KEY=your_secret_key

# ============================================
# API Keys (required)
# ============================================
TUSHARE_TOKEN=your_tushare_token
OPENAI_API_KEY=your_openai_key
OPENAI_BASE_URL=https://api.openai.com/v1
OPENAI_MODEL=gpt-4

# ============================================
# Cache TTL Settings (seconds)
# ============================================
CACHE_TTL_QUOTE=60
CACHE_TTL_DAILY=86400
CACHE_TTL_BASIC=3600
CACHE_TTL_OVERVIEW=300
```

---

## Startup Scripts

### docker-start.sh

```bash
#!/bin/bash
# scripts/docker-start.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_DIR"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

usage() {
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "Options:"
    echo "  --full      Complete deployment (infra + langfuse + app)"
    echo "  --app       Application only (connect to existing infra)"
    echo "  --dev       Development mode with hot reload"
    echo "  --infra     Infrastructure only (clickhouse + redis + postgres)"
    echo "  --down      Stop all services"
    echo "  --logs      Show logs"
    echo ""
}

case "${1:-full}" in
    --full|full)
        echo -e "${GREEN}Starting complete deployment...${NC}"
        docker compose -f docker-compose.yml \
                       -f docker-compose.infra.yml \
                       -f docker-compose.langfuse.yml \
                       up -d --build
        ;;
    --app|app)
        echo -e "${GREEN}Starting application services only...${NC}"
        docker compose up -d --build
        ;;
    --dev|dev)
        echo -e "${YELLOW}Starting development mode...${NC}"
        docker compose -f docker-compose.yml \
                       -f docker-compose.infra.yml \
                       -f docker-compose.dev.yml \
                       up --build
        ;;
    --infra|infra)
        echo -e "${GREEN}Starting infrastructure only...${NC}"
        docker compose -f docker-compose.infra.yml up -d
        ;;
    --down|down)
        echo -e "${YELLOW}Stopping all services...${NC}"
        docker compose -f docker-compose.yml \
                       -f docker-compose.infra.yml \
                       -f docker-compose.langfuse.yml \
                       down
        ;;
    --logs|logs)
        docker compose logs -f
        ;;
    *)
        usage
        ;;
esac
```

---

## Data Isolation Strategy

### ClickHouse 数据库隔离

| 服务 | 数据库 | 表前缀 |
|------|--------|--------|
| Langfuse | `default` | `langfuse_*` |
| Stock Platform | `stock_data` | 无 |

初始化脚本自动创建 `stock_data` 数据库：

```sql
-- docker/init-clickhouse.sql
CREATE DATABASE IF NOT EXISTS stock_data;
```

### Redis 数据库隔离

| 服务 | DB | Key 前缀 |
|------|-----|---------|
| Langfuse | 0 | 无 |
| Stock Platform | 1 | `stock:` |

---

## Health Checks

```yaml
# 健康检查端点更新
backend /health 响应：
{
  "status": "healthy",
  "services": {
    "clickhouse": "connected",
    "redis": "connected",
    "langfuse": "connected"  # 可选
  },
  "cache": {
    "available": true,
    "hits": 1234,
    "misses": 56,
    "keys": 89
  }
}
```

---

## Migration Path

### Phase 1: Docker 化
1. 创建 Docker 文件
2. 创建 Compose 编排
3. 验证独立部署

### Phase 2: Redis 集成
1. 添加 Redis 依赖
2. 实现缓存服务
3. 配置数据库隔离

### Phase 3: 缓存集成
1. 高频 API 添加缓存
2. 添加缓存监控
3. 优化 TTL 配置

### Phase 4: Langfuse 集成
1. 共享基础设施配置
2. 网络互通验证
3. 监控整合

---

## Risks & Mitigations

| 风险 | 影响 | 缓解措施 |
|------|------|----------|
| ClickHouse 数据冲突 | Langfuse 数据污染 | 使用独立数据库 `stock_data` |
| Redis 内存溢出 | 服务异常 | 设置 1GB 上限 + LRU 淘汰 |
| Redis 密码不一致 | 连接失败 | 统一使用环境变量 |
| 端口冲突 | 服务启动失败 | 可配置端口映射 |
| 初次构建慢 | 开发体验差 | 多阶段构建 + 层缓存 |
