# Spec: Realtime Kline Decoupled Stream Sync

## ADDED Requirements

### Requirement: Decoupled Realtime Kline Runtime
系统 SHALL 将实时日线能力实现为独立运行时，不与其他实时模块共享关键采集与同步执行链路。

#### Scenario: 独立启动与故障隔离
- **WHEN** `realtime_kline` 运行时启动
- **THEN** 采集、推送、落库 worker 在该模块内独立创建
- **AND** 不依赖 `realtime_minute` 的采集/同步服务对象
- **AND** 任一外部模块故障不应阻塞实时日线采集

#### Scenario: 独立配置命名空间
- **WHEN** 系统加载实时日线配置
- **THEN** 使用 `RT_KLINE_*` 前缀参数
- **AND** 参数变更仅影响实时日线链路

### Requirement: 1.5 秒采集并写入 Redis Latest 与 Stream
系统 SHALL 按 1.5 秒周期从 Tushare 实时接口采集快照，并同时写入 Redis latest 与 Redis stream。

#### Scenario: 正常采集周期
- **GIVEN** 交易时段内
- **WHEN** 采集循环触发（每 1.5 秒）
- **THEN** 调用 `rt_k`、`rt_etf_k`、`rt_idx_k`、`rt_hk_k`
- **AND** 最新快照写入 `stock:rtk:latest:{market}:{ts_code}`
- **AND** 事件写入 `stock:rtk:stream:{market}`

#### Scenario: 限流时自动降频与恢复
- **GIVEN** 采集 worker 运行中
- **WHEN** 连续 3 次异常（超时、限流、服务异常）
- **THEN** 采集周期退避到 3 秒
- **WHEN** 再连续 3 次异常
- **THEN** 采集周期进一步退避到 5 秒
- **WHEN** 连续 5 次成功调用
- **THEN** 采集周期回到当前级别的上一级（逐级恢复到 1.5 秒）
- **AND** 计数独立按市场维度

#### Scenario: Redis stream 与 checkpoint 消费
- **WHEN** 采集成功后，事件写入 `stock:rtk:stream:{market}`
- **THEN** stream entry 保留至少 72 小时
- **AND** 推送与落库 worker 分别维护各自的 checkpoint
- **AND** 推送 checkpoint 更新条件：云端返回 ACK success
- **AND** 落库 checkpoint 更新条件：全市场批次写入成功

### Requirement: 秒级云端增量推送（隐藏功能开关）
系统 SHALL 提供秒级云端增量推送能力，且该能力默认关闭，并受显式开关控制。

#### Scenario: 开关默认关闭
- **WHEN** 系统使用默认配置启动
- **THEN** `RT_KLINE_CLOUD_PUSH_ENABLED=false`
- **AND** 不启动推送 worker
- **AND** 不产生任何云端推送流量

#### Scenario: 开启后按 2 秒触发 + 10 秒滑动窗口推送增量
- **GIVEN** 推送开关开启
- **WHEN** 推送 worker 每 2 秒消费 stream 事件
- **THEN** 每轮计算窗口固定为最近 10 秒 `[now-10s, now)`
- **AND** 仅发送相对 `last_acked_state` 发生变化的字段（如 `code/price/vol/amount/trade_time`）
- **AND** 使用 `(ts_code, market, version)` 作为幂等键

#### Scenario: 推送报文符合 v1 契约
- **WHEN** 发送任一推送事件
- **THEN** 报文包含 `schema_version/event_id/event_time/market/source_api/symbol/version/delta`
- **AND** `delta` 仅包含本轮变化字段
- **AND** 能通过服务端契约校验

#### Scenario: ACK 与重试分流
- **GIVEN** 云端返回 ACK
- **WHEN** `status=ok` 且 `code=0`
- **THEN** 推进推送 checkpoint
- **AND** 更新 `stock:rtk:last_acked_state:{market}` 中该 symbol 的全部 delta 字段
- **WHEN** 返回 `retryable`（含 429/503）
- **THEN** 按指数退避重试（最多 5 次）
- **WHEN** 返回不可重试失败（如 400/401）
- **THEN** 写入死信 `stock:rtk:deadletter:push:{market}`
- **AND** 触发告警

