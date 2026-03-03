# Tasks: 实时日线解耦流式缓存与秒级推送

## 1. 规格与接口契约确认
- [x] 1.1 固化 Tushare 四个接口字段映射（含可选盘口字段）
- [x] 1.2 确认 Redis key/stream/checkpoint 命名与保留周期（latest 24h / stream 72h）
- [x] 1.3 固化云端推送 `payload v1` 契约与字段必填规则
- [x] 1.4 固化 ACK 状态码语义（ok/retryable/failed）与重试矩阵
- [x] 1.5 固化幂等键规范：推送 `(ts_code,market,version)`、落库 `(ts_code,trade_time,version)`
- [x] 1.6 确认版本字段生成规则：`version = floor(collected_at * 1000)`

## 2. 解耦运行时搭建
- [x] 2.1 建立独立 `realtime_kline` 运行时入口（不依赖 `realtime_minute`）
- [x] 2.2 拆分三个 worker：collector / cloud-push / minute-sink
- [x] 2.3 为三类 worker 建立独立生命周期管理与健康检查
- [x] 2.4 实现降频规则：3次失败→3s，再3次→5s；5次成功→恢复上一级

## 3. 采集与缓存链路
- [x] 3.1 实现 1.5 秒采集循环（含限流退避）
- [x] 3.2 写入 Redis latest（覆盖）与 Redis Stream（事件）
- [x] 3.3 实现快照规范化与版本号生成逻辑
- [x] 3.4 设置 Redis key TTL：latest 24h / stream 72h

## 4. 云端秒级推送（隐藏功能）
- [x] 4.1 实现 `RT_KLINE_CLOUD_PUSH_ENABLED` 开关（默认关闭）
- [x] 4.2 实现"2 秒触发 + 10 秒滑动窗口"的增量计算与推送
- [x] 4.3 实现 `last_acked_state` 基线（Redis Hash）与窗口重叠去重
- [x] 4.4 实现云端 token 鉴权与过期刷新（401 重试一次）
- [x] 4.5 实现推送熔断规则（失败 > 30min 激活）与内存队列（最多 10000 条）
- [x] 4.6 实现死信队列 `stock:rtk:deadletter:push:{market}` 与 7 天自动清理
- [x] 4.7 实现开关运行时切换与审计日志（Redis Stream + structured log）
- [x] 4.8 验证关闭状态下"零推送流量"

## 5. Redis 到 ClickHouse 每分钟同步
- [x] 5.1 实现 60 秒批量聚合与分市场并行写入
- [x] 5.2 固定写入表：`ods_rt_kline_tick_cn/etf/index/hk`
- [x] 5.3 实现全窗口 checkpoint 提交规则（全部市场成功才提交）
- [x] 5.4 实现单市场失败隔离（失败 > 3 次转死信，其他市场继续）
- [x] 5.5 实现市场级死信队列 `stock:rtk:deadletter:sink:{market}`
- [x] 5.6 实现 checkpoint 与失败重试（不重复写）
- [x] 5.7 验证幂等语义（重复执行不产生重复有效记录）
- [x] 5.8 确认 ClickHouse 表 DDL 预先创建（代码不自动创建）

## 6. 可观测性与验证
- [x] 6.1 上报采集指标：calls_total / success_total / errors_total / latency_ms / backoff_level
- [x] 6.2 上报推送指标：events_total / latency_ms / retry_count / deadletter_size / circuit_breaker_active / ack_lag_ms
- [x] 6.3 上报落库指标：batches_total / records_total / latency_ms / backlog_depth / deadletter_size / market_failure_count
- [x] 6.4 配置告警规则：采集成功率<95% / 推送成功率<98% / 落库成功率<99% / 死信>100条
- [x] 6.5 增加开关操作审计日志（时间戳、状态、操作源、环境）
- [x] 6.6 增加链路级集成测试（采集→推送→落库）
- [x] 6.7 增加降级场景测试（限流、云端不可达、CH写失败、单市场隔离）

## 7. OpenSpec 校验
- [x] 7.1 运行 `openspec validate add-realtime-kline-cache-sync --strict`
- [x] 7.2 修复校验问题直至全部通过
