# Capability: Redis Cache Layer

## ADDED Requirements

### Requirement: Cache Service
系统 MUST 提供统一的缓存服务层，支持与 Langfuse 共存。

#### Scenario: 命名空间隔离
**Given** 缓存服务已初始化  
**When** 调用 `cache.set("quote:600519", data)`  
**Then** 实际存储的 Key 为 `stock:quote:600519`  
**And** 存储在 Redis DB 1

#### Scenario: 缓存读写
**Given** 缓存服务已初始化  
**When** 调用 `cache.set("key", {"data": 123}, ttl=60)`  
**Then** 数据存储到 Redis DB 1  
**And** 60 秒后自动过期

#### Scenario: 缓存命中
**Given** 缓存中存在 key="quote:600519"  
**When** 调用 `cache.get("quote:600519")`  
**Then** 返回缓存的数据  
**And** 响应时间 <10ms

### Requirement: Cache Decorator
系统 MUST 提供装饰器简化函数结果缓存。

#### Scenario: 使用缓存装饰器
**Given** 函数使用 `@cached("quote:{ts_code}", ttl=60)`  
**When** 首次调用 `get_quote("600519.SH")`  
**Then** 执行原始函数并缓存结果  
**And** 后续调用直接返回缓存

#### Scenario: 缓存 Key 模板
**Given** 装饰器使用 `@cached("daily:{code}:{date}")`  
**When** 调用 `get_daily(code="600519", date="2025-01-19")`  
**Then** 缓存 Key 为 `stock:daily:600519:2025-01-19`

### Requirement: Cache Invalidation
系统 MUST 支持按模式批量失效缓存。

#### Scenario: 模式匹配删除
**Given** 缓存中有 keys: stock:quote:600519, stock:quote:000001, stock:daily:600519  
**When** 调用 `cache.delete_pattern("quote:*")`  
**Then** stock:quote:600519 和 stock:quote:000001 被删除  
**And** stock:daily:600519 保留

#### Scenario: 工作流更新触发失效
**Given** 用户创建新工作流  
**When** 工作流保存成功  
**Then** `stock:workflow:*` 相关缓存被主动失效

### Requirement: Graceful Degradation
Redis 不可用时系统 MUST 优雅降级。

#### Scenario: Redis 连接失败
**Given** Redis 服务不可用  
**When** 调用带缓存的 API  
**Then** 直接查询数据库返回结果  
**And** 记录警告日志  
**And** 不影响用户体验

#### Scenario: Redis 恢复
**Given** Redis 从故障中恢复  
**When** 下次 API 调用  
**Then** 自动重新使用缓存  
**And** 无需手动干预

### Requirement: High-Frequency API Caching
高频 API MUST 集成缓存提升性能。

#### Scenario: 市场概览缓存
**Given** `/api/overview/hot-etfs` 被频繁调用  
**When** 首次请求  
**Then** 查询数据库并缓存结果（TTL=60s）  
**And** 后续请求直接返回缓存  
**And** 缓存命中时响应 <50ms

#### Scenario: 股票基础信息缓存
**Given** `/api/stock/{code}/basic` 被调用  
**When** 数据已缓存  
**Then** 响应时间 <20ms（原 100-300ms）  
**And** TTL 为 1 小时

#### Scenario: 工作流列表缓存
**Given** `/api/workflows` 被调用  
**When** 工作流列表已缓存  
**Then** 返回缓存数据（TTL=5min）

### Requirement: Cache Monitoring
系统 MUST 提供缓存状态监控能力。

#### Scenario: 健康检查包含缓存状态
**Given** 系统运行一段时间  
**When** 调用 `/health` 端点  
**Then** 返回包含 Redis 连接状态  
**And** 返回缓存命中率统计（hits/misses/keys）

### Requirement: Memory Management
Redis MUST 配置合理的内存限制和淘汰策略。

#### Scenario: 内存限制
**Given** Redis 配置 maxmemory=1gb  
**When** 缓存数据接近 1GB  
**Then** 自动淘汰最近最少使用的 Key  
**And** 不会导致 OOM

#### Scenario: 持久化配置
**Given** Redis 开启 AOF 持久化  
**When** Redis 重启  
**Then** 之前的缓存数据恢复  
**And** 热点数据无需重新加载