#### Scenario: 推送熔断与恢复
- **GIVEN** 推送 worker 运行中
- **WHEN** 连续推送失败（非 retryable）> 30 分钟
- **THEN** 激活熔断，标记 `stock:rtk:push_circuit_breaker:{market} = 1`
- **AND** 后续事件转入内存队列（最多 10000 条）
- **WHEN** 超出内存积压上限
- **THEN** 丢弃最早事件并记告警
- **WHEN** 云端恢复（成功响应）
- **THEN** 立即解除熔断
- **AND** 内存队列继续推送

#### Scenario: 运行时关闭立即生效
- **GIVEN** 推送功能正在运行
- **WHEN** 运行时开关切换为关闭
- **THEN** 推送 worker 应在当前周期后停止
- **AND** 本地采集与分钟落库保持正常运行

### Requirement: Redis 每分钟同步到 ClickHouse
系统 SHALL 每 60 秒将 Redis 事件聚合后批量同步到 ClickHouse，并保证可重试且幂等。

#### Scenario: 分钟批量入库成功
- **WHEN** minute-sink worker 触发（每 60 秒）
- **THEN** 按市场聚合增量事件并批量写入 ClickHouse
- **AND** 写入成功后更新 checkpoint

#### Scenario: 固定目标表写入
- **WHEN** 按市场执行分钟入库
- **THEN** `cn/etf/index/hk` 分别写入 `ods_rt_kline_tick_cn/etf/index/hk`
- **AND** 表使用 `ReplacingMergeTree(version)`
- **AND** 以 `(ts_code, trade_time, version)` 支撑幂等覆盖

#### Scenario: 全窗口提交规则
- **GIVEN** 窗口 `[T-60s, T)` 包含多个市场数据
- **WHEN** 任一市场写入失败
- **THEN** 本窗口 checkpoint 不提交
- **AND** 下一轮重放整窗数据
- **AND** 依赖幂等键避免重复有效记录
- **WHEN** 单市场重试 > 3 次仍失败
- **THEN** 跳过该市场，其他市场照常提交 checkpoint
- **AND** 失败事件转入市场级死信 `stock:rtk:deadletter:sink:{market}`

#### Scenario: ClickHouse 表初始化与版本升级
- **WHEN** sink worker 启动
- **THEN** 校验 4 张目标表是否存在（不自动创建）
- **AND** 表不存在时记错误并启动失败告警
- **WHEN** 新增字段需求
- **THEN** 使用 `ALTER TABLE ... ADD COLUMN` + 默认值
- **AND** 旧版本代码继续读取（忽略新字段）

#### Scenario: 版本字段与幂等覆盖
- **WHEN** 采集时刻写入 stream 事件
- **THEN** `version = floor(collected_at_timestamp * 1000)`
- **WHEN** 同一秒内同一 symbol 多条数据落库
- **THEN** 版本相同，后到的按 ReplacingMergeTree 的 `version` 覆盖（UPSERT）

#### Scenario: 落库失败后重试不重复
- **GIVEN** 某批次写入失败
- **WHEN** 下一轮重试执行
- **THEN** 仅重放未确认批次
- **AND** 不产生重复有效记录

### Requirement: 链路可观测性与审计
系统 SHALL 为采集、推送、落库与开关操作提供可观测指标与审计记录。

#### Scenario: 采集/推送/落库指标上报
- **WHEN** 链路运行
- **THEN** 上报采集成功率与延迟
- **AND** 上报推送量、失败率与重试次数
- **AND** 上报落库批次耗时与积压深度

#### Scenario: 开关操作审计
- **WHEN** 推送开关状态发生变化
- **THEN** 记录变更时间、环境、操作者（若可识别）与目标状态

## MODIFIED Requirements
(None)

## REMOVED Requirements
(None)
