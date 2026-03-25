# API 参考文档

## 目录
1. [WebSocket 消息格式](#websocket-消息格式)
2. [数据字段说明](#数据字段说明)
3. [客户端连接示例](#客户端连接示例)
4. [动态订阅管理](#动态订阅管理)
5. [排错指南](#排错指南)

---

## WebSocket 消息格式

### welcome（连接时）

```json
{
    "type": "welcome",
    "message": "实时行情 WebSocket 已连接",
    "server_symbols": ["00700.HK", "09988.HK"],
    "poll_interval": 3.0,
    "instructions": {}
}
```

### snapshot（初始快照 / 请求快照）

```json
{
    "type": "snapshot",
    "count": 4,
    "data": [
        {"ts_code": "00700.HK", "name": "腾讯控股", "close": 450.0}
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

---

## 数据字段说明

| 字段 | 类型 | 说明 |
|------|------|------|
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

---

## 客户端连接示例

### Python

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

### wscat 命令行

```bash
# 安装: npm install -g wscat
wscat -c ws://localhost:8765
```

### 浏览器 JavaScript

```javascript
const ws = new WebSocket("ws://localhost:8765");
ws.onmessage = (e) => {
    const data = JSON.parse(e.data);
    if (data.type === "tick") {
        console.log(`${data.name}: ${data.close} 元  ${data.pct_chg}%`);
    }
};
```

---

## 动态订阅管理

连接后发送 JSON 指令管理订阅：

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

---

## 排错指南

| 问题 | 解决方案 |
|------|---------|
| Connection refused (HTTP) | 确认 `STOCK_RT_NODE_URL` 正确，检查防火墙 |
| Connection refused (WebSocket) | 确认服务端 `subscribe_client.py` 已启动 |
| No data / tick not updating | 确认当前是交易时间（A股 9:30-15:00，港股 9:30-16:00） |
| Symbol not found | 使用完整代码格式：`600519.SH`（上交所）、`000001.SZ`（深交所）、`00700.HK`（港股） |
| 安装 websockets | `pip install websockets` |
