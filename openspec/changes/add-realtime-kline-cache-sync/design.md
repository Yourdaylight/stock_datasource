# Design: 实时日线解耦流式架构（1.5 秒采集 / 秒级推送 / 分钟入库）

## Context
本次重设目标是把实时日线链路做成高稳定、低耦合的数据平面：
- 数据源：Tushare 实时日线接口（A股/ETF/指数/港股）
- 本地：1.5 秒采集并写入 Redis
- 云端：秒级增量推送（隐藏功能，开关控制）
- 存储：Redis 每分钟同步到 ClickHouse

你明确要求该能力不要与其他模块耦合，因此设计上采取独立运行时和独立故障域。

## Goals / Non-Goals
### Goals
- 实时日线全链路与 `realtime_minute`、通用调度流解耦。
- 在不影响稳定性的前提下支持秒级云端数据分发。
- 每分钟稳定落库到 ClickHouse，并保证幂等。
- 推送能力默认隐藏（默认关闭）。

### Non-Goals
- 不在本次定义中实现前端展示策略。
- 不覆盖历史批量回填。
- 不引入新行情供应商。

## Architecture (Logical)
```text
Tushare APIs (rt_k/rt_etf_k/rt_idx_k/rt_hk_k)
        │  every 1.5s
        ▼
[Collector Worker - 独立进程/线程组]
        │
        ├─ SET latest snapshot (Redis String)
        └─ XADD stream event   (Redis Stream)
                │
                ├─ [Cloud Push Worker, every 2s, 可关闭]
                │       ├─ XREAD recent events
                │       ├─ 计算 delta(仅变化字段)
                │       └─ 推送到云端接收服务
                │
                └─ [Minute Sink Worker, every 60s]
                        ├─ 聚合最近 1min 事件
                        ├─ 批量写 ClickHouse
                        └─ ACK/清理已消费窗口
```

## Decoupling Strategy
1. 独立模块边界：`realtime_kline` 不复用 `realtime_minute` 的采集/同步服务对象。
2. 独立配置空间：所有参数前缀统一使用 `RT_KLINE_*`。
3. 独立任务生命周期：采集、推送、落库 worker 单独启动/停止。
4. 故障隔离：推送失败不影响采集与落库；落库失败不阻塞采集。

## Data Contracts
### Canonical Snapshot
- 主键维度：`ts_code + market + trade_date`
- 核心字段：`open/high/low/close/vol/amount/pre_close/trade_time`
- 扩展字段：港股/ETF盘口相关字段（若接口返回）
- 元字段：`collected_at`, `version`, `source_api`

### Redis Layout
- latest: `stock:rtk:latest:{market}:{ts_code}`
- stream: `stock:rtk:stream:{market}`（Redis Stream）
- switch: `stock:rtk:switch:cloud_push`（运行时开关，可选）
- sync checkpoint: `stock:rtk:ckpt:clickhouse:{market}`

## Timing Model
- 采集：每 1.5 秒
- 推送：每 2 秒消费最近窗口事件并发云
- 落库：每 60 秒批量写入 ClickHouse

### 限流与降频规则
当 API 限流/超时时，采集周期自动退避至 3 秒或 5 秒，恢复后回到 1.5 秒。

**降频触发条件**：
- 3 次连续异常（超时、限流、服务异常）→ 退避到 3 秒
- 再 3 次连续异常 → 退避到 5 秒
- 计数独立按市场维度（4 个接口独立计数，互不影响）

**降频恢复条件**：
- 5 次连续成功 → 回到当前周期的上一级
- 例如 5秒→3秒→1.5秒（逐级回升）

### Redis 数据保留策略

**`latest` key 生命周期**：
- 盘中持续覆盖（最新快照）
- 交易日结束后 24 小时清理
- 意义：支持本地行情查询的低延迟访问

