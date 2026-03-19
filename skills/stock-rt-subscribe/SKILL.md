---
name: stock-rt-subscribe
description: Subscribe to real-time stock market data via WebSocket long connection from receiver nodes (A-shares, HK stocks, ETFs). Use this skill when the user wants to monitor live stock prices, set up real-time alerts, or stream minute-level K-line data. The skill provides a WebSocket server that connects to receiver nodes and pushes real-time price updates to all connected clients.
---

# Real-time Stock Data Subscription (WebSocket)

通过 **WebSocket 长连接** 实时接收 A 股、港股、ETF 的行情数据，数据每 3~5 秒更新一次。

## 架构

```
  Receiver Node (HTTP API)         subscribe_client.py             用户
  ┌─────────────────────┐     ┌──────────────────────────┐     ┌────────────────┐
  │ /api/v1/rt-kline/   │────▶│  后台轮询 HTTP → 解析    │────▶│ WebSocket 客户端│
  │  latest?ts_code=... │     │  WebSocket 推送给所有连接 │     │ (浏览器/Python/ │
  └─────────────────────┘     └──────────────────────────┘     │  wscat/任意语言)│
                                ws://localhost:8765             └────────────────┘
```

## Prerequisites

1. **Python 3.8+** with `requests` and `websockets` installed
2. **STOCK_RT_NODE_URL** environment variable — Receiver 节点 HTTP 地址

```bash
# 安装依赖
pip install requests websockets

# 设置节点地址
export STOCK_RT_NODE_URL="http://your-node:9100"
export STOCK_RT_TOKEN="your-token-here"   # 如果需要鉴权
```

## Quick Start

### 1. 启动 WebSocket 推送服务

```bash
cd skills/stock-rt-subscribe

# 订阅腾讯、阿里、百度、京东港股
python3 subscribe_client.py --symbols 00700.HK 09988.HK 09888.HK 09618.HK

# 指定节点和端口
python3 subscribe_client.py --node-url http://your-node:9100 --ws-port 8765 --symbols 00700.HK

# 自定义轮询间隔
python3 subscribe_client.py --symbols 00700.HK --interval 5

# 安静模式（不显示终端面板，WebSocket 正常推送）
python3 subscribe_client.py --symbols 00700.HK --quiet

# 同时输出到文件
python3 subscribe_client.py --symbols 00700.HK --output ticks.jsonl

# 涨跌幅告警
python3 subscribe_client.py --symbols 00700.HK --alert-pct 2.0
```

### 2. 连接 WebSocket 接收数据

服务启动后，用户通过任意 WebSocket 客户端连接即可接收实时推送：

#### Python 客户端

```python
import asyncio, websockets, json

async def listen():
    async with websockets.connect("ws://localhost:8765") as ws:
        async for msg in ws:
            data = json.loads(msg)
            if data["type"] == "tick":
                print(f"{data['name']} 现价: {data['close']}  涨跌幅: {data['pct_chg']}%")

asyncio.run(listen())
```

#### wscat 命令行

```bash
# 安装: npm install -g wscat
wscat -c ws://localhost:8765
```

#### 浏览器 JavaScript

```javascript
const ws = new WebSocket("ws://localhost:8765");
ws.onmessage = (e) => {
    const data = JSON.parse(e.data);
    if (data.type === "tick") {
        console.log(`${data.name}: ${data.close} 元  ${data.pct_chg}%`);
    }
};
```

### 3. 动态订阅管理

连接后可以发送 JSON 指令动态管理订阅：

```json
// 添加订阅
{"action": "subscribe", "symbols": ["00700.HK", "09988.HK"]}

// 取消订阅
{"action": "unsubscribe", "symbols": ["09988.HK"]}

// 获取当前所有最新行情快照
{"action": "snapshot"}

// 查看当前订阅列表
{"action": "list"}
```

### 4. 编程使用（启动服务）

```python
from subscribe_client import StockWSServer

# 创建 WebSocket 推送服务
server = StockWSServer(
    node_url="http://your-node:9100",
    symbols=["00700.HK", "09988.HK", "09888.HK"],
    poll_interval=3.0,
)

# 添加本地回调（可选，用于本地处理）
server.add_callback(lambda sym, tick: print(f"{tick.name}: {tick.close}"))

# 阻塞运行（启动 WebSocket 在 8765 端口）
server.run(port=8765)
```

### 5. 一次性查询

```bash
# 不启动 WebSocket，只查一次
python3 subscribe_client.py --symbols 00700.HK 09988.HK --once
```

## WebSocket 推送消息格式

### welcome（连接时）

```json
{
    "type": "welcome",
    "message": "实时行情 WebSocket 已连接",
    "server_symbols": ["00700.HK", "09988.HK"],
    "poll_interval": 3.0,
    "instructions": { ... }
}
```

### snapshot（初始快照 / 请求快照）

```json
{
    "type": "snapshot",
    "count": 4,
    "data": [
        {"ts_code": "00700.HK", "name": "腾讯控股", "close": 450.0, ...},
        ...
    ]
}
```

### tick（实时推送）

```json
{
    "type": "tick",
    "timestamp": "2026-03-18T15:30:00.123456",
    "ts_code": "00700.HK",
    "name": "腾讯控股",
    "market": "hk",
    "open": 445.0,
    "high": 452.0,
    "low": 443.0,
    "close": 450.0,
    "vol": 12345678,
    "amount": 5678901234.0,
    "pre_close": 448.0,
    "pct_chg": 0.45,
    "trade_date": 20260318,
    "collected_at": "2026-03-18T15:30:00",
    "version": 42
}
```

## Data Fields

| Field | Type | Description |
|-------|------|-------------|
| `ts_code` | string | 股票代码（如 `00700.HK`） |
| `name` | string | 股票名称 |
| `market` | string | 市场（`a_stock` / `hk` / `etf` / `index`） |
| `open` | float | 开盘价 |
| `high` | float | 最高价 |
| `low` | float | 最低价 |
| `close` | float | 最新价 |
| `vol` | int | 成交量 |
| `amount` | float | 成交额 |
| `pre_close` | float | 昨收价 |
| `pct_chg` | float | 涨跌幅（%） |
| `trade_date` | int | 交易日期（如 `20260318`） |
| `collected_at` | string | 数据采集时间 |
| `version` | int | 数据版本号（用于去重） |

## Subscription Plans

| Plan | Max Symbols | Markets | Price |
|------|-------------|---------|-------|
| Pack 5 (Entry) | 5 | A-shares + HK | 10 CNY/month |
| Pack 15 (Standard) | 15 | A-shares + HK | 20 CNY/month |
| Pack 50 (Pro) | 50 | A-shares + HK | 50 CNY/month |

All plans include ETF and index data. Data refreshes every 3-5 seconds during market hours.

## Troubleshooting

- **Connection refused (HTTP)**: 确认 `STOCK_RT_NODE_URL` 正确，检查防火墙
- **Connection refused (WebSocket)**: 确认服务端 `subscribe_client.py` 已启动
- **No data / tick not updating**: 确认当前是交易时间（A股 9:30-15:00，港股 9:30-16:00）
- **Symbol not found**: 使用完整代码格式如 `600519.SH`（上交所）、`000001.SZ`（深交所）、`00700.HK`（港股）
- **安装 websockets**: `pip install websockets`
