---
name: stock-rt-subscribe
description: Subscribe to real-time stock market data via WebSocket long connection from receiver nodes (A-shares, HK stocks, ETFs). Use this skill when the user wants to monitor live stock prices, set up real-time alerts, or stream minute-level K-line data. The skill provides a WebSocket server that connects to receiver nodes and pushes real-time price updates to all connected clients.
---

# 实时股票数据订阅（WebSocket）

通过 **WebSocket 长连接** 实时接收 A 股、港股、ETF 行情数据，每 3~5 秒更新一次。

## 架构

```
Receiver Node (HTTP API) → scripts/subscribe_client.py → ws://localhost:8765 → 客户端
```

## 环境准备

```bash
pip install requests websockets
export STOCK_RT_NODE_URL="http://your-node:9100"
export STOCK_RT_TOKEN="your-token"   # 可选，有鉴权时设置
```

## 快速开始

### 一次性查询（验证连通性）

```bash
python3 scripts/subscribe_client.py --symbols 00700.HK 600519.SH --once
```

### 启动 WebSocket 推送服务

```bash
# 基础订阅
python3 scripts/subscribe_client.py --symbols 00700.HK 09988.HK 600519.SH

# 指定节点和端口
python3 scripts/subscribe_client.py --node-url http://your-node:9100 --ws-port 8765 --symbols 00700.HK

# 涨跌幅告警（±2% 触发）
python3 scripts/subscribe_client.py --symbols 00700.HK --alert-pct 2.0

# 输出到文件
python3 scripts/subscribe_client.py --symbols 00700.HK --output ticks.jsonl
```

### 编程方式启动

```python
from scripts.subscribe_client import StockWSServer

server = StockWSServer(
    node_url="http://your-node:9100",
    symbols=["00700.HK", "09988.HK"],
    poll_interval=3.0,
)
server.add_callback(lambda sym, tick: print(f"{tick.name}: {tick.close}"))
server.run(port=8765)
```

### AI Agent 集成

```python
from scripts.ai_agent_integration import StockDataAgent

agent = StockDataAgent()
agent.install()  # 检查依赖、验证节点连通性

# 完整工作流（订阅 + 告警监控 60 秒）
import asyncio
asyncio.run(agent.complete_workflow(['00700.HK', '600519.SH'], duration=60))
```

## 告警策略

告警规则配置见 [references/strategy_config.json](references/strategy_config.json)，内置策略：
- `limit_up_down`：涨停/跌停监控
- `big_move`：大幅波动（≥ ±5%）
- `vol_spike`：成交量异动（≥ 近5日均量3倍）
- `price_breakout`：价格突破近20日高点

## 参考文档

- **[references/api.md](references/api.md)**：WebSocket 消息格式、数据字段说明、客户端连接示例（Python/JS/wscat）、动态订阅管理指令、排错指南
- **[references/strategy_config.json](references/strategy_config.json)**：告警策略完整配置