**`stream` key 生命周期**：
- 从事件写入开始保留 72 小时（兼容长期故障重放）
- 超期自动清理（可配置 `RT_KLINE_STREAM_TTL_HOURS`）
- 意义：推送失败、落库故障可在 72h 内重新消费

**checkpoint 生命周期**：
- 按市场维护，指向最后成功的 stream ID
- 推送 checkpoint：云端 ACK 成功后更新
- 落库 checkpoint：全市场批次成功后更新
- 无过期时间，依赖业务日志归档

## Hidden Push Switch Design
### Switch Layers
1. 编译/部署默认值：`RT_KLINE_CLOUD_PUSH_ENABLED=false`
2. 运行时动态开关：Redis/配置中心（可选实现）
3. 安全白名单：仅在指定环境允许开启（如 `prod-canary`）

### Switch Behavior
- OFF：不创建推送 worker，不出网。
- ON：启动推送 worker，开始读取 stream 并发送 delta。
- ON→OFF：立即停止推送 worker，保留本地缓存与落库。

## Cloud Push Semantics
- 推送内容：仅变化字段（例如 `code`, `price`, `vol`, `amount`, `trade_time`）
- 去重依据：`(ts_code, market, version)`
- 语义：至少一次（at-least-once）+ 接收端幂等
- 失败重试：指数退避 + 本地短暂缓冲

### Sliding Window Model (按架构图补充)
- 推送 worker 每 2 秒触发一次，但**读取最近 10 秒滑动窗口**：`[now-10s, now)`。
- 10 秒窗口用于“变化判定输入集”，不是 10 秒全量快照回放。
- 同一 symbol 在窗口内多次变化时，仅取该窗口末状态与上次已确认状态比较后生成 delta。
- 窗口右移规则：每 2 秒右移一次（重叠窗口），保证短抖动不丢变更。
- 本地维护 `last_acked_state`，仅对“相对已确认状态有变化”的字段发云端。

示例：
1. `t=00s` 窗口 `[ -10s, 00s )`，symbol A 无变化，不发送。
2. `t=02s` 窗口 `[ -8s, 02s )`，A 的 `close/vol` 变化，发送 delta。
3. `t=04s` 窗口 `[ -6s, 04s )`，A 仅 `vol` 再变，发送仅含 `vol` 的 delta。

### Last Acked State 维护
- 存储位置：Redis Hash `stock:rtk:last_acked_state:{market}`
- 结构：`{symbol} -> json(open/high/low/close/vol/amount/...)`
- 更新时机：云端返回 ACK success 且 `code=0` 时，更新该 symbol 的全部 delta 字段
- 失败回退：若 ACK 返回 retryable/failed，不更新 `last_acked_state`，下轮继续发送相同 delta
- TTL：无过期时间，直到下个交易日清理对应市场的全部 state

### Push Payload Contract (v1)
```json
{
  "schema_version": "v1",
  "event_id": "1740813600123-0",
  "event_time": "2026-03-01T09:30:01.500Z",
  "market": "cn",
  "source_api": "rt_k",
  "symbol": "600000.SH",
  "version": 1740813601500,
  "delta": {
    "close": 10.52,
    "vol": 125600,
    "amount": 1320456.12,
    "trade_time": "2026-03-01 09:30:01"
  },
  "full_ref": {
    "redis_latest_key": "stock:rtk:latest:cn:600000.SH"
  }
}
```

### Cloud ACK Contract
```json
{
  "ack_event_id": "1740813600123-0",
  "status": "ok",
  "server_time": "2026-03-01T09:30:01.900Z",
  "code": 0,
  "message": "accepted"
}
```

ACK 语义：
- `status=ok` 且 `code=0`：视为已确认，可推进本地推送 checkpoint。
- `status=retryable`（如 429/503）：进入退避重试队列。
- `status=failed`（如 400/401）：进入死信队列并触发告警，不阻塞采集与落库。

