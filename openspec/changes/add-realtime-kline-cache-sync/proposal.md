# Change: 实时日线解耦流式缓存、云端秒级推送与分钟入库

## Why
当前 `add-realtime-kline-cache-sync` 方案主要强调“盘中缓存 + 日终入库”，但你提出了更高稳定性与实时性要求：
1. 实时日线链路必须与其他模块解耦，避免联动故障影响核心行情能力。
2. 数据链路从“低频采集 + 日终同步”升级为“1.5 秒采集 + 秒级云端推送 + 每分钟入库”。
3. 云端推送是隐藏能力，必须具备默认关闭的开关控制。

## What Changes
- 将实时日线能力重构为**独立运行时模块**（独立配置、独立调度、独立故障域），不依赖 `realtime_minute` 任务编排。
- 采集层改为从 Tushare 实时接口（`rt_k` / `rt_etf_k` / `rt_idx_k` / `rt_hk_k`）按 **1.5 秒周期**抓取快照。
- 写入层改为 Redis 双通道：
  - `latest`：覆盖式最新快照（本地查询低延迟）
  - `stream`：事件流（供推送与分钟落库消费）
- 新增云端推送链路：
  - 本地每 2 秒计算增量（仅变化字段：`code/price/vol/...`）
  - 推送至云端接收服务（秒级数据）
  - 该功能为**隐藏功能**，默认关闭，支持运行期开关。
- 新增分钟落库链路：Redis 每 60 秒聚合批量写入 ClickHouse，写入后确认并清理已消费数据。
- 增加链路级可观测性（采集、推送、落库三段指标）与故障降级策略。

## Scope Boundaries
### In Scope
- 实时日线采集、缓存、秒级推送、分钟入库全链路设计与规格更新。
- 云端推送隐藏开关设计（默认关闭、灰度开启、紧急熔断）。
- Redis → ClickHouse 的每分钟批量同步与幂等保障。

### Out of Scope
- 前端可视化改版（仅定义数据契约，不改 UI）。
- 历史全量回填框架重构。
- 非 Tushare 实时源的接入。

## Impact
- Affected spec delta: `openspec/changes/add-realtime-kline-cache-sync/specs/realtime-kline-cache-sync/spec.md`
- Affected design/tasks:
  - `openspec/changes/add-realtime-kline-cache-sync/design.md`
  - `openspec/changes/add-realtime-kline-cache-sync/tasks.md`
- Expected code impact (implementation stage, not in this proposal):
  - `src/stock_datasource/modules/realtime_kline/`（独立模块）
  - Redis stream / sink / push adapters
  - ClickHouse minute ingest pipeline

## External API References
- `rt_k`: https://tushare.pro/document/2?doc_id=372
- `rt_etf_k`: https://tushare.pro/document/2?doc_id=383
- `rt_idx_k`: https://tushare.pro/document/2?doc_id=403
- `rt_hk_k`: https://tushare.pro/document/2?doc_id=400

## Assumptions
- Tushare 账号已具备上述实时接口权限。
- 1.5 秒轮询可在当前账号配额下运行；若触发限流将按降频策略执行。
- 云端已有可接收秒级增量数据的稳定入口（HTTP/QUIC 由实现阶段确定）。

## Risks & Mitigations
- 高频采集触发限流：增加动态降频（1.5s → 3s → 5s）和退避重试。
- 推送链路抖动：本地保留短时重试队列，推送失败不阻塞本地缓存与落库。
- 分钟落库积压：按市场并行批次写入 + 幂等去重键。
- 隐藏功能误开启：默认关闭 + 环境白名单 + 运行时审计日志。

## Success Criteria
- 本地采集稳定运行：交易时段内成功率 ≥ 99%。
- 秒级推送在开启后端到端延迟（P95）≤ 3 秒。
- 分钟入库任务成功率 ≥ 99.5%，且无重复主键污染。
- 推送开关关闭时，系统不产生任何云端推送流量。