# CSV 实时数据流水线

> 轻量级实时行情采集 → 推送 → 接收 全链路方案。  
> 采集/推送端为 Python 脚本，接收端为 Go 编译的高性能二进制，不依赖 Redis / ClickHouse。

---

## 架构总览

```
┌─────────────────────────────────────────────────────────────┐
│  代理节点 (proxy)                                            │
│                                                             │
│  csv_pipeline.py（控制进程）                                  │
│    ├── collect  子进程 ×1  — TuShare 实时行情 → CSV            │
│    ├── push     子进程 ×N  — 增量读取 CSV → POST 到订阅节点     │
│    └── cleanup  子进程 ×1  — 定期清理过期 CSV 文件              │
└──────────────────────┬──────────────────────────────────────┘
                       │ POST /api/v1/rt-kline/push
                       ▼
┌─────────────────────────────────────────────────────────────┐
│  订阅节点 (receiver) × N — Go 二进制 rt-receiver              │
│                                                             │
│  ├── HTTP 接收 push → spool JSONL 追加写                     │
│  ├── builder 线程 → 批量刷入 SQLite 最新快照                   │
│  └── WebSocket Hub → 实时 broadcast 到客户端                  │
└──────────────────────┬──────────────────────────────────────┘
                       │ ws://node:9100/ws
                       ▼
              浏览器 / Python / 前端
```

---

## 目录