### Retry & Backoff Matrix
- 网络超时/连接失败：`1s -> 2s -> 4s -> 8s`（最多 5 次）
- `429`：按响应头或默认 `5s` 后重试
- `5xx`：指数退避（最多 5 次）
- `4xx`（非 429）：不重试，直接死信

### 云端推送鉴权与可靠性
**鉴权机制**：
- 使用 `Authorization: Bearer <token>` 或签名方式（由云端确定）
- Token 由环境变量 `RT_KLINE_CLOUD_PUSH_TOKEN` 注入
- Token 过期刷新：云端返回 `401` 时，本地尝试从配置中心或 Redis 拉新 token（1 次），若仍失败则转死信

**推送目标熔断规则**：
- 连续推送失败（非 retryable）> 30 分钟 → 熔断，本地事件转入内存队列
- 熔断期间：继续内存积累，可配置最大积压数量（如 10000 条）
- 超出积压上限 → 丢弃最早事件并记告警
- 云端恢复（成功响应）→ 立即解除熔断，内存队列接力推送
- 熔断状态记录到 Redis key `stock:rtk:push_circuit_breaker:{market}`，可人工干预

**死信队列管理**：
- 存储位置：Redis List `stock:rtk:deadletter:push:{market}`
- 写入条件：非 retryable 失败（如 400/401/403）或超过重试上限
- 自动清理：超过 7 天的事件自动删除
- 监控告警：死信队列大小 > 100 条 or 最早事件年龄 > 1 小时 → 触发告警，通知运维

## ClickHouse Minute Sync
- 每分钟从 stream/checkpoint 读取增量事件。
- 按市场分批写入（并行）。
- 幂等键：`ts_code + market + version`。

## ClickHouse 表 DDL 与初始化
所有表由运维预先创建，代码启动时进行表存在性校验（不自动创建）。

### 表定义（示例）
```sql
CREATE TABLE ods_rt_kline_tick_cn (
    ts_code String,
    trade_date Date,
    trade_time String,
    open Float64,
    high Float64,
    low Float64,
    close Float64,
    vol Int64,
    amount Float64,
    pre_close Float64,
    version Int64,
    collected_at DateTime,
    _sign Int8 DEFAULT 1,
    _version UInt64
) ENGINE = ReplacingMergeTree(_version)
PARTITION BY toYYYYMM(trade_date)
ORDER BY (ts_code, trade_date, trade_time, version);
```

### 字段说明
- `_version` 用于 ReplacingMergeTree 的版本字段，与业务 `version` 保持一致
- `_sign` 预留（ReplacingMergeTree 扩展功能，当前不用）
- `trade_date` 由 `trade_time` 解析得出

### 版本升级与兼容性
- 新增字段：使用 `ALTER TABLE ... ADD COLUMN` + 默认值
- 删除字段：通过 VIEW 做向后兼容（不直接删列）
- 字段类型变更：需 TTL 过期后再改（或创建新表灰度迁移）
- 版本管理：表 DDL 版本记录在 `src/stock_datasource/migrations/clickhouse/` 目录下

### Minute Sink Commit Rule
1. 读取窗口 `[T-60s, T)` 的 stream 事件。
2. 批量写入 ClickHouse（按市场）。
3. 全部市场写入成功后再提交 checkpoint。
4. 任一市场失败则不提交该窗口 checkpoint，下一轮整窗重放（依赖幂等键去重）。

### 分市场失败隔离与恢复
**单市场写入失败处理**：
- 若 A 市场写入失败，其他市场（B/C/D）照常继续写入
- 单市场失败重试上限：3 次
- 超过上限的市场：
  - 当前窗口跳过该市场，不写入；checkpoint 仅提交其他市场的进度
  - 失败事件转入市场级死信 `stock:rtk:deadletter:sink:{market}`
  - 触发告警，通知运维介入

