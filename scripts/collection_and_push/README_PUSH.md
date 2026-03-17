# push_csv_to_cloud.py — CSV 增量推送脚本

> 独立脚本，不依赖 Redis / ClickHouse / FastAPI。  
> 从 `collect_tushare_to_csv.py` 产出的 CSV 目录中增量读取，按 **RawTickBatchPayload v2** 协议推送到云端。

---

## 目录

- [功能特性](#功能特性)
- [环境准备](#环境准备)
- [快速启动](#快速启动)
- [命令行参数](#命令行参数)
- [推送协议（RawTickBatchPayload v2）](#推送协议rawtickbatchpayload-v2)
  - [请求格式](#请求格式)
  - [Payload 字段说明](#payload-字段说明)
  - [items 数组元素](#items-数组元素)
  - [tick 对象](#tick-对象)
  - [完整请求示例](#完整请求示例)
- [ACK 回执协议](#ack-回执协议)
  - [ACK 响应格式](#ack-响应格式)
  - [ACK 状态码约定](#ack-状态码约定)
- [重试策略](#重试策略)
- [断点续传](#断点续传)
- [市场与数据源映射](#市场与数据源映射)
- [常见场景](#常见场景)
- [注意事项](#注意事项)

---

## 功能特性

- ✅ **纯 Python**：仅依赖 `pandas` + `requests`，无外部服务依赖
- ✅ **增量推送**：只推送新增行，不重复发送
- ✅ **断点续传**：通过 JSON checkpoint 记录每个文件已推送行数，重启自动续传
- ✅ **循环监控**：`--loop` 模式持续监控 CSV 目录增量
- ✅ **指数退避重试**：网络抖动自动重试，指数退避 + 上限封顶
- ✅ **多市场支持**：A 股、ETF、指数、港股

---

## 环境准备

```bash
pip install pandas requests
```

环境变量（可选，免去命令行传参）：

```bash
export RT_KLINE_CLOUD_PUSH_URL=https://your-cloud/api/v1/rt-kline/push
export RT_KLINE_CLOUD_PUSH_TOKEN=your_push_token
export CSV_DIR=data/tushare_csv
```

---

## 快速启动

### 单次推送

```bash
python scripts/collection_and_push/push_csv_to_cloud.py \
  --push-url $RT_KLINE_CLOUD_PUSH_URL \
  --push-token $RT_KLINE_CLOUD_PUSH_TOKEN
```

### 持续循环推送（每 5 秒检查增量）

```bash
python scripts/collection_and_push/push_csv_to_cloud.py \
  --push-url $RT_KLINE_CLOUD_PUSH_URL \
  --push-token $RT_KLINE_CLOUD_PUSH_TOKEN \
  --loop --interval 5.0
```

### 指定市场和批量大小

```bash
python scripts/collection_and_push/push_csv_to_cloud.py \
  --push-url $RT_KLINE_CLOUD_PUSH_URL \
  --markets a_stock,etf \
  --batch-size 500 \
  --loop
```

### 后台运行

```bash
nohup python scripts/collection_and_push/push_csv_to_cloud.py \
  --push-url $RT_KLINE_CLOUD_PUSH_URL \
  --push-token $RT_KLINE_CLOUD_PUSH_TOKEN \
  --loop --interval 5.0 \
  > logs/push.log 2>&1 &
```

---

## 命令行参数

| 参数 | 默认值 | 说明 |
|------|--------|------|
| **数据源** | | |
| `--csv-dir` | `data/tushare_csv` / `$CSV_DIR` | CSV 文件目录（`collect_tushare_to_csv.py` 的输出） |
| `--markets` | `a_stock,etf,index,hk` | 要推送的市场，逗号分隔 |
| **推送目标** | | |
| `--push-url` | `$RT_KLINE_CLOUD_PUSH_URL` | 云端推送 URL（**必填**） |
| `--push-token` | `$RT_KLINE_CLOUD_PUSH_TOKEN` | Bearer 鉴权 Token |
| **批量/重试** | | |
| `--batch-size` | `1000` | 每批推送条数 |
| `--max-retry` | `3` | 单批最大重试次数 |
| `--retry-backoff-base` | `1.0` | 重试退避基数（秒） |
| `--retry-backoff-max` | `10.0` | 重试退避上限（秒） |
| `--timeout` | `15` | HTTP 请求超时（秒） |
| `--shards` | `4` | 分片数（`shard_id` 计算） |
| **循环模式** | | |
| `--loop` | 关闭 | 持续循环监控 CSV 目录增量推送 |
| `--interval` | `3.0` | 循环间隔（秒） |
| `--rounds` | `0` | 最大循环轮次，0 = 无限 |
| **断点** | | |
| `--checkpoint-file` | `data/push_checkpoint.json` | 断点记录文件路径 |
| **日志** | | |
| `--log-level` | `INFO` | 日志级别：`DEBUG` / `INFO` / `WARNING` / `ERROR` |

---

## 推送协议（RawTickBatchPayload v2）

本脚本是**推送方**（HTTP client），将 CSV 中的实时行情数据批量 POST 到远端云服务。  
**如果你是云端接收方，按此协议实现接收接口即可。**

### 请求格式

```
POST <push-url>
Authorization: Bearer <push_token>
Content-Type: application/json
```

### Payload 字段说明

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `schema_version` | string | ✅ | 固定 `"v2"` |
| `mode` | string | ✅ | 固定 `"raw_tick_batch"` |
| `batch_seq` | int | ✅ | 批次序列号（同 market 内递增） |
| `event_time` | string | ✅ | 发送时间，ISO 8601 UTC（如 `2026-03-10T06:30:00.123456+00:00`） |
| `market` | string | ✅ | 市场标识：`a_stock` / `etf` / `index` / `hk` |
| `source_api` | string | ✅ | 采集来源 API 名称（见[市场映射表](#市场与数据源映射)） |
| `count` | int | ✅ | `items` 数组长度（必须与实际长度一致） |
| `first_stream_id` | string | ✅ | 本批首条 stream_id |
| `last_stream_id` | string | ✅ | 本批末条 stream_id |
| `items` | array | ✅ | Tick 数据数组 |

### items 数组元素

| 字段 | 类型 | 说明 |
|------|------|------|
| `stream_id` | string | 流内唯一 ID，格式 `{毫秒时间戳}-{序号}` |
| `ts_code` | string | 证券代码（如 `000001.SZ`） |
| `version` | string | 数据版本号 |
| `shard_id` | int | 分片 ID = `hash(ts_code) % shards` |
| `tick` | object | 原始行情数据（CSV 行的完整字段） |

### tick 对象

`tick` 是 CSV 中一行数据的全部字段转为 JSON object，字段与 `collect_tushare_to_csv.py` 产出的 CSV 列一致。始终包含 `market` 字段。`NaN` / `Inf` 值会被转为 `null`。

### 完整请求示例

```json
{
  "schema_version": "v2",
  "mode": "raw_tick_batch",
  "batch_seq": 1,
  "event_time": "2026-03-10T06:30:00.123456+00:00",
  "market": "a_stock",
  "source_api": "tushare_rt_k",
  "count": 2,
  "first_stream_id": "1741588200123-0",
  "last_stream_id": "1741588200123-1",
  "items": [
    {
      "stream_id": "1741588200123-0",
      "ts_code": "000001.SZ",
      "version": "1741588200123",
      "shard_id": 2,
      "tick": {
        "ts_code": "000001.SZ",
        "market": "a_stock",
        "open": 10.50,
        "high": 10.88,
        "low": 10.45,
        "close": 10.80,
        "vol": 12345678,
        "amount": 134000000.0
      }
    },
    {
      "stream_id": "1741588200123-1",
      "ts_code": "600519.SH",
      "version": "1741588200123",
      "shard_id": 1,
      "tick": {
        "ts_code": "600519.SH",
        "market": "a_stock",
        "open": 1680.00,
        "high": 1695.50,
        "low": 1675.00,
        "close": 1690.00,
        "vol": 2345678,
        "amount": 39600000.0
      }
    }
  ]
}
```

---

## ACK 回执协议

### ACK 响应格式

接收方（云端）需返回 JSON 格式的 ACK 回执：

```json
{
  "status": "ok",
  "code": 0,
  "ack_seq": 1,
  "accepted_count": 2,
  "rejected_count": 0
}
```

| 字段 | 类型 | 说明 |
|------|------|------|
| `status` | string | 状态标识 |
| `code` | int | 状态码 |
| `ack_seq` | int | 确认的 `batch_seq` |
| `accepted_count` | int | 成功接收条数 |
| `rejected_count` | int | 拒绝条数 |

### ACK 状态码约定

| 分类 | status 值 | code 值 | 脚本行为 |
|------|-----------|---------|----------|
| ✅ 成功 | `ok` / `success` / `accepted` / 空 | `0` / `200` / `202` | 确认成功，推进 checkpoint |
| 🔄 可重试 | `retryable` / `throttle` / `busy` / `timeout` / `temporarily_unavailable` | `408` / `409` / `425` / `429` / `500` / `502` / `503` / `504` / `1001` / `1002` / `1003` | 进入重试队列 |
| ❌ 失败 | 其他 | 其他 | 停止推送该批次 |

> **空 body**（`Content-Length: 0`）也视为成功。

---

## 重试策略

- **最大重试次数**：`--max-retry`（默认 3 次）
- **退避算法**：指数退避 `base × 2^(attempt-1)`，封顶 `--retry-backoff-max`
- **触发条件**：
  - HTTP 状态码：`408` / `425` / `429` / `500` / `502` / `503` / `504`
  - ACK 状态为 `retryable` / `throttle` / `busy` / `timeout` / `temporarily_unavailable`
  - ACK code 为 `408` / `409` / `425` / `429` / `500` / `502` / `503` / `504` / `1001` / `1002` / `1003`
  - 网络超时 / 连接错误

**默认退避序列**：`1s → 2s → 4s`（base=1.0, max=10.0）

---

## 断点续传

脚本通过 `--checkpoint-file`（默认 `data/push_checkpoint.json`）记录每个 CSV 文件已推送的行偏移量：

```json
{
  "data/tushare_csv/a_stock.csv": 15000,
  "data/tushare_csv/etf.csv": 8200
}
```

- 每成功推送一个批次，立即更新 checkpoint
- 重启后自动从上次位置继续
- 使用原子写入（先写 `.tmp` 再 `os.replace`）保证一致性

---

## 市场与数据源映射

| 市场 (`market`) | CSV 文件名前缀 | `source_api` 值 |
|-----------------|---------------|-----------------|
| `a_stock` | `a_stock*.csv` | `tushare_rt_k` |
| `etf` | `etf*.csv` | `tushare_rt_etf_k` |
| `index` | `index*.csv` | `tushare_rt_idx_k` |
| `hk` | `hk*.csv` | `tushare_rt_hk_k` |

CSV 文件按前缀匹配，支持带日期后缀的文件名（如 `a_stock_20260310.csv`）。

---

## 常见场景

| 场景 | 命令 |
|------|------|
| 手动推送一次 | `python scripts/collection_and_push/push_csv_to_cloud.py --push-url $RT_KLINE_CLOUD_PUSH_URL` |
| 持续推送 | 加 `--loop --interval 5.0` |
| 只推 A 股和 ETF | 加 `--markets a_stock,etf` |
| 减小单批大小 | 加 `--batch-size 200` |
| 增加重试 | 加 `--max-retry 5 --retry-backoff-max 30` |
| 调试查看详细日志 | 加 `--log-level DEBUG` |
| 重置断点重新推送 | 删除 `data/push_checkpoint.json` |

---

## 接收端脚本 `receive_push_data.py`

配套的接收端脚本，启动一个 HTTP 服务接收本脚本推送的数据。

当前实现采用轻量的三段式模型：

- `push` 请求只负责把 tick 追加写入 spool JSONL 文件
- 后台单个 builder 线程按固定时间窗口批量把增量数据刷入 SQLite 最新快照表
- 查询接口直接读取 SQLite，不再依赖常驻内存快照

### 快速启动

```bash
# 启动接收服务（默认 0.0.0.0:9100）
python scripts/collection_and_push/receive_push_data.py

# 指定端口 + Token 鉴权
python scripts/collection_and_push/receive_push_data.py --port 9100 --token my_secret_token

# 每 3 秒批量刷一次 SQLite，并额外导出市场级 CSV 快照
python scripts/collection_and_push/receive_push_data.py --flush-interval-seconds 3 --save-csv
```

### 参数

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `--host` | `0.0.0.0` | 监听地址 |
| `--port` | `9100` | 监听端口 |
| `--token` | `$RT_KLINE_CLOUD_PUSH_TOKEN` | 兼容旧参数，等同 `--push-token` |
| `--push-token` | `$RT_KLINE_CLOUD_PUSH_TOKEN` | Push 写入 Bearer Token |
| `--policy-token` | `$RT_STOCK_POLICY_TOKEN` | 接收管理平台下发 policy 的 Bearer Token |
| `--jwt-public-key-path` | `$RT_STOCK_JWT_PUBLIC_KEY_PATH` | 实时订阅 JWT 公钥路径 |
| `--data-dir` | `data/received_push` | 数据落地目录 |
| `--spool-dir` | `<data-dir>/spool` | 原始 push 追加写目录 |
| `--snapshot-dir` | `<data-dir>/snapshot` | SQLite/CSV 快照目录 |
| `--sqlite-path` | `<snapshot-dir>/rt_snapshot.db` | SQLite 快照文件路径 |
| `--save-csv` | 关闭 | 每次刷盘后导出市场级最新快照 CSV |
| `--flush-interval-seconds` | `3` | builder 批量刷 SQLite 的时间间隔 |
| `--flush-max-items` | `2000` | 单次 builder 最多处理的 spool 记录数 |
| `--subscription-step-seconds` | `3` | skills 拉取订阅数据的时间步长 |
| `--debug` | 关闭 | Flask debug 模式 |

### 提供的接口

| 接口 | 说明 |
|------|------|
| `POST /api/v1/rt-kline/push` | 接收推送数据（与 push_csv_to_cloud.py 对接） |
| `POST /api/v1/rt-kline/policies/apply` | 接收 nps_enhanced 下发的订阅 policy 快照 |
| `POST /api/v1/rt-kline/subscription/sync` | 按 JWT + policy 同步当前用户的批量订阅 symbols |
| `GET /api/v1/rt-kline/subscription/list` | 查看当前用户已登记的订阅清单 |
| `GET /api/v1/rt-kline/latest?market=&ts_code=&limit=` | 查询最新行情快照 |
| `GET /api/v1/rt-kline/subscription/latest` | 返回当前用户已登记订阅的最新快照，可选 `?symbols=` 取子集 |
| `GET /stats` | 查看 spool/SQLite 刷盘状态 |
| `GET /health` | 健康检查 |

### 订阅节点模式

当前实时订阅节点按“**独立脚本 + spool + SQLite 快照查询**”工作，不要求部署完整 `stock_datasource` 服务。

- `push_csv_to_cloud.py` 或其他采集脚本持续把实时 tick 写入该节点
- `nps_enhanced` 把用户的 realtime policy 下发到 `POST /api/v1/rt-kline/policies/apply`
- 用户的 skills 使用管理平台签发的 JWT，先通过 `POST /api/v1/rt-kline/subscription/sync` 批量登记自己当前订阅的 symbols
- 然后通过 `GET /api/v1/rt-kline/subscription/latest` 轮询读取自己已登记订阅的最新快照
- 当前默认返回 **3 秒步长** 的快照数据，适合 skills 直接轮询

### skills 侧订阅与拉取示例

先登记当前用户的批量订阅：

```bash
curl -X POST \
  -H "Authorization: Bearer $STOCK_RT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"mode":"replace","symbols":["000001.SZ","600519.SH"]}' \
  http://your-node:9100/api/v1/rt-kline/subscription/sync
```

查看当前已登记的订阅清单：

```bash
curl -H "Authorization: Bearer $STOCK_RT_TOKEN" \
  http://your-node:9100/api/v1/rt-kline/subscription/list
```

再拉取最新快照：

```bash
curl -H "Authorization: Bearer $STOCK_RT_TOKEN" \
  http://your-node:9100/api/v1/rt-kline/subscription/latest
```

返回示例：

```json
{
  "status": "ok",
  "code": 0,
  "user_id": "alice",
  "revision": 3,
  "max_subs": 5,
  "registered_symbols": ["000001.SZ", "600519.SH"],
  "accepted_symbols": ["000001.SZ", "600519.SH"],
  "rejected_symbols": [],
  "step_seconds": 3,
  "count": 2,
  "data": [
    {"ts_code": "000001.SZ", "market": "a_stock", "close": 10.52},
    {"ts_code": "600519.SH", "market": "a_stock", "close": 1690.00}
  ],
  "missing": []
}
```

如果 `sync` 请求中的 symbol 超过 JWT/Policy 的 `max_subs`，超额部分会出现在 `rejected_symbols` 中，并标记 `quota_exceeded`。

如果 `latest` 请求显式传了 `?symbols=`，只有已经登记订阅的 symbol 才会返回；未登记的会以 `not_subscribed` 出现在 `rejected_symbols` 中。

### 数据落地

- **spool JSONL**：`data/received_push/spool/{market}/{YYYYMMDD}.jsonl`，接收端只做追加写
- **SQLite 快照**：`data/received_push/snapshot/rt_snapshot.db`，保存每个 `(market, ts_code)` 的最新一条记录
- **CSV 快照**（可选，加 `--save-csv` 开启）：
  - `data/received_push/snapshot/{market}_latest.csv`
  - 每次 builder 刷盘完成后原子重写
  - 适合排查或离线导出，不建议作为高频查询主路径

### 推送 + 接收联调示例

```bash
# 终端 1：启动接收端
python scripts/collection_and_push/receive_push_data.py --port 9100 --flush-interval-seconds 3 --save-csv

# 终端 2：启动推送端，指向接收端
python scripts/collection_and_push/push_csv_to_cloud.py \
  --push-url http://localhost:9100/api/v1/rt-kline/push \
  --loop --interval 5.0
```

### 现网快速验证

如果你只是想在现网环境快速确认节点是否可用，建议按下面顺序验证。这样能最短路径覆盖：服务存活、push 入站、SQLite 刷盘、policy 下发、用户订阅同步、订阅查询。

#### 1. 启动接收端

```bash
python scripts/collection_and_push/receive_push_data.py \
  --host 0.0.0.0 \
  --port 9100 \
  --push-token "$RT_KLINE_CLOUD_PUSH_TOKEN" \
  --policy-token "$RT_STOCK_POLICY_TOKEN" \
  --jwt-public-key-path "$RT_STOCK_JWT_PUBLIC_KEY_PATH" \
  --flush-interval-seconds 3 \
  --save-csv
```

#### 2. 用内置验证脚本跑一遍

```bash
BASE_URL=http://127.0.0.1:9100 \
PUSH_TOKEN="$RT_KLINE_CLOUD_PUSH_TOKEN" \
POLICY_TOKEN="$RT_STOCK_POLICY_TOKEN" \
STOCK_RT_TOKEN="$STOCK_RT_TOKEN" \
bash scripts/collection_and_push/verify_receiver_flow.sh
```

如果当前只想先验证 push 和 SQLite 刷盘，不想验证订阅接口：

```bash
BASE_URL=http://127.0.0.1:9100 \
PUSH_TOKEN="$RT_KLINE_CLOUD_PUSH_TOKEN" \
bash scripts/collection_and_push/verify_receiver_flow.sh --skip-policy --skip-subscription
```

#### 3. 预期看到的关键结果

1. `/health` 返回 `{"status":"ok"...}`。
2. `/stats` 里能看到 `flush_interval_seconds`，并且在 push 之后 `last_flush_at`、`last_flush_items` 会更新。
3. `POST /api/v1/rt-kline/push` 返回 `status=ok`，`accepted_count > 0`。
4. `GET /api/v1/rt-kline/latest?ts_code=000001.SZ` 返回 `count=1`，说明数据已经进入 SQLite 最新快照。
5. `POST /api/v1/rt-kline/subscription/sync` 返回 `accepted_symbols`，说明用户订阅清单已经登记。
6. `GET /api/v1/rt-kline/subscription/list` 返回 `subscribed_symbols`。
7. `GET /api/v1/rt-kline/subscription/latest` 返回 `data`，说明 JWT、policy、订阅态、快照查询都串起来了。

#### 4. 现网排障时优先看这几个位置

1. `data/received_push/spool/` 下是否持续有新的 JSONL 文件增长。
2. `data/received_push/snapshot/rt_snapshot.db` 是否生成。
3. `data/received_push/snapshot/*_latest.csv` 在开启 `--save-csv` 时是否更新。
4. `/stats` 里的 `subscription_rows`、`subscription_users` 是否增长。
5. 如果 `latest` 查不到数据，但 push 已成功，优先看 `last_flush_at` 是否没有更新，说明 builder 没有正常刷盘。

#### 5. 现网验证完成后的最小保留检查

建议至少保留下面两条命令，后续上线后排查最快：

```bash
curl -sS http://127.0.0.1:9100/health
curl -sS http://127.0.0.1:9100/stats
```

如果这两条正常，再跑：

```bash
BASE_URL=http://127.0.0.1:9100 \
PUSH_TOKEN="$RT_KLINE_CLOUD_PUSH_TOKEN" \
bash scripts/collection_and_push/verify_receiver_flow.sh --skip-policy --skip-subscription
```

---

## 注意事项

1. **`--push-url` 必填**：未设置时脚本直接报错退出
2. **CSV 目录必须存在**：脚本不会自动创建，需先用 `collect_tushare_to_csv.py` 生成
3. **NaN / Inf 处理**：CSV 中的 `NaN` / `Inf` 会自动转为 `null`（JSON 中无 NaN）
4. **shard_id 分配**：`hash(ts_code) % shards`，用于接收方做并行分片消费
5. **stream_id 生成**：`{毫秒时间戳}-{批内序号}`，仅作为流内唯一标识，不用于排序
6. **checkpoint 安全**：原子写入，断电不丢失已确认的进度
7. **配合 Pipeline 使用**：也可通过 `csv_pipeline.py` 统一编排，详见 `scripts/README.md`