- [快速开始](#快速开始)
- [文件清单](#文件清单)
- [环境配置](#环境配置)
- [一键运维 (run.sh)](#一键运维-runsh)
- [采集端](#采集端)
  - [csv_pipeline.py（控制进程）](#csv_pipelinepy控制进程)
  - [collect_tushare_to_csv.py（采集脚本）](#collect_tushare_to_csvpy采集脚本)
  - [push_csv_to_cloud.py（推送脚本）](#push_csv_to_cloudpy推送脚本)
  - [cleanup_csv.py（清理脚本）](#cleanup_csvpy清理脚本)
- [接收端 (Go rt-receiver)](#接收端-go-rt-receiver)
  - [编译](#编译)
  - [启动](#启动)
  - [HTTP API](#http-api)
  - [WebSocket 实时推送](#websocket-实时推送)
- [推送协议 (RawTickBatchPayload v2)](#推送协议-rawtickbatchpayload-v2)
- [部署与运维](#部署与运维)
- [常见场景速查](#常见场景速查)

---

## 快速开始

```bash
# 1. 配置环境变量
cp scripts/collection_and_push/.env.example scripts/collection_and_push/.env
vim scripts/collection_and_push/.env

# 2. 编译 Go 接收端（需要 Go 1.21+）
cd scripts/collection_and_push/go-rt-receiver && make && cd -

# 3. 一键部署到所有节点
bash scripts/collection_and_push/run.sh deploy

# 4. 启动所有服务（先 receiver 后 proxy）
bash scripts/collection_and_push/run.sh start

# 5. 验证数据流
bash scripts/collection_and_push/run.sh verify
```

---

## 文件清单

| 文件 | 说明 |
|------|------|
| **Python 脚本（采集端/代理节点）** | |
| `csv_pipeline.py` | 控制进程，统一管理采集/推送/清理三个子流程 |
| `collect_tushare_to_csv.py` | 从 TuShare API 采集 A股/ETF/指数/港股实时行情写入 CSV |
| `push_csv_to_cloud.py` | 增量读取 CSV，按 v2 协议推送到订阅节点（支持多目标） |
| `cleanup_csv.py` | 定期清理过期 CSV 文件 |
| **Go 源码（接收端/订阅节点）** | |
| `go-rt-receiver/main.go` | HTTP 服务主入口、路由注册、优雅关闭 |
| `go-rt-receiver/store.go` | 数据存储层（spool 文件 + SQLite 快照读写、每日自动清理） |
| `go-rt-receiver/auth.go` | 鉴权中间件（Bearer Token + JWT/RSA 公钥验证） |
| `go-rt-receiver/websocket.go` | WebSocket Hub，支持客户端实时订阅推送 |
| `go-rt-receiver/util.go` | 配置解析（命令行 flag + 环境变量） |
| `go-rt-receiver/Makefile` | 编译脚本，输出 `rt-receiver`（amd64/arm64） |
| **Shell 脚本（运维）** | |
| `run.sh` | 一键全流程运维入口（deploy/start/stop/restart/status/verify） |
| `deploy.sh` | 通过 sshpass+scp 部署到远程服务器 |
| `start_proxy.sh` | 代理节点：启动采集 + 多节点推送进程 |
| `start_receiver.sh` | 订阅节点：启动 Go 二进制 rt-receiver |
| `stop_all.sh` | 停止进程（本机/远程/全部） |
| `check_status.sh` | 进程状态检查 + HTTP 健康检查 |
| `verify_receiver_flow.sh` | 验证 receiver 数据流（push/policy/subscription 测试） |
| `common.sh` | 公共函数库（颜色输出、SSH 封装、服务器配置加载） |
| **配置** | |
| `.env.example` | 环境变量配置模板 |
| `servers.conf` | 服务器清单配置（禁止入库） |

---

## 环境配置

复制模板并填入实际值：

```bash
cp .env.example .env
```

```bash
# ---- TuShare 采集配置（仅代理服务器需要）----
TUSHARE_TOKEN=your_tushare_token_here

# ---- 推送鉴权 Token（代理和所有订阅节点需一致）----
RT_KLINE_CLOUD_PUSH_TOKEN=your_push_token_here

# ---- 节点地址（start_proxy.sh 使用）----
NODE1_URL=http://your-node1-ip:9100/api/v1/rt-kline/push
NODE2_URL=http://your-node2-ip:9100/api/v1/rt-kline/push
NODE3_URL=http://your-node3-ip:9100/api/v1/rt-kline/push

# ---- 订阅鉴权（可选）----
# RT_STOCK_POLICY_TOKEN=your_policy_token
# RT_STOCK_JWT_PUBLIC_KEY_PATH=/path/to/public.pem
```

---

## 一键运维 (run.sh)

```bash
bash scripts/collection_and_push/run.sh <command>
```

| 命令 | 说明 |
|------|------|
| `deploy` | 部署到所有可达服务器 |
| `start` | 启动全部（先 receiver 后 proxy） |
| `stop` | 停止所有远程进程 |
| `restart` | 停止 → 启动 |
| `status` | 检查所有远程状态 |
| `verify` | 验证数据流 |
| `full` | 部署 → 启动 → 验证（完整流程） |
| `deploy+start` | 部署 → 启动 |

---

## 采集端

### csv_pipeline.py（控制进程）

统一编排采集/推送/清理三个子流程，支持崩溃自动重启。

```bash
# 完整流水线：采集 + 推送 + 清理
python scripts/collection_and_push/csv_pipeline.py \
  --env-file .env \
  --collect-interval 2.0 \
  --push-interval 5.0

# 只采集 + 清理（不推送）
python scripts/collection_and_push/csv_pipeline.py \
  --token $TUSHARE_TOKEN --disable-push

# 后台运行
nohup python scripts/collection_and_push/csv_pipeline.py --env-file .env \
  --collect-interval 2.0 --push-interval 5.0 \
  > logs/csv_pipeline.log 2>&1 &
```

**Pipeline 参数总览：**

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `--env-file` | 无 | 加载 .env 文件 |
| `--csv-dir` | `data/tushare_csv` | CSV 目录 |
| `--markets` | `a_stock,etf,index,hk` | 市场列表 |
| `--disable-collect` | 关闭 | 禁用采集 |
| `--disable-push` | 关闭 | 禁用推送 |
| `--disable-cleanup` | 关闭 | 禁用清理 |
| `--token` | `$TUSHARE_TOKEN` | TuShare Token |
| `--collect-interval` | `1.5` | 采集间隔（秒） |
| `--push-url` | `$RT_KLINE_CLOUD_PUSH_URL` | 推送 URL |
| `--push-token` | `$RT_KLINE_CLOUD_PUSH_TOKEN` | 推送 Token |
| `--push-interval` | `3.0` | 推送间隔（秒） |
| `--batch-size` | `1000` | 每批条数 |
| `--max-age-days` | `2.0` | CSV 保留天数 |
| `--cleanup-interval` | `3600` | 清理间隔（秒） |
| `--max-restarts` | `10` | 子进程最大重启次数 |

### collect_tushare_to_csv.py（采集脚本）

```bash
# 持续循环采集（追加模式）
python scripts/collection_and_push/collect_tushare_to_csv.py \
  --token $TUSHARE_TOKEN --loop --append --interval 2.0

# 指定市场
python scripts/collection_and_push/collect_tushare_to_csv.py \
  --token $TUSHARE_TOKEN --loop --append --markets a_stock,etf

# 调试模式（忽略交易时段）
python scripts/collection_and_push/collect_tushare_to_csv.py \
  --token $TUSHARE_TOKEN --loop --append --ignore-trading-window
```

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `--token` | `$TUSHARE_TOKEN` | TuShare API Token（**必填**） |
| `--markets` | `a_stock,etf,index,hk` | 采集市场 |
| `--output-dir` | `data/tushare_csv` | CSV 输出目录 |
| `--append` | 关闭 | 追加模式 |
| `--loop` | 关闭 | 持续循环采集 |
| `--interval` | `1.5` | 循环间隔（秒） |
| `--ignore-trading-window` | 关闭 | 忽略交易时段限制 |

### push_csv_to_cloud.py（推送脚本）

```bash
# 持续循环推送
python scripts/collection_and_push/push_csv_to_cloud.py \
  --push-url $RT_KLINE_CLOUD_PUSH_URL \
  --push-token $RT_KLINE_CLOUD_PUSH_TOKEN \
  --loop --interval 5.0

# 指定市场和批量大小
python scripts/collection_and_push/push_csv_to_cloud.py \
  --push-url $RT_KLINE_CLOUD_PUSH_URL \
  --markets a_stock,etf --batch-size 500 --loop
```

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `--push-url` | `$RT_KLINE_CLOUD_PUSH_URL` | 推送 URL（**必填**） |
| `--push-token` | `$RT_KLINE_CLOUD_PUSH_TOKEN` | 鉴权 Token |
| `--csv-dir` | `data/tushare_csv` | CSV 文件目录 |
| `--markets` | `a_stock,etf,index,hk` | 要推送的市场 |
| `--batch-size` | `1000` | 每批推送条数 |
| `--loop` | 关闭 | 持续循环推送 |
| `--interval` | `3.0` | 循环间隔（秒） |
| `--checkpoint-file` | `data/push_checkpoint.json` | 断点记录文件 |
| `--max-retry` | `3` | 单批最大重试次数 |

### cleanup_csv.py（清理脚本）

```bash
# 预览将要删除的文件
python scripts/collection_and_push/cleanup_csv.py --csv-dir data/tushare_csv --dry-run

# 清理 2 天以外的 CSV
python scripts/collection_and_push/cleanup_csv.py --csv-dir data/tushare_csv

# 循环模式
python scripts/collection_and_push/cleanup_csv.py --csv-dir data/tushare_csv --loop --interval 7200
```

---

## 接收端 (Go rt-receiver)

Go 编写的高性能接收服务，替代旧的 Python `receive_push_data.py`。

**相比旧版的改进：**

- ⚡ 内存占用从 ~200MB 降至 ~15MB
- ⚡ 推送处理吞吐量提升 5-10 倍
- ⚡ 内建 WebSocket 实时推送，延迟从 3-6 秒轮询降至 <10ms
- ⚡ 每日 9:00 自动清理前一天的 spool/SQLite 数据
- ⚡ 单二进制部署，无 Python 依赖

### 编译

需要 Go 1.21+ 和 CGO（SQLite 依赖）：

```bash
cd scripts/collection_and_push/go-rt-receiver

# amd64 (默认)
make build

# arm64
make build-arm64
```

编译产物：`scripts/collection_and_push/rt-receiver`

### 启动

```bash
# 通过启动脚本（推荐，自动加载 .env）
bash scripts/collection_and_push/start_receiver.sh

# 直接运行
./scripts/collection_and_push/rt-receiver \
  --host 0.0.0.0 \
  --port 9100 \
  --push-token "$RT_KLINE_CLOUD_PUSH_TOKEN" \
  --data-dir data/received_push \
  --flush-interval 5
```

| 参数 / 环境变量 | 默认值 | 说明 |
|------|--------|------|
| `--host` | `0.0.0.0` | 监听地址 |
| `--port` | `9100` | 监听端口 |
| `--push-token` / `RT_KLINE_CLOUD_PUSH_TOKEN` | 空 | Push 写入 Bearer Token |
| `--policy-token` / `RT_STOCK_POLICY_TOKEN` | 空 | Policy 管理 Bearer Token |
| `--jwt-public-key-path` / `RT_STOCK_JWT_PUBLIC_KEY_PATH` | 空 | JWT RSA 公钥路径 |
| `--data-dir` | `data/received_push` | 数据落地目录 |
| `--flush-interval` | `5` | builder 刷 SQLite 间隔（秒） |

### HTTP API

| 接口 | 方法 | 说明 |
|------|------|------|
| `/health` | GET | 健康检查 |
| `/stats` | GET | 运行状态（spool/SQLite 刷盘、WS 连接数） |
| `/ws` | GET | WebSocket 实时行情推送 |
| `/api/v1/rt-kline/push` | POST | 接收推送数据（与 push_csv_to_cloud.py 对接） |
| `/api/v1/rt-kline/latest` | GET | 查询最新行情快照（`?market=&ts_code=&limit=`） |
| `/api/v1/rt-kline/policies/apply` | POST | 接收订阅 policy 快照 |
| `/api/v1/rt-kline/subscription/sync` | POST | 批量同步用户订阅 symbols |
| `/api/v1/rt-kline/subscription/list` | GET | 查看用户已登记的订阅清单 |
| `/api/v1/rt-kline/subscription/latest` | GET | 返回用户已订阅的最新快照 |

### WebSocket 实时推送

连接地址：`ws://<host>:9100/ws`

```bash
# wscat 命令行
wscat -c ws://your-node:9100/ws

# 带 JWT 鉴权
wscat -c "ws://your-node:9100/ws?token=YOUR_JWT_TOKEN"
```

**Python 客户端示例：**

```python
import asyncio, websockets, json

async def listen():
    async with websockets.connect("ws://your-node:9100/ws") as ws:
        await ws.send(json.dumps({
            "action": "subscribe",
            "symbols": ["00700.HK", "600519.SH"]
        }))
        async for msg in ws:
            data = json.loads(msg)
            if data.get("type") == "tick":
                print(f"{data['ts_code']} {data.get('close')} {data.get('pct_chg')}")

asyncio.run(listen())
```

**浏览器 JS 示例：**

```javascript
const ws = new WebSocket("ws://your-node:9100/ws");
ws.onmessage = (e) => {
  const data = JSON.parse(e.data);
  if (data.type === "tick") {
    console.log(`${data.ts_code} ${data.close} ${data.pct_chg}%`);
  }
};
ws.send(JSON.stringify({ action: "subscribe", symbols: ["00700.HK"] }));
```

**WebSocket 指令：**

| 指令 | 格式 | 说明 |
|------|------|------|
| subscribe | `{"action":"subscribe","symbols":["00700.HK"]}` | 订阅指定 symbol |
| unsubscribe | `{"action":"unsubscribe","symbols":["00700.HK"]}` | 取消订阅 |
| snapshot | `{"action":"snapshot"}` | 获取已订阅 symbol 的最新快照 |
| list | `{"action":"list"}` | 查看当前订阅列表 |

**推送消息格式：**

```json
{
  "type": "tick",
  "timestamp": "2026-03-25T06:30:00.123Z",
  "ts_code": "00700.HK",
  "market": "hk",
  "close": 388.20,
  "open": 385.00,
  "high": 390.00,
  "low": 384.00,
  "vol": 12345678,
  "pct_chg": 1.23,
  "batch_seq": 42
}
```

**鉴权说明：**

- WebSocket 连接时可选传入 JWT Token（`?token=xxx` 或 `Authorization: Bearer xxx`）
- 已认证用户连接后会自动加载服务端已登记的订阅列表
- `subscribe`/`unsubscribe` 变更会自动同步到服务端订阅表（重启不丢失）
- 未认证用户也可连接，订阅仅在本次连接内生效

---

## 推送协议 (RawTickBatchPayload v2)

`push_csv_to_cloud.py` 发送、`rt-receiver` 接收的 HTTP 协议。

### 请求格式

```
POST /api/v1/rt-kline/push
Authorization: Bearer <push_token>
Content-Type: application/json
```

### Payload 字段

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `schema_version` | string | ✅ | 固定 `"v2"` |
| `mode` | string | ✅ | 固定 `"raw_tick_batch"` |
| `batch_seq` | int | ✅ | 批次序列号 |
| `event_time` | string | ✅ | ISO 8601 时间戳 |
| `market` | string | ✅ | `a_stock` / `etf` / `index` / `hk` |
| `source_api` | string | ✅ | 采集来源 API |
| `count` | int | ✅ | items 数组长度 |
| `first_stream_id` | string | ✅ | 首条 stream_id |
| `last_stream_id` | string | ✅ | 末条 stream_id |
| `items` | array | ✅ | Tick 数据数组 |

### items 元素

| 字段 | 类型 | 说明 |
|------|------|------|
| `stream_id` | string | 流内唯一 ID `{毫秒时间戳}-{序号}` |
| `ts_code` | string | 证券代码（如 `000001.SZ`） |
| `version` | string | 数据版本号 |
| `shard_id` | int | 分片 ID = `hash(ts_code) % shards` |
| `tick` | object | 原始行情数据 |

### 请求示例

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
    }
  ]
}
```

### ACK 响应

```json
{
  "status": "ok",
  "code": 0,
  "ack_seq": 1,
  "accepted_count": 2,
  "rejected_count": 0
}
```

| ACK status | 脚本行为 |
|------------|----------|
| `ok` / `success` / `accepted` | 确认成功，推进 checkpoint |
| `retryable` / `throttle` / `busy` / `timeout` | 指数退避重试 |
| 其他 | 停止推送该批次 |

### 市场映射

| 市场 | CSV 文件名前缀 | source_api |
|------|---------------|------------|
| `a_stock` | `a_stock*.csv` | `tushare_rt_k` |
| `etf` | `etf*.csv` | `tushare_rt_etf_k` |
| `index` | `index*.csv` | `tushare_rt_idx_k` |
| `hk` | `hk*.csv` | `tushare_rt_hk_k` |

---

## 部署与运维

### 服务器角色

| 角色 | 说明 | 运行的组件 |
|------|------|-----------|
| **proxy** | 代理节点 | `csv_pipeline.py` (采集) + `push_csv_to_cloud.py` (推送) |
| **receiver** | 订阅节点 | `rt-receiver` (Go 二进制) |

### 部署流程

```bash
# 部署到所有节点
bash scripts/collection_and_push/run.sh deploy

# 仅部署指定节点
bash scripts/collection_and_push/deploy.sh node1 node2
```

### 启动/停止

```bash
# 启动全部
bash scripts/collection_and_push/run.sh start

# 停止全部远程
bash scripts/collection_and_push/stop_all.sh --remote

# 停止指定节点
bash scripts/collection_and_push/stop_all.sh node2 node3

# 检查状态
bash scripts/collection_and_push/run.sh status
```

### 数据落地

- **spool JSONL**：`data/received_push/spool/{market}/{YYYYMMDD}.jsonl`
- **SQLite 快照**：`data/received_push/snapshot/rt_snapshot.db`
- 每日 9:00 自动清理前一天的 spool/SQLite 数据

### 现网快速验证

```bash
# 健康检查
curl -sS http://127.0.0.1:9100/health

# 运行状态
curl -sS http://127.0.0.1:9100/stats

# 完整数据流验证
BASE_URL=http://127.0.0.1:9100 \
PUSH_TOKEN="$RT_KLINE_CLOUD_PUSH_TOKEN" \
bash scripts/collection_and_push/verify_receiver_flow.sh
```

### systemd 配置（生产环境推荐）

```ini
[Unit]
Description=CSV Realtime Pipeline
After=network.target

[Service]
Type=simple
User=deploy
WorkingDirectory=/path/to/stock_datasource
EnvironmentFile=/path/to/stock_datasource/scripts/collection_and_push/.env
ExecStart=/usr/bin/python3 scripts/collection_and_push/csv_pipeline.py \
  --env-file scripts/collection_and_push/.env \
  --collect-interval 2.0 \
  --push-interval 5.0 \
  --cleanup-interval 7200
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

---

## 常见场景速查

| 场景 | 命令 |
|------|------|
| 一键完整部署 | `bash scripts/collection_and_push/run.sh full` |
| 开发调试（忽略交易时段） | `python csv_pipeline.py --env-file .env --ignore-trading-window --disable-push` |
| 只跑采集看数据 | `python collect_tushare_to_csv.py --token $TUSHARE_TOKEN --append --ignore-trading-window` |
| 手动推送一次 | `python push_csv_to_cloud.py --push-url $RT_KLINE_CLOUD_PUSH_URL` |
| 检查哪些 CSV 会被清理 | `python cleanup_csv.py --csv-dir data/tushare_csv --dry-run` |
| 重置断点重新推送 | 删除 `data/push_checkpoint.json` |
| WebSocket 实时订阅 | `wscat -c ws://your-node:9100/ws` |
| 查看所有节点状态 | `bash scripts/collection_and_push/run.sh status` |

---

## 注意事项

1. **2C4G 服务器建议**：`--collect-interval 2.0`、`--push-interval 5.0`，降低 CPU/内存压力
2. **API 限频**：TuShare 默认 50 次/分钟，脚本内置限频器
3. **数据安全**：清理前先用 `--dry-run` 预览
4. **磁盘空间**：追加模式下 CSV 持续增长，建议 `--max-age-days 2`
5. **断点续传**：推送脚本使用 `push_checkpoint.json` 记录进度，重启自动续传
6. **崩溃恢复**：Pipeline 控制脚本自动重启子进程（5 分钟内最多 10 次）
7. **Go 编译**：需要 CGO（SQLite 依赖），确保 `gcc` 已安装
8. **servers.conf**：包含敏感信息，已在 `.gitignore` 中忽略