**市场级死信处理**：
- 存储位置：Redis List `stock:rtk:deadletter:sink:{market}`
- 触发条件：单市场累积失败 > 5 次（10 分钟内）
- 运维干预：
  - 可手动查询和重放死信队列
  - 可通过 Redis 命令直接清理
  - 恢复后手动标记市场为"可用"，重新消费 checkpoint 之后的数据

**版本字段生成规则**：
- `version = floor(collected_at_timestamp * 1000)`
- `collected_at` 是采集时刻（秒级精度），乘以 1000 得毫秒版本号
- 同一秒内多条 (ts_code, trade_time) 行：版本相同，后到的按 ReplacingMergeTree 的 `version` 覆盖（UPSERT）

## Observability
### 采集指标（Collector）
- `rt_kline_collector_calls_total`（counter）：按市场计，调用次数
- `rt_kline_collector_success_total`（counter）：成功次数
- `rt_kline_collector_errors_total`（counter）：按错误类型（timeout/limit/service）分类
- `rt_kline_collector_latency_ms`（histogram）：单次调用耗时，分位数 p50/p95/p99
- `rt_kline_collector_backoff_level`（gauge）：当前降频等级（1/3/5 秒）
- **告警阈值**：成功率 < 95% for 5min → 告警

### 推送指标（Push Worker）
- `rt_kline_push_events_total`（counter）：发送事件数，按 market/status(ok/retryable/failed)
- `rt_kline_push_latency_ms`（histogram）：云端往返延迟
- `rt_kline_push_retry_count`（counter）：重试次数
- `rt_kline_push_deadletter_size`（gauge）：死信队列大小（按市场）
- `rt_kline_push_circuit_breaker_active`（gauge）：熔断状态（0=normal/1=broken）
- `rt_kline_push_ack_lag_ms`（gauge）：最后一次成功 ACK 距离现在的延迟
- **告警阈值**：
  - 成功率 < 98% for 5min → 告警
  - 死信队列 > 100 条 → 告警
  - 熔断激活 > 10min → 严重告警

### 落库指标（Minute Sink Worker）
- `rt_kline_sink_batches_total`（counter）：批次数，按 market/status(success/failed)
- `rt_kline_sink_records_total`（counter）：写入记录数，按市场
- `rt_kline_sink_latency_ms`（histogram）：单批次写入耗时
- `rt_kline_sink_backlog_depth`（gauge）：未提交的 stream 消息堆积（按市场）
- `rt_kline_sink_deadletter_size`（gauge）：死信队列大小（按市场）
- `rt_kline_sink_market_failure_count`（counter）：单市场失败次数（用于激活隔离）
- **告警阈值**：
  - 成功率 < 99% for 5min → 告警
  - 堆积深度 > 1000 events → 告警
  - 市场级失败 > 5 times in 10min → 激活隔离

### 开关操作审计
- `rt_kline_push_switch_changes`（structured log）：
  - 字段：时间戳、目标状态（on/off）、操作源（env-var/redis/api）、环境、变更前状态
  - 存储：结构化日志系统或 Redis Stream `stock:rtk:audit:push_switch`
  - 保留期：90 天

## Failure Handling
- Tushare 异常：退避重试，不中断 worker。
- Redis 异常：采集暂存内存缓冲（短时），恢复后回补（实现阶段可选）。
- 云端不可达：推送降级为本地继续累积，不影响落库。
- ClickHouse 异常：当前批次重试，失败保留 checkpoint。

## Trade-offs
- 选择 Redis Stream 而非 List：便于多消费者与 checkpoint 管理。
- 选择分钟落库而非实时逐条落库：降低 CH 写放大，换取最多 60 秒可见性延迟。
- 选择隐藏开关默认关闭：降低未经验证情况下的线上风险。

## Open Questions
- 云端推送协议最终选择（HTTP/QUIC/gRPC）与鉴权方式。
- 推送目标是否需要多租户隔离标签。
- ClickHouse 表命名与分区策略是否沿用现有命名规范。